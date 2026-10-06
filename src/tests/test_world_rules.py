"""This line's rules, fixed in code and not in flags (A §1.1's table, D8).

One test per row of the table, each named for the row it holds, and each checked
through `World` — the object the rest of the apparatus talks to — rather than
only through the function that implements it. The unit checks are here too where
the function has something the loop cannot show (the count a sweep returns, the
census the sweep must not move).

    generated/venv/bin/python -m pytest src/tests/test_world_rules.py -q
"""
import pytest

from p3focus import constants as K
from p3focus.world import (
    ACTION_INDEX,
    ENERGY_PIN,
    FOOD_PIN,
    LAVA,
    LAVA_BECOMES,
    MONSTER_TYPES,
    NOOP,
    VERBS,
    WALKABLE,
    World,
    make_env,
    remove_monsters,
    sweep_lava,
)

SEED = 7
#: seed 7's worldgen, counted once and pinned: a change to either number means
#: the substrate moved under every test in this directory.
SEED7_MONSTERS = {"zombie": 15, "skeleton": 5, "arrow": 0}
SEED7_LAVA = 40


def materials(env):
    """`{(x, y): name}` for the whole world, WORLD axis, read from the material
    map and not from the window."""
    world = env._world
    names = {int(i): n for i, n in world._mat_names.items()}
    mat = world._mat_map
    return {(x, y): names[int(mat[x, y])]
            for x in range(mat.shape[0]) for y in range(mat.shape[1])}


def a_world(seed=SEED):
    world = World(seed)
    world.reset()
    return world


# -- verbs (A §1.1, last row) --------------------------------------------------

def test_the_verbs_are_four_moves_and_nothing_else():
    assert VERBS == ("move_left", "move_right", "move_up", "move_down")
    assert "drink" not in VERBS, "water is walkable here; the drink verb is gone"
    assert NOOP not in VERBS, "noop exists only inside the harness, for a defaulted reply"


def test_every_verb_maps_to_the_vendors_own_action_index():
    """The old line's table was the vendor's own names, and so is this one: the
    world hands crafter an index, never a name of its own invention."""
    assert [ACTION_INDEX[v] for v in VERBS] == [1, 2, 3, 4]
    assert ACTION_INDEX[NOOP] == 0


def test_a_verb_the_world_has_not_got_is_refused_and_takes_no_step():
    world = a_world()
    before = world.last_frame["step"]
    for bad in ("drink", "do", "sleep", "place_stone", "goto", "", "MOVE_UP"):
        with pytest.raises(ValueError, match="unknown verb"):
            world.step(bad)
    assert world.last_frame["step"] == before, "no refused verb advanced the world"


def test_each_move_verb_moves_the_body_the_way_its_name_says():
    """Screen words, WORLD axis: `move_up` is `y - 1`, because +y is down.

    One press, one cell: a move both turns the body and moves it when the target
    is walkable. Only a BLOCKED move spends its step on the turn alone, which is
    the case `test_world_outcome.py` covers and the reason the old walk to the
    beach needed seven `move_right`s for five cells.
    """
    for verb, (dx, dy) in (("move_left", (-1, 0)), ("move_right", (1, 0)),
                           ("move_up", (0, -1)), ("move_down", (0, 1))):
        world = a_world()
        start = tuple(world.last_frame["player"]["pos"])
        frame, _, _ = world.step(verb)
        assert tuple(frame["player"]["pos"]) == (start[0] + dx, start[1] + dy), verb
        assert tuple(frame["player"]["facing"]) == (dx, dy), verb


def test_noop_takes_a_world_step_and_leaves_the_body_where_it_was():
    world = a_world()
    start = list(world.last_frame["player"]["pos"])
    frame, said, _ = world.step(NOOP)
    assert frame["step"] == 1 and frame["player"]["pos"] == start
    assert said == "waited"


# -- no monsters (A §1.1) ------------------------------------------------------

def test_reset_removes_every_zombie_skeleton_and_arrow_and_keeps_the_cows():
    world = a_world()
    assert world.monsters_removed == SEED7_MONSTERS
    assert not [o for o in world.env._world.objects if isinstance(o, MONSTER_TYPES)]
    assert [o for o in world.env._world.objects if type(o).__name__ == "Cow"], \
        "cows stay: only the three hunting kinds go"


def test_no_monster_comes_back_over_a_run():
    """The removal is once, at reset — which only holds because the balancer is
    off. With it on, `_balance_chunk` would spawn more every ten steps."""
    world = a_world()
    for _ in range(40):
        world.step("move_right")
    assert not [o for o in world.env._world.objects if isinstance(o, MONSTER_TYPES)]
    assert "zombie" not in {c for f in [world.last_frame] for row in f["window"] for c in row}


def test_remove_monsters_reports_what_it_took():
    env = make_env(SEED)
    env.reset()
    assert remove_monsters(env) == SEED7_MONSTERS
    assert remove_monsters(env) == {"zombie": 0, "skeleton": 0, "arrow": 0}, "idempotent"


# -- lava swept (A §1.1) -------------------------------------------------------

def test_reset_turns_every_lava_cell_to_stone():
    world = a_world()
    assert world.lava_swept == SEED7_LAVA
    assert LAVA not in set(materials(world.env).values())


def test_the_sweep_changes_nothing_but_the_lava_and_does_not_move_the_census():
    """A §1.1: stone is non-walkable as lava was, so the walkable census does not
    move. Nothing else in the map may change either."""
    env = make_env(SEED)
    env.reset()
    before = materials(env)
    walkable_before = {c for c, m in before.items() if m in WALKABLE}
    n = sweep_lava(env)
    after = materials(env)
    assert n == SEED7_LAVA
    changed = {c for c in before if before[c] != after[c]}
    assert changed == {c for c, m in before.items() if m == LAVA}
    assert all(after[c] == LAVA_BECOMES for c in changed)
    assert {c for c, m in after.items() if m in WALKABLE} == walkable_before
    assert sweep_lava(env) == 0, "one pass; a second finds nothing"


# -- food and energy pinned (A §1.1) -------------------------------------------

def test_frame_zero_is_already_in_the_pinned_world():
    """The pins run before frame 0, so the first frame the body ever reads is
    already the world it is told about — not a 9/9/9/9 world that changes under
    it on step 1."""
    world = a_world()
    f0 = world.last_frame
    assert f0["player"]["food"] == FOOD_PIN and f0["player"]["energy"] == ENERGY_PIN
    assert world.env._player._hunger == 0 and world.env._player._fatigue == 0
    assert f0["player"]["drink"] == 3, "and the starting drink is START_NEEDS'"


def test_food_and_energy_never_move_over_a_long_run():
    """Pinned BEFORE every step, so hunger can never reach the vendor's 25 and
    fatigue never its 30 — over a run far longer than either.

    The counters read 1, not 0, when a step has just finished: the pin zeroes
    them and then the step adds its one tick. One tick is the ceiling, which is
    the whole claim — nothing accumulates.
    """
    world = a_world()
    moved = []
    for i in range(120):
        frame, _, _ = world.step(VERBS[i % 4])
        assert frame["player"]["food"] == FOOD_PIN
        assert frame["player"]["energy"] == ENERGY_PIN
        assert world.env._player._hunger <= 1
        assert world.env._player._fatigue <= 1
        moved += [k for k in frame["deltas"]["inventory"] if k in ("food", "energy")]
    assert moved == [], "food and energy are never logged moving, so no page can show them"


def test_the_body_never_sleeps():
    """Fatigue pinned at 0 means the vendor never puts it to sleep, so `sleeping`
    is False in every frame and the outcome sentences never need the branch."""
    world = a_world()
    for i in range(60):
        frame, _, _ = world.step(VERBS[i % 4])
        assert frame["player"]["sleeping"] is False


# -- the seeds' errand cells (A §1.1) ------------------------------------------

def test_the_world_carries_its_seeds_errand_cells_world_axis():
    for seed, cells in K.ERRANDS.items():
        world = World(seed)
        assert world.errand_cells == tuple(tuple(c) for c in cells)
        assert world.errand_cells[-1] == K.SPAWN, "the return is the spawn on every seed"
    assert len(K.ERRANDS[7]) == 3, "two visits and a return"


def test_a_seed_with_no_errand_cells_is_refused():
    with pytest.raises(ValueError, match="no errand cells"):
        World(99)


def test_the_world_is_not_usable_before_reset():
    with pytest.raises(RuntimeError, match="reset"):
        World(SEED).step("move_up")
