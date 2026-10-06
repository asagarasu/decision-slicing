"""One scripted focus cell, 44 steps on `World(7)`, read back from its rows.

The run is `fixtures/focus_run.py`: a fixed action a step, so the gate's steps
do not move, and a plan that once each adds an entry at the note, edits one,
declines a deletion, confirms two, empties the list, chooses, names a target,
and answers invalidly in every round — twice, where a default is wanted.

Every page asserted here is read out of `calls.jsonl`, the logged record of the
pages as sent. Nothing contacts a server.
"""
import functools
import json
import pathlib
import re
import tempfile

from fixtures import focus_run, scripted
from p3focus import cell, constants, grammars, list_store, pages, texts, trace
from p3focus import world as world_mod


@functools.lru_cache(maxsize=1)
def run():
    """The cell, run once for this module: `(dir, summary, script)`."""
    script = focus_run.script()
    client = scripted.ScriptedClient(script)
    out = tempfile.mkdtemp(prefix="p3focus_focus_")
    cell_dir, summary = trace.run_trace_cell("focus", focus_run.SEED, focus_run.STEPS,
                                             client, out, quiet=True)
    return cell_dir, summary, script


def _rows(name):
    path = pathlib.Path(run()[0]) / name
    return [json.loads(line) for line in path.read_text().splitlines()]


def calls():
    return _rows("calls.jsonl")


def events():
    return _rows("events.jsonl")


def _prompts(round_id=None, step=None):
    """Every prompt sent, retries included — what B §6's checkers hold for."""
    return [c["prompt"] for c in calls()
            if (round_id is None or c["round"] == round_id) and (step is None or c["step"] == step)]


def _pages(round_id=None, step=None):
    """One prompt per *occasion*: a retry is the same page with a reason line,
    not a second page (A §3.4)."""
    return [c["prompt"] for c in calls()
            if c["attempt"] == 1
            and (round_id is None or c["round"] == round_id) and (step is None or c["step"] == step)]


def history_of(page):
    """The history block of a page (B §0's second block). The background block
    has a blank line inside it, so the split is on the blocks that bracket it."""
    start = page.index(texts.BACKGROUND_TRACE) + len(texts.BACKGROUND_TRACE) + 2
    end = page.index("HOW TO USE THIS CONSOLE")
    return page[start:end].rstrip("\n")


def _kinds(step=None):
    return [e["kind"] for e in events() if step is None or e["step"] == step]


NOTE_LINE = world_mod.trace_note_line(
    constants.NOTE_STEP, world_mod.errand_note(constants.ERRANDS[focus_run.SEED]))


# -- B §6's checker list, on the pages this run rendered --------------------


def test_b6_1_focus_acting_pages_carry_no_list_no_manual_and_no_op():
    for page in _prompts("R3") + _prompts("R4"):
        assert "current list:" not in page
        assert "THE LIST: what it is" not in page
        assert '"op"' not in page


def test_b6_2_r4s_command_block_and_grammar_have_only_action_and_intent():
    block = pages.command_block("R4")
    assert '"action"' in block and '"intent"' in block and '"ops"' not in block
    r4 = grammars.grammar("R4")
    assert '\\"ops\\"' not in r4 and '\\"action\\"' in r4 and '\\"intent\\"' in r4
    r3 = grammars.grammar("R3")
    for key in ("need", "candidates", "target", "why"):
        assert '\\"%s\\"' % key in r3
    assert '\\"ops\\"' not in r3


def test_b6_3_the_ask_pages_carry_the_manual_and_the_whole_list():
    for round_id in ("R1", "R1.5", "R2"):
        got = _prompts(round_id)
        assert got, round_id
        for page in got:
            assert pages.list_manual() in page
            assert "\ncurrent list: [" in page


def test_b6_4_every_page_carries_the_background_history_manual_and_state_line():
    for call in calls():
        page = call["prompt"]
        assert page.startswith(texts.BACKGROUND_TRACE + "\n\n")
        assert texts.console_manual() in page
        line = [ln for ln in page.splitlines() if ln.startswith("step current: ")]
        assert len(line) == 1
        body = json.loads(line[0][line[0].index("{"):line[0].rindex("}") + 1])
        assert {"window", "player", "standing_on"} <= set(body)


def test_b6_4_history_is_a_block_of_its_own_on_every_page():
    for call in calls():
        block = history_of(call["prompt"])
        lines = block.splitlines()
        assert len(lines) <= constants.K_HISTORY
        assert all(ln.startswith("step ") for ln in lines) or block == texts.FIRST_STEP_LINE


def test_b6_5_the_focus_line_is_on_the_acting_pages_and_on_no_other():
    for call in calls():
        on_page = "\nthe one you are on: " in call["prompt"]
        assert on_page == (call["round"] in ("R3", "R4")), (call["step"], call["round"])


def test_b6_6_the_asks_leave_no_trace_line_and_no_conversation():
    # no ask's text survives into a later page: every page is rebuilt (B §0)
    for page in _prompts("R3") + _prompts("R4"):
        assert pages.ASK_R1_HEAD not in page
        assert pages.ASK_R2_HEAD not in page
    # and history holds one line a step, plus the note's, and nothing else
    history = _last_history()
    assert all(line.startswith("step ") for line in history)


def test_b6_9_r4_runs_every_step_r3_on_its_occasions_and_r2_never_without_an_r1():
    per_step = {}
    for call in calls():
        per_step.setdefault(call["step"], []).append(call["round"])
    assert sorted(per_step) == list(range(1, focus_run.STEPS + 1))
    for step, rounds in per_step.items():
        assert "R4" in rounds, step
        assert ("R3" in rounds) == (step in focus_run.R3_STEPS), (step, rounds)
        if "R2" in rounds:
            assert "R1" in rounds, step
        assert rounds.count("R1") <= 2 * 2, step        # two pages, one retry each
    # the event occasion is exactly "an ask ran this step" (A §3.1)
    for step, rounds in per_step.items():
        if focus_run.R3_STEPS.get(step) == "event":
            assert "R1" in rounds, step
        if "R1" in rounds:
            assert "R3" in rounds, step


def test_b6_11_r3s_page_carries_the_occasions_line_and_r4s_block_says_the_step():
    for step, occasion in focus_run.R3_STEPS.items():
        page = _pages("R3", step=step)[0]
        has_line = any(needle in page for needle in (
            "You are standing on your destination, ", "There is no way over cells you have seen",
            "Your destination until now: "))
        assert has_line == (occasion != "missing"), (step, occasion)
        if occasion == "reached":
            assert "You are standing on your destination, [35, 31], named at step 1." in page
        if occasion == "event" and step == 11:
            assert "Your destination until now: [30, 31], named at step 4" in page
    for call in calls():
        if call["round"] != "R4":
            continue
        page = call["prompt"]
        fresh = call["step"] in focus_run.R3_STEPS
        if "THE DESTINATION YOU CHOSE: none" in page:
            assert fresh, call["step"]
            continue
        named_now = "named this step." in page or ", kept this step." in page
        assert named_now == fresh, call["step"]
        assert ("This is the same window you just read" in page) == fresh, call["step"]
        if not fresh:
            assert re.search(r"THE DESTINATION YOU CHOSE: \[\d+, \d+\], named at step \d+\.", page), call["step"]
    # the kept form, where the plan keeps the held cell at an event (B §3.4, §3.5)
    assert "named at step 11, kept this step." in _pages("R4", step=19)[0]


# -- history (B §1.2), the note, and A, D3 ---------------------------------


def _last_history():
    """The history block of the last page rendered, as lines."""
    return history_of(calls()[-1]["prompt"]).splitlines()


def test_history_never_carries_a_list_line():
    seen = set()
    for call in calls():
        seen.update(history_of(call["prompt"]).splitlines())
    for line in seen:
        assert "current list" not in line and '"op"' not in line
        assert line == texts.FIRST_STEP_LINE or line.startswith("step ")


def test_the_note_is_history_from_step_11_to_15_and_gone_at_16():
    for step in range(1, focus_run.STEPS + 1):
        block = history_of(_pages("R4", step=step)[0])
        assert (NOTE_LINE in block) == (11 <= step <= 15), step


def test_the_first_page_says_nothing_has_happened_yet():
    assert texts.FIRST_STEP_LINE in _pages("R3", step=1)[0]


def test_an_intent_comes_back_in_the_next_steps_history():
    page = _pages("R4", step=4)[0]
    assert 'you took action "move_right" on "step 3", and ' in page


# -- A §4.2's rows ----------------------------------------------------------


def test_ops_in_acting_reply_never_fires():
    assert "ops_in_acting_reply" not in _kinds()


def test_the_note_gates_the_next_steps_r1_and_the_line_is_the_worlds():
    assert {"note_landed", "gate_fired"} <= set(_kinds(constants.NOTE_STEP))
    assert not _pages("R1", step=constants.NOTE_STEP)
    page = _pages("R1", step=constants.NOTE_STEP + 1)[0]
    assert pages.EVENT_NOTE in page
    assert history_of(page).splitlines()[-1] == NOTE_LINE


def test_an_add_writes_ops_applied_and_the_next_page_shows_the_entry():
    applied = [e for e in events() if e["kind"] == "ops_applied" and e["step"] == 11]
    assert len(applied) == 1 and applied[0]["source"] == "R1"
    assert [op["op"] for op in applied[0]["ops"]] == ["add", "edit"]
    assert [e["id"] for e in applied[0]["list_after"]] == ["e1", "e2"]
    assert applied[0]["list_after"][0]["why"] == "the standing task"      # the edit
    assert '"id": "e2"' in _pages("R2", step=11)[0]


def test_an_op_naming_an_unknown_id_rejects_the_whole_reply_and_retries():
    step19 = [e for e in events() if e["step"] == 19]
    invalid = [e for e in step19 if e["kind"] == "reply_invalid" and e["round"] == "R1"]
    assert len(invalid) == 1 and "e99" in invalid[0]["reason"]
    rejected = [e for e in step19 if e["kind"] == "ops_rejected"]
    assert len(rejected) == 1 and rejected[0]["source"] == "R1"
    # nothing was applied from the refused reply, and the retry's ops were
    assert [e["kind"] for e in step19].index("ops_rejected") < \
        [e["kind"] for e in step19].index("ops_applied")
    # the retry carries the reason line on the same page
    r1 = [c for c in calls() if c["step"] == 19 and c["round"] == "R1"]
    assert len(r1) == 2 and r1[1]["attempt"] == 2
    assert r1[1]["prompt"].startswith(r1[0]["prompt"])
    assert r1[1]["prompt"].splitlines()[-1].startswith("your last reply was not accepted:")


def test_a_declined_deletion_keeps_the_entry_and_r1_5_defaults_to_false():
    step19 = [e for e in events() if e["step"] == 19]
    assert [e["kind"] for e in step19].count("reply_invalid") >= 2
    defaulted = [e for e in step19 if e["kind"] == "reply_defaulted"]
    assert [(e["round"], e["default"]) for e in defaulted] == [("R1.5", "false")]
    assert [e["id"] for e in step19 if e["kind"] == "delete_declined"] == ["e1"]
    assert "delete_confirmed" not in _kinds(19)
    assert '"id": "e1"' in _pages("R2", step=19)[-1]


def test_r1_5_shows_the_entry_to_be_deleted_with_the_adds_already_applied():
    page = _pages("R1.5", step=19)[0]
    assert "Your last reply deletes this entry:\n  " + list_store.render_entry(
        {"id": "e1", "name": "map_world", "until": "every walkable cell mapped",
         "why": "the standing task"}) in page
    assert '"id": "e2"' in page          # the add of step 11 is on the list line


def test_two_confirmed_deletions_empty_the_list_and_lose_the_entry_in_force():
    step31 = [e for e in events() if e["step"] == 31]
    assert [e["id"] for e in step31 if e["kind"] == "delete_confirmed"] == ["e1", "e2"]
    assert [e["reason"] for e in step31 if e["kind"] == "focus_missing"] == ["deleted"]
    assert [e["reason"] for e in step31 if e["kind"] == "focus_none"] == ["empty"]
    assert "focus_chosen" not in _kinds(31)          # R2 does not run on an empty list
    assert _pages("R2", step=31) == []


def test_the_second_r1_page_of_a_step_carries_only_the_no_focus_line():
    r1 = _pages("R1", step=31)
    assert len(r1) == 2
    assert pages.event_line_stall() in r1[0] and pages.NO_FOCUS_EMPTY not in r1[0]
    assert pages.NO_FOCUS_EMPTY in r1[1] and pages.event_line_stall() not in r1[1]
    assert "current list: []" in r1[1]


def test_an_empty_list_shows_none_on_the_acting_pages_and_drops_two_phrases():
    r3 = _pages("R3", step=31)[0]
    assert "the one you are on: none" in r3
    body = pages.ask_r3("focus", has_focus=False).split("\n\n", 1)[1]
    assert body in r3 and pages.ASK_R3_HEAD in r3
    assert "the one you are on: none" in _pages("R4", step=31)[0]


def test_an_empty_list_brings_r1_on_a_step_the_gate_did_not_open():
    assert "gate_fired" not in _kinds(31 + 1 - 1) or True   # step 31's gate fired at 30
    assert not [e for e in events() if e["step"] == 31 and e["kind"] == "gate_fired"]
    r1 = _pages("R1", step=32)
    assert len(r1) == 1 and pages.NO_FOCUS_EMPTY in r1[0]
    assert pages.event_line_stall() not in r1[0]
    assert [e["id"] for e in events() if e["step"] == 32 and e["kind"] == "focus_chosen"] == ["e3"]


def test_r2_failing_twice_with_nothing_to_keep_leaves_none_and_says_why():
    step42 = [e for e in events() if e["step"] == 42]
    assert [(e["round"], e["default"]) for e in step42 if e["kind"] == "reply_defaulted"] \
        == [("R2", "none")]
    assert [e["reason"] for e in step42 if e["kind"] == "focus_none"] == ["r2_defaulted"]
    assert "the one you are on: none" in _pages("R3", step=42)[0]
    # the list is not empty, so the next step's R1 opens with the other line
    r1 = _pages("R1", step=43)
    assert len(r1) == 1 and pages.NO_FOCUS_NONE in r1[0]
    assert 'current list: [{"id": "e4"' in r1[0]


def test_r2s_previous_line_names_a_deletion_when_r1_5_took_the_entry_in_force():
    assert pages.previous_line("e3", deleted=True) in _pages("R2", step=42)[0]
    assert pages.previous_line("e2") in _pages("R2", step=19)[-1]
    assert pages.previous_line(None) in _pages("R2", step=43)[0]


def test_r1_failing_twice_defaults_to_no_and_r2_still_follows_it():
    step43 = [e for e in events() if e["step"] == 43]
    assert [(e["round"], e["default"]) for e in step43 if e["kind"] == "reply_defaulted"] \
        == [("R1", "no")]
    assert [e["id"] for e in step43 if e["kind"] == "focus_chosen"] == ["e4"]


def test_the_acting_rounds_take_their_defaults_after_two_invalid_replies():
    step44 = [e for e in events() if e["step"] == 44]
    assert [(e["round"], e["default"]) for e in step44 if e["kind"] == "reply_defaulted"] \
        == [("R3", "target: null"), ("R4", constants.NOOP)]
    assert pages.DEST_DEFAULTED_HEAD in _pages("R4", step=44)[0]   # B §3.5, third shape: refused, not chosen
    action = [r for r in _rows("actions.jsonl") if r["step"] == 44][0]
    assert action["action"] == constants.NOOP and action["target"] is None
    # a defaulted reply has no intent, so its history line carries no clause
    assert action["intent"] == ""
    assert texts.trace_action_line(44, constants.NOOP, "", "waited") == \
        'step 44: you took action "noop", and waited.'




# -- the route hint (A §6) --------------------------------------------------


def test_the_route_row_and_sentence_ride_a_chosen_target_that_is_not_here():
    rows = [e for e in events() if e["kind"] == "route"]
    assert rows, "no route was ever taken"
    for row in rows:
        assert row["sentence_id"] in (1, 2, 3)
        assert row["first_step"] in (None,) + tuple(constants.VERBS)
    step = rows[0]["step"]
    page = _pages("R4", step=step)[0]
    assert "The way there, over cells you have seen" in page or "No way there" in page \
        or "past the cells" in page


def test_no_route_row_when_the_target_is_the_cell_the_body_stands_on():
    for row in _rows("actions.jsonl"):
        if row["target"] is not None and row["target"] == row["pos_before"]:
            assert row["route_first_step"] is None
            assert not [e for e in events()
                        if e["kind"] == "route" and e["step"] == row["step"]]


# -- the files (A §4) -------------------------------------------------------


def test_the_cell_directory_holds_a_4s_six_files():
    names = {p.name for p in pathlib.Path(run()[0]).iterdir()}
    assert names == {"manifest.json", "calls.jsonl", "events.jsonl", "actions.jsonl",
                     "frames.jsonl", "summary.json"}


def test_every_call_row_carries_a_4_1s_keys_and_the_page_it_sent():
    from p3focus import client as client_mod
    for i, call in enumerate(calls(), 1):
        assert set(call) == set(client_mod.CALL_ROW_KEYS)
        assert call["call_no"] == i
        assert call["prefix_sha256"] is None
        assert call["page_sha256"] == client_mod.messages_sha256(
            [{"role": "user", "content": call["prompt"]}])
        assert call["grammar_id"] == call["round"]
        assert call["attempt"] in (1, 2) and call["transport_tries"] == 1


def test_every_action_row_carries_a_4_3s_keys_and_counts_its_calls():
    rows = _rows("actions.jsonl")
    assert [r["step"] for r in rows] == list(range(1, focus_run.STEPS + 1))
    counted = {}
    for call in calls():
        counted[call["step"]] = counted.get(call["step"], 0) + 1
    for row in rows:
        assert set(row) == set(cell.ACTION_KEYS)
        assert row["arm"] == "focus" and row["destination"] is None
        assert row["n_calls"] == counted[row["step"]]
        assert row["moved"] == (row["pos_before"] != row["pos_after"])


def test_frames_are_one_a_step_with_frame_zero_first():
    frames = _rows("frames.jsonl")
    assert [f["step"] for f in frames] == list(range(0, focus_run.STEPS + 1))
    assert frames[0]["schema_version"] == constants.FRAME_SCHEMA_VERSION


def test_the_manifest_copies_every_constant_a_reader_would_guess():
    body = json.loads((pathlib.Path(run()[0]) / "manifest.json").read_text())
    assert body["arm"] == "focus" and body["seed"] == focus_run.SEED
    assert body["note_step"] == constants.NOTE_STEP
    assert body["k_history"] == constants.K_HISTORY
    assert body["stall_length"] == constants.STALL_LENGTH
    assert body["grammar_ids"] == list(trace.ARM_ROUNDS["focus"])
    assert body["errand_cells"] == [list(c) for c in constants.ERRANDS[focus_run.SEED]]
    assert body["server"].startswith("scripted:")


def test_the_summary_counts_the_invalid_and_defaulted_replies_by_round():
    _, summary, _ = run()
    assert summary["defaulted_replies"] == {"R1": 1, "R1.5": 1, "R2": 1, "R3": 1, "R4": 1}
    assert set(summary["invalid_replies"]) == {"R1", "R1.5", "R2", "R3", "R4"}
    assert summary["steps_survived"] == focus_run.STEPS and summary["died"] is False
    assert summary["destinations_named"] is None      # flat's and chat's column
    assert summary["destinations_chosen"] == len(
        [e for e in events() if e["kind"] == "destination_chosen"])
    assert summary["n_calls"] == len(calls())


def test_the_gates_own_rows_reach_events_jsonl_with_its_own_numbers():
    """A §4.2: `stall_start` and `stall_end` are the gate's, and `gate_fired` is
    stamped with the step whose world events opened the asks, one before them."""
    starts = [e for e in events() if e["kind"] == "stall_start"]
    ends = [e for e in events() if e["kind"] == "stall_end"]
    assert starts and ends
    for row in starts:
        assert row["length"] == constants.STALL_LENGTH
        assert row["since_step"] == row["step"] - constants.STALL_LENGTH + 1
    for row in ends:
        assert row["length"] >= constants.STALL_LENGTH
    fired = [e for e in events() if e["kind"] == "gate_fired"]
    assert [e["step"] for e in fired] == [10, 18, 30, 41]
    for row in fired:
        # the asks it opened are on the next step (A §4.2)
        assert _pages("R1", step=row["step"]) == []
        assert _pages("R1", step=row["step"] + 1)
