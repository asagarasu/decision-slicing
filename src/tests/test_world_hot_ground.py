"""Hot sand: a step that ENDS on it costs one drink (A §1.1, second row).

Ported from the old repo's `src/tests/test_hot_ground.py` — its physics tests
and its two clause tests. What is not here: its flag tests (this line has no
flag), its manifest and replay tests (not this piece's), its courier test (the
courier is not brought), and its byte pins of old pages (`FROZEN_BACKGROUND`,
the world-law shas), which pinned text `pages.md` now owns.

The old file's calibration compared a hot battery against a cold one. There is
no cold one here, so the control is built the other way round: the same walk, on
the same cells, with the sand repainted grass. Sand and grass are both walkable,
so the body takes exactly the same path and the vendor's own thirst counter runs
exactly the same clock; the difference in the meter is the heat and nothing else.

The charge is immediate and the sentence names it by design:
a 72B crossed a hot field eleven times against a DEFERRED charge, could attribute
nothing to the heat, concluded it cost HEALTH, and at health 1 refused to cross
three cells of it to reach water it could name. A price the body cannot observe
is a price it will invent.

    generated/venv/bin/python -m pytest src/tests/test_world_hot_ground.py -q
"""
import pytest

from p3focus.world import (
    HOT_GROUND_CLAUSE,
    HOT_GROUND_CLAUSE_EMPTY,
    HOT_GROUND_DRINK,
    HOT_GROUND_MATERIAL,
    World,
    accrue_hot_ground,
    hot_ground_clause,
    make_env,
    on_hot_ground,
    outcome,
)

SEED = 7
#: seed 7, from the spawn at [32, 32] to [43, 39] — the grass cell just west of
#: the beach at the south-east lake. Two of the eastward moves are spent on a cow
#: standing at [39, 39] (a blocked move turns you and costs the step), which is
#: why the run of `move_right` at the end is seven and not five.
APPROACH = (["move_right"] * 5 + ["move_down"] * 6 + ["move_right"] + ["move_down"]
            + ["move_right"] * 7)
BEACH = (43, 39)
#: and then TEN steps that each END on sand, out and back across the beach
SAND_WALK = (["move_right"] * 4 + ["move_down"] + ["move_left"] * 3 + ["move_right"]
             + ["move_down"])
SAND_END = (45, 41)


def at_the_beach(drink=None):
    """A world walked to `BEACH`, one grass cell short of the sand."""
    world = World(SEED)
    world.reset()
    for move in APPROACH:
        world.step(move)
    assert tuple(world.last_frame["player"]["pos"]) == BEACH, \
        "the approach no longer lands west of the beach; seed 7 moved"
    if drink is not None:
        world.env._player.inventory["drink"] = int(drink)
    return world


def walk_the_sand(world):
    """Take `SAND_WALK` and return one row per step: where it ended (WORLD axis),
    what the frame said the meter was, what the heat took, what the meter really
    was after the charge, the sentence, and the ground it ended on."""
    rows = []
    for move in SAND_WALK:
        frame, said, _ = world.step(move)
        rows.append({"pos": tuple(frame["player"]["pos"]),
                     "frame_drink": frame["player"]["drink"],
                     "fell": world.last_hot_fell,
                     "live": int(world.env._player.inventory["drink"]),
                     "said": said,
                     "ground": frame["standing_on"]})
    assert tuple(world.last_frame["player"]["pos"]) == SAND_END
    return rows


# -- the charge ----------------------------------------------------------------

def test_the_charge_is_immediate_and_lands_on_drink_not_on_the_hidden_counter():
    """By design the charge is immediate. It used to go to `_thirst`, so the cost surfaced later,
    folded into ordinary thirst and indistinguishable from it."""
    env = make_env(SEED)
    env.reset()
    player = env._player
    drink, thirst = player.inventory["drink"], player._thirst

    assert env._world[tuple(player.pos)][0] != HOT_GROUND_MATERIAL
    assert accrue_hot_ground(env) == 0
    assert player._thirst == thirst and player.inventory["drink"] == drink

    env._world[tuple(player.pos)] = HOT_GROUND_MATERIAL
    assert on_hot_ground(env) is True
    assert accrue_hot_ground(env) == HOT_GROUND_DRINK
    assert player.inventory["drink"] == drink - HOT_GROUND_DRINK
    assert player._thirst == thirst, "the heat never touches the hidden counter"

    player.inventory["drink"] = 0
    assert accrue_hot_ground(env) == 0, "nothing left to take"
    assert player.inventory["drink"] == 0, "and the meter never goes negative"


def test_ten_sand_steps_cost_ten_drink_more_than_the_same_ten_steps_on_grass():
    """The calibration, against its own control: the same walk over the same
    cells, sand repainted grass. Floored at an empty meter, which is why this
    reads `max(0, ...)` rather than a flat subtraction."""
    hot = at_the_beach(drink=9)
    hot_rows = walk_the_sand(hot)
    assert [r["ground"] for r in hot_rows] == [HOT_GROUND_MATERIAL] * 10, \
        "the walk stopped crossing ten cells of sand"

    cold = at_the_beach(drink=9)
    for cell in {r["pos"] for r in hot_rows}:   # exactly the cells it ends on
        cold.env._world[cell] = "grass"
    cold_rows = walk_the_sand(cold)
    assert [r["pos"] for r in cold_rows] == [r["pos"] for r in hot_rows], \
        "the control has to take the same path, or it is not a control"
    assert [r["ground"] for r in cold_rows] == ["grass"] * 10, "and really be cold"

    hot_drink = int(hot.env._player.inventory["drink"])
    cold_drink = int(cold.env._player.inventory["drink"])
    assert hot_drink == max(0, cold_drink - 10 * HOT_GROUND_DRINK)
    # the two runs differ by the heat's charges and by nothing else
    assert sum(r["fell"] for r in hot_rows) == cold_drink - hot_drink
    assert sum(r["fell"] for r in cold_rows) == 0
    # non-vacuous, and the floor is real: ten sand steps is more than a full
    # meter holds, so the last two of them find nothing left to take
    assert hot_drink == 0 and sum(r["fell"] for r in hot_rows) == 8
    assert [r["fell"] for r in hot_rows][-2:] == [0, 0]


def test_only_a_step_that_ends_on_hot_ground_is_charged():
    """The cell that charges is the one the body ENDED on. The twenty-step
    approach runs over grass through the same world and costs nothing."""
    world = World(SEED)
    world.reset()
    charged = 0
    for move in APPROACH:
        frame, _, _ = world.step(move)
        assert frame["standing_on"] != HOT_GROUND_MATERIAL
        charged += world.last_hot_fell
    assert charged == 0


def test_standing_still_on_hot_ground_is_not_free():
    """A step that ENDS on sand, not a step that MOVES onto it: the clock runs
    whether the body acts or not, and so does the heat."""
    world = at_the_beach(drink=9)
    world.step("move_right")
    assert on_hot_ground(world.env)
    drink = int(world.env._player.inventory["drink"])
    assert drink >= 3, "the sum below wants a meter with room to fall three times"
    for _ in range(3):
        world.step("noop")
    assert int(world.env._player.inventory["drink"]) == drink - 3 * HOT_GROUND_DRINK


def test_a_blocked_move_that_leaves_the_body_on_sand_is_charged_too():
    """The charge is keyed on where the body IS at the end of the step, not on
    whether it went anywhere."""
    world = at_the_beach(drink=9)
    world.step("move_right")
    x, y = (int(v) for v in world.env._player.pos)
    world.env._world[(x, y - 1)] = "stone"
    world._walkable_cells = None
    frame, said, _ = world.step("move_up")
    assert tuple(frame["player"]["pos"]) == (x, y)
    assert said == "did not move; the cell above you is stone" + HOT_GROUND_CLAUSE
    assert world.last_hot_fell == HOT_GROUND_DRINK


# -- the sentence --------------------------------------------------------------

def test_the_clause_names_the_charge_and_says_nothing_else():
    """Replacing told-by-contact for this one sentence, by design."""
    assert HOT_GROUND_CLAUSE == "; the ground here is hot, drink fell 1"
    assert HOT_GROUND_CLAUSE_EMPTY == ("; the ground here is hot, but your drink is "
                                       "already empty, so nothing fell")
    assert "!" not in HOT_GROUND_CLAUSE
    assert not any(word in HOT_GROUND_CLAUSE.lower()
                   for word in ("avoid", "should", "careful", "danger"))
    assert hot_ground_clause(1) == HOT_GROUND_CLAUSE
    assert hot_ground_clause(0) == HOT_GROUND_CLAUSE_EMPTY


def test_the_clause_is_keyed_on_what_the_heat_took_not_on_the_meter():
    """It reports an event; it does not decide one. Both halves ride the same
    sand step, and which one rides it is `accrue_hot_ground`'s return."""
    # drink 2, because the vendor's own thirst counter crosses on this very step
    # and takes the first unit: 2 -> 1 from thirst, 1 -> 0 from the heat, and
    # from the next step on there is nothing left for the heat to take.
    world = at_the_beach(drink=2)
    rows = walk_the_sand(world)
    assert rows[0]["fell"] == 1 and rows[0]["said"].endswith(HOT_GROUND_CLAUSE)
    assert rows[0]["live"] == 0
    assert rows[1]["fell"] == 0 and rows[1]["said"].endswith(HOT_GROUND_CLAUSE_EMPTY)
    assert all(r["ground"] == HOT_GROUND_MATERIAL for r in rows), "every one is a sand step"


def test_the_clause_rides_whatever_the_result_was_and_replaces_none_of_it():
    """A suffix on the honest result, not a line of its own: a move that moved
    and a move that was refused both keep their own sentence."""
    world = at_the_beach(drink=9)
    before = world.last_frame
    after, said, _ = world.step("move_right")
    cold = outcome("move_right", before, after)
    assert said == cold + HOT_GROUND_CLAUSE
    assert outcome("move_right", before, after, hot=False) == cold
    assert outcome("move_right", before, after, hot=True, fell=0) == cold + HOT_GROUND_CLAUSE_EMPTY


def test_the_walk_carries_the_clause_on_its_sand_steps_and_nowhere_else():
    """Through the loop: only on the steps that ended on sand, and on every one
    of them — including the ones where the meter was already empty, which are
    still the clause reporting a sand step."""
    world = World(SEED)
    world.reset()
    said = []
    for move in APPROACH + SAND_WALK:
        said.append(world.step(move)[1])
    approach, sand = said[:len(APPROACH)], said[len(APPROACH):]
    assert not any(HOT_GROUND_CLAUSE in s or HOT_GROUND_CLAUSE_EMPTY in s for s in approach)
    assert all(s.endswith(HOT_GROUND_CLAUSE) or s.endswith(HOT_GROUND_CLAUSE_EMPTY)
               for s in sand)
    assert len(sand) == 10
    # the clause follows the world's own sentence about the step. [44, 24] not
    # [44, 39]: the body is shown +y up and 63 - 39 = 24.
    assert sand[0] == "moved to [44, 24]" + HOT_GROUND_CLAUSE


# -- the A-QUESTION, pinned so it cannot move in silence -----------------------

def test_the_frame_shows_this_steps_hot_charge():
    """Settled 09-24: the charge runs between the env step and the frame, so the
    frame the body reads on a sand step already shows the fall the sentence
    beside it names. The old code logged it one frame late (measured by the
    world builder); this test is the one that says so if it ever comes back.
    """
    world = at_the_beach(drink=9)
    rows = walk_the_sand(world)
    for row in rows:
        assert row["live"] == row["frame_drink"], "the frame shows this step's charge"
    first = rows[0]
    assert first["fell"] == HOT_GROUND_DRINK
    assert first["said"].endswith(HOT_GROUND_CLAUSE), "the sentence says a fall of 1"
    assert first["frame_drink"] == first["live"] <= 8, "and the frame has fallen with it (thirst may tick too)"


@pytest.mark.parametrize("pos", [(0, 0), (63, 63)])
def test_on_hot_ground_is_false_where_there_is_no_material(pos):
    """Out of bounds is False, because the vendor returns no material there and a
    hazard the world cannot name cannot charge."""
    world = World(SEED)
    world.reset()
    assert on_hot_ground(world.env, pos) in (True, False)
    assert on_hot_ground(world.env, (-1, -1)) is False
    assert accrue_hot_ground(world.env, (-1, -1)) == 0
