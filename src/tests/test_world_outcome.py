"""The coordinates the model reads, and the sentences the world says (A §1.1, §1.3).

`shown_y` is the whole of the axis rule: the world stores and logs +y down, the
model is shown +y up, and because `63 - y` is its own inverse a coordinate the
model writes is read back with the same call.

The outcome sentences are the old `loop.outcome` / `loop._outcome_text` to the
byte, for the cases four moves and a noop can produce. They are honest results:
flat, no advice, no verdict on the body. `did not move; the cell to your right is
tree` is the world saying what is there.

    generated/venv/bin/python -m pytest src/tests/test_world_outcome.py -q
"""
import pytest

from p3focus import constants as K
from p3focus.world import (
    HOT_GROUND_CLAUSE,
    HOT_GROUND_CLAUSE_EMPTY,
    NOOP,
    VERBS,
    World,
    objects,
    outcome,
    shown_pos,
    shown_y,
)

SEED = 7


def a_world(seed=SEED):
    world = World(seed)
    world.reset()
    return world


def wall_the_body_in(world, materials=("tree", "stone", "coal", "iron")):
    """Put a different non-walkable material in each of the four cells beside the
    body, in `move_up, move_down, move_left, move_right` order. WORLD axis, so
    `up` is `y - 1`."""
    x, y = (int(v) for v in world.env._player.pos)
    cells = {"move_up": (x, y - 1), "move_down": (x, y + 1),
             "move_left": (x - 1, y), "move_right": (x + 1, y)}
    for material, verb in zip(materials, cells):
        world.env._world[cells[verb]] = material
    world._walkable_cells = None
    return dict(zip(cells, materials))


# -- the axis (A §1.1) ---------------------------------------------------------

def test_shown_y_is_63_minus_y():
    assert shown_y(0) == 63 and shown_y(63) == 0
    assert shown_y(32) == 31 and shown_y(31) == 32
    assert shown_y(40) == 23, "seed 7's first errand cell, as A §1.1 quotes it"


def test_shown_y_is_an_involution_over_the_whole_map():
    """Why the map may be applied at a boundary without bookkeeping: a coordinate
    the model writes is read back with the same call."""
    assert all(shown_y(shown_y(y)) == y for y in range(K.WORLD_SIZE))


def test_shown_pos_never_touches_x():
    assert shown_pos([42, 40]) == [42, 23]
    assert all(shown_pos([x, 0])[0] == x for x in range(K.WORLD_SIZE))
    assert shown_pos(shown_pos([7, 11])) == [7, 11]


def test_the_spawn_is_32_32_in_the_world_and_32_31_on_the_page():
    assert K.SPAWN == (32, 32)
    assert shown_pos(K.SPAWN) == [32, 31]


# -- a move that moved ---------------------------------------------------------

def test_a_move_that_moved_names_the_cell_in_the_shown_axis():
    world = a_world()
    frame, said, _ = world.step("move_down")
    assert frame["player"]["pos"] == [32, 33], "the world logs +y down"
    assert said == "moved to [32, 30]", "and the sentence shows +y up"


def test_every_move_verbs_sentence_agrees_with_the_frame_it_came_from():
    for verb in VERBS:
        world = a_world()
        frame, said, _ = world.step(verb)
        p = shown_pos(frame["player"]["pos"])
        assert said == f"moved to [{p[0]}, {p[1]}]", verb


# -- a move that did not ------------------------------------------------------

def test_a_blocked_move_names_the_direction_and_the_material():
    """Four directions, four different materials, so neither the word nor the
    name can be right by accident. `above you` is `y - 1`: +y is down."""
    world = a_world()
    walled = wall_the_body_in(world)
    here = list(world.last_frame["player"]["pos"])
    words = {"move_up": "above you", "move_down": "below you",
             "move_left": "to your left", "move_right": "to your right"}
    for verb, material in walled.items():
        frame, said, _ = world.step(verb)
        assert frame["player"]["pos"] == here, f"{verb} should not have moved the body"
        assert said == f"did not move; the cell {words[verb]} is {material}"


def test_a_blocked_move_names_what_the_window_shows_object_and_all():
    """The sentence reads the cell out of the window the body just got, so an
    object standing on grass is named as the object. That is the old line's
    behaviour and it is honest: the cow really is what stopped the body."""
    world = a_world()
    x, y = (int(v) for v in world.env._player.pos)
    world.env._world.add(objects.Cow(world.env._world, (x + 1, y)))
    frame, said, _ = world.step("move_right")
    assert frame["player"]["pos"] == [x, y]
    assert said == "did not move; the cell to your right is cow"


def test_the_sentence_says_what_stopped_the_body_and_nothing_about_what_to_do():
    world = a_world()
    wall_the_body_in(world)
    said = world.step("move_up")[1]
    for word in ("should", "try", "instead", "cannot", "careful", "!"):
        assert word not in said.lower(), said


# -- a defaulted reply ---------------------------------------------------------

def test_noop_says_waited():
    world = a_world()
    assert world.step(NOOP)[1] == "waited"


def test_there_is_no_sentence_for_a_verb_this_world_has_not_got():
    """`outcome` is public, so it says so rather than inventing a sentence for a
    verb that cannot reach the world."""
    world = a_world()
    before = world.last_frame
    after = world.step("move_down")[0]
    with pytest.raises(ValueError, match="no outcome sentence"):
        outcome("do", before, after)
    with pytest.raises(ValueError, match="no outcome sentence"):
        outcome("drink", before, after)


# -- the heat's clause rides them ----------------------------------------------

def test_the_hot_clause_is_a_suffix_on_every_one_of_them():
    world = a_world()
    before = world.last_frame
    after = world.step("move_down")[0]
    plain = outcome("move_down", before, after)
    assert outcome("move_down", before, after, hot=True, fell=1) == plain + HOT_GROUND_CLAUSE
    assert outcome("move_down", before, after, hot=True, fell=0) == plain + HOT_GROUND_CLAUSE_EMPTY
    assert outcome(NOOP, before, after, hot=True, fell=1) == "waited" + HOT_GROUND_CLAUSE
