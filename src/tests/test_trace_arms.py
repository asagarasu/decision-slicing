"""flat and sliced: one scripted cell each, and the three cross-arm checkers.

flat is the one-pass control (B §3.6): one call a step, ops applied as written
with no R1.5 (A §7, D5), and — since 09-25 (A §7 D9, E2) — a destination held
from step to step, whose own tests are `test_trace_flat_hold.py`'s. sliced is
focus without R2 (B §3.7): the whole list, read-only, where focus shows the one
entry in force.
"""
import functools
import json
import pathlib
import tempfile

from fixtures import scripted as s
from p3focus import constants, grammars, pages, route, texts, trace
from p3focus import world as world_mod

NOTE_LINE = world_mod.trace_note_line(
    constants.NOTE_STEP, world_mod.errand_note(constants.ERRANDS[7]))


def _run(arm, steps, script, quiet=True):
    out = tempfile.mkdtemp(prefix=f"p3focus_{arm}_")
    cell_dir, summary = trace.run_trace_cell(arm, 7, steps, s.ScriptedClient(script), out,
                                             quiet=quiet)
    return cell_dir, summary


def _route_lines(page):
    """The route hint's own line on a page, if any — one of A §6's three, and
    never the command block's prose about destinations."""
    wanted = {route.SENTENCES[0]} | {
        template.format(verb=verb) for template in route.SENTENCES[1:]
        for verb in route.MOVE_VERBS}
    return [line for line in page.splitlines() if line in wanted]


def _rows(cell_dir, name):
    return [json.loads(line)
            for line in (pathlib.Path(cell_dir) / name).read_text().splitlines()]


# -- flat (B §3.6) ----------------------------------------------------------

FLAT_STEPS = 14


@functools.lru_cache(maxsize=1)
def flat_run():
    plan = {
        # a destination on step 3, answered on step 4's page
        (3, "flat"): [s.flat("move_right", "east", destination=(30, 31))],
        # an add and a delete in one reply: both apply at once, no R1.5
        (5, "flat"): [s.flat("move_right", "east",
                             ops=[s.op_add("find_water", "drink is 9"), s.op_delete("e1")])],
        # one invalid reply, answered on the retry
        (7, "flat"): ['{"action": "swim", "intent": "", "ops": [], "destination": null}',
                      s.flat("move_left", "west")],
        # two invalid replies: noop, and the ops of the refused reply are dropped
        (9, "flat"): [s.flat("move_left", "west", ops=[s.op_delete("e99")]),
                      s.flat("move_left", "west", ops=[s.op_delete("e99")])],
    }
    script = s.Script({"flat": s.flat("move_right", "east")}, plan)
    cell_dir, summary = _run("flat", FLAT_STEPS, script)
    return cell_dir, summary, script


def _flat_calls():
    return _rows(flat_run()[0], "calls.jsonl")


def test_flat_makes_one_call_a_step_and_names_one_grammar():
    calls = _flat_calls()
    assert [c["round"] for c in calls] == ["flat"] * len(calls)
    per_step = {}
    for call in calls:
        per_step[call["step"]] = per_step.get(call["step"], 0) + 1
    assert per_step == {step: (2 if step in (7, 9) else 1)
                        for step in range(1, FLAT_STEPS + 1)}


def test_b6_8_flats_page_has_the_manual_and_the_list_and_no_event_line_or_ask():
    for call in _flat_calls():
        page = call["prompt"]
        assert pages.list_manual() in page
        assert "\ncurrent list: [" in page
        assert pages.axis_line() in page and pages.command_block("flat") in page
        assert pages.EVENT_NOTE not in page and pages.event_line_stall() not in page
        assert pages.ASK_R1_HEAD not in page


def test_b6_8_flats_destination_block_rides_the_steps_that_hold_one_and_no_other():
    """B §6 checker 8 since the hold: §3.5's block in its held shape on exactly the
    steps that start with a destination held, and never the shapes a step that asked
    would render. The cell names one at step 3, so steps 4 to 14 carry it."""
    holding = set(range(4, FLAT_STEPS + 1))
    for call in _flat_calls():
        page, step = call["prompt"], call["step"]
        assert ("THE DESTINATION YOU CHOSE: [30, 31], named at step 3." in page) is \
            (step in holding), step
        assert "named this step" not in page and "kept this step" not in page
        assert pages.DEST_NULL_HEAD not in page and pages.DEST_DEFAULTED_HEAD not in page
        assert "This is the same window you just read" not in page


def test_flats_destination_is_held_and_its_route_answers_this_page():
    """A §3.2 under the hold: the cell named at step 3 is held from there on — the page
    first shows it at step 4, because the reply came after step 3's page — and the route
    sentence on each of those pages is the way to it from where the body stands then, so
    the row is that step's and not the naming step's."""
    pages_by_step = {c["step"]: c["prompt"] for c in _flat_calls() if c["attempt"] == 1}
    assert _route_lines(pages_by_step[3]) == []
    assert len(_route_lines(pages_by_step[4])) == 1
    rows = [e for e in _rows(flat_run()[0], "events.jsonl") if e["kind"] == "route"]
    assert [r["step"] for r in rows] == list(range(4, FLAT_STEPS + 1))
    # the rows are world axis; the model wrote the shown axis (A §1.1, §4)
    held = [30, constants.WORLD_SIZE - 1 - 31]
    assert all(r["target"] == held for r in rows)
    actions = {r["step"]: r for r in _rows(flat_run()[0], "actions.jsonl")}
    assert actions[3]["destination"] is None
    assert [actions[s]["destination"] for s in range(4, FLAT_STEPS + 1)] == \
        [held] * (FLAT_STEPS - 3)
    assert actions[4]["route_first_step"] == rows[0]["first_step"]
    assert all(a["target"] is None for a in _rows(flat_run()[0], "actions.jsonl"))


def test_flat_applies_deletes_at_once_with_no_confirmation():
    events = _rows(flat_run()[0], "events.jsonl")
    applied = [e for e in events if e["kind"] == "ops_applied"]
    assert [e["step"] for e in applied] == [5]
    assert applied[0]["source"] == "flat"
    assert [e["id"] for e in applied[0]["list_after"]] == ["e2"]      # e1 is gone at once
    assert "delete_confirmed" not in {e["kind"] for e in events}
    assert not [c for c in _flat_calls() if c["round"] == "R1.5"]
    page6 = [c["prompt"] for c in _flat_calls() if c["step"] == 6][0]
    assert "current list: [{\"id\": \"e2\", \"name\": \"find_water\"" in page6


def test_a_refused_flat_reply_is_a_noop_whose_ops_are_dropped():
    events = _rows(flat_run()[0], "events.jsonl")
    step9 = [e for e in events if e["step"] == 9]
    assert [e["kind"] for e in step9 if e["kind"] == "reply_invalid"] == \
        ["reply_invalid"] * 2
    assert [(e["round"], e["default"]) for e in step9 if e["kind"] == "reply_defaulted"] == \
        [("flat", constants.NOOP)]
    assert [e["source"] for e in step9 if e["kind"] == "ops_rejected"] == ["flat", "flat"]
    assert "ops_applied" not in {e["kind"] for e in step9}
    action = [r for r in _rows(flat_run()[0], "actions.jsonl") if r["step"] == 9][0]
    assert action["action"] == constants.NOOP
    # the hold is not dropped with the ops: `null` keeps it, and a reply refused twice
    # named nothing (A §3.4's table for flat)
    assert action["destination"] == [30, constants.WORLD_SIZE - 1 - 31]
    assert not [e for e in step9 if e["kind"].startswith("destination_")]


def test_flats_summary_counts_the_destinations_it_named_and_the_ones_it_chose():
    """A §4.4: flat has both fields since the hold — the replies that named a cell, and
    the rows a new cell wrote. Here one reply named one, so both read 1."""
    assert flat_run()[1]["destinations_named"] == 1
    assert flat_run()[1]["destinations_chosen"] == 1
    assert flat_run()[1]["arm"] == "flat"


def test_flat_writes_no_gate_row_and_no_focus_row():
    kinds = {e["kind"] for e in _rows(flat_run()[0], "events.jsonl")}
    assert not kinds & {"gate_fired", "stall_start", "focus_chosen", "focus_none",
                        "focus_missing", "delete_confirmed", "delete_declined"}


# -- sliced (B §3.7) --------------------------------------------------------

SLICED_STEPS = 14


@functools.lru_cache(maxsize=1)
def sliced_run():
    plan = {
        # the note's gate: delete the one entry, confirm it, and the list empties
        (11, "R1"): [s.r1_ops(s.op_delete("e1")), s.r1_no()],
        (11, "R1.5"): [s.r1_5(True)],
        # the empty list brings R1 again on the next step, with no gate
        (12, "R1"): [s.r1_ops(s.op_add("map_again", "every walkable cell mapped"))],
    }
    defaults = {"R1": s.r1_no(), "R1.5": s.r1_5(False),
                "R3": s.r3(target=(42, 40), do="go toward it"),
                "R4": s.r4("move_right")}
    cell_dir, summary = _run("sliced", SLICED_STEPS, s.Script(defaults, plan))
    return cell_dir, summary


def _sliced_calls():
    return _rows(sliced_run()[0], "calls.jsonl")


def test_sliced_never_runs_r2():
    assert "R2" not in {c["round"] for c in _sliced_calls()}
    kinds = {e["kind"] for e in _rows(sliced_run()[0], "events.jsonl")}
    assert not kinds & {"focus_chosen", "focus_none", "focus_missing"}


def test_b6_10_sliced_acting_pages_carry_the_read_only_list_and_no_manual():
    for call in _sliced_calls():
        if call["round"] not in ("R3", "R4"):
            continue
        page = call["prompt"]
        assert "\ncurrent list (this round you can read it and not change it): " in page
        assert pages.list_manual() not in page
        assert '"op"' not in page
        assert "the one you are on" not in page


def test_b6_10_sliced_uses_focuss_own_r3_and_r4_grammars():
    assert grammars.grammar("R3") and grammars.grammar("R4")
    for call in _sliced_calls():
        assert call["grammar_id"] == call["round"]
    assert trace.ARM_ROUNDS["sliced"] == ("R1", "R1.5", "R3", "R4")


def test_sliceds_r3_ask_points_at_the_list_and_r1_5_is_focuss_own():
    r3 = [c["prompt"] for c in _sliced_calls() if c["round"] == "R3"][0]
    assert pages.ask_r3("sliced") in r3
    r1_5 = [c["prompt"] for c in _sliced_calls() if c["round"] == "R1.5"][0]
    assert pages.ask_r1_5({"id": "e1", "name": "map_world",
                           "until": "every walkable cell mapped"}) in r1_5


def test_an_empty_list_brings_sliceds_own_line_once_a_step():
    by_step = {}
    for call in _sliced_calls():
        if call["round"] == "R1" and call["attempt"] == 1:
            by_step.setdefault(call["step"], []).append(call["prompt"])
    assert sorted(by_step) == [11, 12]
    assert len(by_step[11]) == 2                       # the gated page, then the empty-list one
    assert pages.NO_LIST_EMPTY not in by_step[11][0]
    assert pages.NO_LIST_EMPTY in by_step[11][1]
    assert pages.NO_FOCUS_EMPTY not in by_step[11][1]  # focus's wording is not sliced's
    assert len(by_step[12]) == 1 and pages.NO_LIST_EMPTY in by_step[12][0]
    # once something is on the list again, R1 stops coming
    assert 13 not in by_step


def test_an_empty_list_renders_as_the_empty_list_on_sliceds_acting_pages():
    page = [c["prompt"] for c in _sliced_calls()
            if c["round"] == "R3" and c["step"] == 11][0]
    assert "current list (this round you can read it and not change it): []" in page


# -- B §6, checker 7: the note's line, across the arms ---------------------


def test_b6_7_the_notes_line_is_byte_identical_across_the_arms():
    seen = {}
    for arm, script in (("flat", s.Script({"flat": s.flat("move_right")})),
                        ("focus", s.Script({"R1": s.r1_no(), "R1.5": s.r1_5(False),
                                            "R2": s.r2("e1"), "R3": s.r3(),
                                            "R4": s.r4("move_right")})),
                        ("sliced", s.Script({"R1": s.r1_no(), "R1.5": s.r1_5(False),
                                             "R3": s.r3(), "R4": s.r4("move_right")}))):
        cell_dir, _ = _run(arm, constants.NOTE_STEP + 1, script)
        last = _rows(cell_dir, "calls.jsonl")[-1]["prompt"]
        lines = [ln for ln in last.splitlines() if ln.startswith("step 10: a note")]
        assert len(lines) == 1, arm
        seen[arm] = lines[0]
    assert set(seen.values()) == {NOTE_LINE}
    assert texts.BACKGROUND_TRACE in last          # and the background is every arm's


# -- death ends the cell (A §4.4, §5) --------------------------------------


def test_death_ends_the_cell_where_it_happened_and_says_so():
    """A §5: a cell that dies is still exit 0; A §4.4: `died`, `steps_survived`."""
    script = s.Script({"flat": s.flat("move_up", "north until the drink runs out")})
    cell_dir, summary = _run("flat", 500, script)
    events = _rows(cell_dir, "events.jsonl")
    death = [e for e in events if e["kind"] == "death"]
    assert len(death) == 1
    step = death[0]["step"]
    assert summary["died"] is True and summary["steps_survived"] == step
    assert summary["steps"] == 500, "the budget asked for is still on the record"
    # the cell stops there: no row, frame or call past the step it died on
    assert [f["step"] for f in _rows(cell_dir, "frames.jsonl")] == list(range(0, step + 1))
    assert [a["step"] for a in _rows(cell_dir, "actions.jsonl")] == list(range(1, step + 1))
    assert max(c["step"] for c in _rows(cell_dir, "calls.jsonl")) == step
    assert max(e["step"] for e in events) == step
    # and the drink crossing that killed it is on the record before the death
    crossings = [e for e in events if e["kind"] == "drink_crossing"]
    assert crossings and crossings[0]["step"] < step
    assert crossings[0]["drink_from"] > 0 and crossings[0]["drink_to"] == 0
