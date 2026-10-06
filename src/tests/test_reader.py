"""What the reader makes of a cell's rows (A §4, A §4.4, A §1.1).

Every number asserted here is a hand count off the fixture in
`fixtures/reader/cells.py`, whose five cells are written by `p3focus.cell`'s own
writers and whose walks, meters and rows are small enough to count. The one
quantity a hand cannot count — the seen set — is checked against a second
implementation written in this file, over the fixture's material map, sharing
no code with the reader.

One test reads a cell the harness really ran (`_real_cell`), and skips where
that directory is not in the checkout.
"""
import json
import os
import sys
from pathlib import Path

import pytest

# the fixture builder, `src/tests/fixtures/reader/cells.py`. Not imported as
# `tests.fixtures.reader.cells`: an unrelated `tests` package is installed in
# the venv and shadows `src/tests`.
sys.path.insert(0, str(Path(__file__).parent / "fixtures" / "reader"))
import cells  # noqa: E402

from p3focus import constants, reader  # noqa: E402

#: the walkable names, written out here rather than read from the reader, so
#: the second count below is a second opinion and not an echo
WALKABLE_NAMES = ("grass", "path", "sand", "water")

#: A cell the harness really ran on 09-24, with the hold: the one place these
#: tests meet rows no fixture wrote. Under the repo root in a full checkout;
#: `P3_REAL_CELL` names it elsewhere, and a worktree finds the main tree beside
#: it, whose `generated/` is the one that has it.
REAL_CELL_NAME = "generated/check_pages_99/focus_s7_20260924T094623"


def _real_cell():
    """The real cell's directory, or None when this checkout has not got it."""
    root = Path(__file__).resolve().parents[2]
    named = os.environ.get("P3_REAL_CELL")
    candidates = ([Path(named)] if named else []) + [
        root / REAL_CELL_NAME, root.parent / "p3_focus" / REAL_CELL_NAME]
    return next((c for c in candidates if (c / "manifest.json").exists()), None)


@pytest.fixture(scope="session")
def made(tmp_path_factory):
    """The five fixture cells, written once."""
    return cells.write_all(tmp_path_factory.mktemp("cells"))


@pytest.fixture(scope="session")
def read(made):
    """`{name: read_cell(...)}` for the five."""
    return {name: reader.read_cell(path) for name, path in made.items()}


# --- the summary, field by field, against a hand count --------------------------

def test_the_completed_focus_cell_s_summary_is_the_hand_count(read):
    """focus, seed 7, 102 steps: ten at the spawn, the note at 10, errand 0 at
    28, errand 1 at 64, the return at 82, twenty steps after it."""
    s = read["focus_s7_completed"]
    assert s["arm"] == "focus" and s["seed"] == 7
    assert s["errands_completed"] is True
    assert s["cells_reached"] == 3
    assert s["steps_survived"] == 102
    assert s["died"] is False
    assert s["first_errand_step"] == 28
    assert s["note_step"] == 10
    assert s["note_to_first_errand_steps"] == 18
    # R2 was invalid once and then defaulted at 29; R3 was invalid once at 30
    assert s["invalid_replies"] == {"R2": 1, "R3": 1}
    assert s["defaulted_replies"] == {"R2": 1}
    # 102 steps × R4 + the 11 steps R3 was asked on (A §3.1: not every step)
    # + 7 gated steps × (R1, R2) + 3 R1.5 (one delete at 83, two at 101)
    # + 2 second attempts = 102 + 11 + 14 + 3 + 2
    assert s["n_calls"] == 132
    assert s["retries"] == 2
    assert s["destinations_named"] == 0      # a focus row holds a target, not a destination
    assert s["destinations_chosen"] == 8


def test_the_flat_cell_that_died_counts_its_death_its_destinations_and_its_retry(read):
    s = read["flat_s10_died"]
    assert s["arm"] == "flat" and s["seed"] == 10
    assert s["died"] is True
    assert s["steps_survived"] == 30
    assert s["errands_completed"] is False
    assert s["cells_reached"] == 0
    assert s["first_errand_step"] is None and s["note_to_first_errand_steps"] is None
    assert s["destinations_named"] == 2
    assert s["invalid_replies"] == {"flat": 1} and s["defaulted_replies"] == {}
    assert s["n_calls"] == 31 and s["retries"] == 1     # one call a step, and one second try
    assert s["after_errands"] is None


def test_standing_on_the_return_cell_before_the_visits_is_not_an_arrival(read, made):
    """The flat body stands on [32, 32] at step 20 — seed 10's return cell — with
    neither visit made. A §1.1: the return counts only after both, and the rows
    and the reader's own derivation agree that nothing happened there."""
    rows = [json.loads(l) for l in
            (made["flat_s10_died"] / "frames.jsonl").read_text().splitlines()]
    assert rows[20]["player"]["pos"] == [32, 32]
    s = read["flat_s10_died"]
    assert s["cells_reached"] == 0
    assert s["ledger_check"]["derived"] == [] and s["ledger_check"]["agrees"] is True


def test_the_focus_numbers_are_the_focus_arm_s_and_nobody_else_s(read):
    s = read["focus_s7_completed"]
    # e2 was in force from 11 to 82 (72 steps) and e4 on the last step: 73 of 102
    assert s["focus_is_errand_steps"] == 73
    assert s["focus_is_errand_fraction"] == pytest.approx(73 / 102)
    assert s["focus_none_steps"] == 1                     # step 101, the list empty
    assert s["focus_switches"] == 5                       # e1 e2 e3 e1 none e4
    for field in ("focus_is_errand_fraction", "focus_none_steps", "focus_switches"):
        assert read["flat_s10_died"][field] is None
        assert read["flat_s7_ledger"][field] is None
        # sliced holds a destination and keeps no focus (A §3.1: focus without
        # R2), so the focus counts are as empty there as on a bare arm
        assert read["sliced_s11_holds"][field] is None


# --- the errand-entry rule (R1) -------------------------------------------------

@pytest.mark.parametrize("entry", [
    {"name": "stand on [42, 23] for the pickaxe"},          # the cell, and a word
    {"name": "go somewhere", "why": "my human asked"},      # a word in `why`
    {"name": "wait", "until": "I hold the rope"},           # a word in `until`
    {"name": "wait", "when": "I next pass [22, 39]"},       # a cell in `when`
    {"name": "come to me at [32, 31]"},                     # the return, and the phrase
    {"name": "the PICKAXE at [42,23]"},                     # case, and no space after the comma
])
def test_an_entry_that_carries_the_note_is_an_errand_entry(entry):
    assert reader.errand_matches(entry, 7)


@pytest.mark.parametrize("entry", [
    {"name": "map_world", "until": "every walkable cell mapped"},   # A §2's dawn entry
    {"name": "walk the shore at [10, 10]", "until": "every cell of it is mapped"},
    {"name": "stand on 42, 23"},                    # two numbers are not a cell
    {"name": "stand on [23, 42]"},                  # the same numbers, the other way round
    {"name": "find water", "why": "my drink is low"},
    {"name": "go to [42, 40]"},                     # the WORLD axis: not what the note said
])
def test_an_entry_that_does_not_is_not(entry):
    assert reader.errand_matches(entry, 7) == []


def test_the_rule_reads_the_seed_s_own_cells(read):
    """Seed 10's note names [14, 33]; seed 7's does not, and the same words
    decide both. The shown axis is the note's, so the rule is written in it."""
    rope = {"name": "fetch the rope at [14, 33]"}
    assert reader.errand_matches(rope, 10) == ["[14, 33]", "rope"]
    assert reader.errand_matches({"name": "stand on [14, 33]"}, 7) == []
    assert reader.errand_cells_shown(7) == ["[42, 23]", "[22, 39]", "[32, 31]"]


def test_the_rule_reports_what_matched_so_a_reading_can_be_audited(read):
    e2 = {e["id"]: e for e in read["focus_s7_completed"]["list_events"]}["e2"]
    assert e2["matched"] == ["[42, 23]", "pickaxe", "human"]


# --- the list, and how long an errand stays on it (R2) --------------------------

def test_each_entry_s_span_comes_from_the_ops_rows(read):
    by_id = {e["id"]: e for e in read["focus_s7_completed"]["list_events"]}
    assert sorted(by_id) == ["e1", "e2", "e3", "e4"]
    # the dawn entry: on the list from step 0, though no op ever added it
    assert by_id["e1"]["seeded"] is True
    assert (by_id["e1"]["added_step"], by_id["e1"]["removed_step"]) == (0, 101)
    assert by_id["e1"]["steps_on_list"] == 101 and by_id["e1"]["is_errand"] is False
    # the errand: added at 11, deleted at 83 — 72 steps on the list
    assert by_id["e2"]["seeded"] is False
    assert (by_id["e2"]["added_step"], by_id["e2"]["removed_step"]) == (11, 83)
    assert by_id["e2"]["steps_on_list"] == 72 and by_id["e2"]["is_errand"] is True
    # a motive the body made itself, and never an errand
    assert (by_id["e3"]["added_step"], by_id["e3"]["removed_step"]) == (65, 101)
    assert by_id["e3"]["is_errand"] is False
    # added on the last step and still there: a span of nothing
    assert (by_id["e4"]["added_step"], by_id["e4"]["removed_step"]) == (102, None)
    assert by_id["e4"]["steps_on_list"] == 0 and by_id["e4"]["is_errand"] is True


def test_a_cell_with_no_ops_row_still_has_the_dawn_entry(read):
    """flat, seed 7, 28 steps, and the body never touched its list. The rows
    carry no snapshot at all, so the reader falls back to A §2's dawn."""
    entries = read["flat_s7_ledger"]["list_events"]
    assert [e["id"] for e in entries] == ["e1"]
    assert entries[0]["name"] == "map_world" and entries[0]["seeded"] is True
    assert entries[0]["steps_on_list"] == 28 and entries[0]["is_errand"] is False


def test_the_map_task_deleted_on_the_first_ask_is_still_on_the_list_until_then(tmp_path):
    """A body that drops the map task at its first maintenance round leaves it
    in no snapshot at all — the first `list_after` shows only what replaced it.
    A §2 says what was there, so the reader says it too: on the list from step 0,
    gone at 11. Without this the plan's "did it go back to the map" question has
    no entry to ask about."""
    errand = {"id": "e2", "name": "stand on [42, 23] for the pickaxe", "until": "I have it"}
    path = cells.write_cell(
        tmp_path / "flat_drops_map", arm="flat", seed=7, legs=[("move_right", 16)],
        ops_rows=[(11, "flat", [{"op": "delete", "id": "e1"},
                                {"op": "add", "name": errand["name"],
                                 "until": errand["until"]}], [errand])])
    by_id = {e["id"]: e for e in reader.read_cell(path)["list_events"]}
    assert by_id["e1"]["seeded"] is True and by_id["e1"]["name"] == "map_world"
    assert (by_id["e1"]["added_step"], by_id["e1"]["removed_step"]) == (0, 11)
    assert by_id["e1"]["steps_on_list"] == 11
    assert (by_id["e2"]["added_step"], by_id["e2"]["removed_step"]) == (11, None)


def test_an_entry_edited_away_from_the_errand_still_counted_while_it_stood(tmp_path):
    """R1 over every version of an entry, not only the last: an entry that named
    the pickaxe for four steps and was then edited into a walk was an errand
    entry for those four, and the reader says so rather than losing it."""
    errand = {"id": "e2", "name": "stand on [42, 23] for the pickaxe",
              "until": "I have it"}
    walk = {"id": "e2", "name": "walk east", "until": "the shore"}
    dawn = cells.MAP_ENTRY
    path = cells.write_cell(
        tmp_path / "flat_edit", arm="flat", seed=7,
        legs=[("move_right", 16)],
        ops_rows=[(11, "flat", [{"op": "add", "name": errand["name"],
                                 "until": errand["until"]}], [dawn, errand]),
                  (15, "flat", [{"op": "edit", "id": "e2", "name": walk["name"],
                                 "until": walk["until"]}], [dawn, walk])])
    e2 = {e["id"]: e for e in reader.read_cell(path)["list_events"]}["e2"]
    assert e2["is_errand"] is True and e2["matched"] == ["[42, 23]", "pickaxe"]
    assert e2["name"] == "walk east"          # the last version's words
    assert e2["added_step"] == 11 and e2["removed_step"] is None


# --- the ledger, from positions (A §1.1) ----------------------------------------

def test_the_ledger_check_agrees_when_the_rows_are_the_world_s(read):
    check = read["focus_s7_completed"]["ledger_check"]
    assert check["agrees"] is True and check["differences"] == []
    assert check["derived"] == check["logged"]
    assert [r["step"] for r in check["derived"]] == [28, 64, 82]
    assert [r["cell"] for r in check["derived"]] == [[42, 40], [22, 24], [32, 32]]
    assert check["errands_completed_derived"] is check["errands_completed_logged"] is True
    assert check["manifest_errand_cells_agree"] is True
    assert check["note_step"] == 10


def test_the_ledger_check_catches_a_planted_wrong_arrival(read):
    """The body really stands on errand 0 at step 28 and no row says so; a row
    claims errand 1 at step 15, where the body was at [37, 32]. The summary
    fields still read the rows — `cells_reached` is 1 and `first_errand_step`
    is 15 — and the check is what says the rows are wrong (A §1.1: from
    positions, never instead)."""
    s = read["flat_s7_ledger"]
    assert s["cells_reached"] == 1 and s["first_errand_step"] == 15
    check = s["ledger_check"]
    assert check["agrees"] is False
    assert check["differences"] == [
        {"kind": "missing_in_events", "index": 0, "frames_step": 28, "events_step": None},
        {"kind": "missing_in_frames", "index": 1, "frames_step": None, "events_step": 15},
    ]


def test_an_arrival_row_without_first_reads_like_one_with_it(read, made):
    """`cell.EVENT_FIELDS` gives `arrival` a `first`; `world._arrivals` writes the
    row without one. The planted row here has no `first` and is read anyway."""
    rows = [json.loads(l) for l in
            (made["flat_s7_ledger"] / "events.jsonl").read_text().splitlines()]
    arrival = [r for r in rows if r["kind"] == "arrival"][0]
    assert "first" not in arrival
    assert read["flat_s7_ledger"]["ledger_check"]["logged"] == [
        {"index": 1, "cell": [22, 24], "step": 15}]


def test_a_step_mismatch_is_its_own_difference(tmp_path):
    """The same arrival, the right cell, the wrong step."""
    path = cells.write_cell(
        tmp_path / "flat_late", arm="flat", seed=7,
        legs=[("move_right", 10), ("move_down", 8), ("move_right", 2)],
        arrivals=[{"step": 19, "kind": "arrival", "cell": [42, 40], "index": 0}])
    check = reader.read_cell(path)["ledger_check"]
    assert check["agrees"] is False
    assert check["differences"] == [
        {"kind": "step_mismatch", "index": 0, "frames_step": 18, "events_step": 19}]


def test_a_completion_the_positions_do_not_support_is_a_difference(tmp_path):
    """An `errands_completed` row on a cell whose body reached nothing."""
    path = cells.write_cell(
        tmp_path / "flat_liar", arm="flat", seed=7, legs=[("move_right", 12)],
        arrivals=[{"step": 12, "kind": "errands_completed"}])
    s = reader.read_cell(path)
    assert s["errands_completed"] is True          # the row says so
    assert {"kind": "completed_mismatch", "frames": False, "events": True} \
        in s["ledger_check"]["differences"]


# --- after the errands (A §4.4) -------------------------------------------------

def test_after_errands_counts_the_steps_the_new_cells_and_what_was_in_force(read):
    """Twenty steps after the return, walked due north up a column the body had
    not been in: each one puts a fresh row of nine cells in the window, so 180.
    What was in force on them: her indicator for whether the body went back to
    the map after the errand (A §4.4)."""
    after = read["focus_s7_completed"]["after_errands"]
    assert after["completed_step"] == 82
    assert after["steps"] == 20
    assert after["new_cells"] == 180
    assert after["focus_ids"] == {"errand": 1, "map_world": 1, "other": 17, "none": 1}
    assert sum(after["focus_ids"].values()) == after["steps"]


def test_after_errands_is_nothing_at_all_when_the_errands_were_not_finished(read):
    assert read["flat_s10_died"]["after_errands"] is None
    assert read["focus_s10_disagrees"]["after_errands"] is None


# --- the hold: the episodes (R5) and R3's asks (R6) -----------------------------

def episode_tuples(summary):
    """The episodes as `(cell, step, end_step, end, held_steps)`, in order."""
    return [(e["cell"], e["step"], e["end_step"], e["end"], e["held_steps"])
            for e in summary["destination_episodes"]]


def test_every_destination_the_body_held_is_an_episode_with_its_end(read):
    """Eight destinations over the completed cell's 102 steps, and all five of
    A §3.1's ends: reached four times, replaced when an event named another
    cell, dropped when an event answered null, cleared where the route hint
    found no way into the stone block, and the last one still held at 102."""
    assert episode_tuples(read["focus_s7_completed"]) == [
        ([42, 32], 1, 21, "reached", 20),
        ([42, 40], 21, 29, "reached", 8),
        ([22, 40], 30, 49, "reached", 19),
        ([20, 24], 49, 65, "replaced", 16),
        ([22, 32], 65, 73, "reached", 8),
        ([10, 10], 73, 83, "dropped", 10),
        ([45, 31], 84, 90, "no_way", 6),
        ([32, 12], 90, 102, "open", 13),
    ]
    assert read["focus_s7_completed"]["destinations_chosen"] == 8


def test_a_closed_episode_s_held_steps_is_the_row_s_own_and_an_open_one_s_is_one_more(read):
    """R5's two forms. A closed episode's `held_steps` comes off the
    `destination_reached` or `destination_cleared` row, and equals
    `end_step - step` because a hold ends at the START of its step; an open one
    has no such row, so it counts the naming step and every step since, the
    cell's last one included — one more than the closed form."""
    for name in ("focus_s7_completed", "focus_s10_disagrees", "sliced_s11_holds"):
        summary = read[name]
        for episode in summary["destination_episodes"]:
            span = episode["end_step"] - episode["step"]
            if episode["end"] == "open":
                assert episode["end_step"] == summary["steps_survived"]
                assert episode["held_steps"] == span + 1
            else:
                assert episode["held_steps"] == span
    open_ones = [e for e in read["focus_s7_completed"]["destination_episodes"]
                 if e["end"] == "open"]
    assert [e["held_steps"] for e in open_ones] == [13]      # 102 - 90 + 1


def test_steps_per_destination_is_the_mean_over_every_episode_the_open_one_too(read):
    # 20 + 8 + 19 + 16 + 8 + 10 + 6 + 13 = 100 over eight
    assert read["focus_s7_completed"]["steps_per_destination"] == 12.5
    # 9 + 1 + 10 + 2 = 22 over four
    assert read["sliced_s11_holds"]["steps_per_destination"] == 5.5
    assert read["flat_s10_died"]["steps_per_destination"] is None


def test_r3_is_asked_on_occasions_and_each_ask_is_counted_by_its_own(read):
    """Eleven asks on the completed cell — steps 1, 11, 21, 29, 30, 49, 65, 73,
    83, 84, 90 — and R6's four occasions between them: four reached, one no
    way, three events (11, 65, 83) and three missing (1, 30, 84). Step 29 both
    reached the held cell and ran the gate's asks, and R6's order reads it
    reached; step 30 asks because 29's answer left nothing held."""
    s = read["focus_s7_completed"]
    assert s["r3_asks"] == 11
    assert s["r3_occasions"] == {"reached": 4, "no_way": 1, "event": 3, "missing": 3}
    assert sum(s["r3_occasions"].values()) == s["r3_asks"]
    # R6 counts asks, not calls: step 30's R3 was refused once and sent again,
    # and the second attempt is the same ask
    r3_calls = [json.loads(l) for l in
                (Path(s["cell_dir"]) / "calls.jsonl").read_text().splitlines()]
    assert len([r for r in r3_calls if r["round"] == "R3"]) == 12
    assert s["retries"] == 2


def test_the_sliced_arm_holds_a_destination_like_focus_and_asks_like_it(read):
    """The third arm, which has no R2 and no focus: the hold reads the same."""
    s = read["sliced_s11_holds"]
    assert s["arm"] == "sliced"
    assert episode_tuples(s) == [
        ([41, 32], 1, 10, "reached", 9),
        ([41, 40], 10, 11, "replaced", 1),
        ([38, 40], 11, 21, "reached", 10),
        ([10, 10], 21, 22, "open", 2),
    ]
    assert s["destinations_chosen"] == 4
    assert s["r3_asks"] == 4
    assert s["r3_occasions"] == {"missing": 1, "reached": 2, "event": 1}


def test_a_cell_whose_rows_hold_nothing_has_no_episodes_no_asks_and_no_mean(read):
    """A cell whose rows carry no hold at all reads 0, [] and None — a fact of
    the rows, not a gate on the arm. These two are flat cells from before the
    hold (A §7 D9, 09-25); their `destinations_named` still counts, because it
    is the replies that named a cell and comes from `calls.jsonl`."""
    for name in ("flat_s10_died", "flat_s7_ledger"):
        s = read[name]
        assert s["destinations_chosen"] == 0
        assert s["destination_episodes"] == []
        assert s["steps_per_destination"] is None
        assert s["r3_asks"] == 0 and s["r3_occasions"] == {}
    assert read["flat_s10_died"]["destinations_named"] == 2


def test_an_end_row_with_no_choice_before_it_is_not_an_episode(tmp_path):
    """A `destination_cleared` for a cell no row ever chose. R5 pairs a closing
    row with the earliest episode open for its cell, and there is none, so the
    reader reports the one episode the rows do support rather than inventing a
    second."""
    path = cells.write_cell(
        tmp_path / "focus_stray", arm="focus", seed=7, legs=[("move_right", 6)],
        r3_plan=[(1, "missing", [38, 32])])
    stray = {"step": 3, "kind": "destination_cleared", "cell": [11, 11],
             "held_steps": 2, "reason": "dropped"}
    with (path / "events.jsonl").open("a") as out:
        out.write(json.dumps(stray, sort_keys=True) + "\n")
    s = reader.read_cell(path)
    assert episode_tuples(s) == [([38, 32], 1, 6, "open", 6)]
    assert s["destinations_chosen"] == 1


def test_the_same_cell_chosen_twice_is_two_episodes(tmp_path):
    """R5's pairing rule where it bites: a cell held, dropped and named again.
    Each closing row closes the earliest episode still open for its cell."""
    path = cells.write_cell(
        tmp_path / "focus_twice", arm="focus", seed=7, legs=[("move_right", 8)],
        gated=(5,),
        r3_plan=[(1, "missing", [40, 32]), (5, "event", None), (6, "missing", [40, 32])])
    assert episode_tuples(reader.read_cell(path)) == [
        ([40, 32], 1, 5, "dropped", 4),
        ([40, 32], 6, 8, "open", 3),
    ]


# --- the seen set (R3) ----------------------------------------------------------

def a_second_count_of_the_seen_set(positions):
    """D2's own rule over the fixture's material map: every walkable cell in the
    9×9 around every cell the body stood on. This shares no code with the
    reader, which reads names out of the windows instead."""
    out = set()
    r = constants.WINDOW // 2
    for px, py in positions:
        for x in range(px - r, px + r + 1):
            for y in range(py - r, py + r + 1):
                if 0 <= x < constants.WORLD_SIZE and 0 <= y < constants.WORLD_SIZE:
                    if cells.material_at(x, y) in WALKABLE_NAMES:
                        out.add((x, y))
    return out


def test_the_seen_set_off_the_windows_is_the_world_s_rule_but_for_the_cow(made):
    """R3's one documented lag: the window draws the cow over the grass under
    her, so the reader cannot count that cell, and the fixture's cow never moves
    off it. Every other cell agrees with the rule read off the map."""
    frames = [json.loads(l) for l in
              (made["focus_s7_completed"] / "frames.jsonl").read_text().splitlines()]
    positions = [tuple(f["player"]["pos"]) for f in frames]
    _, seen = reader.seen_growth(frames)
    second = a_second_count_of_the_seen_set(positions)
    assert cells.COW in second and cells.material_at(*cells.COW) == "grass"
    assert seen == second - {cells.COW}


def test_the_reader_s_walkable_names_are_the_world_s():
    """The reader keeps its own copy so that reading a log needs no Crafter;
    this is the test that says the copy is the same set."""
    from p3focus import world
    assert reader.WALKABLE == world.WALKABLE


@pytest.mark.parametrize("seed", [7, 11])
def test_the_seen_set_off_real_windows_is_the_world_s_but_for_a_hidden_cell(seed):
    """The only check here that meets the real world: a body walked 120 steps
    through Crafter, and the set the reader reads out of the logged windows is
    compared with the set the world grew off its own material map (A §6, D2).

    The reader's set is never larger — it cannot invent a cell — and where it is
    smaller, an object stood on the cell in every window that showed it. On
    these two walks that is one cell of 782 (seed 11, a cow that did not move).
    """
    from p3focus import world
    w = world.World(seed)
    frames = [w.reset()]
    for verb in (["move_right"] * 10 + ["move_down"] * 10
                 + ["move_left"] * 10 + ["move_up"] * 10) * 3:
        frames.append(w.step(verb)[0])
    _, seen = reader.seen_growth(frames)
    assert seen <= w.seen                       # never a cell the world has not got
    hidden = w.seen - seen
    for cell in hidden:
        names = {f["window"][cell[1] - f["player"]["pos"][1] + 4]
                 [cell[0] - f["player"]["pos"][0] + 4]
                 for f in frames
                 if abs(cell[0] - f["player"]["pos"][0]) <= 4
                 and abs(cell[1] - f["player"]["pos"][1]) <= 4}
        assert not (names & reader.WALKABLE), f"{cell} showed {names} and was still missed"
    assert len(hidden) <= 1


def test_the_seen_set_counts_water_and_does_not_count_stone(made):
    """Water is walkable on this line (A §1.1) and is in the set; stone is not,
    and the block the body passes stays out of it."""
    frames = [json.loads(l) for l in
              (made["focus_s7_completed"] / "frames.jsonl").read_text().splitlines()]
    _, seen = reader.seen_growth(frames)
    assert (39, 40) in seen and cells.material_at(39, 40) == "water"
    assert (45, 31) not in seen and cells.material_at(45, 31) == "stone"


# --- the cell's own summary.json (never believed) -------------------------------

def test_a_summary_json_that_agrees_with_the_rows_reports_nothing(read):
    for name in ("focus_s7_completed", "flat_s10_died", "sliced_s11_holds"):
        assert read[name]["summary_json_present"] is True
        assert read[name]["summary_disagreements"] == []


def test_a_summary_json_that_disagrees_is_reported_field_by_field(read):
    """25 quiet steps, and a file that claims a finished run."""
    s = read["focus_s10_disagrees"]
    by_field = {d["field"]: d for d in s["summary_disagreements"]}
    assert by_field["errands_completed"] == {
        "field": "errands_completed", "rows": False, "summary_json": True}
    assert by_field["cells_reached"] == {"field": "cells_reached", "rows": 0,
                                         "summary_json": 2}
    assert by_field["steps_survived"]["rows"] == 25
    assert by_field["n_calls"] == {"field": "n_calls", "rows": 30, "summary_json": 40}
    assert by_field["focus_is_errand_fraction"]["rows"] == 0.0
    # the file claims five destinations chosen and the rows carry two
    assert by_field["destinations_chosen"] == {"field": "destinations_chosen",
                                               "rows": 2, "summary_json": 5}
    assert set(by_field) == {
        "errands_completed", "cells_reached", "steps_survived", "first_errand_step",
        "note_to_first_errand_steps", "after_errands", "invalid_replies",
        "defaulted_replies", "focus_is_errand_fraction", "destinations_chosen",
        "n_calls"}
    # what the file got right is not reported, and `wall_s` is never judged.
    # `destinations_named` is the file's null against the reader's 0 rows, which
    # A §4.4 makes the same claim about a focus cell (`NULL_IS_ZERO_FIELDS`)
    assert "died" not in by_field and "destinations_named" not in by_field
    assert s["destinations_named"] == 0
    assert "wall_s" not in by_field


def test_a_null_count_the_field_does_not_apply_to_agrees_with_no_rows_at_all(tmp_path):
    """A §4.4 gates `destinations_named` to (flat, chat) and
    `destinations_chosen` to (focus, sliced), and the harness writes null for
    the arm each does not apply to. The reader counts rows for every arm and
    finds none. The two readings are the same claim, and only for these two
    fields: a null anywhere else is still a disagreement, and so is a null
    against a count that is not 0.
    """
    def disagreements(name, **summary):
        path = cells.write_cell(
            tmp_path / name, arm="flat", seed=7, legs=[("move_right", 4)],
            destinations={2: [40, 40]},
            summary={"errands_completed": False, "cells_reached": 0, **summary})
        return {d["field"]: d for d in reader.read_cell(path)["summary_disagreements"]}

    # the field flat does not have, written null; the reader has 0 rows of it
    assert disagreements("held_null", destinations_chosen=None) == {}
    assert "destinations_named" not in disagreements("named_one", destinations_named=1)
    # a null beside a count that is not 0 is still two readings
    assert disagreements("named_null", destinations_named=None)["destinations_named"] == {
        "field": "destinations_named", "rows": 1, "summary_json": None}
    # and no other field is loosened: this one really is 0 in the rows
    assert disagreements("reached_null", cells_reached=None)["cells_reached"] == {
        "field": "cells_reached", "rows": 0, "summary_json": None}


def test_no_summary_json_is_not_a_disagreement(read):
    s = read["flat_s7_ledger"]
    assert s["summary_json_present"] is False
    assert s["summary_disagreements"] == []


# --- the cell directory ---------------------------------------------------------

def test_the_arm_and_the_seed_come_from_the_manifest_not_from_the_name(made, tmp_path):
    """A cell directory renamed to something else reads exactly the same."""
    import shutil
    other = tmp_path / "not_a_cell_name_at_all"
    shutil.copytree(made["focus_s7_completed"], other)
    s = reader.read_cell(other)
    assert (s["arm"], s["seed"]) == ("focus", 7)
    assert s["steps_survived"] == 102


def test_a_directory_without_a_manifest_says_which_file_is_missing(tmp_path):
    (tmp_path / "bare").mkdir()
    with pytest.raises(FileNotFoundError, match="manifest.json"):
        reader.read_cell(tmp_path / "bare")


def test_a_cell_with_a_manifest_and_nothing_else_reads_as_a_cell_that_did_nothing(tmp_path):
    """A run the driver killed before its first frame. Every count is 0 or None
    — not an error, and not a measurement either: `focus_is_errand_fraction` is
    None rather than 0.0, because no step happened to hold anything."""
    from p3focus import cell as cellmod
    empty = tmp_path / "focus_s7_killed"
    empty.mkdir()
    cellmod.write_manifest(empty / "manifest.json", arm="focus", seed=7, steps=400,
                           server="s", model="m", grammar_ids=[])
    s = reader.read_cell(empty)
    assert (s["steps_survived"], s["cells_reached"], s["n_calls"]) == (0, 0, 0)
    assert s["errands_completed"] is False and s["died"] is False
    assert s["focus_is_errand_fraction"] is None and s["after_errands"] is None
    assert s["ledger_check"]["agrees"] is True and s["ledger_check"]["derived"] == []
    assert reader.table([s]).splitlines()[-1] == "- focus: 0/1 cells completed the errands"
    assert len(reader.trajectory(empty).splitlines()) > constants.WORLD_SIZE


def test_a_row_that_will_not_parse_names_its_file_and_its_line(made, tmp_path):
    import shutil
    other = tmp_path / "broken"
    shutil.copytree(made["flat_s10_died"], other)
    lines = (other / "events.jsonl").read_text().splitlines()
    lines.insert(2, "{not json")
    (other / "events.jsonl").write_text("\n".join(lines) + "\n")
    with pytest.raises(ValueError, match=r"events\.jsonl:3"):
        reader.read_cell(other)


def test_a_line_separator_inside_a_string_does_not_end_the_row(made, tmp_path):
    """JSON takes U+2028 raw inside a string, and a model's reply can carry one;
    `str.splitlines` ends a line there, which would cut the row in two and leave
    neither half JSON. Written raw (`ensure_ascii=False`), the row reads back as
    the row it was."""
    import shutil
    other = tmp_path / "separator"
    shutil.copytree(made["flat_s10_died"], other)
    path = other / "calls.jsonl"
    rows = [json.loads(line) for line in path.read_text().split("\n") if line.strip()]
    rows[0]["reply_text"] = '{"why": "east of the lake\u2028then south"}'
    path.write_text("".join(json.dumps(r, sort_keys=True, ensure_ascii=False) + "\n"
                            for r in rows))
    assert "\u2028" in path.read_text()          # the character itself, not its escape
    assert reader.Cell(other).calls == rows


def test_every_number_in_the_summary_survives_a_round_trip_through_json(read):
    for s in read.values():
        assert json.loads(json.dumps(s)) == s


# --- one cell the harness really ran --------------------------------------------

@pytest.mark.skipif(_real_cell() is None, reason=f"{REAL_CELL_NAME} is not in this checkout")
def test_a_real_focus_cell_s_hold_reads_as_the_rows_the_harness_wrote():
    """44 steps of the 09-24 check run, the first cell with the hold in it.
    Three destinations: one reached at step 4, one replaced at the note's asks
    at 11, one dropped at 43 after 32 steps of walking toward errand 0.

    The number of asks is where the brief for this change and its own rule
    disagree, and the rule wins: `calls.jsonl` carries eleven rows of round R3,
    two of which are second attempts — the same ask sent again with a reason
    line (A §3.4) — so this cell asked **nine** times. Both counts are pinned
    here so either reading is auditable from the test.
    """
    cell_dir = _real_cell()
    s = reader.read_cell(cell_dir)
    assert s["arm"] == "focus" and s["steps_survived"] == 44
    assert s["destinations_chosen"] == 3
    assert episode_tuples(s) == [
        ([35, 32], 1, 4, "reached", 3),
        ([30, 32], 4, 11, "replaced", 7),
        ([42, 40], 11, 43, "dropped", 32),
    ]
    assert [e["end"] for e in s["destination_episodes"]] == ["reached", "replaced", "dropped"]
    assert s["steps_per_destination"] == pytest.approx((3 + 7 + 32) / 3)
    r3 = [json.loads(l) for l in (cell_dir / "calls.jsonl").read_text().splitlines()
          if json.loads(l)["round"] == "R3"]
    assert len(r3) == 11 and sum(1 for r in r3 if r["attempt"] == 2) == 2
    assert s["r3_asks"] == 9
    # steps 1 and 44 held nothing, step 4 stood on the held cell, and the other
    # six asks were steps whose gate had opened R1 (11, 19, 31, 32, 42, 43)
    assert s["r3_occasions"] == {"missing": 2, "reached": 1, "event": 6}
    assert sum(s["r3_occasions"].values()) == s["r3_asks"]
    # the summary the harness wrote agrees on `destinations_chosen`, and its
    # null for `destinations_named`, which a focus cell has not got, is not a
    # disagreement. The one left is older than this change and untouched by it:
    # `trace.summary` writes `focus_is_errand_fraction` null on purpose (A §4.4:
    # "by a reader's rule, not the harness's") and the reader computes 0.5, so
    # every real focus cell reports that one field. Pinned here to say so.
    assert s["destinations_named"] == 0
    assert [d["field"] for d in s["summary_disagreements"]] == ["focus_is_errand_fraction"]
