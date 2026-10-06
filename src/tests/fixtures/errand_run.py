"""A walk that actually runs the errands, for the rows only a finished errand
writes (A §1.1, §4.2, §4.4).

The verbs are computed once against a throwaway `World`, by following the route
hint over the cells that world has seen and stepping toward the cell blindly
when there is no way over them yet. That is a fixture builder, not a policy the
experiment ships: nothing in `p3focus` chooses a cell, and this only exists so a
test can reach `arrival` and `errands_completed` without hand-copying seventy
verbs.

Every coordinate here is the WORLD axis (+y down), because `World` and `route`
both speak it; the scripted R3 target is converted to the shown axis where it
is written, since that is the axis the model writes in (A §1.1).
"""

import functools

from p3focus import axis, constants, route, world as world_mod

SEED = 7
#: two steps past the return, so `after_errands` has something to count
EXTRA_STEPS = 3


@functools.lru_cache(maxsize=4)
def walk(seed=SEED):
    """`(verbs, targets)`: one verb a step, and the errand cell each step is
    for, WORLD axis. The last errand is reached on `len(verbs)`."""
    world = world_mod.World(seed)
    world.reset()
    verbs = []
    targets = []
    for cell in constants.ERRANDS[seed]:
        for _ in range(400):
            pos = tuple(int(v) for v in world.last_frame["player"]["pos"])
            if pos == tuple(cell):
                break
            verb = route.route(pos, cell, world.seen).first_step
            if verb is None:                      # no way over seen cells yet
                dx = (cell[0] > pos[0]) - (cell[0] < pos[0])
                dy = (cell[1] > pos[1]) - (cell[1] < pos[1])
                verb = ("move_right" if dx > 0 else "move_left") if dx else (
                    "move_down" if dy > 0 else "move_up")
            world.step(verb)
            verbs.append(verb)
            targets.append(tuple(cell))
        else:
            raise RuntimeError(f"seed {seed} never reached {cell}")
    return tuple(verbs), tuple(targets)


def steps(seed=SEED):
    """How many world steps the cell runs: the walk, plus a few after it."""
    return len(walk(seed)[0]) + EXTRA_STEPS


def plan(seed=SEED):
    """`{(step, round): [reply]}` for `fixtures.scripted.Script`: R3 names the
    errand cell the body is walking to, in the SHOWN axis, and R4 gives the
    walk's verb."""
    from fixtures import scripted as s

    verbs, targets = walk(seed)
    out = {}
    for i, (verb, target) in enumerate(zip(verbs, targets), start=1):
        shown = axis.shown_pos(target)
        out[(i, "R3")] = [s.r3(target=shown, do="go toward it", candidates=[shown])]
        out[(i, "R4")] = [s.r4(verb, intent=f"toward {shown}")]
    return out
