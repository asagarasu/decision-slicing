"""A walk that grows a seen set and asks a route on every step (A §6).

The seen set here is the world's rule (A §6, D2) played out by hand: the
walkable cells inside the 9×9 around every cell the body has stood on, grown
every step. The world is a hand-built one — a field with a fence across it and
a gap near the bottom — so the answers can be checked against a second,
plainly written breadth-first search that shares no code with `p3focus.route`.

Everything is WORLD axis, +y down: `move_up` is −1 in y, and the fence's gap
is at the bottom of the map.

The claim: on every step the verb the hint names steps onto a seen cell that is
one nearer the goal than the body is — a real shortest path, not a bearing —
and when it names none, there is really no way. Following it, the body walks
around the fence and arrives.
"""
import collections
import json

from p3focus.constants import WINDOW
from p3focus.route import route, route_event

SIDE = 16
#: a fence down the middle, from the top edge to y = 10; (7, 11) and below are open
FENCE = {(7, y) for y in range(11)}
WALKABLE = {(x, y) for x in range(SIDE) for y in range(SIDE)} - FENCE

START = (2, 2)            # top left, on this side of the fence
TARGET = (12, 2)          # top right, on the far side; only the gap leads there
STEP_BUDGET = 60

#: the four moves as world-axis deltas, written out here so the check owes the
#: module nothing: +y is down, so `move_up` is −1 in y (A §1.1)
DELTAS = {"move_up": (0, -1), "move_down": (0, 1), "move_left": (-1, 0), "move_right": (1, 0)}


def grow(seen, pos):
    """The world's seen set after one step from `pos` (A §6, D2): every walkable
    cell in the 9×9 around it. World axis."""
    reach = WINDOW // 2
    x, y = pos
    for cx in range(x - reach, x + reach + 1):
        for cy in range(y - reach, y + reach + 1):
            if (cx, cy) in WALKABLE:
                seen.add((cx, cy))


def goal_for(target, seen):
    """Where the way ends, by A §6's rule read here for a second time: the
    target when it is seen, else the seen cell nearest it by Manhattan
    distance, ties to the lower cell."""
    if target in seen:
        return target
    return min(seen, key=lambda c: (abs(c[0] - target[0]) + abs(c[1] - target[1]), c))


def distances_from(goal, cells):
    """Steps from every cell of `cells` to `goal` over 4-neighbour moves inside
    `cells`. A plain search, written here so the hint is checked against
    something and not against itself."""
    dist = {goal: 0}
    queue = collections.deque([goal])
    while queue:
        cur = queue.popleft()
        for dx, dy in DELTAS.values():
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt in cells and nxt not in dist:
                dist[nxt] = dist[cur] + 1
                queue.append(nxt)
    return dist


def explore(pos):
    """What the body does on a step the hint cannot answer: the first walkable
    cell of down, right, up, left. Not the hint's business — a body has to do
    something — but it has to be deterministic for the walk to be a test."""
    for verb in ("move_down", "move_right", "move_up", "move_left"):
        dx, dy = DELTAS[verb]
        if (pos[0] + dx, pos[1] + dy) in WALKABLE:
            return verb
    raise AssertionError(f"walled in at {pos}")


def walk():
    """Follow the hint from START toward TARGET, growing the seen set every
    step. Yields `(pos, seen, result)` before each move; returns at the target
    or when the budget runs out."""
    pos, seen = START, set()
    for _ in range(STEP_BUDGET):
        grow(seen, pos)
        result = route(pos, TARGET, seen)
        yield pos, set(seen), result
        if pos == TARGET:
            return
        verb = result.first_step or explore(pos)
        dx, dy = DELTAS[verb]
        pos = (pos[0] + dx, pos[1] + dy)


def test_every_step_the_hint_names_is_one_step_along_a_real_shortest_path():
    """And where it names none there is really no way: the body either stands
    on the goal or cannot reach it over the cells it has seen."""
    steps = 0
    for pos, seen, result in walk():
        steps += 1
        goal = goal_for(TARGET, seen)
        dist = distances_from(goal, seen)
        if result.first_step is None:
            assert goal == pos or pos not in dist, (pos, goal)
            continue
        dx, dy = DELTAS[result.first_step]
        nxt = (pos[0] + dx, pos[1] + dy)
        assert nxt in seen and nxt in WALKABLE, (pos, result.first_step)
        assert dist[nxt] == dist[pos] - 1, (pos, result.first_step, dist[pos], dist[nxt])
    assert steps > 20, "a walk short enough to be a straight line proves nothing"


def test_the_hint_is_direct_exactly_when_the_target_is_in_the_seen_set():
    """`direct` is about the goal, not the distance: it says the way ends on
    the cell the body named. (With no way at all there is no verb and `direct`
    is False; that is the other test's business.)"""
    for pos, seen, result in walk():
        if result.first_step is not None:
            assert result.direct is (TARGET in seen), (pos, result)


def test_the_walk_meets_all_three_sentences_and_each_matches_its_step():
    """The fence makes one walk say all three: the target is out of the seen
    set at first (3), then the fence cuts every way to it (1), and at the end
    the body has seen the target itself (2)."""
    said = {}
    for pos, seen, result in walk():
        said.setdefault(result.sentence_id, (pos, result.sentence))
        assert result.sentence.count("\n") == 0
        if result.sentence_id == 1:
            assert result.sentence == "No way there over cells you have seen yet."
        else:
            assert result.first_step in result.sentence
            assert ("past the cells you know" in result.sentence) is (result.sentence_id == 3)
    assert sorted(said) == [1, 2, 3], said


def test_following_the_hint_walks_the_body_around_the_fence_to_the_target():
    """The whole point of the aid: over a seen set that grows as the body
    moves, the hint gets it there. It also never sends it into the fence."""
    seen_at_end, last = set(), None
    for pos, seen, result in walk():
        last, seen_at_end = pos, seen
    assert last == TARGET, last
    assert not seen_at_end & FENCE, "the seen set is walkable cells only"
    assert TARGET in seen_at_end


def test_one_event_row_per_step_of_the_walk_and_every_row_is_json():
    """A §4.2: `target`, `first_step` or null, the sentence's number."""
    rows = [route_event(step, TARGET, result)
            for step, (_pos, _seen, result) in enumerate(walk())]
    assert len(rows) > 20
    for step, row in enumerate(rows):
        assert row["step"] == step and row["kind"] == "route"
        assert row["target"] == list(TARGET)
        assert row["sentence_id"] in (1, 2, 3)
        assert json.loads(json.dumps(row)) == row
    assert {r["first_step"] for r in rows} - {None} <= set(DELTAS)
    # the arrival step: the body stands on the cell it named and is told there is
    # no way there, the old line's behaviour and the module's `# A-QUESTION:`
    assert rows[-1] == {"step": len(rows) - 1, "kind": "route", "target": list(TARGET),
                        "first_step": None, "sentence_id": 1}
