"""The gate — once per step, does anything open the maintenance asks?

A §6 (the gate row) and A §4.2 (the rows it writes). The gate reads two things,
step by step: the world's events for that step, and the size of the seen set
after it. It answers with the kinds that fired — focus and sliced open R1, then
any R1.5, then R2 when the answer is not empty — and it writes `gate_fired`,
`stall_start` and `stall_end`.

Three of the four kinds are the world's (`note_landed`, `arrival`,
`drink_crossing`). The fourth, `stall`, is the gate's own and the only thing
this module decides. An earlier design's E1 (a vital crossed), E2 (a move refused)
and E3 (a new kind of cell in view) are not here: the plan names the four events
above and no others.

No coordinates cross this boundary. An `arrival` row carries a `cell` in the
world axis (+y down) and the gate reads only that row's `kind`; the gate never
reads a position, so neither axis (world, +y down; shown, +y up) appears in this
module.
"""
import collections
from collections.abc import Mapping

from p3focus import constants

#: The four kinds the gate fires on (A §4.2), in the order `gate_fired`'s
#: `events` lists them — which is also the order B §3.1 renders their event
#: lines on R1's page (note, arrival, drink, stall).
GATE_KINDS = ("note_landed", "arrival", "drink_crossing", "stall")

#: The three of them the world writes. `stall` is the gate's own.
WORLD_GATE_KINDS = ("note_landed", "arrival", "drink_crossing")

#: The gate's own kind, in the set `observe` returns and in `gate_fired.events`.
STALL = "stall"


def opening_kinds(world_events):
    """The gate-opening kinds among one step's world events (A §4.2).

    `world_events` is an iterable of that step's `events.jsonl` rows — mappings
    with a `kind` — or of bare kind strings. Anything else is ignored, and so is
    any kind outside `WORLD_GATE_KINDS`: `errands_completed` and `death` happen
    without opening an ask. Repeats collapse, so two arrivals on one step are
    one `arrival`.

    A §4.2 makes the *world* responsible for writing `arrival` only after
    `note_landed` (before the note no errand exists for the body). The gate
    trusts that ledger rather than re-deriving it, so a world that broke the
    rule would be visible here instead of masked.
    """
    # A-QUESTION: A §4.2 gives the shape of an `events.jsonl` row but not what
    # the controller hands the gate. Rows are the primary reading (they are what
    # the world already builds); bare kind strings are accepted too, so a caller
    # that has only kinds is not forced to wrap them.
    kinds = set()
    for event in world_events or ():
        kind = event.get("kind") if isinstance(event, Mapping) else event
        if kind in WORLD_GATE_KINDS:
            kinds.add(kind)
    return kinds


class Gate:
    """The gate for one cell: call `observe` once per world step, in order.

    A §6 hands the gate the world's events and the seen set's size, step by
    step; A §4.2 gives the rows. One call per step, steps consecutive, starting
    wherever the run starts (step 0, the reset frame, is the usual first). The
    stall is counted in steps, so a repeated or skipped call would silently move
    it, and `observe` raises `ValueError` rather than let that happen.

    `seen_count` is the size of the world's seen set after that step's world
    step (A §6, D2: the walkable cells inside the 9×9 around every cell the body
    has stood on, grown every step). The gate reads its size and nothing else.

    **The step a fire belongs to.** `observe(N, …)` answers for step N's world
    events, and A §4.2's rule is that those open step N+1's asks: the note lands
    after step 10's world step and its R1 renders on step 11. Every row this
    class writes is stamped with the step it was handed, N — the shift to the
    asking step is the controller's.

    Rows are appended to `self.rows` in the order they were written; the rows of
    the newest step alone are `self.last_rows`, for a caller writing
    `events.jsonl` as it goes.
    """

    def __init__(self):
        #: The seen counts of the last `STALL_WINDOW` steps, oldest first — one
        #: longer than the stall; see `_stalled` for why the extra count matters.
        self._counts = collections.deque(maxlen=constants.STALL_WINDOW)
        self._last_step = None
        #: The step the stall in force began on, or None when not in one. Set
        #: when `stall_start` is written, cleared by `stall_end`.
        self._stall_since = None
        self.rows = []
        self.last_rows = []

    def observe(self, step, seen_count, world_events=()):
        """What fired on step `step`; the empty set means no ask (A §6, §4.2).

        Returns the kinds as a set. `gate_fired`'s `events` carries the order
        (`GATE_KINDS`), because a set has none. Writes, in this order, any
        `stall_end`, any `stall_start`, and one `gate_fired` if anything fired
        at all — to `self.rows`, and to `self.last_rows` as this step's rows.

        `seen_count` is the seen set's size after step `step`'s world step;
        `world_events` is that step's world events (see `opening_kinds`).
        """
        step = int(step)
        if self._last_step is not None and step != self._last_step + 1:
            raise ValueError(
                "the gate is observed once per step, in order: "
                f"step {self._last_step} was followed by step {step}")
        seen_count = int(seen_count)
        grew = bool(self._counts) and seen_count > self._counts[-1]
        rows = []
        fired = opening_kinds(world_events)

        # A stall ends when the set grows (A §4.2). Only a stall that was
        # announced is closed: a run of stillness shorter than STALL_LENGTH
        # never became a stall, so nothing brackets it.
        if grew and self._stall_since is not None:
            # A-QUESTION: A §4.2 puts `since_step` and `length` on one table row
            # for `stall_start` and `stall_end` together, so both are written
            # here. On `stall_start` the length is the stall so far, which is
            # always STALL_LENGTH; on `stall_end` it is the whole stall, which
            # may be longer. `since_step` is the stall's first still step — the
            # step after the last one that grew the set — not the last step that
            # grew it.
            rows.append({"step": step, "kind": "stall_end",
                         "since_step": self._stall_since,
                         "length": step - self._stall_since})
            self._stall_since = None

        if self._stalled(seen_count):
            fired.add(STALL)
            # The crossing fires on the stall's eighth still step and only
            # there, so the stall began STALL_LENGTH - 1 steps ago.
            self._stall_since = step - constants.STALL_LENGTH + 1
            rows.append({"step": step, "kind": "stall_start",
                         "since_step": self._stall_since,
                         "length": constants.STALL_LENGTH})

        if fired:
            # A-QUESTION: A §4.2's note on `gate_fired` — "the events of step N's
            # world step gate step N+1's asks" — does not say which of the two
            # steps stamps the row. It is stamped N here, the step whose events
            # opened it, so that every row the gate writes is dated by what it
            # read; the note in A is then exactly what tells a reader why the R1
            # calls in `calls.jsonl` sit one step later. Stamping it N+1 instead
            # (so `gate_fired` lines up with the calls it opened) is this one
            # expression.
            rows.append({"step": step, "kind": "gate_fired",
                         "events": [k for k in GATE_KINDS if k in fired]})

        self._counts.append(seen_count)
        self._last_step = step
        self.rows.extend(rows)
        self.last_rows = rows
        return fired

    def _stalled(self, seen_count):
        """Has the seen set just completed `STALL_LENGTH` still steps?

        Ported from an earlier implementation's stall-detection branch: the count
        has not grown across the last N steps AND the same was not already true one
        step earlier, which makes this step the stall's Nth. A crossing, not a
        state, so it fires once per stall and not once per stalled step. Every step
        is a freshly rendered frame: the body has no accumulating experience of
        having been asked, so a second tap is the same ask on a page that looks the
        same; if one does not move it, more will not.

        The window this reads is `STALL_WINDOW` = N + 1 counts, one longer than
        the stall. With only N the earlier window does not exist, `still_before`
        can never be true, and every stalled step would read as a stall's first:
        that is a bug an earlier implementation had, where a stalled round was
        tapped on every step rather than once. An earlier pure-function test missed
        it because it handed the gate unlimited history; here the window is the
        gate's own, so every test runs on the real one.
        """
        n = constants.STALL_LENGTH
        history = self._counts
        if len(history) < n:
            return False
        still_now = seen_count <= history[-n]
        still_before = len(history) > n and history[-1] <= history[-(n + 1)]
        return still_now and not still_before
