"""The two coordinate axes (A §1.1; a design ruling of 09-15, the original coordinates.md).

The world stores and logs **+y down**, Crafter's own frame. The model reads
**+y up**: `y_shown = 63 - y_world`, x unchanged. The map is an involution, so
the same function reads a model-written coordinate back. Direction words are
screen-relative and carry no sign in either axis.
"""
from p3focus import constants

#: facing / move deltas in the WORLD axis (+y down) -> the screen word
FACING_NAMES = {(0, -1): "up", (0, 1): "down", (-1, 0): "left", (1, 0): "right"}
#: the same deltas -> the phrase the outcome sentence uses (A §1.3)
DIRS = {(0, -1): "above you", (0, 1): "below you", (-1, 0): "to your left", (1, 0): "to your right"}


def shown_y(y):
    """World y -> shown y, and back (an involution): `63 - y` for a 64-cell world."""
    return constants.WORLD_SIZE - 1 - int(y)


def shown_pos(pos):
    """World `[x, y]` -> shown `[x, y]`, and back (the same involution)."""
    return [int(pos[0]), shown_y(pos[1])]


def facing_word(facing):
    """The frame's `[dx, dy]` -> up/down/left/right (world deltas, screen words)."""
    return FACING_NAMES.get((int(facing[0]), int(facing[1])), "?")
