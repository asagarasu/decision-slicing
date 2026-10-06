"""The gate's parts (A §6, A §4.2): which kinds open it, what its rows say, and
the window an earlier implementation had to widen.

The stall is driven step by step in `test_gate_loop.py`, which is what A §6 means
by tested through a loop. Even here the window is the gate's own — there is no
way to hand it more history than a run would — which is the difference from an
earlier pure-function test.
"""
import inspect

import pytest

from p3focus import constants
from p3focus.gate import GATE_KINDS, STALL, WORLD_GATE_KINDS, Gate, opening_kinds

N = constants.STALL_LENGTH


def row(kind, **fields):
    """One `events.jsonl` row, as the world writes it (A §4.2)."""
    return dict(kind=kind, **fields)


# --- the four kinds -------------------------------------------------------------

def test_it_fires_on_four_kinds_and_their_order_is_the_page_s():
    assert GATE_KINDS == ("note_landed", "arrival", "drink_crossing", "stall")
    # three of them are the world's; the fourth is the gate's own
    assert WORLD_GATE_KINDS == GATE_KINDS[:3]
    assert STALL == "stall" and STALL not in WORLD_GATE_KINDS
    # and the order is B §3.1's, so a controller can render the lines straight
    # off `gate_fired.events`: note, arrival, drink, stall
    assert GATE_KINDS.index("note_landed") < GATE_KINDS.index("arrival")
    assert GATE_KINDS.index("drink_crossing") < GATE_KINDS.index(STALL)


def test_each_of_the_world_s_three_opens_it_as_a_row_or_a_bare_kind():
    for kind in WORLD_GATE_KINDS:
        assert opening_kinds([row(kind, cell=[42, 40], index=0, first=True)]) == {kind}
        assert opening_kinds([kind]) == {kind}
    assert opening_kinds(()) == set()
    assert opening_kinds(None) == set()


def test_nothing_else_in_the_step_s_events_opens_it():
    """The old E1 (a vital crossed), E2 (a move refused) and E3 (a new kind of
    cell in view) are not ported, and the rows the world and the other pieces
    write for their own reasons are not the gate's business either — a
    controller may hand it the whole step's `events.jsonl` and get silence."""
    quiet = [row("errands_completed"), row("death"),
             row("ops_applied", source="R1", ops=[], list_after=[]),
             row("focus_chosen", id="e1"),
             row("route", target=[9, 9], first_step="move_up", sentence="go up")]
    assert opening_kinds(quiet) == set()
    g = Gate()
    assert g.observe(0, 25, quiet) == set()
    assert g.rows == []


def test_two_arrivals_on_one_step_are_one_arrival():
    assert opening_kinds([row("arrival", index=0, first=True),
                          row("arrival", index=1, first=True)]) == {"arrival"}


def test_a_world_event_fires_on_its_step_and_the_gate_keeps_no_memory_of_it():
    g = Gate()
    assert g.observe(0, 25, [row("note_landed")]) == {"note_landed"}
    assert g.observe(1, 26) == set()
    assert g.observe(2, 27) == set()


# --- the window -----------------------------------------------------------------

def test_the_window_is_one_count_longer_than_the_stall():
    """A past bug's lesson, pinned at the constant and at the deque: the
    crossing compares against the count N+1 steps back, so a window of N leaves
    that comparison impossible and every stalled step reads as a stall's first.
    `test_gate_loop.py` runs the buggy width and shows what it does."""
    assert constants.STALL_LENGTH == 8
    assert constants.STALL_WINDOW == constants.STALL_LENGTH + 1
    assert Gate()._counts.maxlen == constants.STALL_WINDOW


def test_it_says_nothing_until_the_seen_set_has_been_still_for_eight_steps():
    g = Gate()
    for step in range(N):
        assert g.observe(step, 40) == set(), step
    assert g.observe(N, 40) == {STALL}


def test_it_stays_quiet_while_the_seen_set_is_growing():
    g = Gate()
    for step in range(40):
        assert g.observe(step, 25 + step) == set(), step
    # one step's growth anywhere inside the window is enough to keep it quiet
    g, count = Gate(), 40
    for step in range(40):
        if step % 4 == 0:
            count += 1
        assert g.observe(step, count) == set(), step


def test_it_reads_the_count_and_not_the_position():
    """Round twenty-six's body oscillated between two cells for 389 steps: its
    position moved on every one of them and its count of cells never stood on
    before moved on none, so a position test would have seen a body going
    somewhere the whole time. In this interface the position is not passed at
    all — the gate is handed a size."""
    assert list(inspect.signature(Gate.observe).parameters) == [
        "self", "step", "seen_count", "world_events"]
    g = Gate()
    assert [step for step in range(40) if g.observe(step, 2)] == [N]


# --- the rows -------------------------------------------------------------------

def test_every_row_carries_its_step_and_its_kind_and_the_fields_A_names():
    g = Gate()
    for step in range(N):
        g.observe(step, 40, [row("death")] if step == 3 else ())
    assert g.observe(N, 40, [row("note_landed")]) == {"note_landed", STALL}
    # the stall began on step 1: step 0 is the baseline the gate was handed, and
    # the eight still steps are 1 through 8
    assert g.last_rows == [
        {"step": 8, "kind": "stall_start", "since_step": 1, "length": N},
        {"step": 8, "kind": "gate_fired", "events": ["note_landed", STALL]},
    ]
    # the set has no order; the row does
    assert g.observe(9, 41) == set()
    assert g.last_rows == [
        {"step": 9, "kind": "stall_end", "since_step": 1, "length": N},
    ]
    assert g.rows[-1] is g.last_rows[-1]
    assert [r["kind"] for r in g.rows] == ["stall_start", "gate_fired", "stall_end"]


def test_a_step_that_fires_nothing_writes_no_row():
    g = Gate()
    for step in range(N):
        assert g.observe(step, 25 + step) == set()
    assert g.rows == [] and g.last_rows == []


# --- the calling contract -------------------------------------------------------

def test_observe_refuses_a_repeated_or_a_skipped_step():
    """The stall is counted in steps, so the gate cannot be observed twice for
    one step or skipped over one — either would move the stall silently."""
    g = Gate()
    g.observe(0, 25)
    g.observe(1, 26)
    with pytest.raises(ValueError):
        g.observe(1, 27)
    with pytest.raises(ValueError):
        g.observe(3, 27)
    # a refusal leaves the gate where it was
    assert g.observe(2, 27) == set()
