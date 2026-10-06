"""The model client against a fake server (A §6, A §4.1).

Every test here runs a `http.server` in a thread on a loopback port it was given
by the OS, records what arrived and answers from a script of canned replies. No
real model server is contacted, and no test needs one: what is under test is the
body the client sends, the one retry, the grammar probe, and the shape of the
`calls.jsonl` row.
"""

import http.server
import json
import socket
import threading
import time

import pytest

from p3focus import client, constants, grammars


# --- the fake server ----------------------------------------------------

def _completion(text, usage=None, timings=None):
    """A llama.cpp `/v1/chat/completions` body, as the server sends it."""
    body = {"choices": [{"message": {"role": "assistant", "content": text}}]}
    if usage is not None:
        body["usage"] = usage
    if timings is not None:
        body["timings"] = timings
    return body


class _Handler(http.server.BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def do_POST(self):
        length = int(self.headers.get("Content-Length") or 0)
        raw = self.rfile.read(length)
        self.server.requests.append({
            "path": self.path,
            "content_type": self.headers.get("Content-Type"),
            "body": json.loads(raw.decode()),
        })
        self._answer()

    def do_GET(self):
        self.server.requests.append({"path": self.path, "content_type": None, "body": None})
        self._answer()

    def _answer(self):
        canned = (self.server.script.pop(0) if self.server.script
                  else {"status": 200, "json": _completion("(unscripted)")})
        if canned.get("delay"):
            time.sleep(canned["delay"])
        payload = canned.get("raw")
        if payload is None:
            payload = json.dumps(canned.get("json", {})).encode()
        self.send_response(canned.get("status", 200))
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(payload)))
        self.end_headers()
        self.wfile.write(payload)

    def log_message(self, *args):
        pass                       # a test run is not a web server's log


class _Server(http.server.ThreadingHTTPServer):
    daemon_threads = True
    allow_reuse_address = True

    def handle_error(self, request, client_address):
        pass       # a test that times out on purpose leaves a half-written reply


@pytest.fixture
def server():
    """A fake model server. `server.script` is the queue of canned replies,
    `server.requests` what arrived, `server.url` where to point a client."""
    httpd = _Server(("127.0.0.1", 0), _Handler)
    httpd.script = []
    httpd.requests = []
    httpd.url = "http://127.0.0.1:%d" % httpd.server_address[1]
    # a short poll interval: shutdown() waits for one, and the suite pays it once a test
    thread = threading.Thread(target=httpd.serve_forever, kwargs={"poll_interval": 0.01},
                              daemon=True)
    thread.start()
    try:
        yield httpd
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=5)


def _dead_url():
    """A loopback address with nothing listening: a connection error on demand."""
    sock = socket.socket()
    sock.bind(("127.0.0.1", 0))
    port = sock.getsockname()[1]
    sock.close()
    return "http://127.0.0.1:%d" % port


# --- the body the client sends (A §6) -----------------------------------

def test_the_post_body_is_As_keys_with_the_constants_values(server):
    server.script = [{"status": 200, "json": _completion('{"delete": true}')}]
    reply = client.Client(server.url).complete(
        [{"role": "user", "content": "the page"}], grammar='root ::= "x"')

    assert reply.text == '{"delete": true}'
    assert len(server.requests) == 1
    request = server.requests[0]
    assert request["path"] == "/v1/chat/completions"
    assert request["content_type"] == "application/json"
    assert set(request["body"]) == {"model", "messages", "temperature", "seed",
                                    "max_tokens", "stream", "grammar"}
    assert request["body"]["model"] == "local"
    assert request["body"]["messages"] == [{"role": "user", "content": "the page"}]
    assert request["body"]["temperature"] == constants.TEMPERATURE
    assert request["body"]["seed"] == constants.SAMPLING_SEED
    assert request["body"]["max_tokens"] == constants.MAX_TOKENS
    assert request["body"]["stream"] is False
    assert request["body"]["grammar"] == 'root ::= "x"'


def test_the_grammar_field_is_sent_only_when_a_grammar_is_given(server):
    server.script = [{"status": 200, "json": _completion("a")},
                     {"status": 200, "json": _completion("b")}]
    caller = client.Client(server.url, model="qwen")
    caller.complete([{"role": "user", "content": "p"}])
    caller.complete([{"role": "user", "content": "p"}], grammar=grammars.grammar("R2"))

    assert "grammar" not in server.requests[0]["body"]
    assert server.requests[1]["body"]["grammar"] == grammars.grammar("R2")
    assert server.requests[0]["body"]["model"] == "qwen"


def test_max_tokens_is_the_constant_unless_the_caller_says_otherwise(server):
    server.script = [{"status": 200, "json": _completion("a")},
                     {"status": 200, "json": _completion("b")}]
    caller = client.Client(server.url)
    caller.complete([{"role": "user", "content": "p"}])
    caller.complete([{"role": "user", "content": "p"}], max_tokens=12)

    assert server.requests[0]["body"]["max_tokens"] == 600
    assert server.requests[1]["body"]["max_tokens"] == 12


# --- what comes back ----------------------------------------------------

def test_tokens_come_from_usage_then_from_timings_and_are_none_when_absent(server):
    server.script = [
        {"status": 200, "json": _completion("a", usage={"prompt_tokens": 11,
                                                        "completion_tokens": 2})},
        {"status": 200, "json": _completion("b", timings={"prompt_n": 7, "predicted_n": 3})},
        {"status": 200, "json": _completion("c")},
    ]
    caller = client.Client(server.url)
    assert caller.complete([{"role": "user", "content": "p"}]).tokens == {"prompt": 11,
                                                                          "eval": 2}
    assert caller.complete([{"role": "user", "content": "p"}]).tokens == {"prompt": 7, "eval": 3}
    assert caller.complete([{"role": "user", "content": "p"}]).tokens is None


def test_elapsed_is_the_wall_clock_of_the_call(server):
    server.script = [{"status": 200, "json": _completion("a"), "delay": 0.05}]
    reply = client.Client(server.url).complete([{"role": "user", "content": "p"}])
    assert reply.elapsed_s >= 0.05
    assert reply.attempt == 1


def test_a_200_with_no_content_is_a_client_error_and_is_not_retried(server):
    server.script = [{"status": 200, "json": {"choices": []}},
                     {"status": 200, "json": _completion("never reached")}]
    with pytest.raises(client.ClientError) as caught:
        client.Client(server.url).complete([{"role": "user", "content": "p"}])
    assert caught.value.status == 200
    assert len(server.requests) == 1


def test_a_body_that_is_not_json_is_a_client_error(server):
    server.script = [{"status": 200, "raw": b"<html>gateway</html>"}]
    with pytest.raises(client.ClientError) as caught:
        client.Client(server.url).complete([{"role": "user", "content": "p"}])
    assert "not JSON" in str(caught.value)


# --- the one retry (A §6) -----------------------------------------------

def test_a_timeout_then_success_is_one_retry_and_the_reply_says_attempt_two(server):
    server.script = [{"status": 200, "json": _completion("late"), "delay": 1.0},
                     {"status": 200, "json": _completion("on time")}]
    reply = client.Client(server.url, timeout_s=0.2).complete(
        [{"role": "user", "content": "p"}])

    assert reply.text == "on time"
    assert reply.attempt == 2
    assert len(server.requests) == 2


def test_a_5xx_then_success_is_one_retry(server):
    server.script = [{"status": 503, "raw": b"busy"},
                     {"status": 200, "json": _completion("second")}]
    reply = client.Client(server.url).complete([{"role": "user", "content": "p"}])
    assert (reply.text, reply.attempt) == ("second", 2)


def test_two_transport_failures_raise_client_error_with_status_and_body(server):
    server.script = [{"status": 500, "raw": b"first down"},
                     {"status": 500, "raw": b"second down"}]
    with pytest.raises(client.ClientError) as caught:
        client.Client(server.url).complete([{"role": "user", "content": "p"}])

    assert caught.value.status == 500
    assert caught.value.body == "second down"
    assert len(server.requests) == 2


def test_a_connection_that_never_opens_is_retried_once_and_then_raises():
    with pytest.raises(client.ClientError) as caught:
        client.Client(_dead_url(), timeout_s=2).complete([{"role": "user", "content": "p"}])
    assert caught.value.status is None
    assert caught.value.transport is True


def test_a_4xx_is_final_at_once_and_is_not_retried(server):
    server.script = [{"status": 400, "raw": b"bad grammar"},
                     {"status": 200, "json": _completion("never reached")}]
    with pytest.raises(client.ClientError) as caught:
        client.Client(server.url).complete([{"role": "user", "content": "p"}])

    assert caught.value.status == 400
    assert caught.value.transport is False
    assert len(server.requests) == 1


# --- the grammar probe (A §6, A §7 D1) ----------------------------------

def test_the_probe_sends_the_one_token_grammar_and_passes_on_the_marker(server):
    marker = constants.GRAMMAR_PROBE_MARKER
    server.script = [{"status": 200, "json": _completion(marker + "\n")}]
    reply = client.Client(server.url).probe()

    assert reply.text.strip() == marker
    assert server.requests[0]["body"]["grammar"] == 'root ::= "%s"' % marker
    assert server.requests[0]["body"]["max_tokens"] == len(marker) + 8


def test_the_probe_fails_when_the_server_ignores_the_grammar_field(server):
    """A §6: a server that does not know llama.cpp's `grammar` answers 200 with
    prose, which is the failure the probe exists to catch."""
    server.script = [{"status": 200, "json": _completion("Sure! What would you like?")}]
    with pytest.raises(client.ClientError) as caught:
        client.Client(server.url).probe()
    assert "does not enforce" in str(caught.value)


def test_the_probe_names_reasoning_tokens_as_themselves(server):
    """A §7 D1: the live server serves with reasoning off, and with it on the measured
    reply was 600 tokens of thinking and empty content. Both shapes of that
    failure are named as themselves, not as a missing grammar."""
    server.script = [{"status": 200, "json": _completion("<think>the user wants…")},
                     {"status": 200, "json": _completion("")}]
    caller = client.Client(server.url)
    with pytest.raises(client.ClientError) as caught:
        caller.probe()
    assert "--reasoning off" in str(caught.value)

    with pytest.raises(client.ClientError) as caught:
        caller.probe()
    assert "empty content" in str(caught.value) and "reasoning on" in str(caught.value)


def test_the_probe_retries_a_transport_failure_like_any_other_call(server):
    marker = constants.GRAMMAR_PROBE_MARKER
    server.script = [{"status": 502, "raw": b"down"}, {"status": 200, "json": _completion(marker)}]
    assert client.Client(server.url).probe().attempt == 2


def test_props_answers_or_returns_none_and_never_raises(server):
    server.script = [{"status": 200, "json": {"model_path": "/models/qwen.gguf"}}]
    assert client.Client(server.url).props() == {"model_path": "/models/qwen.gguf"}
    assert server.requests[0]["path"] == "/props"
    assert client.Client(_dead_url(), timeout_s=2).props() is None


# --- the calls.jsonl row (A §4.1) ---------------------------------------

def _row(**over):
    row = {
        "call_no": 1, "step": 11, "round": "R1", "attempt": 1, "transport_tries": 1,
        "prompt": "the page", "page_sha256": "0" * 64, "prefix_sha256": None,
        "grammar_id": "R1", "reply_text": '{"maintain": "no"}',
        "parsed": {"maintain": "no"}, "valid": True, "reason": None,
        "elapsed_s": 0.5, "tokens": {"prompt": 10, "eval": 4},
    }
    row.update(over)
    return row


def test_a_call_row_is_one_sorted_json_object_a_line(tmp_path):
    log = client.CallLog(tmp_path / "runs" / "cell" / "calls.jsonl")
    log.append(_row())
    log.append(_row(call_no=2, round="R1.5", attempt=2, parsed=None, valid=False,
                    reason="no entry e9", tokens=None))

    lines = log.path.read_text().splitlines()
    assert len(lines) == 2 and log.n_rows == 2
    first = json.loads(lines[0])
    assert list(first) == sorted(client.CALL_ROW_KEYS)      # sort_keys=True, as A says
    assert set(first) == set(client.CALL_ROW_KEYS)
    assert lines[0] == json.dumps(_row(), sort_keys=True)
    assert json.loads(lines[1])["reason"] == "no entry e9"
    # elapsed_s is the only clock in the row (A §4.1)
    assert not [key for key in first if "time" in key or key.endswith("_at")]


def test_a_row_missing_a_key_or_carrying_a_spare_one_is_refused(tmp_path):
    log = client.CallLog(tmp_path / "calls.jsonl")
    short = _row()
    short.pop("tokens")
    with pytest.raises(ValueError) as caught:
        log.append(short)
    assert "tokens" in str(caught.value)

    with pytest.raises(ValueError) as caught:
        log.append(_row(timestamp="2026-09-24T00:00:00Z"))
    assert "timestamp" in str(caught.value)
    assert not log.path.exists() and log.n_rows == 0


def test_a_reply_fills_the_three_row_fields_that_are_the_clients(server, tmp_path):
    """A §4.1: `reply_text`, `elapsed_s` and `tokens` come off the `Reply`; the
    rest is the controller's context. This is the whole path — a page in, a
    reply out of the socket, a row on disk."""
    server.script = [{"status": 200, "json": _completion(
        '{"focus": "e1"}', usage={"prompt_tokens": 900, "completion_tokens": 8})}]
    reply = client.Client(server.url).complete(
        [{"role": "user", "content": "page"}], grammar=grammars.grammar("R2"))

    log = client.CallLog(tmp_path / "calls.jsonl")
    row = log.append(_row(round="R2", grammar_id="R2", reply_text=reply.text,
                          parsed=json.loads(reply.text), elapsed_s=reply.elapsed_s,
                          tokens=reply.tokens))
    assert row["tokens"] == {"prompt": 900, "eval": 8}
    written = json.loads(log.path.read_text())
    assert written["reply_text"] == '{"focus": "e1"}'
    assert written["elapsed_s"] == reply.elapsed_s


# --- the sha helpers (A §4.1) -------------------------------------------

def test_prefix_sha_hashes_everything_before_the_newest_turn():
    """A §4.1, chat: the prefix is the cache-hit check, so the newest user turn
    is the one message it does not cover."""
    turns = [{"role": "system", "content": "s"}, {"role": "user", "content": "one"},
             {"role": "assistant", "content": "a"}, {"role": "user", "content": "two"}]
    assert client.prefix_sha256(turns) == client.messages_sha256(turns[:-1])
    assert client.prefix_sha256(turns) != client.messages_sha256(turns)
    # the same prefix under a different newest turn is the same hash
    other = turns[:-1] + [{"role": "user", "content": "three"}]
    assert client.prefix_sha256(other) == client.prefix_sha256(turns)


def test_the_page_sha_is_stable_and_ignores_key_order():
    """A §4.1, trace: the row hashes the page itself. Sorted JSON, so a message
    dict written in another key order hashes the same."""
    page = [{"role": "user", "content": "the page"}]
    assert client.messages_sha256(page) == client.messages_sha256(
        [{"content": "the page", "role": "user"}])
    assert client.messages_sha256(page) != client.messages_sha256(
        [{"role": "user", "content": "another page"}])
    assert len(client.messages_sha256(page)) == 64


# --- the scripted client (A §5) -----------------------------------------

def test_the_scripted_client_answers_from_its_policy_and_contacts_nothing():
    seen = []

    def policy(messages):
        seen.append(messages)
        return '{"action": "move_up", "intent": "scripted"}'

    scripted = client.ScriptedClient(policy)
    reply = scripted.complete([{"role": "user", "content": "page"}],
                              grammar=grammars.grammar("R4"))

    assert reply.text == '{"action": "move_up", "intent": "scripted"}'
    assert (reply.tokens, reply.attempt) == (None, 1)
    assert seen == [[{"role": "user", "content": "page"}]]
    assert scripted.probe() is None


def test_the_scripted_client_refuses_a_policy_that_does_not_return_text():
    with pytest.raises(TypeError):
        client.ScriptedClient("not callable")
    with pytest.raises(TypeError):
        client.ScriptedClient(lambda messages: {"action": "move_up"}).complete([])
