"""The human's note (A §1.1).

Ported from the old repo's `src/tests/test_errands.py`, its note-text tests. The
old `errand_note` had four switches (`y_up`, `stakes`, `steps`, `errand_drink`);
this line has the one shape arm O ran — numbered steps, stakes on — so the tests
for the other shapes are gone with the shapes.

The first test is the one that matters: A §1.1 quotes seed 7's line in full, and
the world has to produce it to the byte. If it does not, the pages the model
reads are not the pages the design says they are.

    generated/venv/bin/python -m pytest src/tests/test_world_note.py -q
"""
from p3focus import constants as K
from p3focus.world import World, errand_note, shown_pos, trace_note_line

#: A §1.1, verbatim. Shown axis: seed 7's cells are [42, 40], [22, 24] and
#: [32, 32] in the world, and 63 - 40 = 23, 63 - 24 = 39, 63 - 32 = 31.
A_SEED7_LINE = (
    'step 10: a note from your human player arrived: "Three things: (1) stand on '
    '[42, 23], my pickaxe is there; (2) stand on [22, 39], my rope is there; (3) then '
    'come to me at [32, 31] with both. I am stuck down here without them. The map can '
    'wait for that; I can\'t."')


def test_seed_sevens_note_line_is_the_one_A_quotes_to_the_byte():
    assert trace_note_line(K.NOTE_STEP, errand_note(K.ERRANDS[7])) == A_SEED7_LINE


def test_the_world_builds_that_line_itself_at_the_step_it_lands():
    """Not just the function: the object the rest of the apparatus talks to."""
    world = World(7)
    world.reset()
    assert world.note_line is None, "nothing has landed yet"
    for _ in range(K.NOTE_STEP):
        world.step("move_up")
    assert world.note_line == A_SEED7_LINE


def test_the_note_speaks_the_shown_axis_on_every_seed():
    for seed, cells in K.ERRANDS.items():
        text = errand_note(cells)
        for pos in cells:
            p = shown_pos(pos)
            assert f"[{p[0]}, {p[1]}]" in text, (seed, pos)
            if p[1] != pos[1]:
                assert f"[{pos[0]}, {pos[1]}]" not in text, \
                    f"seed {seed} leaked a world-axis coordinate into the note"


def test_the_items_are_named_in_visit_order():
    text = errand_note(K.ERRANDS[7])
    assert K.ERRAND_ITEMS == ("pickaxe", "rope")
    assert text.index("pickaxe") < text.index("rope")
    assert "(1) stand on [42, 23], my pickaxe is there" in text
    assert "(2) stand on [22, 39], my rope is there" in text


def test_the_delivery_is_its_own_numbered_step_and_the_count_matches():
    text = errand_note(K.ERRANDS[7])
    assert text.startswith("Three things: "), "two visits and a delivery"
    assert "(3) then come to me at [32, 31] with both." in text
    assert "(4)" not in text


def test_the_stakes_sentence_is_the_last_thing_the_human_says():
    """The note's job is to interrupt the standing task, which needs the last
    sentence: the map can wait, and the human cannot."""
    text = errand_note(K.ERRANDS[7])
    assert text.endswith("I am stuck down here without them. The map can wait for that; I can't.")
    assert "The map is still the job." not in text, "that is the stakes-off form, not this one"


def test_the_note_never_names_water_thirst_or_a_direction():
    """The note is an errand, not a hint. The old `errand_drink` form added a
    fourth numbered step telling the body to drink when it passed water; this
    line does not have it, and the note must not smuggle it back."""
    text = errand_note(K.ERRANDS[7]).lower()
    for word in ("water", "drink", "thirst", "north", "south", "east", "west", "hot", "sand"):
        assert word not in text, word


def test_the_line_is_one_history_line_in_the_worlds_voice():
    assert trace_note_line(10, "hello") == \
        'step 10: a note from your human player arrived: "hello"'
    assert trace_note_line(7, "x").startswith("step 7: ")


def test_a_note_for_one_visit_and_for_three_reads_as_english():
    """`errand_note` takes the visits and the meeting place, not a fixed pair, so
    the singular and the longer plural have to hold. No seed uses them today; a
    seed that did would otherwise ship a sentence nobody read."""
    one = errand_note([(5, 5), (6, 6)])
    assert "(1) stand on [5, 58], my pickaxe is there" in one
    assert "come to me at [6, 57] with it." in one
    assert one.endswith("I am stuck down here without it. The map can wait for that; I can't.")
    three = errand_note([(1, 1), (2, 2), (3, 3), (4, 4)])
    assert three.startswith("Four things: ")
    assert "with all of them." in three
    assert "my pickaxe is there" in three and "my rope is there" in three
