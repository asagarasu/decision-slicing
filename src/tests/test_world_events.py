"""The five event kinds the world writes (A §4.2, and the world row of A §6).

    note_landed · arrival · errands_completed · drink_crossing · death

Every one of them is checked through a loop, because that is the only place the
claims live: "once", "after the note", "in any order", "only after both visits"
are all statements about a sequence of steps, not about a function.

The ledger tests are ported from the old repo's `src/tests/test_errands.py`
(`test_arrival_is_ledgered_from_the_step_after_the_note`, `test_the_meeting_place_
counts_only_after_every_visit`, `test_arrivals_before_the_note_do_not_count`),
which drove them through `run_battery` with a scripted client. There is no client
here — the world is the piece under test — so the same walks are driven through
`World.step` directly.

They use errand cells beside the spawn rather than the seed's real ones, which is
the old file's own idiom (its `VISIT` was [32, 34] and its `MEET` [32, 33] on this
same seed): the real cells are eight to twenty cells away and walking to them
would test the map, not the ledger. `test_world_rules.py` is where the real cells
are pinned.

    generated/venv/bin/python -m pytest src/tests/test_world_events.py -q
"""
from p3focus import constants as K
from p3focus.world import World

SEED = 7
#: two visits and a return, all beside the spawn and all grass on seed 7
NEARBY = ((32, 34), (32, 33), (32, 32))
#: ten steps that end where they started, so the note lands with the body on the
#: spawn — and that stand on an errand cell five times on the way, before the
#: note, which no arrival may be ledgered for
TO_THE_NOTE = ["move_down", "move_up"] * 5


def a_world(cells=NEARBY, seed=SEED):
    """A world whose errand cells are `cells`, WORLD axis. They are set before
    `reset`, because `reset` is where the note text is built from them."""
    world = World(seed)
    world.errand_cells = cells
    world.reset()
    return world


def walk(world, moves):
    """Take `moves` and return every event they produced, in order."""
    events = []
    for move in moves:
        events.extend(world.step(move)[2])
    return events


def kinds(events, kind):
    return [e for e in events if e["kind"] == kind]


# -- every row (A §4.2) --------------------------------------------------------

def test_every_event_row_carries_a_step_and_a_kind():
    world = a_world()
    events = walk(world, TO_THE_NOTE + ["move_down", "move_down", "move_up", "move_up"])
    assert events, "the walk produced no events at all"
    assert all(set(e) >= {"step", "kind"} for e in events)
    assert {e["kind"] for e in events} == {"note_landed", "arrival", "errands_completed"}
    assert all(isinstance(e["step"], int) for e in events)


# -- note_landed ---------------------------------------------------------------

def test_the_note_lands_once_after_the_step_numbered_NOTE_STEP():
    world = a_world()
    events = walk(world, TO_THE_NOTE + ["move_left"] * 6)
    landed = kinds(events, "note_landed")
    assert len(landed) == 1
    assert landed[0]["step"] == K.NOTE_STEP == 10
    assert landed[0] == {"step": 10, "kind": "note_landed"}, "the row has no other fields"


def test_nothing_of_the_note_exists_before_it_lands():
    world = a_world()
    for step in range(1, K.NOTE_STEP):
        assert world.step("move_left")[2] == []
        assert world.note_line is None and world.note_delivered is False
    world.step("move_left")
    assert world.note_delivered is True and world.note_line is not None


def test_a_run_shorter_than_the_note_step_never_sees_it():
    world = a_world()
    assert walk(world, ["move_left"] * (K.NOTE_STEP - 1)) == []
    assert world.note_delivered is False


# -- arrival -------------------------------------------------------------------

def test_arrivals_before_the_note_do_not_count():
    """No errand exists for the body before the note, so the five times it stood
    on [32, 33] on the way to step 10 are not arrivals and never become any."""
    world = a_world()
    before = walk(world, TO_THE_NOTE)
    assert kinds(before, "arrival") == []
    assert world.errands_reached == {}


def test_no_arrival_is_ledgered_on_the_step_the_note_lands():
    """The body is standing on the meeting cell at step 10 — the note lands and
    nothing else does."""
    world = a_world()
    events = walk(world, TO_THE_NOTE)
    assert tuple(world.last_frame["player"]["pos"]) == NEARBY[2]
    assert [e["kind"] for e in events] == ["note_landed"]


def test_visits_count_in_any_order_and_the_return_only_after_both():
    """The whole ledger, in one walk: the second visit first, then the first, and
    a return that only counts once both are done."""
    world = a_world()
    walk(world, TO_THE_NOTE)
    events = walk(world, ["move_down", "move_down", "move_up", "move_up"])
    assert [(e["kind"], e.get("index"), e["step"]) for e in events] == [
        ("arrival", 1, 11),          # [32, 33], the SECOND visit, reached first
        ("arrival", 0, 12),          # [32, 34], the first
        # step 13: back over [32, 33], already counted, no row (A §4.2, once per cell)
        ("arrival", 2, 14),          # the return, now that both are done
        ("errands_completed", None, 14),
    ]
    assert world.errands_reached == {1: 11, 0: 12, 2: 14}
    assert world.errands_completed is True


def test_an_arrival_row_names_the_cell_in_the_world_axis():
    world = a_world()
    walk(world, TO_THE_NOTE)
    row = walk(world, ["move_down"])[0]
    assert row == {"step": 11, "kind": "arrival", "cell": [32, 33], "index": 1}
    assert row["cell"] == list(NEARBY[1]), "A §4: coordinates in logs are world axis"


def test_the_return_cell_before_both_visits_is_not_an_arrival_at_all():
    """No row at all: until both visits are done the meeting place is not a
    place the body has been told to be."""
    world = a_world(cells=((32, 34), (32, 35), (32, 32)))
    walk(world, TO_THE_NOTE)
    events = walk(world, ["move_down", "move_up"])   # [32, 33], then back to the return
    assert tuple(world.last_frame["player"]["pos"]) == (32, 32)
    assert events == []
    assert world.errands_reached == {} and world.errands_completed is False


def test_errands_completed_fires_once_however_often_the_body_comes_back():
    world = a_world()
    walk(world, TO_THE_NOTE)
    events = walk(world, ["move_down", "move_down", "move_up", "move_up",
                          "move_down", "move_up", "move_down", "move_up"])
    assert len(kinds(events, "errands_completed")) == 1
    # and the later passes over a counted cell are not arrivals: once per cell (A §4.2)
    assert [e for e in kinds(events, "arrival") if e["step"] > 14] == []
    assert len(kinds(events, "arrival")) == 3


def test_the_ledger_can_be_re_derived_from_the_positions_alone():
    """A §1.1: the reader re-derives the ledger from `frames.jsonl` as a check,
    never instead. So the two have to agree — this is that check, run here."""
    world = a_world()
    positions, events = {}, []
    for move in TO_THE_NOTE + ["move_down", "move_down", "move_up", "move_up"]:
        frame, _, step_events = world.step(move)
        positions[frame["step"]] = tuple(frame["player"]["pos"])
        events.extend(step_events)
    note_step = kinds(events, "note_landed")[0]["step"]
    derived = {}
    for step, pos in sorted(positions.items()):
        if step <= note_step or pos not in NEARBY:
            continue
        index = NEARBY.index(pos)
        if index == len(NEARBY) - 1 and any(i not in derived for i in range(len(NEARBY) - 1)):
            continue
        derived.setdefault(index, step)
    assert derived == world.errands_reached
    assert derived == {e["index"]: e["step"] for e in kinds(events, "arrival")}


# -- drink_crossing and death --------------------------------------------------

#: the walk from `test_world_hot_ground.py`, which empties the meter on the sand,
#: and then a pace back and forth on the beach until the body dies of thirst.
APPROACH = (["move_right"] * 5 + ["move_down"] * 6 + ["move_right"] + ["move_down"]
            + ["move_right"] * 7)
SAND_WALK = (["move_right"] * 4 + ["move_down"] + ["move_left"] * 3 + ["move_right"]
             + ["move_down"])
PACE = ["move_left", "move_right"] * 80


def test_the_crossing_fires_when_the_meter_reaches_zero_and_again_on_every_health_fall():
    """A §4.2's `drink_crossing`, the old gate's E1 at its default: drink going
    from above 0 to 0, OR health falling. Both halves happen in this walk without
    anything being poked — the sand empties the meter, and the empty meter drains
    the health."""
    world = World(SEED)
    world.reset()
    events = walk(world, APPROACH + SAND_WALK + PACE)
    crossings = kinds(events, "drink_crossing")
    assert crossings, "the walk never emptied the meter"
    first = crossings[0]
    assert (first["drink_from"], first["drink_to"]) == (1, 0)
    assert (first["health_from"], first["health_to"]) == (9, 9), "the meter half fired"
    assert len([c for c in crossings if c["drink_from"] > 0]) == 1, \
        "the meter reaches 0 once and is never refilled on this walk"
    falls = [c for c in crossings[1:] if c["health_to"] < c["health_from"]]
    assert len(falls) == 9, "nine health falls from 9 to 0"
    assert [c["health_from"] - c["health_to"] for c in falls] == [1] * 9
    assert all(c["drink_from"] == c["drink_to"] == 0 for c in falls)


def test_death_fires_once_on_the_first_frame_whose_health_is_zero():
    world = World(SEED)
    world.reset()
    healths = {}
    events = []
    for move in APPROACH + SAND_WALK + PACE:
        frame, _, step_events = world.step(move)
        healths[frame["step"]] = frame["player"]["health"]
        events.extend(step_events)
    deaths = kinds(events, "death")
    assert len(deaths) == 1, "a run may step past death; the row may not repeat"
    zero = min(step for step, health in healths.items() if health == 0)
    assert deaths[0] == {"step": zero, "kind": "death"}
    assert world.died is True
    assert max(healths) > zero, "the world kept stepping after it; the controller stops, not this"
