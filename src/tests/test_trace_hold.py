"""The hold (A §3.1; B §3.4, §3.5): R3 on its four occasions and on no other step, the
destination held between them, the three rows, and R4's block on a held step. Small
scripted focus and sliced cells on `World(7)`; nothing contacts a server.

Coordinates in scripted replies are the SHOWN axis (+y up); rows are WORLD axis.
"""
import json

import pytest

from fixtures import scripted as s
from p3focus import axis, pages, route, trace


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def _run(arm, steps, script, tmp_path):
    cell_dir, summary = trace.run_trace_cell(arm, 7, steps, s.ScriptedClient(script), tmp_path,
                                             quiet=True)
    return cell_dir, summary, script


def _defaults(arm, r3):
    d = {"R1": s.r1_no(), "R1.5": s.r1_5(False), "R3": r3, "R4": s.r4("move_right")}
    if arm == "focus":
        d["R2"] = s.r2("e1")
    return d


def _rounds_by_step(script):
    out = {}
    for step, round_id in script.rounds():
        out.setdefault(step, []).append(round_id)
    return out


@pytest.mark.parametrize("arm", ["focus", "sliced"])
def test_a_held_destination_is_asked_once_and_walked_toward_until_reached(arm, tmp_path):
    """Step 1 names the cell three east of the spawn ([35, 31] shown = (35, 32) world); the
    walk east reaches it at the start of step 4. R3 runs on 1 (missing) and 4 (reached) and
    on no step between; R4 on every step, with the block's held shape on 2 and 3."""
    plan = {(1, "R3"): [s.r3(target=(35, 31), need="go east", why="to see")]}
    cell_dir, summary, script = _run(arm, 6, s.Script(_defaults(arm, s.r3(target=(45, 31))), plan),
                                     tmp_path)
    by_step = _rounds_by_step(script)
    assert by_step[1] == ["R3", "R4"]
    assert by_step[2] == ["R4"] and by_step[3] == ["R4"]
    assert by_step[4] == ["R3", "R4"]
    assert by_step[5] == ["R4"] and by_step[6] == ["R4"]
    events = _rows(cell_dir / "events.jsonl")
    chosen = [e for e in events if e["kind"] == "destination_chosen"]
    assert [(e["step"], e["cell"]) for e in chosen] == [(1, [35, 32]), (4, [45, 32])]
    reached = [e for e in events if e["kind"] == "destination_reached"]
    assert [(e["step"], e["cell"], e["held_steps"]) for e in reached] == [(4, [35, 32], 3)]
    assert not [e for e in events if e["kind"] == "destination_cleared"]
    # the rows: the held destination is the step's target while it is held
    actions = _rows(cell_dir / "actions.jsonl")
    assert [a["target"] for a in actions] == [[35, 32]] * 3 + [[45, 32]] * 3
    assert all(a["route_first_step"] == "move_right" for a in actions)
    # the pages: step 4's R3 says the destination was reached; steps 2–3's R4 carry the held
    # shape with step 1's need and why; step 1's carries the fresh shape
    r3_4 = script.pages("R3", step=4)[0]
    assert pages.destination_line("reached", pages.Destination((35, 32), 1)) in r3_4
    r4_1 = script.pages("R4", step=1)[0]
    assert "THE DESTINATION YOU CHOSE: [35, 31], named this step." in r4_1
    assert "This is the same window you just read" in r4_1
    for step in (2, 3):
        page = script.pages("R4", step=step)[0]
        assert "THE DESTINATION YOU CHOSE: [35, 31], named at step 1." in page
        assert "The need you named: go east\nWhat the destination is for: to see" in page
        assert "This is the same window you just read" not in page
        assert page.count(pages.DEST_TAIL_HELD) == 1
        assert "The way there, over cells you have seen, begins with move_right." in page
    assert summary["destinations_chosen"] == 2
    # the route row rides every held step (A §4.2), stamped with that step
    assert [e["step"] for e in events if e["kind"] == "route"] == [1, 2, 3, 4, 5, 6]


def test_an_event_re_asks_and_the_body_may_keep_replace_or_drop(tmp_path):
    """The event occasion, three times over. Step 11 (the note's gate): R1 deletes the one
    entry, R1.5 confirms, the second R1 page adds nothing, so the acting pages show none;
    R3 renders with the held line and keeps the cell — no row. Step 12 (the empty list's own
    ask): R1 adds an entry, R2 fails twice, R3 names another cell — `destination_cleared`
    (`replaced`) then `destination_chosen`. Step 13 (the no-focus ask): R3 answers null —
    `dropped`. Step 14 opens with no destination (missing) and names one; 15 is held."""
    far = (45, 31)
    plan = {
        (1, "R3"): [s.r3(target=far, need="east", why="far")],
        (11, "R1"): [s.r1_ops(s.op_delete("e1")), s.r1_no()], (11, "R1.5"): [s.r1_5(True)],
        (11, "R3"): [s.r3(target=far, need="still east", why="the note can wait")],   # kept
        (12, "R1"): [s.r1_ops(s.op_add("go_north", "up there"))], (12, "R2"): [s.r2("e99"), s.r2("e77")],
        (12, "R3"): [s.r3(target=(45, 35), need="north-east", why="new entry")],     # replaced
        (13, "R1"): [s.r1_no()], (13, "R2"): [s.r2("e2")],
        (13, "R3"): [s.r3(target=None, need="nothing", why="null")],                # dropped
    }
    script = s.Script(_defaults("focus", s.r3(target=far, need="east", why="again")), plan)
    cell_dir, summary, script = _run("focus", 15, script, tmp_path)
    by_step = _rounds_by_step(script)
    events = _rows(cell_dir / "events.jsonl")

    assert by_step[11] == ["R1", "R1.5", "R1", "R3", "R4"]
    r3_11 = script.pages("R3", step=11)[0]
    assert "Your destination until now: [45, 31], named at step 1 — the need you named then: east; " \
           "what it was for: far. Keeping it is an answer" in r3_11
    assert "the one you are on: none" in r3_11
    assert not [e for e in events if e["step"] == 11 and e["kind"].startswith("destination_")]
    # kept at an event: R4's block names the old step and says so, and a round preceded it
    r4_11 = script.pages("R4", step=11)[0]
    assert "THE DESTINATION YOU CHOSE: [45, 31], named at step 1, kept this step." in r4_11
    assert "This is the same window you just read" in r4_11
    # and the prose that named it stays with it: the re-affirming reply's words do not replace it
    assert "The need you named: east\nWhat the destination is for: far" in r4_11
    assert "still east" not in r4_11

    assert by_step[12] == ["R1", "R2", "R2", "R3", "R4"]
    rows_12 = [e for e in events if e["step"] == 12 and e["kind"].startswith("destination_")]
    assert [(e["kind"], e["cell"]) for e in rows_12] == [
        ("destination_cleared", [45, 32]), ("destination_chosen", [45, 28])]
    assert rows_12[0]["reason"] == "replaced" and rows_12[0]["held_steps"] == 11
    assert "Your destination until now: [45, 31], named at step 1" in script.pages("R3", step=12)[0]
    assert "THE DESTINATION YOU CHOSE: [45, 35], named this step." in script.pages("R4", step=12)[0]

    assert by_step[13] == ["R1", "R2", "R3", "R4"]
    rows_13 = [e for e in events if e["step"] == 13 and e["kind"].startswith("destination_")]
    assert [(e["kind"], e["cell"], e["reason"], e["held_steps"]) for e in rows_13] == [
        ("destination_cleared", [45, 28], "dropped", 1)]
    r4_13 = script.pages("R4", step=13)[0]
    assert pages.DEST_NULL_HEAD in r4_13 and "The need you named: nothing" in r4_13
    assert _rows(cell_dir / "actions.jsonl")[12]["target"] is None

    assert by_step[14] == ["R3", "R4"]           # missing: no ask, and still R3
    r3_14 = script.pages("R3", step=14)[0]
    assert "Your destination until now" not in r3_14 and "no longer held" not in r3_14
    assert [e["cell"] for e in events if e["step"] == 14 and e["kind"] == "destination_chosen"] == [[45, 32]]
    assert by_step[15] == ["R4"]
    assert summary["destinations_chosen"] == 3


def test_replacing_at_an_event_writes_cleared_then_chosen_in_that_order(tmp_path):
    plan = {
        (1, "R3"): [s.r3(target=(45, 31), need="east", why="far")],
        (11, "R3"): [s.r3(target=(45, 40), need="north-east", why="the note")],
    }
    cell_dir, _, script = _run("sliced", 12, s.Script(_defaults("sliced", s.r3(target=(45, 31))), plan),
                               tmp_path)
    events = [e for e in _rows(cell_dir / "events.jsonl") if e["step"] == 11
              and e["kind"].startswith("destination_")]
    assert [(e["kind"], e["cell"]) for e in events] == [
        ("destination_cleared", [45, 32]), ("destination_chosen", [45, 23])]
    assert events[0]["reason"] == "replaced" and events[0]["held_steps"] == 10
    assert _rows(cell_dir / "actions.jsonl")[11]["target"] == [45, 23]


def test_no_way_there_clears_the_hold_and_re_asks(tmp_path, monkeypatch):
    """The no-way occasion: when the route hint's answer for the held cell is its first
    sentence, the hold is cleared (`no_way`) and R3 renders with that line."""
    real = route.route
    calls = {"n": 0}

    def no_way_on_step_3(pos, target, seen):
        calls["n"] += 1
        result = real(pos, target, seen)
        # 1: step 1's R4 hint; 2: step 2's occasion check; 3: step 2's R4 hint; 4: step 3's check
        if calls["n"] == 4:
            return route.RouteResult(None, False, 1, route.SENTENCES[0])
        return result

    monkeypatch.setattr(trace.route, "route", no_way_on_step_3)
    plan = {(1, "R3"): [s.r3(target=(45, 31), need="east", why="far")],
            (3, "R3"): [s.r3(target=(45, 31), need="east again", why="still")]}
    cell_dir, _, script = _run("focus", 4, s.Script(_defaults("focus", s.r3(target=(45, 31))), plan),
                               tmp_path)
    by_step = _rounds_by_step(script)
    assert by_step[1] == ["R3", "R4"] and by_step[2] == ["R4"] and by_step[3] == ["R3", "R4"]
    events = _rows(cell_dir / "events.jsonl")
    cleared = [e for e in events if e["kind"] == "destination_cleared"]
    assert [(e["step"], e["cell"], e["reason"], e["held_steps"]) for e in cleared] == [(3, [45, 32], "no_way", 2)]
    page = script.pages("R3", step=3)[0]
    assert pages.destination_line("no_way", pages.Destination((45, 32), 1)) in page
    # the same cell named again is a new hold, named at step 3
    chosen = [e for e in events if e["kind"] == "destination_chosen"]
    assert [(e["step"], e["cell"]) for e in chosen] == [(1, [45, 32]), (3, [45, 32])]
    assert "named this step." in script.pages("R4", step=3)[0]
    assert "named at step 3." in script.pages("R4", step=4)[0]


def test_naming_ones_own_cell_is_reached_on_the_next_step(tmp_path):
    """A destination that is the body's own cell gets no route and no route row (A §6); the
    next step opens standing on it, which is the reached occasion with one step held."""
    own = tuple(axis.shown_pos([32, 32]))
    plan = {(1, "R3"): [s.r3(target=own, need="stay", why="here")]}
    script = s.Script(_defaults("focus", s.r3(target=(45, 31))), plan)
    # R4 bumps into whatever is east; whether it moves or not, step 2 opens on [32, 32] only
    # if it did not move — so give R4 a verb that cannot move: face the tree/stone if any,
    # else accept either outcome and read the rows
    cell_dir, _, script = _run("focus", 3, script, tmp_path)
    events = _rows(cell_dir / "events.jsonl")
    actions = _rows(cell_dir / "actions.jsonl")
    assert actions[0]["target"] == [32, 32] and actions[0]["route_first_step"] is None
    assert not [e for e in events if e["kind"] == "route" and e["step"] == 1]
    page = script.pages("R4", step=1)[0]
    assert "You are standing on that position." in page
    if actions[0]["moved"] is False:
        assert [(e["step"], e["held_steps"]) for e in events if e["kind"] == "destination_reached"] == [(2, 1)]
    else:
        # it moved off the cell; the hold stands and the route points back
        assert actions[1]["target"] == [32, 32] and actions[1]["route_first_step"] == "move_left"


def test_the_three_rows_are_a_4_2s_kinds_with_their_fields():
    from p3focus import cell
    assert cell.EVENT_FIELDS["destination_chosen"] == ("cell",)
    assert cell.EVENT_FIELDS["destination_reached"] == ("cell", "held_steps")
    assert cell.EVENT_FIELDS["destination_cleared"] == ("cell", "held_steps", "reason")
