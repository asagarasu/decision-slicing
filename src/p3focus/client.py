"""The model client (A §6, the client row; A §4.1; the transport half of A §3.4).

One call: messages + a grammar in, reply text out, with the wall clock and the
token counts the server reported. One retry on a **transport** failure — a
timeout, a connection that failed, a 5xx — and then `ClientError`. Semantic
validation of a reply (ids that exist, coordinates on the map) is A §3.4's and
belongs to the controllers; this module never reads a reply's content except in
`probe`, where the content is the whole point.

Nothing here has a coordinate in it: the axes (world +y down, shown +y up,
A §1.1) are the pages' and the controllers'. The client carries text.

No API keys, no headers but `Content-Type`; `urllib` only, as the old line had it
(`p3_crafter_body_errands_94/src/loop.py` ~368-427).
"""

import hashlib
import http.client
import json
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from p3focus import constants

COMPLETIONS_PATH = "/v1/chat/completions"

# the first try and the one retry (A §6, "one retry on a transport failure")
TRANSPORT_ATTEMPTS = 2

# the keys of one `calls.jsonl` row, exactly as A §4.1 lists them
CALL_ROW_KEYS = (
    "call_no", "step", "round", "attempt", "transport_tries", "prompt", "page_sha256",
    "prefix_sha256", "grammar_id", "reply_text", "parsed", "valid", "reason", "elapsed_s",
    "tokens",
)


class ClientError(RuntimeError):
    """The model server did not return a completion this run can use. Carries
    the HTTP status (None when the connection itself failed) and the body. A §5:
    a server failure that survives the retry is the run command's exit 2.

    `transport` says whether the failure is one the retry is for (a timeout, a
    connection error, a 5xx). A 4xx, a body that is not JSON, and a probe the
    server failed are all final at once."""

    def __init__(self, status, body, transport=False):
        self.status = status
        self.body = body
        self.transport = bool(transport)
        super().__init__(f"HTTP {status}: {body[:500] if isinstance(body, str) else body!r}")


@dataclass(frozen=True)
class Reply:
    """One completion (A §6). `tokens` is `{prompt, eval}` as the server
    reports them, or None when it reports neither. `attempt` is the transport
    try this reply came back on, 1 or 2 (the row's `transport_tries`)."""

    text: str
    elapsed_s: float
    tokens: dict | None
    # A §4.1 (settled 09-24 on this module's A-question): the row carries both
    # numbers. `attempt` is §3.4's semantic try, the controller's to fill;
    # `transport_tries` is this field, the tries the client needed.
    attempt: int


class Client:
    """llama.cpp's OpenAI-shaped `/v1/chat/completions` (A §6). Greedy
    (`temperature` 0) with a fixed sampling `seed`, both constants: reproducible
    at the root. Records nothing itself — `CallLog` below writes the row."""

    def __init__(self, server=constants.SERVER_DEFAULT, model="local",
                 timeout_s=constants.TIMEOUT_S):
        self.server = server.rstrip("/")
        self.model = model
        self.timeout_s = timeout_s

    def request_body(self, messages, grammar=None, max_tokens=constants.MAX_TOKENS):
        """The POST body of one call (A §6): `model`, `messages`, `temperature`,
        `seed`, `max_tokens`, `stream`, and `grammar` only when one is given."""
        body = {
            "model": self.model,
            "messages": [dict(m) for m in messages],
            "temperature": constants.TEMPERATURE,
            "seed": constants.SAMPLING_SEED,
            "max_tokens": int(max_tokens),
            "stream": False,
        }
        if grammar is not None:
            # llama.cpp's own field, not OpenAI's: a server that does not know it
            # ignores it and answers 200, which is what `probe` is for.
            body["grammar"] = str(grammar)
        return body

    def complete(self, messages, grammar=None, max_tokens=constants.MAX_TOKENS):
        """One call to the server; returns a `Reply` (A §6). Retries once on a
        transport failure and then raises `ClientError`. Whether the reply means
        anything is A §3.4's question, asked by the controller, not here."""
        body = self.request_body(messages, grammar=grammar, max_tokens=max_tokens)
        for attempt in range(1, TRANSPORT_ATTEMPTS + 1):
            try:
                return self._post(body, attempt)
            except ClientError as err:
                if attempt == TRANSPORT_ATTEMPTS or not err.transport:
                    raise
        raise AssertionError("unreachable: the loop returns or raises")

    def probe(self):
        """Prove the live server enforces `grammar`, before a cell's first real
        call (A §6; old `probe_grammar`, loop.py ~3457-3469). One request whose
        grammar admits only the marker: a server that enforces returns exactly
        it, one that ignores the field returns prose with the same HTTP 200.
        Returns the `Reply`; raises `ClientError` when the server fails it.

        The same reply also carries A §7 D1's assertion: a server serving with
        reasoning on answers with `<think>` and empty content, so a reply that
        opens with `<think>` is named as that and not as a missing grammar."""
        marker = constants.GRAMMAR_PROBE_MARKER
        reply = self.complete(
            [{"role": "user", "content": "reply with anything."}],
            grammar=f'root ::= "{marker}"', max_tokens=len(marker) + 8)
        text = reply.text.strip()
        if not text:
            raise ClientError(200, "the server answered the grammar probe with empty content, "
                                   "which is what serving with reasoning on looks like: 600 "
                                   "tokens of thinking and nothing in `content` (A §7 D1)")
        if text.startswith("<think>"):
            raise ClientError(200, "the server answered the grammar probe with reasoning "
                                   f"tokens ({text[:120]!r}); serve with --reasoning off (A §7 D1)")
        if text != marker:
            raise ClientError(200, "the server does not enforce the `grammar` field: the probe "
                                   f"asked for {marker!r} and got {text[:200]!r}")
        return reply

    def props(self):
        """llama.cpp's `/props`, or None if it will not answer. Never raises: a
        cell must not die because a fingerprint could not be taken. The drivers
        read the model name for the manifest from here (A §4.4)."""
        try:
            req = urllib.request.Request(self.server + "/props", method="GET")
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                return json.loads(resp.read().decode())
        except Exception:
            return None

    def _post(self, body, attempt):
        """One POST. Raises `ClientError`, with `transport` set on the failures
        the retry is for."""
        data = json.dumps(body).encode()
        req = urllib.request.Request(
            self.server + COMPLETIONS_PATH, data=data, method="POST",
            headers={"Content-Type": "application/json"})
        t0 = time.perf_counter()
        try:
            with urllib.request.urlopen(req, timeout=self.timeout_s) as resp:
                raw = json.loads(resp.read().decode())
        except urllib.error.HTTPError as err:          # a status came back
            raise ClientError(err.code, err.read().decode(errors="replace"),
                              transport=err.code >= 500) from None
        except urllib.error.URLError as err:           # the connection failed
            raise ClientError(None, str(err.reason), transport=True) from None
        except OSError as err:                         # timed out, reset
            raise ClientError(None, str(err), transport=True) from None
        except http.client.HTTPException as err:       # a reply that stopped halfway
            raise ClientError(None, f"{type(err).__name__}: {err}", transport=True) from None
        except ValueError as err:                      # 200, and not JSON
            raise ClientError(200, f"reply body is not JSON: {err}") from None
        elapsed = time.perf_counter() - t0
        try:
            text = raw["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError):
            raise ClientError(
                200, f"no choices[0].message.content in {json.dumps(raw)[:500]}") from None
        return Reply(text="" if text is None else str(text), elapsed_s=round(elapsed, 4),
                     tokens=_tokens(raw), attempt=attempt)


class ScriptedClient:
    """`policy(messages) -> reply text`, with `Client`'s shape and no server —
    what A §5's `--policy scripted:` runs on. The grammar is accepted and
    ignored: a scripted reply is authored, not decoded. Timing is real, token
    counts are None. Reading a fixture file into a policy belongs to whoever
    owns the run command; this is only the client half."""

    def __init__(self, policy):
        if not callable(policy):
            raise TypeError("ScriptedClient takes a callable policy(messages) -> str")
        self.policy = policy
        self.model = "scripted"

    def complete(self, messages, grammar=None, max_tokens=constants.MAX_TOKENS):
        """One scripted reply, in a `Reply` (A §5)."""
        t0 = time.perf_counter()
        text = self.policy([dict(m) for m in messages])
        if not isinstance(text, str):
            raise TypeError(f"policy must return the reply text, got {type(text).__name__}")
        return Reply(text=text, elapsed_s=round(time.perf_counter() - t0, 4),
                     tokens=None, attempt=1)

    def probe(self):
        """No server, nothing to prove (A §6: the probe is about a live server)."""
        return None


class CallLog:
    """`calls.jsonl` (A §4.1): one JSON object per line, one line per model
    call, retries included. Keys are exactly A §4.1's — a row that is missing
    one or carries a spare is refused, because a reader that has to guess which
    of two spellings a run used is a reader that reads two experiments.

    `Reply` fills `reply_text`, `elapsed_s` and `tokens`; everything else is the
    controller's context. Nothing here has a timestamp: `elapsed_s` is the only
    clock in the row."""

    def __init__(self, path):
        self.path = Path(path)
        self._n_rows = 0

    @property
    def n_rows(self):
        """Rows this object has written. A controller that wants A §4.1's
        `call_no` (1, 2, … within the cell) can count with it; the client does
        not number rows itself."""
        return self._n_rows

    def append(self, row):
        """Write one row (A §4.1) and return it. Refuses a row whose key set is
        not exactly `CALL_ROW_KEYS`."""
        missing = [key for key in CALL_ROW_KEYS if key not in row]
        spare = sorted(set(row) - set(CALL_ROW_KEYS))
        if missing or spare:
            raise ValueError(
                f"a calls.jsonl row carries exactly A §4.1's keys; missing {missing}, "
                f"spare {spare}")
        # serialize first: a bad value never half-writes a line (the old
        # `store._append`'s habit)
        line = json.dumps(row, sort_keys=True) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as handle:
            handle.write(line)
        self._n_rows += 1
        return row


def messages_sha256(messages):
    """sha256 of the sorted-JSON serialization of a message list (old
    `prefix_sha256`, loop.py ~452-456). This is A §4.1's `prefix_sha256` for a
    **trace** arm, where the row hashes the page itself."""
    return hashlib.sha256(
        json.dumps([dict(m) for m in messages], sort_keys=True).encode()).hexdigest()


# A §4.1 (settled 09-24 on this module's A-question): two columns. A trace arm
# fills `page_sha256` with `messages_sha256(page)` and leaves `prefix_sha256`
# null; chat fills `prefix_sha256` with the function below and leaves
# `page_sha256` null.
def prefix_sha256(messages):
    """sha256 of every message before the newest — the conversation so far, the
    cache-hit check of A §4.1 for **chat**, where the newest turn is the only
    thing that is not prefix."""
    return messages_sha256(list(messages)[:-1])


def _tokens(raw):
    """`{prompt, eval}` as the server reports them (A §4.1), or None. llama.cpp
    answers with OpenAI's `usage` and with its own `timings`; the first is
    preferred and the second is the fallback, and neither is invented."""
    usage = raw.get("usage") or {}
    if "prompt_tokens" in usage and "completion_tokens" in usage:
        return {"prompt": int(usage["prompt_tokens"]), "eval": int(usage["completion_tokens"])}
    timings = raw.get("timings") or {}
    if "prompt_n" in timings and "predicted_n" in timings:
        return {"prompt": int(timings["prompt_n"]), "eval": int(timings["predicted_n"])}
    return None
