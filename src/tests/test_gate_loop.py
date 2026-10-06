"""The gate driven step by step, which is what A §6 asks for: tested through a
loop, not only as a pure function.

An earlier stall predicate was a pure function of a window its *caller*
kept, and its pure-function test handed it unlimited history. So when the loop's
window turned out to be one count short of what the crossing reads, the gate
tapped the body on every stalled step, and the test said nothing. Here the
window belongs to `Gate`,
so there is no unlimited history to hand it; these tests script seventy steps of
seen counts and world events, feed them in order, and read every step's answer.
`test_the_buggy_window_taps_on_every_stalled_step` runs the buggy width on the
same script and says exactly what it costs.
"""
import collections

from p3focus import constants
from p3focus.gate import STALL, WORLD_GATE_KINDS, Gate

N = constants.STALL_LENGTH


def _counts():
    """The seen set's size after each step, step 0 first: a walk, a twenty-step
    stall, a seven-step pause one short of a stall, a second stall, and a walk
    out. The sizes are plausible rather than real — it is the shape of the
    growth the gate reads, and nothing else."""
    counts, count = [], 25
    def walk(n):
        nonlocal count
        for _ in range(n):
            count += 1
            counts.append(count)
    def still(n):
        for _ in range(n):
            counts.append(count)
    still(1)    # step 0      the reset frame: the 9x9 around spawn
    walk(9)     # steps 1-9   new ground on every step
    still(20)   # steps 10-29 the twenty-step stall
    walk(1)     # step 30     it ends
    still(7)    # steps 31-37 the seven-step pause
    walk(1)     # step 38
    still(22)   # steps 39-60 the second stall
    walk(1)     # step 61     it ends
    walk(8)     # steps 62-69
    return counts


COUNTS = _counts()

#: The world's events per step, as `events.jsonl` rows (A §4.2). Steps 33, 50
#: and 69 carry rows that are not the gate's: two of the world's own and two
#: another piece writes, all of which it must ignore.
EVENTS = {
    10: [{"kind": "note_landed"}],
    17: [{"kind": "arrival", "cell": [42, 40], "index": 0, "first": True}],
    22: [{"kind": "arrival", "cell": [22, 24], "index": 1, "first": True},
         {"kind": "drink_crossing", "drink_from": 1, "drink_to": 0,
          "health_from": 9, "health_to": 9}],
    33: [{"kind": "arrival", "cell": [32, 32], "index": 2, "first": True},
         {"kind": "errands_completed"}],
    45: [{"kind": "drink_crossing", "drink_from": 0, "drink_to": 0,
          "health_from": 9, "health_to": 8}],
    50: [{"kind": "focus_chosen", "id": "e1"},
         {"kind": "route", "target": [40, 20], "first_step": "move_up",
          "sentence": "Your target is nine cells up."}],
    69: [{"kind": "death"}],
}

#: What each of those steps should fire. Every other step fires nothing.
FIRES = {
    10: {"note_landed"},
    17: {"arrival", STALL},
    22: {"arrival", "drink_crossing"},
    33: {"arrival"},
    45: {"drink_crossing"},
    46: {STALL},
}


def drive(gate=None):
    """One `Gate` over the scripted run, one `observe` per step, in order.
    Returns the gate and the fired set of every step."""
    gate = gate or Gate()
    return gate, {step: gate.observe(step, count, EVENTS.get(step, ()))
                  for step, count in enumerate(COUNTS)}


def test_the_script_is_the_run_these_tests_say_it_is():
    """A guard on the fixture: if the counts are edited the claims below stop
    meaning what they say."""
    assert len(COUNTS) == 70
    assert COUNTS[9] > COUNTS[8]                          # growth right up to step 9
    assert len(set(COUNTS[10:30])) == 1 and len(COUNTS[10:30]) == 20
    assert COUNTS[30] > COUNTS[29]                        # the stall ends
    assert len(set(COUNTS[31:38])) == 1 and len(COUNTS[31:38]) == N - 1
    assert COUNTS[38] > COUNTS[37]                        # the pause ends
    assert len(set(COUNTS[39:61])) == 1 and len(COUNTS[39:61]) == 22
    assert COUNTS[61] > COUNTS[60]


def test_every_step_fires_exactly_what_it_should():
    _, fires = drive()
    for step in range(len(COUNTS)):
        assert fires[step] == FIRES.get(step, set()), step


def test_a_twenty_step_stall_fires_once():
    _, fires = drive()
    assert [s for s in range(10, 30) if STALL in fires[s]] == [17]


def test_a_seven_step_pause_never_fires_and_is_never_bracketed():
    gate, fires = drive()
    assert all(STALL not in fires[s] for s in range(31, 39))
    # no stall row either: a pause that never became a stall is not bracketed.
    # Step 33's arrival still opens an ask, which is the point of checking the
    # stall rows and not the step's rows.
    assert not [r for r in gate.rows
                if 31 <= r["step"] <= 38 and r["kind"].startswith("stall_")]


def test_a_second_stall_after_the_set_grows_fires_again():
    _, fires = drive()
    assert [s for s in range(39, 61) if STALL in fires[s]] == [46]


def test_a_stall_that_starts_at_step_zero_is_handled():
    """Step 0 is the reset frame, and the gate has nothing before it to compare
    against — so step 0 is the baseline and the stall's still steps are 1
    through 8. It fires on step 8 and not again, which is also where the window
    of commit 3e1a822's bug would have begun tapping every step."""
    gate = Gate()
    assert [step for step in range(40) if STALL in gate.observe(step, 25)] == [N]
    assert gate.rows == [
        {"step": N, "kind": "stall_start", "since_step": 1, "length": N},
        {"step": N, "kind": "gate_fired", "events": [STALL]},
    ]


def test_a_world_event_fires_on_the_step_it_arrives_and_never_again():
    _, fires = drive()
    for kind in WORLD_GATE_KINDS:
        scripted = {s for s, evs in EVENTS.items()
                    if any(e["kind"] == kind for e in evs)}
        assert {s for s, f in fires.items() if kind in f} == scripted, kind


def test_the_kinds_outside_the_four_ride_along_without_opening_it():
    _, fires = drive()
    assert fires[33] == {"arrival"}   # errands_completed came with the return
    assert fires[50] == set()         # focus_chosen and route are other pieces'
    assert fires[69] == set()         # death


def test_stall_start_and_stall_end_bracket_each_stall():
    gate, _ = drive()
    assert [r for r in gate.rows if r["kind"] != "gate_fired"] == [
        {"step": 17, "kind": "stall_start", "since_step": 10, "length": N},
        {"step": 30, "kind": "stall_end", "since_step": 10, "length": 20},
        {"step": 46, "kind": "stall_start", "since_step": 39, "length": N},
        {"step": 61, "kind": "stall_end", "since_step": 39, "length": 22},
    ]


def test_one_gate_fired_row_per_firing_step_in_the_page_s_order():
    gate, _ = drive()
    assert [r for r in gate.rows if r["kind"] == "gate_fired"] == [
        {"step": 10, "kind": "gate_fired", "events": ["note_landed"]},
        {"step": 17, "kind": "gate_fired", "events": ["arrival", STALL]},
        {"step": 22, "kind": "gate_fired", "events": ["arrival", "drink_crossing"]},
        {"step": 33, "kind": "gate_fired", "events": ["arrival"]},
        {"step": 45, "kind": "gate_fired", "events": ["drink_crossing"]},
        {"step": 46, "kind": "gate_fired", "events": [STALL]},
    ]


def test_the_rows_of_a_step_are_that_step_s_alone():
    """A controller writing `events.jsonl` as it goes reads `last_rows`; `rows`
    is the whole cell's, in the order they were written."""
    gate, seen = Gate(), []
    for step, count in enumerate(COUNTS):
        gate.observe(step, count, EVENTS.get(step, ()))
        assert all(r["step"] == step for r in gate.last_rows), step
        seen.extend(gate.last_rows)
    assert seen == gate.rows
    assert gate.last_rows == []   # step 69 fired nothing
    assert len(gate.rows) == 10   # six gate_fired, two stall_start, two stall_end


def test_the_buggy_window_taps_on_every_stalled_step():
    """Commit 3e1a822, run on this script. With a window as long as the stall
    the crossing's earlier comparison has no count to read, `still_before` can
    never be true, and both stalls tap on every one of their steps instead of
    once — twenty-eight asks where there should be two. This is the test the old
    line did not have."""
    gate = Gate()
    gate._counts = collections.deque(maxlen=constants.STALL_LENGTH)
    _, fires = drive(gate)
    tapped = [s for s in range(len(COUNTS)) if STALL in fires[s]]
    assert tapped == list(range(17, 30)) + list(range(46, 61))
    assert len(tapped) == 28
