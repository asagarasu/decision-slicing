"""The two things that must never happen, exercised so the detectors are live.

`ops_in_acting_reply` is A §4.2's defect row: R3's and R4's grammars have no
`ops` key and the parser has no path from the acting rounds to the list, so the
row must never appear in a real run (`test_trace_focus.py` asserts that). A
detector nobody ever fires is a detector nobody knows works, so here a scripted
reply carries `ops` past the grammar and the row is checked to fire — with
nothing applied.

The second is A §5's chat dispatch: the chat controller is built on another
branch, and every trace arm has to run whether or not it has landed.
"""
import importlib
import json
import pathlib
import sys
import tempfile

from fixtures import scripted as s
from p3focus import trace


def _run(arm, steps, script):
    out = tempfile.mkdtemp(prefix="p3focus_defect_")
    cell_dir, summary = trace.run_trace_cell(arm, 7, steps, s.ScriptedClient(script), out,
                                             quiet=True)
    return pathlib.Path(cell_dir), summary


def _events(cell_dir):
    return [json.loads(line)
            for line in (cell_dir / "events.jsonl").read_text().splitlines()]


def test_an_acting_reply_carrying_ops_is_logged_and_applies_nothing():
    defaults = {"R1": s.r1_no(), "R1.5": s.r1_5(False), "R2": s.r2("e1"),
                "R3": s.r3(), "R4": s.r4("move_right")}
    smuggled = '{"op": "delete", "id": "e1"}'
    plan = {
        (2, "R3"): ['{"need": "n", "candidates": [], "target": null, "why": "w", "ops": [%s]}' % smuggled],
        (3, "R4"): ['{"action": "move_right", "intent": "east", "ops": [%s]}' % smuggled],
    }
    cell_dir, _ = _run("focus", 4, s.Script(defaults, plan))
    rows = [e for e in _events(cell_dir) if e["kind"] == "ops_in_acting_reply"]
    assert [(e["step"], e["round"]) for e in rows] == [(2, "R3"), (3, "R4")]
    assert rows[0]["ops"] == [json.loads(smuggled)]
    # nothing was applied: no list row, and the entry is still there
    assert "ops_applied" not in {e["kind"] for e in _events(cell_dir)}
    last = [json.loads(line) for line in
            (cell_dir / "calls.jsonl").read_text().splitlines()][-1]
    assert '"id": "e1"' in last["prompt"]
    # and the call row keeps the evidence rather than quietly dropping the key
    smuggling = [json.loads(line) for line in
                 (cell_dir / "calls.jsonl").read_text().splitlines()
                 if json.loads(line)["step"] == 2 and json.loads(line)["round"] == "R3"][0]
    assert "ops" in smuggling["parsed"] and smuggling["valid"] is True


def test_a_reply_that_is_not_json_is_a_reason_and_one_retry_not_a_crash():
    defaults = {"R1": s.r1_no(), "R1.5": s.r1_5(False), "R2": s.r2("e1"),
                "R3": s.r3(), "R4": s.r4("move_right")}
    plan = {(1, "R3"): ["I would rather not say.", s.r3(do="explore north")]}
    cell_dir, _ = _run("focus", 2, s.Script(defaults, plan))
    invalid = [e for e in _events(cell_dir) if e["kind"] == "reply_invalid"]
    assert len(invalid) == 1 and "not one JSON object" in invalid[0]["reason"]
