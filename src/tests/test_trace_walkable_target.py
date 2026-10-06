"""A §3.4 (09-24): a target the body can see and cannot stand on is refused, once with
the reason, then R3 defaults to the exploring branch. The first show run spent 204 steps
naming the stone cell east of [32, 26] (registrations/20260924_show_run_focus_s7_98b.md)."""
import json

from fixtures import scripted
from p3focus import axis, trace, world as world_mod


def _rows(path):
    return [json.loads(l) for l in path.read_text().splitlines()]


def test_a_visible_stone_target_is_refused_then_defaulted(tmp_path):
    # walk north six steps from the spawn to [32, 26] (world), where east is stone on seed 7
    w = world_mod.World(7); w.reset()
    for _ in range(6):
        w.step("move_up")
    assert w.last_frame["window"][4][5] == "stone", "seed 7 moved; the cell east of [32, 26] is not stone"
    stone_shown = axis.shown_pos([33, 26])
    # the standing destination is [32, 26] itself: named on step 1, it is reached at the
    # start of step 7, which is what brings R3 back on that step (A §3.1, the hold)
    grass_shown = axis.shown_pos([32, 26])
    r3_stone = json.dumps({"need": "go east", "candidates": [stone_shown], "target": stone_shown, "why": "break through"})
    r3_grass = json.dumps({"need": "go north", "candidates": [grass_shown], "target": grass_shown, "why": "step north"})
    defaults = {"R1": json.dumps({"why": "as it stands", "maintain": "no"}), "R1.5": json.dumps({"delete": False}),
                "R2": json.dumps({"why": "the task", "focus": "e1"}), "R3": r3_grass,
                "R4": json.dumps({"action": "move_up", "intent": "north"})}
    # step 7 (the reached occasion) names the stone cell twice: refused, refused, defaulted
    plan = {(7, "R3"): [r3_stone, r3_stone]}
    script = scripted.Script(defaults, plan)
    client = scripted.ScriptedClient(script)
    cell_dir, summary = trace.run_trace_cell("focus", 7, 8, client, tmp_path, quiet=True)
    events = _rows(cell_dir / "events.jsonl")
    invalid = [e for e in events if e["kind"] == "reply_invalid" and e["step"] == 7]
    assert [e["round"] for e in invalid] == ["R3", "R3"]
    assert "is stone; you cannot stand on it" in invalid[0]["reason"]
    assert any(e["kind"] == "reply_defaulted" and e["round"] == "R3" and e["step"] == 7 for e in events)
    calls = [c for c in _rows(cell_dir / "calls.jsonl") if c["step"] == 7 and c["round"] == "R4"]
    assert "the position you named was refused twice" in calls[0]["prompt"]
    assert any(e["kind"] == "destination_reached" and e["step"] == 7 for e in events)
    # step 8 opens with no destination (the default dropped it), so R3 runs again, and an
    # ordinary grass target is not refused
    assert [c["round"] for c in _rows(cell_dir / "calls.jsonl") if c["step"] == 8] == ["R3", "R4"]
    assert not any(e["kind"] == "reply_invalid" and e["step"] == 8 for e in events)
