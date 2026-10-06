"""flat under the hold (A §3.2, A §7 D9; B §3.6): one reply a step, and the cell it
names held from step to step.

E2's question is whether the treatment's win is the slicing or the hold, so flat gets
the hold and nothing else: the same one page, the same one reply, the same list on it.
What that means step by step is here — the block from the next page on, the route to the
held cell on this one, `null` keeping what is held, and the three rows of A §4.2 written
by the rules focus writes them by.

Small scripted cells on `World(7)`; nothing contacts a server. Coordinates in scripted
replies are the SHOWN axis (+y up); rows are WORLD axis.
"""
import json

from fixtures import scripted as s
from p3focus import axis, pages, reader, route, trace

#: three cells east of the spawn ([32, 31] shown): named at step 1, stood on at the
#: start of step 4 by a body that moves right every step
EAST3_SHOWN = (35, 31)
EAST3_WORLD = [35, 32]
#: far east, out of reach of any of these cells: held until something takes it away
FAR_SHOWN = (45, 31)
FAR_WORLD = [45, 32]

DEST_HEAD = "THE DESTINATION YOU CHOSE"


def _rows(cell_dir, name):
    return [json.loads(line) for line in (cell_dir / name).read_text().splitlines()]


def _run(steps, script, tmp_path):
    cell_dir, summary = trace.run_trace_cell("flat", 7, steps, s.ScriptedClient(script),
                                             tmp_path, quiet=True)
    return cell_dir, summary, script


def _page(script, step):
    """The page flat was shown on a step; its first attempt, when there were two."""
    return script.pages("flat", step=step)[0]


def _of_kind(cell_dir, *kinds):
    return [e for e in _rows(cell_dir, "events.jsonl") if e["kind"] in kinds]


# -- the destination named, held, walked toward, reached --------------------


def test_a_named_cell_is_held_from_the_next_page_and_reached_where_the_body_stands(tmp_path):
    """The brief's first cell: the reply names three east at step 1 and `null` after.
    The block first rides step 2's page — the reply comes after the page, so the step it
    was named on still shows nothing — the route sentence is to it on every step it is
    held, and the start of step 4 stands on it: `destination_reached`, the hold cleared,
    and nothing held after (A §3.2; B §3.6)."""
    plan = {(1, "flat"): [s.flat("move_right", "east", destination=EAST3_SHOWN)]}
    cell_dir, summary, script = _run(6, s.Script({"flat": s.flat("move_right", "east")},
                                                 plan), tmp_path)
    assert DEST_HEAD not in _page(script, 1)
    for step in (2, 3):
        page = _page(script, step)
        assert f"{DEST_HEAD}: [35, 31], named at step 1." in page
        assert "The way there, over cells you have seen, begins with move_right." in page
        # no round preceded this page and no round was asked (B, P10; §3.6)
        assert "This is the same window you just read" not in page
        assert "named this step" not in page and "kept this step" not in page
        assert page.count(pages.DEST_TAIL_HELD) == 1
        # flat's reply has no `need` and no `why`, so their lines are not there
        assert "The need you named" not in page and "What the destination is for" not in page
    for step in (4, 5, 6):
        assert DEST_HEAD not in _page(script, step)

    chosen = _of_kind(cell_dir, "destination_chosen")
    assert [(e["step"], e["cell"]) for e in chosen] == [(1, EAST3_WORLD)]
    reached = _of_kind(cell_dir, "destination_reached")
    assert [(e["step"], e["cell"], e["held_steps"]) for e in reached] == [(4, EAST3_WORLD, 3)]
    assert not _of_kind(cell_dir, "destination_cleared")
    # the route rides the steps that carried it, stamped with the step of the page
    assert [e["step"] for e in _of_kind(cell_dir, "route")] == [2, 3]


def test_the_action_rows_carry_the_cell_that_was_in_force_while_the_body_acted(tmp_path):
    """A §4.3: flat's `target` stays null and `destination` is the cell its page carried
    — so it and `route_first_step` are one step's reading. The step a reply first names
    one is null: the body had already acted when it answered."""
    plan = {(1, "flat"): [s.flat("move_right", "east", destination=EAST3_SHOWN)]}
    cell_dir, _, _ = _run(6, s.Script({"flat": s.flat("move_right", "east")}, plan), tmp_path)
    actions = _rows(cell_dir, "actions.jsonl")
    assert [a["destination"] for a in actions] == [None, EAST3_WORLD, EAST3_WORLD,
                                                   None, None, None]
    assert [a["target"] for a in actions] == [None] * 6
    assert [a["route_first_step"] for a in actions] == [None, "move_right", "move_right",
                                                        None, None, None]


def test_null_keeps_what_is_held_and_names_none_when_there_is_none(tmp_path):
    """A §3.2's `null`: the reply that names nothing keeps the cell it holds. With none
    held it names none, and then no block, no route and no row is written at all."""
    cell_dir, summary, script = _run(3, s.Script({"flat": s.flat("move_right", "east")}),
                                     tmp_path)
    for step in (1, 2, 3):
        page = _page(script, step)
        assert DEST_HEAD not in page
        assert pages.list_manual() in page and pages.command_block("flat") in page
    assert not _of_kind(cell_dir, "destination_chosen", "destination_reached",
                        "destination_cleared", "route")
    assert [a["destination"] for a in _rows(cell_dir, "actions.jsonl")] == [None] * 3
    assert summary["destinations_named"] == 0 and summary["destinations_chosen"] == 0


def test_another_cell_replaces_the_held_one_and_writes_cleared_then_chosen(tmp_path):
    """The brief's second cell: step 5 names another cell. `destination_cleared`
    (`replaced`) then `destination_chosen`, in that order, and step 6's page carries the
    new cell named at step 5 (A §4.2; B §3.6)."""
    plan = {(1, "flat"): [s.flat("move_right", "east", destination=FAR_SHOWN)],
            (5, "flat"): [s.flat("move_right", "east", destination=(45, 35))]}
    cell_dir, summary, script = _run(6, s.Script({"flat": s.flat("move_right", "east")},
                                                 plan), tmp_path)
    step5 = [e for e in _rows(cell_dir, "events.jsonl")
             if e["step"] == 5 and e["kind"].startswith("destination_")]
    assert [(e["kind"], e["cell"]) for e in step5] == [
        ("destination_cleared", FAR_WORLD), ("destination_chosen", [45, 28])]
    assert step5[0]["reason"] == "replaced" and step5[0]["held_steps"] == 4
    # the page of the step that replaced it still carries the old cell: it is what the
    # body acted on, and the new one is first shown next step
    assert f"{DEST_HEAD}: [45, 31], named at step 1." in _page(script, 5)
    assert f"{DEST_HEAD}: [45, 35], named at step 5." in _page(script, 6)
    actions = _rows(cell_dir, "actions.jsonl")
    assert actions[4]["destination"] == FAR_WORLD and actions[5]["destination"] == [45, 28]
    assert summary["destinations_named"] == 2 and summary["destinations_chosen"] == 2


def test_naming_the_held_cell_again_keeps_it_and_writes_no_row(tmp_path):
    """The same cell named again keeps the hold and its naming step (A §3.2), so the page
    goes on saying `named at step 1`. It is still a reply that named a cell, which is
    what `destinations_named` counts, and it writes no row, which is what
    `destinations_chosen` counts — the two numbers come apart here (A §4.4)."""
    plan = {(1, "flat"): [s.flat("move_right", "east", destination=FAR_SHOWN)],
            (3, "flat"): [s.flat("move_right", "east", destination=FAR_SHOWN)]}
    cell_dir, summary, script = _run(4, s.Script({"flat": s.flat("move_right", "east")},
                                                 plan), tmp_path)
    assert [(e["step"], e["kind"]) for e in _of_kind(
        cell_dir, "destination_chosen", "destination_cleared", "destination_reached")] == [
        (1, "destination_chosen")]
    assert f"{DEST_HEAD}: [45, 31], named at step 1." in _page(script, 4)
    assert summary["destinations_named"] == 2 and summary["destinations_chosen"] == 1


def test_a_reply_refused_twice_is_a_noop_and_keeps_the_held_cell(tmp_path):
    """A §3.4's default for flat: `noop`, the ops dropped — and the hold kept, because
    `null` is this reply's own way of keeping it and a reply nobody could read names
    nothing. (R3's default drops one, D10: there `null` means the opposite.)"""
    bad = s.flat("swim", "west")
    plan = {(1, "flat"): [s.flat("move_right", "east", destination=FAR_SHOWN)],
            (3, "flat"): [bad, bad]}
    cell_dir, summary, script = _run(4, s.Script({"flat": s.flat("move_right", "east")},
                                                 plan), tmp_path)
    step3 = [e for e in _rows(cell_dir, "events.jsonl") if e["step"] == 3]
    assert [e["kind"] for e in step3 if e["kind"] == "reply_invalid"] == ["reply_invalid"] * 2
    assert [e["default"] for e in step3 if e["kind"] == "reply_defaulted"] == ["noop"]
    assert not [e for e in step3 if e["kind"].startswith("destination_")]
    actions = _rows(cell_dir, "actions.jsonl")
    assert actions[2]["action"] == "noop" and actions[2]["destination"] == FAR_WORLD
    assert f"{DEST_HEAD}: [45, 31], named at step 1." in _page(script, 4)
    assert summary["destinations_chosen"] == 1


def test_no_way_over_seen_cells_clears_the_hold_and_the_next_page_carries_none(tmp_path,
                                                                               monkeypatch):
    """The other end of a hold (A §3.2, A §4.2): the route hint's first sentence for the
    held cell at a step's start clears it with `no_way`. flat has no R3 to re-open the
    question — the page simply carries no block, and the reply may name a cell again,
    which is a new hold with a new naming step."""
    real = route.route
    calls = {"n": 0}

    def no_way_on_step_3(pos, target, seen):
        calls["n"] += 1
        # step 1 holds nothing and asks nothing of the hint; 1: step 2's check at its
        # start; 2: step 2's hint for its page; 3: step 3's check at its start
        if calls["n"] == 3:
            return route.RouteResult(None, False, 1, route.SENTENCES[0])
        return real(pos, target, seen)

    monkeypatch.setattr(trace.route, "route", no_way_on_step_3)
    plan = {(1, "flat"): [s.flat("move_right", "east", destination=FAR_SHOWN)],
            (3, "flat"): [s.flat("move_right", "east", destination=FAR_SHOWN)]}
    cell_dir, summary, script = _run(4, s.Script({"flat": s.flat("move_right", "east")},
                                                 plan), tmp_path)
    cleared = _of_kind(cell_dir, "destination_cleared")
    assert [(e["step"], e["cell"], e["reason"], e["held_steps"]) for e in cleared] == \
        [(3, FAR_WORLD, "no_way", 2)]
    assert DEST_HEAD not in _page(script, 3)
    assert [(e["step"], e["cell"]) for e in _of_kind(cell_dir, "destination_chosen")] == [
        (1, FAR_WORLD), (3, FAR_WORLD)]
    assert f"{DEST_HEAD}: [45, 31], named at step 3." in _page(script, 4)
    assert summary["destinations_chosen"] == 2


def test_the_cell_the_body_stands_on_is_reached_at_the_next_steps_start(tmp_path):
    """The reply names the cell the body is standing on. The body has already moved off it
    by then (the reply comes after the page), so step 2 carries it one cell back and walks
    onto it, and step 3 opens standing on it: reached, two steps held.

    So a flat page never carries the bearing line's `You are standing on that position.` —
    a hold that is the body's own cell is cleared at the step's start, before the page
    renders. A §6's rule (no hint, no row, for the cell under the body) has nothing left to
    catch here, and the controller keeps its guard for the rule, not for a case."""
    own = tuple(axis.shown_pos([32, 32]))
    plan = {(1, "flat"): [s.flat("move_right", "east", destination=own)],
            (2, "flat"): [s.flat("move_left", "back")]}
    cell_dir, _, script = _run(3, s.Script({"flat": s.flat("move_right", "east")}, plan),
                               tmp_path)
    assert f"{DEST_HEAD}: [32, 31], named at step 1." in _page(script, 2)
    assert ("From where you stand, that position is 1 x move_left away: it is the cell to "
            "your left, grass.") in _page(script, 2)
    assert [(e["step"], e["held_steps"]) for e in _of_kind(cell_dir,
                                                           "destination_reached")] == [(3, 2)]
    assert DEST_HEAD not in _page(script, 3)
    for step in (1, 2, 3):
        assert "You are standing on that position." not in _page(script, step)


# -- what the reader makes of one (A §4.4; the table) -----------------------


def test_the_reader_reads_flats_hold_as_it_reads_the_other_arms(tmp_path):
    """`HOLD_ARMS` has flat since 09-25: its `destinations` column is the cells it chose
    and `steps / dest` the mean it held them. `R3 asks` stays empty — flat has no such
    round to count (A §7 D9)."""
    plan = {(1, "flat"): [s.flat("move_right", "east", destination=EAST3_SHOWN)],
            (4, "flat"): [s.flat("move_right", "east", destination=FAR_SHOWN)]}
    cell_dir, summary, _ = _run(6, s.Script({"flat": s.flat("move_right", "east")}, plan),
                                tmp_path)
    read = reader.read_cell(cell_dir)
    assert read["destinations_chosen"] == 2 == summary["destinations_chosen"]
    assert read["destinations_named"] == 2 == summary["destinations_named"]
    assert read["summary_disagreements"] == []
    assert [(e["cell"], e["step"], e["end"], e["held_steps"])
            for e in read["destination_episodes"]] == [
        (EAST3_WORLD, 1, "reached", 3), (FAR_WORLD, 4, "open", 3)]
    assert read["r3_asks"] == 0 and read["r3_occasions"] == {}
    row = reader.table([read]).splitlines()[2].split(" | ")
    assert row[-3:] == ["2", "—", "3.0 |"]      # destinations, R3 asks, steps / dest
