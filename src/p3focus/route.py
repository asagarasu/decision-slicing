"""The route hint — A §6 (the `route` row), A §1.3 (the `route` field of `State`),
A §4.2 (the `route` event).

A single locomotion exception (a design ruling of 09-22: "locomotion is not the
capability under test"). Given where the body stands, the cell it named, and the
cells it has seen, this says which of the four moves a shortest way there begins
with, and the one sentence that tells the body so. It holds nothing, ranks nothing
and decides no salience: the cell is always the model's, never chosen here.

**Axis.** Every coordinate in and out of this module is the WORLD axis, +y down
(A §1.1), as `(x, y)`. The shown axis, +y up, never reaches here: the
controller reads the model's cell back through the world's `shown_pos`
involution before calling. The verbs this module names — `move_up`,
`move_down`, `move_left`, `move_right` — are screen words and carry no sign,
so they are the same in either axis; in the world axis `move_up` is −1 in y.

**The seen set is the world's** (A §6, D2: the walkable cells, water included,
inside the 9×9 around every cell the body has stood on, grown every step).
Nothing here grows it, and nothing here reads the world: the search looks only
inside the set it is handed, and never changes it.
"""

import collections

#: the four moves as world-axis deltas (+y down, so `move_up` is −1 in y).
#: The insertion order is the original harness's (its `FACING_NAMES`) and decides
#: which of several equally short ways the search finds first, hence which verb
#: comes back on a tie; keeping the order keeps the original run an answer key for
#: the verb and not only for the distance.
MOVE_DELTAS = {(0, -1): "up", (0, 1): "down", (-1, 0): "left", (1, 0): "right"}

#: the four action names, in the same order
MOVE_VERBS = tuple("move_" + name for name in MOVE_DELTAS.values())

#: the three sentences, by `sentence_id` − 1: no way (1), the target itself (2),
#: the seen cell nearest it (3). The original harness's exact strings; a page
#: carries exactly one of them and nothing else says the way (B §3.5, §3.6, §7).
SENTENCES = (
    "No way there over cells you have seen yet.",
    "The way there, over cells you have seen, begins with {verb}.",
    "Over cells you have seen, the way toward it begins with {verb}; past the cells "
    "you know, the rest is unseen.",
)


class RouteResult(collections.namedtuple("RouteResult",
                                         "first_step direct sentence_id sentence")):
    """One answer of the hint (A §6): `first_step`, a move verb or None;
    `direct`, whether the way ends on the target itself; `sentence_id`, 1, 2 or
    3; `sentence`, that sentence, ready for the page."""

    __slots__ = ()


def route_first_step(pos, target, cells):
    """The first move of a shortest way from `pos` to `target` over `cells` (A §6).

    All three are WORLD axis, +y down: `pos` and `target` are `(x, y)` pairs,
    `cells` the seen set. A breadth-first search over the four neighbour moves,
    entering only cells in the set. If `target` is in the set the way ends
    there and `direct` is True; otherwise it ends at the seen cell nearest the
    target by Manhattan distance — ties to the lower `(x, y)`, so the answer is
    reproducible — and `direct` is False.

    Returns `(verb, direct)`, the verb one of `MOVE_VERBS`, or `(None, False)`
    when there is no way over seen cells at all, when the body already stands
    where the way would end, or when the set is empty. Note that an unreachable
    target reports `direct` False even if it is itself seen: with no verb there
    is no way to be direct about.

    Pure; nothing here reads the world or changes `cells`.
    """
    pos = (int(pos[0]), int(pos[1]))
    target = (int(target[0]), int(target[1]))
    cells = _as_cells(cells)
    if pos == target or not cells:
        return None, False
    direct = target in cells
    goal = target if direct else min(
        cells, key=lambda c: (abs(c[0] - target[0]) + abs(c[1] - target[1]), c))
    if goal == pos:
        return None, False
    prev = {pos: None}
    queue = collections.deque([pos])
    while queue:
        cur = queue.popleft()
        if cur == goal:
            break
        for (dx, dy) in MOVE_DELTAS:
            nxt = (cur[0] + dx, cur[1] + dy)
            if nxt in cells and nxt not in prev:
                prev[nxt] = cur
                queue.append(nxt)
    if goal not in prev:
        return None, False
    step = goal
    while prev[step] != pos:
        step = prev[step]
    delta = (step[0] - pos[0], step[1] - pos[1])
    return "move_" + MOVE_DELTAS[delta], direct


def route_hint_line(verb, direct):
    """The one sentence the page carries for a hint (A §6; B §3.5, §3.6, §7).

    `verb` is `route_first_step`'s first step or None, `direct` its second
    value. Three sentences and no fourth; the verb is a screen word, so no
    axis is spoken.
    """
    if verb is None:
        return SENTENCES[0]
    return SENTENCES[1 if direct else 2].format(verb=verb)


def route(pos_world, target_world, seen):
    """The hint for one named cell: the first move and the sentence (A §6, §1.3).

    `pos_world` is where the body stands and `target_world` the cell it named —
    focus's R3 `target` on R4's page, flat's and chat's `destination` on the
    next step's page — both WORLD axis, +y down, the controller having already
    read the model's shown-axis cell back. `seen` is the world's seen set, a
    set of world-axis `(x, y)` pairs; any other iterable of pairs is read as
    one. Returns a `RouteResult`. Called only when a cell was named: there is
    no hint for `target: null` and no row for it either (A §1.3).
    """
    # A §6 (a design decision of 09-24 on this module's open question): the
    # controller does not call this when the named cell is the body's own; handed
    # that case anyway, the function still answers the original `(None, False)`,
    # sentence 1.
    verb, direct = route_first_step(pos_world, target_world, seen)
    sentence_id = 1 if verb is None else (2 if direct else 3)
    return RouteResult(verb, direct, sentence_id, route_hint_line(verb, direct))


def route_event(step, target_world, result):
    """The `route` row of `events.jsonl` (A §4.2), as a JSON-ready dict.

    `step` is the world step the hint served, `target_world` the cell that was
    routed to in the WORLD axis (logs are world axis, A §4) and `result` what
    `route` returned. `first_step` is the verb or None; the row is written by
    the caller that owns the file.
    """
    # A §4.2 (a design decision of 09-24 on this module's open question): the
    # row's field is `sentence_id`, the number 1–3, never the text.
    return {"step": int(step),
            "kind": "route",
            "target": [int(target_world[0]), int(target_world[1])],
            "first_step": result.first_step,
            "sentence_id": result.sentence_id}


def _as_cells(seen):
    """The seen set as something `in` can be asked of, without copying a set.

    The world owns the set (A §6) and hands it over as a set of world-axis int
    pairs; a list or any other iterable of pairs is converted here rather than
    silently missing every membership test, which would read as "no way there".
    """
    if isinstance(seen, (set, frozenset)):
        return seen
    return {(int(c[0]), int(c[1])) for c in seen}
