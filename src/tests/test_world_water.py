"""Water is walkable, and standing in it is drinking (A §1.1, first row).

Ported from the old repo's `src/tests/test_water_walkable.py` — its physics
tests, which is all of it that is this piece's. What is not here: its manual and
page tests (`walkable_words`, `trace_console_manual`, `trace_slot_manual`), which
belong to `pages.md` and to whoever builds it; and its `test_default_is_off` and
`test_off_*` tests, which pinned the frozen record on the far side of a flag this
line does not have. Here the rule is the world, so "off" does not exist.

The old file's four reasons for existing, of which three survive as claims below:

- the world and the manual agreeing. Not this piece's to check any more, but the
  world half of it is: water is walkable, and the one cell the window cannot show
  says so (`standing_on`, A §1.2);
- the counter still meaning what it meant. A swallow banks `collect_drink` only
  when it actually MOVES the meter; a body parked in water would otherwise bank
  one a step forever;
- the rule surviving death. `respawn` builds a NEW `Player`, so the attribute is
  re-applied every step. Without that the page would go on promising water is
  walkable after the first death while the engine refused it — silently.

The tests move the MATERIAL, never the body: putting water in the cell the body
faces is the old file's own idiom, and it keeps the walk deterministic.

    generated/venv/bin/python -m pytest src/tests/test_world_water.py -q
"""
from p3focus.world import WALKABLE, WATER, World, objects, pin_water_walkable

SEED = 7


def a_world(seed=SEED):
    world = World(seed)
    world.reset()
    return world


def water_to_the_right(world):
    """Put water in the cell east of the body and return it, WORLD axis.

    The walkable-cell cache is dropped because the map just changed under it:
    `World._walkable()` computes once and is right to, since a real run changes
    no material after reset. A test that edits the map has to say so.
    """
    x, y = (int(v) for v in world.env._player.pos)
    world.env._world[(x + 1, y)] = WATER
    world._walkable_cells = None
    return (x + 1, y)


def pocket_of_water(world):
    """Water under the body and in the cell east of it, so the body can stay in
    the water by bumping or by stepping along it."""
    x, y = (int(v) for v in world.env._player.pos)
    for cell in ((x, y), (x + 1, y)):
        world.env._world[cell] = WATER
    world._walkable_cells = None


# -- water is walkable ---------------------------------------------------------

def test_water_is_in_the_walkable_set_this_world_uses():
    assert WATER in WALKABLE
    assert WALKABLE == {"grass", "path", "sand", "water"}


def test_the_body_steps_into_the_water_rather_than_being_stopped_by_it():
    world = a_world()
    water = water_to_the_right(world)
    assert WATER in world.env._player.walkable
    frame, said, _ = world.step("move_right")
    assert tuple(frame["player"]["pos"]) == water
    assert said.startswith("moved to "), said
    assert world.env._world[water][0] == WATER, "the cell is still water; nothing was consumed"


def test_the_frame_says_the_body_is_standing_in_water_and_the_window_cannot():
    """Why `standing_on` is in the frame at all (A §1.2, D4): the window draws
    the body OVER its own cell, so a body in water sees `player` at the centre
    and no water there."""
    world = a_world()
    water_to_the_right(world)
    frame, _, _ = world.step("move_right")
    assert frame["standing_on"] == WATER
    assert frame["window"][4][4] == "player"


# -- standing in it is drinking ------------------------------------------------

def test_arriving_in_the_water_is_already_a_swallow():
    world = a_world()
    water_to_the_right(world)
    world.env._player.inventory["drink"] = 3
    frame, _, _ = world.step("move_right")
    assert frame["player"]["drink"] == 4


def test_staying_in_the_water_raises_the_meter_a_step_and_clamps_at_nine():
    """A §1.1: drink rises by 1 each step while the body stands on water, up to
    9, and the hidden thirst counter is held at 0 the whole time."""
    world = a_world()
    pocket_of_water(world)
    world.env._player.inventory["drink"] = 2
    seen = []
    for _ in range(12):
        frame, _, _ = world.step("noop")
        seen.append(frame["player"]["drink"])
    assert seen[:7] == [3, 4, 5, 6, 7, 8, 9]
    assert seen[7:] == [9] * 5, "clamped at the item max"
    assert world.env._player._thirst == 0, "and thirst is held down while it stands there"


def test_a_body_that_wants_to_stay_in_water_can_bump_instead_of_waiting():
    """A §1.1's own sentence, and the reason `noop` is not offered to the model:
    a body in water has to keep moving inside it or bump. A blocked move spends
    the step without leaving the cell, and the meter rises exactly as it does for
    a step taken along the water."""
    world = a_world()
    pocket_of_water(world)
    x, y = (int(v) for v in world.env._player.pos)
    world.env._world[(x, y - 1)] = "stone"     # a wall to press into
    world._walkable_cells = None
    world.env._player.inventory["drink"] = 4

    frame, said, _ = world.step("move_up")     # bumped: did not move, still in water
    assert tuple(frame["player"]["pos"]) == (x, y)
    assert said == "did not move; the cell above you is stone"
    assert frame["standing_on"] == WATER and frame["player"]["drink"] == 5

    frame, said, _ = world.step("move_right")  # or moved, along the water
    assert frame["standing_on"] == WATER and frame["player"]["drink"] == 6


def test_collect_drink_fires_only_when_the_swallow_moves_the_meter():
    """A body parked in water would otherwise bank one achievement a step, and
    every drinking count in the record would change sense."""
    world = a_world()
    pocket_of_water(world)
    player = world.env._player
    player.inventory["drink"] = 7
    before = player.achievements["collect_drink"]
    world.step("noop")   # 7 -> 8
    world.step("noop")   # 8 -> 9
    assert player.achievements["collect_drink"] == before + 2
    at_full = player.achievements["collect_drink"]
    for _ in range(10):
        world.step("noop")
    assert player.inventory["drink"] == 9
    assert player.achievements["collect_drink"] == at_full


def test_the_decay_branch_still_runs_outside_the_water():
    """Water walkable does not turn thirst off; it gives the body somewhere to
    answer it. On dry ground the vendor's own counter still empties the meter."""
    world = a_world()
    player = world.env._player
    assert world.last_frame["standing_on"] != WATER
    player.inventory["drink"] = 5
    player._thirst = 20.0
    frame, _, _ = world.step("noop")
    assert frame["player"]["drink"] == 4


# -- the rule surviving death --------------------------------------------------

def test_the_rule_is_re_applied_every_step_because_respawn_builds_a_new_player():
    """The one failure mode this must not have. `store.respawn` — which this line
    inherits the shape of — removes the corpse and builds a NEW `Player`, and a
    new Player has never seen the pin. The re-application before every step is
    what keeps the world the page describes true after the first death."""
    world = a_world()
    env = world.env
    assert WATER in env._player.walkable

    corpse, pos = env._player, tuple(int(v) for v in env._player.pos)
    env._world.remove(corpse)
    fresh = objects.Player(env._world, pos)
    env._world.add(fresh)
    env._player = fresh
    assert fresh is not corpse
    assert WATER not in fresh.walkable, "the attribute went with the corpse"

    world.step("noop")   # which is why the world re-pins before every step
    assert WATER in env._player.walkable


def test_the_pin_is_idempotent_and_touches_only_the_live_player():
    world = a_world()
    other = objects.Player(world.env._world, (0, 0))
    pin_water_walkable(world.env)
    pin_water_walkable(world.env)
    assert WATER in world.env._player.walkable
    assert WATER not in other.walkable, "a Player the world never touched is unchanged"
