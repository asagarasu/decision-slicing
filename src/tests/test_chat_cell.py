"""One chat cell, run end to end: A §4's six files and B §7's turns.

The run is `fixtures/chat/walk_s7.jsonl` on `World(7)` — forty-four steps and
forty-five calls, because one step is refused twice and defaults. The fixture is
a body that names a destination, sends `null`, names a cell off the map (retry,
then `noop`), names the cell it is about to stand on (no hint for that one), and
walks south and east onto seed 7's first errand cell on step 19.

The turns are checked twice over: as the conversation holds them, and as
`calls.jsonl` logged them — B §6's checker asks about the page "as sent on its
own step", and the log is what a reader will have.
"""
import json
import pathlib

import pytest

from p3focus import axis, cell, chat, client, constants, route, state

DESIGN = pathlib.Path(__file__).resolve().parents[2] / "design"
FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "chat" / "walk_s7.jsonl"

SEED, STEPS = 7, 44
#: the fixture's own landmarks, asserted against the file in the guard below
RETRIED_STEP = 3                 # two off-map destinations, then the `noop` default
OWN_CELL_STEP = 5                # names the cell it will be standing on next turn
NOTE_TURN = constants.NOTE_STEP + 1                       # B §7: the turn after it lands
ARRIVAL_STEP = 19
ROUTE_TURNS = (2, 20)            # steps 1 and 19 named a cell somewhere else


def _lines():
    return FIXTURE.read_text().splitlines()


def _policy(lines):
    """A §5's `--policy scripted:`, as a policy: the file's replies, verbatim,
    in call order. A retry therefore reads the next line, which is how the
    fixture can refuse twice."""
    replies = iter(lines)
    return lambda messages: next(replies)


def _rows(path):
    return [json.loads(line) for line in pathlib.Path(path).read_text().splitlines()]


@pytest.fixture(scope="module")
def run(tmp_path_factory):
    """The one run every test in this file reads."""
    out = tmp_path_factory.mktemp("chat_cell")
    return chat.run_chat_cell(SEED, STEPS, client.ScriptedClient(_policy(_lines())), out,
                              quiet=True)


@pytest.fixture(scope="module")
def turns(run):
    """The user turns as they were sent, step 1 first."""
    return [t["user"]["content"] for t in run.conversation.turns]


def _a_note_line():
    """The note's line as A §1.1 quotes it for seed 7, shown axis."""
    for line in (DESIGN / "interfaces.md").read_text().split("\n"):
        if line.strip().startswith("step 10: a note from your human player arrived:"):
            return line.strip()
    raise AssertionError("A §1.1 no longer quotes the note's line")


# -- a guard on the fixture ----------------------------------------------------

def test_the_fixture_is_the_run_these_tests_say_it_is():
    """If the fixture is edited the claims below stop meaning what they say."""
    lines = _lines()
    assert len(lines) == STEPS + 1                       # one step is called twice
    replies = [json.loads(line) for line in lines]
    assert replies[0]["destination"] == [42, 23]         # shown; world [42, 40]
    assert replies[1]["destination"] is None
    assert replies[2]["destination"] == [64, 23] and replies[3]["destination"] == [42, -1]
    assert replies[5]["destination"] == [32, 27]         # shown; world [32, 36]
    assert replies[19]["destination"] == [22, 39]        # shown; world [22, 24]
    assert {r["action"] for r in replies} <= set(constants.VERBS)
    assert all(isinstance(r["why"], str) for r in replies)


# -- the cell's files (A §4) ---------------------------------------------------

def test_a_4_names_six_files_and_the_run_wrote_all_six(run):
    assert run.dir.name.startswith("chat_s7_")
    assert sorted(p.name for p in run.dir.iterdir()) == [
        "actions.jsonl", "calls.jsonl", "events.jsonl", "frames.jsonl",
        "manifest.json", "summary.json"]


def test_frames_are_one_per_step_with_frame_0_first(run):
    frames = _rows(run.dir / "frames.jsonl")
    assert [f["step"] for f in frames] == list(range(0, STEPS + 1))
    assert all(f["schema_version"] == constants.FRAME_SCHEMA_VERSION for f in frames)
    assert all("standing_on" in f for f in frames)


def test_the_manifest_says_which_arm_and_which_grammar_ran(run):
    body = json.loads((run.dir / "manifest.json").read_text())
    assert body["arm"] == "chat" and body["seed"] == SEED and body["steps"] == STEPS
    assert body["grammar_ids"] == ["chat"]
    assert body["chat_budget_tokens"] == constants.CHAT_BUDGET_TOKENS
    assert body["chat_keep_turns"] == constants.CHAT_KEEP_TURNS
    assert body["model"] == "scripted"                   # what this client reports


# -- calls.jsonl (A §4.1) ------------------------------------------------------

def test_one_call_row_per_call_with_a_4_1s_keys_and_nothing_else(run):
    rows = _rows(run.dir / "calls.jsonl")
    assert len(rows) == STEPS + 1
    assert [r["call_no"] for r in rows] == list(range(1, STEPS + 2))
    for row in rows:
        assert set(row) == set(client.CALL_ROW_KEYS)
        assert row["round"] == "chat" and row["grammar_id"] == "chat"
        assert row["transport_tries"] == 1               # no transport failure in a scripted run


def test_a_chat_row_hashes_the_prefix_and_leaves_the_page_hash_null(run):
    """A §4.1: `page_sha256` is the trace arms', `prefix_sha256` is chat's — the
    cache-hit check over every message before the newest turn."""
    rows = _rows(run.dir / "calls.jsonl")
    assert all(r["page_sha256"] is None for r in rows)
    assert all(len(r["prefix_sha256"]) == 64 for r in rows)
    # at the first call the prefix is exactly the system message
    assert rows[0]["prefix_sha256"] == client.messages_sha256(
        [{"role": "system", "content": chat.system_message()}])
    assert len({r["prefix_sha256"] for r in rows}) == len(rows)


def test_a_chat_rows_prompt_is_the_new_user_turn_and_not_the_conversation(run, turns):
    """A §4.1: chat's `prompt` is the new user turn only."""
    rows = _rows(run.dir / "calls.jsonl")
    firsts = [r for r in rows if r["attempt"] == 1]
    assert [r["prompt"] for r in firsts] == turns
    assert all(chat.system_message() not in r["prompt"] for r in rows)


def test_the_retried_step_has_two_rows_and_the_second_prompt_is_the_reason(run):
    rows = [r for r in _rows(run.dir / "calls.jsonl") if r["step"] == RETRIED_STEP]
    assert [r["attempt"] for r in rows] == [1, 2]
    assert [r["valid"] for r in rows] == [False, False]
    assert all("off the map" in r["reason"] for r in rows)
    assert rows[0]["parsed"]["destination"] == [64, 23]  # the object is logged, refused
    assert rows[1]["prompt"] == chat.RETRY_LINE.format(reason=rows[0]["reason"])


def test_every_other_reply_was_accepted_on_its_first_attempt(run):
    rows = _rows(run.dir / "calls.jsonl")
    assert [r["step"] for r in rows if not r["valid"]] == [RETRIED_STEP, RETRIED_STEP]
    assert all(r["reason"] is None for r in rows if r["valid"])
    assert [r["step"] for r in rows if r["attempt"] == 2] == [RETRIED_STEP]


def test_a_calls_step_is_the_world_step_it_serves_not_the_frame_it_read(run, turns):
    """A §4.1's `step`: turn N renders frame N−1 and its action produces frame N,
    so the row says N and the state JSON in its prompt says N−1."""
    for row in _rows(run.dir / "calls.jsonl"):
        if row["attempt"] != 1:
            continue
        assert json.loads(row["prompt"].split("\n")[-1])["step"] == row["step"] - 1


# -- the turns (B §7) ----------------------------------------------------------

def test_there_is_one_turn_per_step(run, turns):
    assert len(turns) == STEPS
    assert [t["step"] for t in run.conversation.turns] == list(range(1, STEPS + 1))


def test_the_axis_line_and_the_state_json_close_every_turn(turns):
    from p3focus import texts
    for turn in turns:
        lines = turn.split("\n")
        assert lines[-2] == texts.AXIS_LINE
        assert json.loads(lines[-1])                     # the state JSON is the last line


def test_every_turn_as_sent_carries_b_6s_three_state_keys(run):
    """B §6, checker 4, on the pages a reader will have: `window`, `player`,
    `standing_on` in the state JSON of every turn as it was sent."""
    for row in _rows(run.dir / "calls.jsonl"):
        if row["attempt"] != 1:
            continue
        body = json.loads(row["prompt"].split("\n")[-1])
        assert {"window", "player", "standing_on"} <= set(body)
        assert len(body["window"]) == 10 and body["window"][0].startswith("x=") and all(r.startswith("y=") for r in body["window"][1:])


def test_the_first_turn_reports_no_outcome_and_every_later_one_reports_the_last_step(run, turns):
    actions = _rows(run.dir / "actions.jsonl")
    assert not turns[0].startswith("outcome of your last action:")
    for step in range(2, STEPS + 1):
        previous = actions[step - 2]
        if previous["action"] == constants.NOOP:
            said = "waited"
        else:
            assert previous["moved"], step
            said = "moved to " + json.dumps(axis.shown_pos(previous["pos_after"]))
        assert turns[step - 1].split("\n")[0].startswith(f"outcome of your last action: {said}")   # a pickup clause may follow (A §1.3)


def test_the_turn_after_a_defaulted_reply_says_waited(turns):
    assert turns[RETRIED_STEP].split("\n")[0] == "outcome of your last action: waited"


def test_the_note_rides_one_turn_and_it_is_the_step_11_turn(run, turns):
    carrying = [i + 1 for i, t in enumerate(turns) if "a note from your human player" in t]
    assert carrying == [NOTE_TURN]
    lines = turns[NOTE_TURN - 1].split("\n")
    assert lines[1] == run.world.note_line
    assert lines[1] == _a_note_line()                    # A §1.1's bytes, shown axis
    assert lines[1].startswith(f"step {constants.NOTE_STEP}: ")


def test_the_route_line_rides_the_turn_after_a_destination_and_no_other(turns):
    forms = [s.split("{verb}")[0] for s in route.SENTENCES]
    carrying = [i + 1 for i, t in enumerate(turns)
                if any(line.startswith(tuple(forms)) for line in t.split("\n"))]
    assert carrying == list(ROUTE_TURNS)


def test_a_destination_the_body_is_already_standing_on_gets_no_line_and_no_row(run, turns):
    """A §4.2: nothing to route, and the old line's "No way there" for that case
    was untrue. Step 5 named the cell step 5 walked onto."""
    actions = _rows(run.dir / "actions.jsonl")
    named = actions[OWN_CELL_STEP - 1]["destination"]
    assert named == actions[OWN_CELL_STEP - 1]["pos_after"]      # world axis, both
    after = turns[OWN_CELL_STEP].split("\n")
    assert after[0].startswith("outcome of your last action:")
    assert len(after) == 4   # outcome, carrying, axis line, state
    assert OWN_CELL_STEP + 1 not in [r["step"] for r in _rows(run.dir / "events.jsonl")
                                     if r["kind"] == "route"]


def test_no_turn_carries_a_list_a_manual_or_a_history_block(turns):
    """B §4: chat has no list. The conversation is its history, so no page of it
    holds trace lines."""
    for turn in turns:
        assert "current list:" not in turn and "the one you are on:" not in turn
        assert "THE LIST" not in turn and '"op"' not in turn
        assert "you took action" not in turn


# -- events.jsonl (A §4.2) -----------------------------------------------------

def test_the_events_of_this_run_are_the_world_s_the_route_s_and_the_controller_s(run):
    rows = _rows(run.dir / "events.jsonl")
    assert sorted({r["kind"] for r in rows}) == [
        "arrival", "note_landed", "reply_defaulted", "reply_invalid", "route"]
    for kind in ("gate_fired", "stall_start", "focus_chosen", "ops_applied",
                 "conversation_trimmed", "death"):
        assert kind not in {r["kind"] for r in rows}, kind


def test_the_note_landed_row_is_stamped_the_step_its_world_step_produced(run):
    rows = [r for r in _rows(run.dir / "events.jsonl") if r["kind"] == "note_landed"]
    assert rows == [{"step": constants.NOTE_STEP, "kind": "note_landed"}]


def test_the_arrival_row_is_the_world_s_and_names_the_cell_in_the_world_axis(run):
    rows = [r for r in _rows(run.dir / "events.jsonl") if r["kind"] == "arrival"]
    assert rows == [{"step": ARRIVAL_STEP, "kind": "arrival", "cell": [42, 40], "index": 0}]
    assert constants.ERRANDS[SEED][0] == (42, 40)
    assert run.world.errands_reached == {0: ARRIVAL_STEP}


def test_a_route_row_per_route_line_with_the_target_in_the_world_axis(run):
    rows = [r for r in _rows(run.dir / "events.jsonl") if r["kind"] == "route"]
    assert [r["step"] for r in rows] == list(ROUTE_TURNS)
    assert [r["target"] for r in rows] == [[42, 40], [22, 24]]
    assert all(r["sentence_id"] in (1, 2, 3) for r in rows)
    assert all(r["first_step"] in route.MOVE_VERBS or r["first_step"] is None for r in rows)
    assert set(rows[0]) == {"step", "kind", "target", "first_step", "sentence_id"}


def test_the_refused_step_left_two_invalid_rows_and_one_defaulted_row(run):
    rows = [r for r in _rows(run.dir / "events.jsonl")
            if r["kind"] in ("reply_invalid", "reply_defaulted")]
    assert [(r["step"], r["kind"], r.get("attempt")) for r in rows] == [
        (RETRIED_STEP, "reply_invalid", 1),
        (RETRIED_STEP, "reply_invalid", 2),
        (RETRIED_STEP, "reply_defaulted", None)]
    assert rows[-1]["default"] == constants.NOOP
    assert all(r["round"] == "chat" for r in rows)


# -- actions.jsonl (A §4.3) ----------------------------------------------------

def test_one_action_row_per_world_step_with_a_4_3s_keys(run):
    rows = _rows(run.dir / "actions.jsonl")
    assert len(rows) == STEPS
    assert [r["step"] for r in rows] == list(range(1, STEPS + 1))
    for row in rows:
        assert set(row) == set(cell.ACTION_KEYS)
        assert row["arm"] == "chat"
        assert row["focus_id"] is None and row["target"] is None    # chat has no list, no R3
        assert row["list_size"] == 0


def test_the_intent_of_a_chat_row_is_the_replys_why(run):
    rows = _rows(run.dir / "actions.jsonl")
    replies = [json.loads(line) for line in _lines()]
    # call order -> step order: the retried step consumed two replies and used neither
    accepted = replies[:RETRIED_STEP - 1] + [None] + replies[RETRIED_STEP + 1:]
    for row, reply in zip(rows, accepted):
        if reply is None:
            assert row["action"] == constants.NOOP and row["intent"] == ""
        else:
            assert row["action"] == reply["action"] and row["intent"] == reply["why"]


def test_a_named_destination_is_logged_in_the_world_axis(run):
    rows = _rows(run.dir / "actions.jsonl")
    named = {r["step"]: r["destination"] for r in rows if r["destination"] is not None}
    assert named == {1: [42, 40], OWN_CELL_STEP: [32, 36], ARRIVAL_STEP: [22, 24]}
    for step, world_cell in named.items():
        shown = json.loads(_lines()[step - 1 if step < RETRIED_STEP else step])["destination"]
        assert axis.shown_pos(shown) == world_cell        # the involution, both ways


def test_the_route_first_step_of_a_row_is_the_hint_that_rode_that_steps_turn(run):
    actions = {r["step"]: r["route_first_step"] for r in _rows(run.dir / "actions.jsonl")}
    hints = {r["step"]: r["first_step"] for r in _rows(run.dir / "events.jsonl")
             if r["kind"] == "route"}
    assert {s: v for s, v in actions.items() if v is not None} == hints
    assert set(hints) == set(ROUTE_TURNS)


def test_the_positions_and_meters_of_a_row_are_the_two_frames_it_sits_between(run):
    frames = {f["step"]: f for f in _rows(run.dir / "frames.jsonl")}
    for row in _rows(run.dir / "actions.jsonl"):
        before, after = frames[row["step"] - 1], frames[row["step"]]
        assert row["pos_before"] == before["player"]["pos"]
        assert row["pos_after"] == after["player"]["pos"]
        assert row["moved"] == (row["pos_after"] != row["pos_before"])
        assert row["standing_on_after"] == after["standing_on"]
        assert row["drink_after"] == after["player"]["drink"]
        assert row["health_after"] == after["player"]["health"]


def test_the_refused_step_counted_two_calls_and_acted_noop(run):
    row = _rows(run.dir / "actions.jsonl")[RETRIED_STEP - 1]
    assert row["action"] == constants.NOOP and row["n_calls"] == 2
    assert row["destination"] is None and row["moved"] is False
    assert [r["n_calls"] for r in _rows(run.dir / "actions.jsonl")].count(2) == 1


# -- summary.json (A §4.4) -----------------------------------------------------

def test_the_summary_is_a_4_4s_keys_for_an_arm_with_no_list(run):
    body = json.loads((run.dir / "summary.json").read_text())
    assert body == run.summary
    assert set(body) == {"errands_completed", "cells_reached", "steps_survived", "died",
                         "first_errand_step", "note_to_first_errand_steps", "after_errands",
                         "invalid_replies", "defaulted_replies", "destinations_named",
                         "n_calls", "wall_s"}
    assert "focus_is_errand_fraction" not in body        # A §4.4: focus only


def test_the_summary_counts_this_run(run):
    body = run.summary
    assert body["steps_survived"] == STEPS and body["died"] is False
    assert body["cells_reached"] == 1 and body["errands_completed"] is False
    assert body["first_errand_step"] == ARRIVAL_STEP
    assert body["note_to_first_errand_steps"] == ARRIVAL_STEP - constants.NOTE_STEP
    assert body["after_errands"] is None                 # the return was never reached
    assert body["invalid_replies"] == {"chat": 2}
    assert body["defaulted_replies"] == {"chat": 1}
    assert body["destinations_named"] == 3               # a refused reply names nothing
    assert body["n_calls"] == STEPS + 1


# -- the conversation this run left (A §3.3) -----------------------------------

def test_the_conversation_is_the_system_message_and_two_messages_a_step(run):
    messages = run.conversation.messages
    assert messages[0]["content"] == chat.system_message()
    assert len(messages) == 1 + 2 * STEPS + 2            # +2 for the refused step's pair
    assert [len(t["members"]) for t in run.conversation.turns].count(4) == 1
    assert {len(t["members"]) for t in run.conversation.turns} == {2, 4}


def test_a_run_this_long_never_reaches_the_budget(run):
    assert run.conversation.est_tokens() < constants.CHAT_BUDGET_TOKENS
    assert all(t["window_omitted"] is False for t in run.conversation.turns)


def test_every_reply_is_in_the_conversation_verbatim(run):
    said = [m["content"] for m in run.conversation.messages if m["role"] == "assistant"]
    assert said == _lines()


# -- trimming, on a budget small enough to bite (A §3.3, B §7) -----------------

def test_a_small_budget_omits_windows_oldest_first_then_drops_whole_turns(tmp_path, monkeypatch):
    """The newest `CHAT_KEEP_TURNS` turns keep their windows, the system message
    is never touched, and every `conversation_trimmed` row names the turn it
    dropped. The budget here is the system message's own size, so every step
    past turn 20 has to give one turn up."""
    monkeypatch.setattr(constants, "CHAT_BUDGET_TOKENS",
                        chat.estimate_tokens([{"content": chat.system_message()}]))
    run = chat.run_chat_cell(SEED, STEPS, client.ScriptedClient(_policy(_lines())), tmp_path,
                             quiet=True)
    keep = constants.CHAT_KEEP_TURNS
    conv = run.conversation
    assert conv.messages[0]["content"] == chat.system_message()
    assert [t["step"] for t in conv.turns] == list(range(STEPS - keep + 1, STEPS + 1))
    for turn in conv.turns:
        assert turn["window_omitted"] is False
        assert len(json.loads(turn["user"]["content"].split("\n")[-1])["window"]) == 10
    rows = [r for r in _rows(run.dir / "events.jsonl") if r["kind"] == "conversation_trimmed"]
    assert [r["step"] for r in rows] == list(range(keep + 1, STEPS + 1))
    assert [r["dropped_turns"] for r in rows] == [[s] for s in range(1, STEPS - keep + 1)]
    assert set(rows[0]) == {"step", "kind", "dropped_turns", "windows_omitted"}


def test_the_first_trim_omits_a_window_and_drops_nothing(tmp_path, monkeypatch):
    """The two passes are in order at the run level too: a budget that one
    omitted window is enough for logs a `conversation_trimmed` row whose
    `dropped_turns` is empty, and the turn that lost its window is the oldest."""
    keep = constants.CHAT_KEEP_TURNS
    steps = keep + 1
    measured = chat.run_chat_cell(SEED, steps, client.ScriptedClient(_policy(_lines())),
                                  tmp_path / "measure", quiet=True).conversation
    measured.turns[0]["user"]["content"] = chat.omit_window(measured.turns[0]["user"]["content"])
    monkeypatch.setattr(constants, "CHAT_BUDGET_TOKENS", measured.est_tokens())

    run = chat.run_chat_cell(SEED, steps, client.ScriptedClient(_policy(_lines())),
                             tmp_path / "trimmed", quiet=True)
    rows = [r for r in _rows(run.dir / "events.jsonl") if r["kind"] == "conversation_trimmed"]
    assert [(r["step"], r["dropped_turns"]) for r in rows] == [(steps, [])]
    assert [t["step"] for t in run.conversation.turns] == list(range(1, steps + 1))
    assert [t["window_omitted"] for t in run.conversation.turns] == [True] + [False] * keep


def test_trimming_changes_nothing_about_the_pages_that_were_sent(tmp_path, monkeypatch):
    """A trimmed run's `calls.jsonl` is a byte-for-byte record of the turns as
    they were sent: trimming edits the conversation, never the log."""
    monkeypatch.setattr(constants, "CHAT_BUDGET_TOKENS",
                        chat.estimate_tokens([{"content": chat.system_message()}]))
    run = chat.run_chat_cell(SEED, 24, client.ScriptedClient(_policy(_lines())), tmp_path,
                             quiet=True)
    prompts = [r["prompt"] for r in _rows(run.dir / "calls.jsonl") if r["attempt"] == 1]
    assert len(prompts) == 24
    assert all(chat.OMITTED_WINDOW not in p for p in prompts)


# -- death ends the cell (A §5) ------------------------------------------------

def test_death_ends_the_cell_on_the_step_it_happens(tmp_path, monkeypatch):
    """A §5: exit 0 on completion, death included. The world this run uses dies
    on step 6, so there is no seventh frame, no seventh action row and no
    seventh turn however many steps were asked for."""
    from p3focus.world import World

    class DiesAtSix(World):
        def step(self, verb):
            frame, said, events = super().step(verb)
            if int(frame["step"]) == 6:
                frame["player"]["health"] = 0
                self.died = True
                events = list(events) + [{"step": 6, "kind": "death"}]
            return frame, said, events

    monkeypatch.setattr(chat, "World", DiesAtSix)
    run = chat.run_chat_cell(SEED, STEPS, client.ScriptedClient(_policy(_lines())), tmp_path,
                             quiet=True)
    assert run.summary["died"] is True and run.summary["steps_survived"] == 6
    assert len(_rows(run.dir / "actions.jsonl")) == 6
    assert [f["step"] for f in _rows(run.dir / "frames.jsonl")] == list(range(0, 7))
    assert len(run.conversation.turns) == 6
    assert {"step": 6, "kind": "death"} in _rows(run.dir / "events.jsonl")


# -- the state JSON a chat turn carries is B §5's object (A §1.3) --------------

def test_a_turns_state_is_what_state_render_state_makes_of_that_frame(run, turns):
    """The page reads a `State`, never the frame (A §1.3). A fresh `World(7)` at
    reset is the same frame 0 and the same seen set, so turn 1's last line can be
    checked to the byte against what `state.render_state` makes of it."""
    from p3focus.world import World
    fresh = World(SEED)
    frame0 = fresh.reset()
    assert turns[0].split("\n")[-1] == state.dumps(
        state.render_state(frame0, fresh.mapped_bits(frame0)))
    body = json.loads(turns[0].split("\n")[-1])
    assert body["player"]["pos"] == axis.shown_pos(frame0["player"]["pos"])
    assert body["step"] == 0                             # turn 1 renders frame 0
