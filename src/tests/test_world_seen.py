"""The seen set, and the `mapped` bits built from it (A §6's world row, D2).

D2's rule, in one sentence: the seen set is every WALKABLE cell — water included
— inside the 9x9 around every cell the body has stood on, and it grows on EVERY
step. The old trace grew it only on the steps that routed, which made "cells you
have seen" false for cells the body walked past (bare arms brief, decision 6).
The test that carries that claim is `test_the_set_is_the_union_of_the_windows_of_
every_cell_the_body_has_stood_on`, which recomputes the union from the positions
alone and compares.

The `mapped` bits are the only thing a page gets from the set: five booleans, no
count (B, P2 — no progress meter on any page). A cell counts as mapped when it is
in the set OR when it is not walkable at all: there is nothing left to map on
stone, and a False would send the body chasing it (the old
`store.MappedTracker.is_mapped`).

    generated/venv/bin/python -m pytest src/tests/test_world_seen.py -q
"""
from p3focus import constants as K
from p3focus.world import WALKABLE, WATER, World

SEED = 7
RADIUS = K.WINDOW // 2


def a_world(seed=SEED):
    world = World(seed)
    world.reset()
    return world


def materials(world):
    """`{(x, y): name}` for the whole world, WORLD axis, read from the map."""
    env = world.env
    names = {int(i): n for i, n in env._world._mat_names.items()}
    mat = env._world._mat_map
    return {(x, y): names[int(mat[x, y])]
            for x in range(mat.shape[0]) for y in range(mat.shape[1])}


def window_of(pos, size=K.WORLD_SIZE):
    x, y = pos
    return {(a, b)
            for a in range(max(0, x - RADIUS), min(size, x + RADIUS + 1))
            for b in range(max(0, y - RADIUS), min(size, y + RADIUS + 1))}


# -- what the set holds --------------------------------------------------------

def test_reset_seeds_the_set_with_the_spawns_own_window():
    """The body is standing on the spawn at frame 0, so the spawn's 9x9 is seen
    before the first step — the old line marked frame 0 the same way."""
    world = a_world()
    ground = materials(world)
    expected = {c for c in window_of(tuple(K.SPAWN)) if ground[c] in WALKABLE}
    assert world.seen == expected
    assert 0 < len(world.seen) <= K.WINDOW * K.WINDOW


def test_only_walkable_cells_are_in_it_and_water_is_one_of_them():
    world = a_world()
    x, y = K.SPAWN
    world.env._world[(x + 1, y)] = WATER
    world.env._world[(x + 2, y)] = "stone"
    world._walkable_cells = None
    world.seen = set()
    world.step("move_up")
    assert (x + 1, y) in world.seen, "water is walkable here, so it is seeable"
    assert (x + 2, y) not in world.seen, "stone is not"
    ground = materials(world)
    assert all(ground[c] in WALKABLE for c in world.seen)


def test_the_set_is_world_axis():
    """Nothing in the seen set is ever in the shown axis: it is a set of world
    cells, and the page layer translates. Near the spawn the two axes are one
    cell apart and any mix-up would hide; ten cells south they are twenty apart,
    which is what this walks to before asking.
    """
    world = a_world()
    stood = [tuple(K.SPAWN)]
    for _ in range(10):
        stood.append(tuple(world.step("move_down")[0]["player"]["pos"]))
    end = stood[-1]
    assert end[1] >= K.SPAWN[1] + 5, f"the walk went south in the WORLD axis; it reached {end}"
    assert world.seen <= {c for pos in stood for c in window_of(pos)}
    mirrored = (end[0], 63 - end[1])
    assert mirrored[1] < min(y for _, y in world.seen), \
        "this test wants a mirror outside every window the walk opened"
    assert mirrored not in world.seen, "a shown-axis cell got into a world-axis set"


# -- how it grows (D2) ---------------------------------------------------------

def test_the_set_is_the_union_of_the_windows_of_every_cell_the_body_has_stood_on():
    """D2 itself, recomputed from the positions alone over a walk that mixes
    moves that landed with moves that were refused."""
    world = a_world()
    x, y = K.SPAWN
    # something to bump into, six cells east — outside the spawn's own 9x9, so
    # reset has not already seen it as the grass it was a moment ago
    world.env._world[(x + 6, y)] = "stone"
    world._walkable_cells = None
    stood = [tuple(K.SPAWN)]
    for move in (["move_right"] * 6 + ["move_up"] * 3 + ["move_down"] * 4
                 + ["move_left"] * 5 + ["move_up"] * 3):
        frame, _, _ = world.step(move)
        stood.append(tuple(frame["player"]["pos"]))
    ground = materials(world)
    expected = {c for pos in stood for c in window_of(pos) if ground[c] in WALKABLE}
    assert world.seen == expected
    assert len(stood) > len(set(stood)), "the walk really did revisit cells"
    assert len(world.seen) > K.WINDOW * K.WINDOW, "and really did grow past one window"
    assert stood.count((x + 5, y)) > 1, "and really was refused at the stone"


def test_it_grows_on_a_step_that_went_nowhere_too():
    """A blocked step is still a step the body took from a cell, so the cells
    around that cell are still cells it has seen. Nothing here depends on a
    route being computed — which is the whole of D2's change."""
    world = a_world()
    world.seen = set()
    x, y = (int(v) for v in world.env._player.pos)
    world.env._world[(x + 1, y)] = "stone"
    world._walkable_cells = None
    frame, said, _ = world.step("move_right")
    assert tuple(frame["player"]["pos"]) == (x, y) and said.startswith("did not move")
    ground = materials(world)
    assert world.seen == {c for c in window_of((x, y)) if ground[c] in WALKABLE}


def test_it_never_shrinks():
    world = a_world()
    sizes, sets = [], []
    for i in range(30):
        world.step(("move_right", "move_down", "move_left", "move_up")[i % 4])
        sizes.append(len(world.seen))
        sets.append(set(world.seen))
    assert sizes == sorted(sizes)
    assert all(sets[i] <= sets[i + 1] for i in range(len(sets) - 1))


def test_it_stops_at_the_worlds_edge():
    """The window is clipped, not wrapped: no cell outside 0..63 is ever in it."""
    world = a_world()
    for _ in range(40):
        world.step("move_up")
    assert all(0 <= x < K.WORLD_SIZE and 0 <= y < K.WORLD_SIZE for x, y in world.seen)


# -- the mapped bits (A §1.3) --------------------------------------------------

def test_the_bits_are_five_booleans_and_there_is_no_count():
    world = a_world()
    bits = world.mapped_bits(world.last_frame)
    assert set(bits) == {"here", "up", "down", "left", "right"}
    assert all(isinstance(v, bool) for v in bits.values())
    assert "count" not in bits, "no progress meter is on any page (B, P2)"


def test_up_is_the_cell_above_the_body_on_screen_which_is_y_minus_one():
    """The direction words are screen relative and carry no sign, so `up` has to
    be `y - 1` in the world axis this reads."""
    world = a_world()
    x, y = K.SPAWN
    world.seen = {(x, y)}
    world.env._world[(x, y - 1)] = "grass"
    world.env._world[(x, y + 1)] = "grass"
    world.env._world[(x - 1, y)] = "grass"
    world.env._world[(x + 1, y)] = "grass"
    world._walkable_cells = None
    for name, cell in (("up", (x, y - 1)), ("down", (x, y + 1)),
                       ("left", (x - 1, y)), ("right", (x + 1, y))):
        world.seen = {(x, y), cell}
        bits = world.mapped_bits(world.last_frame)
        assert bits[name] is True, name
        assert [k for k, v in bits.items() if v] == ["here", name], \
            f"{name} lit a neighbour that is not {cell}"


def test_a_cell_that_is_not_walkable_is_already_mapped():
    """There is nothing left to map on stone, and a False would send the body
    chasing it."""
    world = a_world()
    x, y = K.SPAWN
    world.env._world[(x + 1, y)] = "stone"
    world._walkable_cells = None
    world.seen = set()
    assert world.is_mapped(x + 1, y) is True, "not walkable: nothing to map"
    assert world.is_mapped(x, y) is False, "walkable and unseen"
    world.seen.add((x, y))
    assert world.is_mapped(x, y) is True


def test_outside_the_world_is_mapped_for_the_same_reason():
    world = a_world()
    assert world.is_mapped(-1, 0) is True
    assert world.is_mapped(K.WORLD_SIZE, 0) is True
    assert world.walkable_at(-1, 0) is False


def test_the_bits_follow_the_body_over_a_walk():
    """Through the loop: `here` is true on every step, because the body's own
    cell is always inside its own window and always walkable — it is standing on
    it. The four neighbours are true or not according to the set alone."""
    world = a_world()
    for i in range(20):
        frame, _, _ = world.step(("move_right", "move_down")[i % 2])
        bits = world.mapped_bits(frame)
        x, y = frame["player"]["pos"]
        assert bits["here"] is True
        assert bits == {"here": world.is_mapped(x, y),
                        "up": world.is_mapped(x, y - 1), "down": world.is_mapped(x, y + 1),
                        "left": world.is_mapped(x - 1, y), "right": world.is_mapped(x + 1, y)}


def test_a_far_cell_is_unmapped_until_the_body_has_been_near_it():
    world = a_world()
    x, y = K.SPAWN
    far = (x, y + 6)
    assert world.walkable_at(*far), "this test wants a walkable cell to be unseen"
    assert world.is_mapped(*far) is False
    for _ in range(2):
        world.step("move_down")
    assert world.is_mapped(*far) is True, "two steps south brought it inside the 9x9"
