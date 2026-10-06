"""The chat conversation stays inside the server's context (A §3.3; 09-24: the first live
chat cell hit llama.cpp's 98,304-token context at step 279 because the byte-per-token
estimate was a quarter too generous and never calibrated)."""
import json

from p3focus import chat, client as clientlib, constants


class _Fake:
    """A client whose server counts 2 bytes a token, and can refuse once for context."""

    def __init__(self, refuse_at_call=None):
        self.calls = 0
        self.refuse_at_call = refuse_at_call
        self.model = "fake"

    def probe(self):
        return None

    def complete(self, messages, grammar=None, max_tokens=constants.MAX_TOKENS):
        self.calls += 1
        total = sum(len(m["content"].encode()) for m in messages)
        if self.calls == self.refuse_at_call:
            body = json.dumps({"error": {"code": 400, "message": "request exceeds", "type": "exceed_context_size_error",
                                         "n_prompt_tokens": total // 2, "n_ctx": 98304}})
            raise clientlib.ClientError(400, body)
        text = json.dumps({"action": "move_right", "why": "east", "destination": None})
        return clientlib.Reply(text=text, elapsed_s=0.01, tokens={"prompt": total // 2, "eval": 20}, attempt=1)


def test_the_ratio_is_calibrated_from_the_servers_count(tmp_path):
    run = chat.run_chat_cell(7, 3, _Fake(), tmp_path, quiet=True)
    assert abs(run.conversation.bytes_per_token - 2.0) < 0.05


def test_a_calibrated_conversation_trims_where_the_server_would_refuse(tmp_path, monkeypatch):
    # a budget the un-calibrated estimate (2.75 bytes/token) would call fine at 2 bytes/token
    monkeypatch.setattr(constants, "CHAT_BUDGET_TOKENS", 9000)
    monkeypatch.setattr(constants, "CHAT_KEEP_TURNS", 3)
    run = chat.run_chat_cell(7, 30, _Fake(), tmp_path, quiet=True)
    assert run.conversation.est_tokens() <= 9000 + 600   # trimmed at open_turn; the last reply then rides on top
    rows = [json.loads(l) for l in (run.dir / "events.jsonl").read_text().splitlines()]
    assert any(r["kind"] == "conversation_trimmed" for r in rows)


def test_a_context_refusal_is_recovered_once_by_trimming(tmp_path, monkeypatch):
    monkeypatch.setattr(constants, "CHAT_KEEP_TURNS", 3)
    fake = _Fake(refuse_at_call=8)
    run = chat.run_chat_cell(7, 12, fake, tmp_path, quiet=True)
    assert run.summary["steps_survived"] == 12
    rows = [json.loads(l) for l in (run.dir / "events.jsonl").read_text().splitlines()]
    trimmed = [r for r in rows if r["kind"] == "conversation_trimmed" and r["step"] == 8]
    assert trimmed, "the refused step was trimmed and retried"
    assert fake.calls == 13  # twelve steps plus the one refused call
