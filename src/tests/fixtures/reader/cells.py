"""Hand-written cell directories for the reader's tests (A §4).

Five cells over three arms, each written by `write_cell` through the real
writers in `p3focus.cell` — `EventLog`, `ActionLog`, `FrameLog`,
`write_manifest`, `write_summary` — so every row is A §4's shape and a row that
is not raises here, in the fixture, rather than quietly in the reader.

    sys.path.insert(0, ".../src/tests/fixtures/reader")   # what the tests do
    import cells
    made = cells.write_all(tmp_path)        # {name: Path}

    python src/tests/fixtures/reader/cells.py /tmp/reader_fixtures   # to look at them

(The dotted path `tests.fixtures.reader.cells` is not available: an unrelated
`tests` package is installed in the venv and shadows `src/tests`.)

**The fixture's world is not Crafter's.** It is a hand-drawn 64×64 map — grass,
one stone block, one water pool, one sand block, one cow — chosen so that every
number a test asserts can be counted by hand: the sand is where the body's last
leg walks, so drink falls a step at a time; the stone is inside a window the
body passes, so a non-walkable cell is in view; the cow stands on grass inside
several windows and never moves, so the one cell the reader's seen set can
never see is exactly the cow's (the reader's rule R3 reads names out of the
window, and the window draws the cow over the grass under it).

**The meters follow two rules and no more** (A §1.1): a step that ends in water
gives 1 drink, a step that ends on sand takes 1. Health is hand-set per cell,
which is where a health fall in `drink_crossing` comes from; nothing here
simulates Crafter's damage.

The five cells, and what each one is for:

`focus_s7_completed` (focus, 7)
    the errands finished at step 82 and twenty steps after them; a retry, a
    defaulted R2, four list entries, a focus that changes five times, eight held
    destinations with every one of A §3.1's five ends, and a `summary.json`
    that agrees with every row.
`flat_s10_died` (flat, 10)
    dead at step 30, a destination named twice, one retry, an agreeing
    `summary.json`.
`focus_s10_disagrees` (focus, 10)
    25 quiet steps, two held destinations, and a `summary.json` that claims a
    finished run.
`flat_s7_ledger` (flat, 7)
    the body really stands on errand 0 and no row says so; a row claims errand
    1 on a step the body was elsewhere. Its `arrival` row is written without
    `first`, the shape `world._arrivals` writes. No `summary.json`.
`sliced_s11_holds` (sliced, 11)
    the third arm: no R2 and no focus, four held destinations, one of them
    replaced at the note's asks and one still held when the cell ends.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

_SRC = Path(__file__).resolve().parents[3]      # src/, so this runs as a script too
if str(_SRC) not in sys.path:
    sys.path.insert(0, str(_SRC))

from p3focus import cell as cellmod    # noqa: E402
from p3focus import constants          # noqa: E402

SIDE = constants.WORLD_SIZE
MOVES = {"move_right": (1, 0), "move_left": (-1, 0), "move_up": (0, -1), "move_down": (0, 1)}

#: the hand-drawn map's three features; everything else is grass
STONE = ((44, 46), (28, 34))     # x range, y range — non-walkable, seen from the east leg
WATER = ((38, 40), (38, 40))     # the west leg walks through it; walkable, gives drink
SAND = ((28, 36), (8, 20))       # the last leg ends on it; walkable, takes drink
COW = (40, 36)                   # never moves; the one cell the reader's seen set misses


def material_at(x, y):
    """The fixture world's material for a WORLD-axis cell."""
    if not (0 <= x < SIDE and 0 <= y < SIDE):
        return "out_of_bounds"
    for (x0, x1), (y0, y1), name in ((*STONE, "stone"), (*WATER, "water"), (*SAND, "sand")):
        if x0 <= x <= x1 and y0 <= y <= y1:
            return name
    return "grass"


def window_rows(pos):
    """A §1.2's `window`: 9 rows of names, north to south, the body in the middle
    drawn over its own cell, the cow drawn over hers, out of bounds padded."""
    px, py = pos
    r = constants.WINDOW // 2
    rows = []
    for y in range(py - r, py + r + 1):
        row = []
        for x in range(px - r, px + r + 1):
            if not (0 <= x < SIDE and 0 <= y < SIDE):
                row.append("out_of_bounds")
            elif (x, y) == (px, py):
                row.append("player")
            elif (x, y) == COW:
                row.append("cow")
            else:
                row.append(material_at(x, y))
        rows.append(row)
    return rows


def walk(legs):
    """`(positions, verbs)` from `[(verb, n), …]`, starting at the spawn.

    `positions[i]` is where the body stands after step `i`, so `positions[0]` is
    the spawn and there is one more position than there are verbs.
    """
    pos = tuple(constants.SPAWN)
    positions, verbs = [pos], []
    for verb, n in legs:
        dx, dy = MOVES[verb]
        for _ in range(n):
            pos = (pos[0] + dx, pos[1] + dy)
            positions.append(pos)
            verbs.append(verb)
    return positions, verbs


def meters(positions, health_plan):
    """`(drinks, healths)`, one per step including 0. Drink starts at A §1.1's 3,
    rises by 1 on a step that ends in water (to 9) and falls by 1 on a step that
    ends on sand (never below 0); health is 9 unless `health_plan` names a step."""
    drink, drinks, healths = 3, [3], [health_plan.get(0, 9)]
    for step, pos in enumerate(positions[1:], 1):
        ground = material_at(*pos)
        if ground == "water":
            drink = min(9, drink + 1)
        elif ground == "sand":
            drink = max(0, drink - 1)
        drinks.append(drink)
        healths.append(health_plan.get(step, healths[-1]))
    return drinks, healths


def frame_row(step, pos, verb, drink, health, previous):
    """A §1.2's frame, schema "2". `previous` is the frame before it, for deltas."""
    dx, dy = MOVES.get(verb, (0, 1))    # frame 0 faces down, as a fresh Player does
    inventory = {"health": health, "food": 9, "drink": drink, "energy": 9,
                 "sapling": 0, "wood": 0, "stone": 0, "coal": 0, "iron": 0, "diamond": 0}
    deltas = {"inventory": {}, "achievements": {}}
    if previous is not None:
        deltas["inventory"] = {k: v - previous["inventory"][k]
                               for k, v in inventory.items() if v != previous["inventory"][k]}
    return {
        "schema_version": constants.FRAME_SCHEMA_VERSION,
        "step": step,
        "daylight": 0.5,
        "player": {"pos": [pos[0], pos[1]], "facing": [dx, dy], "sleeping": False,
                   "health": health, "food": 9, "drink": drink, "energy": 9},
        "inventory": inventory,
        "window": window_rows(pos),
        "standing_on": material_at(*pos),
        "achievements": {},
        "deltas": deltas,
    }


def _rounds(arm, step, gated, deletes, r3_steps=()):
    """The rounds one step ran, in order (A §3.1, §3.2, §3.3): one for a bare
    arm, and for focus the asks on a gated step — R1, one R1.5 per delete, R2 —
    before the acting rounds. R4 runs every step; **R3 only on the steps the
    hold asked on** (A §3.1, the hold: missing, reached, no way, event)."""
    if arm == "flat":
        return ["flat"]
    if arm == "chat":
        return ["chat"]
    asks = []
    if step in gated:
        asks = ["R1"] + ["R1.5"] * deletes.get(step, 0) + (["R2"] if arm == "focus" else [])
    return asks + (["R3"] if step in r3_steps else []) + ["R4"]


def call_rows(arm, n_steps, gated, deletes, retries, defaulted_rounds, r3_steps=(),
              named=None):
    """A §4.1's rows: one per model call, plus one more for each retry — the
    same page sent again with the reason line (`attempt` 2). A retried round's
    first reply is not valid; its second is, unless the round defaulted (A §3.4),
    in which case neither is.

    `named` is `{step: [x, y]}`, the cells a flat cell's replies named: since the
    hold (A §7 D9) the reader counts `destinations_named` off these replies and
    not off the action rows, whose `destination` is the cell in force, so a flat
    cell's `parsed` carries what its reply said.
    """
    named = dict(named or {})
    rows, call_no = [], 0
    for step in range(1, n_steps + 1):
        rounds = _rounds(arm, step, gated, deletes, r3_steps)
        if step in retries and retries[step] not in rounds:
            raise ValueError(f"step {step} ran {rounds}, so it cannot have retried "
                             f"{retries[step]}")
        for round_name in rounds:
            retried = retries.get(step) == round_name
            for attempt in range(1, 2 + retried):
                call_no += 1
                valid = not retried or (attempt == 2 and (step, round_name)
                                        not in defaulted_rounds)
                rows.append({
                    "call_no": call_no, "step": step, "round": round_name,
                    "attempt": attempt, "transport_tries": 1,
                    "prompt": f"<{round_name} page, step {step}>",
                    "page_sha256": None if arm == "chat" else f"{call_no:064x}",
                    "prefix_sha256": f"{call_no:064x}" if arm == "chat" else None,
                    "grammar_id": f"{arm}_{round_name.lower().replace('.', '_')}",
                    "reply_text": "{}", "valid": valid,
                    "parsed": ({"destination": named.get(step)}
                               if arm == "flat" and valid else {}),
                    "reason": None if valid else "the same page, one reason line",
                    "elapsed_s": 0.5, "tokens": {"prompt": 100, "eval": 20},
                })
    return rows


def hold(r3_plan, positions, gated, n_steps):
    """The held destination, step by step (A §3.1, the hold; A §4.2's rows).

    `r3_plan` is `[(step, occasion, answer), …]`: the steps R3 rendered on, why
    it rendered (`missing`, `reached`, `no_way`, `event`), and the cell the
    reply named, world axis, or None for the exploring branch. Returns
    `(before, after, held)` — `before[step]` are the `(kind, fields)` rows the
    occasion writes (a hold ends at the START of the step, before R3 is asked),
    `after[step]` are the rows the answer writes, and `held[step]` is the
    destination held during that step's R4, A §4.3's `target`, None on a step
    that explored.

    A plan the harness could not have written raises here rather than becoming
    rows no reader should ever meet: a `reached` whose step does not start with
    the body on the held cell, an `event` on a step that ran no asks, a
    `missing` with a destination still held, an occasion with nothing to end, a
    step that holds nothing and does not ask, or a step that stands on the held
    cell and does not.
    """
    asks = {int(step): (occasion, answer) for step, occasion, answer in r3_plan}
    before, after, held_at = {}, {}, {}
    held = None                      # (cell, the step it was named on)
    for step in range(1, n_steps + 1):
        standing = tuple(positions[step - 1])     # where the body is when the step starts
        rows_before, rows_after = [], []
        if step not in asks:
            if held is None:
                raise ValueError(f"step {step} holds nothing and does not ask; A §3.1 "
                                 f"renders R3 on every step that starts with no hold")
            if held[0] == standing:
                raise ValueError(f"step {step} starts on the held cell {list(standing)}; "
                                 f"A §3.1 reaches it and asks")
        else:
            occasion, answer = asks[step]
            if occasion == "missing":
                if held is not None:
                    raise ValueError(f"step {step} is missing but holds {list(held[0])}")
            elif occasion in ("reached", "no_way", "event"):
                if held is None:
                    raise ValueError(f"step {step} is {occasion} and holds nothing")
            else:
                raise ValueError(f"step {step}: {occasion!r} is not one of A §3.1's four")
            if occasion == "reached":
                if held[0] != standing:
                    raise ValueError(f"step {step} is reached, but it starts at "
                                     f"{list(standing)} and holds {list(held[0])}")
                rows_before.append(("destination_reached",
                                    {"cell": list(held[0]), "held_steps": step - held[1]}))
                held = None
            elif occasion == "no_way":
                rows_before.append(("destination_cleared",
                                    {"cell": list(held[0]), "held_steps": step - held[1],
                                     "reason": "no_way"}))
                held = None
            elif occasion == "event" and step not in gated:
                raise ValueError(f"step {step} is an event ask, but no asks ran on it")
            if answer is None:
                # the exploring branch: what is held is dropped, and a step that
                # held nothing simply explores and writes no row (A §3.1)
                if held is not None:
                    rows_after.append(("destination_cleared",
                                       {"cell": list(held[0]), "held_steps": step - held[1],
                                        "reason": "dropped"}))
                    held = None
            else:
                cell = tuple(int(v) for v in answer)
                if held is not None and held[0] != cell:
                    rows_after.append(("destination_cleared",
                                       {"cell": list(held[0]), "held_steps": step - held[1],
                                        "reason": "replaced"}))
                    held = None
                if held is None:                  # the same cell again keeps its own step
                    rows_after.append(("destination_chosen", {"cell": list(cell)}))
                    held = (cell, step)
        before[step], after[step] = rows_before, rows_after
        held_at[step] = None if held is None else list(held[0])
    return before, after, held_at


def write_cell(dest, *, arm, seed, legs, health_plan=None, ops_rows=(), focus_plan=(),
               gated=(), retries=None, invalid=(), defaulted=(), destinations=None,
               death_step=None, route_steps=(), arrivals="derive", r3_plan=(),
               summary=None):
    """Write one cell directory and return its path (A §4).

    `legs` is the walk; `ops_rows` are `(step, source, ops, list_after)`;
    `focus_plan` is `[(from_step, focus_id), …]`, an id holding until the next
    pair; `gated` are the steps whose asks ran; `retries` is `{step: round}`;
    `invalid` and `defaulted` are `(step, round, …)` rows; `destinations` is
    `{step: [x, y]}`, the cells a flat cell's replies named — written both to
    those steps' action rows and to their `parsed` replies. (A live flat cell
    has held its destination since 09-25, A §7 D9, so its action row carries the
    cell in force on **every** step it is held; these cells exercise the reader's
    arithmetic over given rows, not the shape the harness now writes, and the
    hold's own rows are tested against a real run in
    `test_trace_flat_hold.py`.) `arrivals` is "derive" (A §1.1's rule over the positions)
    or an explicit list of rows to plant instead; `r3_plan` is the hold (see
    `hold`), which decides A §4.2's three destination rows, A §4.3's `target`,
    and the steps whose `calls.jsonl` carries an R3 row. A focus or sliced cell
    written without one asks R3 on no step at all.
    """
    dest = Path(dest)
    dest.mkdir(parents=True, exist_ok=True)
    health_plan = dict(health_plan or {})
    retries = dict(retries or {})
    destinations = dict(destinations or {})
    positions, verbs = walk(legs)
    n_steps = len(verbs)
    drinks, healths = meters(positions, health_plan)
    errands = [tuple(c) for c in constants.ERRANDS[seed]]
    deletes = {step: sum(1 for op in ops if op.get("op") == "delete")
               for step, _source, ops, _after in ops_rows}
    if r3_plan and arm not in ("focus", "sliced"):
        raise ValueError(f"{arm} has no R3 and holds no destination (A §3.1)")
    r3_steps = {int(step) for step, _occasion, _answer in r3_plan}
    before_r3, after_r3, held_at = (
        hold(r3_plan, positions, set(gated), n_steps) if r3_plan else ({}, {}, {}))

    events = cellmod.EventLog(dest / "events.jsonl")
    actions = cellmod.ActionLog(dest / "actions.jsonl")
    frames = cellmod.FrameLog(dest / "frames.jsonl")
    calls = cellmod.JsonlLog(dest / "calls.jsonl")

    previous = None
    for step in range(0, n_steps + 1):
        row = frame_row(step, positions[step], None if step == 0 else verbs[step - 1],
                        drinks[step], healths[step], previous)
        frames.frame(row)
        previous = row

    # -- the rows, step by step, in the order A §4.2 has the pieces write them --
    ops_by_step = {step: (source, ops, after) for step, source, ops, after in ops_rows}
    invalid_by_step, defaulted_by_step = {}, {}
    for step, round_name, reason in invalid:
        invalid_by_step.setdefault(step, []).append((round_name, reason))
    for step, round_name, default in defaulted:
        defaulted_by_step.setdefault(step, []).append((round_name, default))
    focus_at, current = {}, None
    for step in range(1, n_steps + 1):
        for from_step, focus_id in focus_plan:
            if from_step == step:
                current = focus_id
        focus_at[step] = current

    planted = {}
    for row in (() if arrivals == "derive" else arrivals):
        planted.setdefault(int(row["step"]), []).append(row)

    reached, list_now = {}, []
    for step in range(1, n_steps + 1):
        pos = positions[step]
        opened = []          # the gate kinds this step's world rows carry (A §4.2)
        if step == constants.NOTE_STEP:
            events.event(step, "note_landed")
            opened.append("note_landed")
        elif step > constants.NOTE_STEP and arrivals == "derive":
            visits_left = any(i not in reached for i in range(len(errands) - 1))
            for index, errand in enumerate(errands):
                if errand != pos or index in reached:
                    continue
                if index == len(errands) - 1 and visits_left:
                    continue
                reached[index] = step
                events.event(step, "arrival", cell=list(errand), index=index)
                opened.append("arrival")
                if index == len(errands) - 1:
                    events.event(step, "errands_completed")
        for row in planted.get(step, ()):
            # straight through `JsonlLog`, not `EventLog`: this is the shape
            # `world._arrivals` writes, without `EVENT_FIELDS`' `first`
            events.append(dict(row))
        if healths[step] < healths[step - 1] or (drinks[step] == 0 and drinks[step - 1] > 0):
            events.event(step, "drink_crossing", drink_from=drinks[step - 1],
                         drink_to=drinks[step], health_from=healths[step - 1],
                         health_to=healths[step])
            opened.append("drink_crossing")
        if step == death_step:
            events.event(step, "death")
        if step in ops_by_step:
            source, ops, after = ops_by_step[step]
            for op in ops:
                if op.get("op") == "delete":
                    events.event(step, "delete_confirmed", id=op["id"])
            events.event(step, "ops_applied", source=source, ops=list(ops),
                         list_after=[dict(e) for e in after])
            list_now = list(after)
        chose = focus_at[step] is not None and focus_at.get(step - 1) != focus_at[step]
        if step in gated and chose:
            events.event(step, "focus_chosen", id=focus_at[step])
        if step > 1 and focus_at[step] is None and focus_at.get(step - 1) is not None:
            events.event(step, "focus_none", reason="empty")
        # the hold, in the controller's own order (A §3.1): the occasion ends
        # the old destination before R3 is asked, the answer writes what it did
        # after. A step's `reply_invalid` rows are one block between them,
        # which is R3's own order and one row out of place for an earlier round
        for kind, fields in before_r3.get(step, ()):
            events.event(step, kind, **fields)
        for round_name, reason in invalid_by_step.get(step, ()):
            events.event(step, "reply_invalid", round=round_name, attempt=1, reason=reason)
        for round_name, default in defaulted_by_step.get(step, ()):
            events.event(step, "reply_defaulted", round=round_name, default=default)
        for kind, fields in after_r3.get(step, ()):
            events.event(step, kind, **fields)
        if step in route_steps:
            events.event(step, "route", target=list(pos), first_step=verbs[step - 1],
                         sentence_id=2)
        if step + 1 in gated:
            # A §4.2: stamped with the step whose world rows opened it, one
            # before the step whose asks it gates
            events.event(step, "gate_fired", events=opened or ["stall"])

        n_calls = (len(_rounds(arm, step, gated, deletes, r3_steps))
                   + (1 if step in retries else 0))
        actions.action(
            step=step, arm=arm, action=verbs[step - 1], intent=f"step {step}",
            focus_id=focus_at[step] if arm == "focus" else None,
            # A §4.3: the destination held during this step's R4, null where
            # the step explored — not the cell the body stands on
            target=held_at.get(step) if arm in ("focus", "sliced") else None,
            destination=destinations.get(step), route_first_step=(
                verbs[step - 1] if step in route_steps else None),
            pos_before=list(positions[step - 1]), pos_after=list(pos),
            moved=positions[step] != positions[step - 1],
            standing_on_after=material_at(*pos), drink_after=drinks[step],
            health_after=healths[step], list_size=len(list_now), n_calls=n_calls)

    defaulted_rounds = {(step, round_name) for step, round_name, _ in defaulted}
    for row in call_rows(arm, n_steps, set(gated), deletes, retries, defaulted_rounds,
                         r3_steps, named=destinations):
        calls.append(row)
    cellmod.write_manifest(dest / "manifest.json", arm=arm, seed=seed, steps=n_steps,
                           server="http://127.0.0.1:8080", model="qwen3.5-9b-bf16",
                           grammar_ids=[f"{arm}_r3", f"{arm}_r4"])
    if summary is not None:
        cellmod.write_summary(dest / "summary.json", summary)
    return dest


# -- the four cells ------------------------------------------------------------

#: seed 7's cells, world axis: [42, 40] [22, 24] [32, 32]; shown axis, which is
#: what the note said and what a body writing an entry would copy: [42, 23]
#: [22, 39] [32, 31].
MAP_ENTRY = {"id": "e1", "name": "map_world", "until": "every walkable cell mapped"}
ERRAND_ENTRY = {"id": "e2", "name": "stand on [42, 23] for the pickaxe",
                "until": "the pickaxe is picked up", "why": "my human asked for it"}
SHORE_ENTRY = {"id": "e3", "name": "walk the shore at [10, 10]",
               "until": "every cell of it is mapped"}
AGAIN_ENTRY = {"id": "e4", "name": "check the rope spot at [22, 39] again",
               "until": "I have looked twice", "why": "it felt wrong"}


def focus_s7_completed(dest):
    """focus, seed 7, 102 steps: the errands finished at 82, 20 steps after them.

    The walk: ten steps of nothing at the spawn (so the note lands at 10 with
    the body where it started), east to x=42, south to errand 0 at step 28, west
    through the water to x=22, north to errand 1 at step 64, south to y=32, east
    to the return at step 82, then twenty steps north, the last nine of them on
    sand, which empties the drink at 99 and lets health fall for the three steps
    after it.

    The hold (A §3.1): eight destinations over eleven asks, with all five ends —
    four reached, one replaced at an event, one dropped at an event, one cleared
    `no_way`, and the last one still held when the cell ends (open). Step 29
    both reached the held cell and ran the gate's asks, which A §3.1 reads as
    `reached`, and step 11 names the held cell again and keeps it.
    """
    return write_cell(
        dest, arm="focus", seed=7,
        legs=[("move_right", 1), ("move_left", 1)] * 5 + [
            ("move_right", 10), ("move_down", 8), ("move_left", 20), ("move_up", 16),
            ("move_down", 8), ("move_right", 10), ("move_up", 20)],
        health_plan={100: 8, 101: 7, 102: 6},
        gated=(11, 29, 65, 83, 100, 101, 102),
        ops_rows=[
            (11, "R1", [{"op": "add", "name": ERRAND_ENTRY["name"],
                         "until": ERRAND_ENTRY["until"], "why": ERRAND_ENTRY["why"]}],
             [MAP_ENTRY, ERRAND_ENTRY]),
            (65, "R1", [{"op": "add", "name": SHORE_ENTRY["name"],
                         "until": SHORE_ENTRY["until"]}],
             [MAP_ENTRY, ERRAND_ENTRY, SHORE_ENTRY]),
            (83, "R1", [{"op": "delete", "id": "e2"}], [MAP_ENTRY, SHORE_ENTRY]),
            (101, "R1", [{"op": "delete", "id": "e1"}, {"op": "delete", "id": "e3"}], []),
            (102, "R1", [{"op": "add", "name": AGAIN_ENTRY["name"],
                          "until": AGAIN_ENTRY["until"], "why": AGAIN_ENTRY["why"]}],
             [AGAIN_ENTRY]),
        ],
        focus_plan=[(1, "e1"), (11, "e2"), (83, "e3"), (100, "e1"), (101, None), (102, "e4")],
        retries={29: "R2", 30: "R3"},
        invalid=[(29, "R2", "no entry with id e9"), (30, "R3", "target [70, 3] is off the map")],
        defaulted=[(29, "R2", "e2")],
        route_steps=(11, 83),
        r3_plan=[
            (1, "missing", [42, 32]),    # the first step holds nothing
            (11, "event", [42, 32]),     # the note's asks, and the same cell again: kept
            (21, "reached", [42, 40]),   # the body starts 21 on it; errand 0 named next
            (29, "reached", None),       # reached, and gated too; the answer explores
            (30, "missing", [22, 40]),   # 29 left nothing held, so 30 asks again
            (49, "reached", [20, 24]),   # a cell two west of errand 1, never stood on
            (65, "event", [22, 32]),     # another cell at an event: replaced
            (73, "reached", [10, 10]),   # the shore, which this walk never reaches
            (83, "event", None),         # dropped at an event; the step explores
            (84, "missing", [45, 31]),   # inside the stone block: no way there
            (90, "no_way", [32, 12]),    # cleared, and the new one is still held at 102
        ],
        summary={
            # the hand count this fixture is built to have; the reader must
            # arrive at every one of these from the rows alone
            "errands_completed": True, "cells_reached": 3, "steps_survived": 102,
            "died": False, "first_errand_step": 28, "note_to_first_errand_steps": 18,
            "after_errands": {"completed_step": 82, "steps": 20, "new_cells": 180,
                              "focus_ids": {"errand": 1, "map_world": 1, "other": 17,
                                            "none": 1}},
            "invalid_replies": {"R2": 1, "R3": 1}, "defaulted_replies": {"R2": 1},
            "focus_is_errand_fraction": 73 / 102,
            # A §4.4 gates the two count fields by arm, and `trace.summary`
            # writes null for the one that does not apply; the reader counts 0
            # rows and the two readings agree (`NULL_IS_ZERO_FIELDS`)
            "destinations_named": None, "destinations_chosen": 8,
            "n_calls": 132, "wall_s": 612.5,
        })


def flat_s10_died(dest):
    """flat, seed 10, 30 steps, dead at the last one, a destination named twice.

    The body never leaves the neighbourhood of the spawn; it stands on the spawn
    at step 20, which is seed 10's return cell, and no arrival counts there
    because neither visit has happened (A §1.1). Health is hand-set to fall from
    step 26 and reach 0 at 30.
    """
    return write_cell(
        dest, arm="flat", seed=10,
        legs=[("move_right", 5), ("move_down", 5), ("move_left", 5),
              ("move_up", 5), ("move_right", 5), ("move_down", 5)],
        health_plan={26: 6, 27: 4, 28: 2, 29: 1, 30: 0},
        death_step=30,
        ops_rows=[(12, "flat", [{"op": "add", "name": "fetch the rope at [14, 33]",
                                 "until": "the rope is in hand"}],
                   [MAP_ENTRY, {"id": "e2", "name": "fetch the rope at [14, 33]",
                                "until": "the rope is in hand"}])],
        retries={14: "flat"},
        invalid=[(14, "flat", "destination [90, 2] is off the map")],
        destinations={12: [36, 40], 18: [28, 30]},
        summary={
            "errands_completed": False, "cells_reached": 0, "steps_survived": 30,
            "died": True, "first_errand_step": None, "note_to_first_errand_steps": None,
            "after_errands": None, "invalid_replies": {"flat": 1}, "defaulted_replies": {},
            "focus_is_errand_fraction": None,
            # flat names a destination a step and holds none: A §4.4's other
            # count is the null, and the reader's 0 rows agree with it
            "destinations_named": 2, "destinations_chosen": None,
            "n_calls": 31, "wall_s": 92.0,
        })


def focus_s10_disagrees(dest):
    """focus, seed 10, 25 quiet steps, and a `summary.json` that claims a run
    that did not happen: the errands finished, two cells reached, forty steps
    survived, a focus fraction of 0.8, five destinations chosen and forty calls.
    The rows say otherwise on every one of them, and agree with it on `died`.

    Two destinations: the corner the walk turns at step 10, reached at 11 — a
    step that is gated as well, and reached wins — and then, after a step that
    explored, a cell it never comes near, still held when the cell ends.
    """
    return write_cell(
        dest, arm="focus", seed=10,
        legs=[("move_up", 5), ("move_right", 5), ("move_down", 5),
              ("move_left", 5), ("move_up", 5)],
        gated=(11,),
        ops_rows=[(11, "R1", [{"op": "add", "name": "look at the water to the south",
                               "until": "I have seen it"}],
                   [MAP_ENTRY, {"id": "e2", "name": "look at the water to the south",
                                "until": "I have seen it"}])],
        focus_plan=[(1, "e1"), (11, "e2")],
        r3_plan=[(1, "missing", [37, 27]), (11, "reached", None), (12, "missing", [10, 10])],
        summary={
            "errands_completed": True, "cells_reached": 2, "steps_survived": 40,
            "died": False, "first_errand_step": 33, "note_to_first_errand_steps": 23,
            "after_errands": {"completed_step": 35, "steps": 5, "new_cells": 40,
                              "focus_ids": {"errand": 5, "map_world": 0, "other": 0,
                                            "none": 0}},
            "invalid_replies": {"R1": 2}, "defaulted_replies": {"R2": 1},
            "focus_is_errand_fraction": 0.8,
            "destinations_named": None, "destinations_chosen": 5,
            "n_calls": 40, "wall_s": 80.0,
        })


def flat_s7_ledger(dest):
    """flat, seed 7, 28 steps: the body really stands on errand 0 at step 28 and
    no `arrival` row says so, while a planted row claims errand 1 at step 15,
    where the body was at [37, 32]. No `summary.json` at all.

    The planted rows are written without `first`, the shape `world._arrivals`
    writes; `cell.EVENT_FIELDS` asks for it and the reader reads both.
    """
    return write_cell(
        dest, arm="flat", seed=7,
        legs=[("move_right", 1), ("move_left", 1)] * 5 + [
            ("move_right", 10), ("move_down", 8)],
        arrivals=[{"step": 15, "kind": "arrival", "cell": [22, 24], "index": 1}])


def sliced_s11_holds(dest):
    """sliced, seed 11, 22 steps: the hold on the arm that has no R2.

    East nine, south eight, west five. Four destinations over four asks, the
    ends `reached`, `replaced`, `reached`, and one chosen at step 21 and still
    held when the cell ends at 22 — an open episode of two steps, the naming
    step and the last one. The asks are the whole of R3 here: no other step
    rendered it.

    The arm matters to the reader in three places: no `focus_id` on any action
    row, no R2 in `calls.jsonl`, and the table's focus column empty while the
    three hold columns are not.
    """
    rope = {"id": "e2", "name": "fetch the rope at [16, 38]",
            "until": "the rope is in hand"}
    return write_cell(
        dest, arm="sliced", seed=11,
        legs=[("move_right", 9), ("move_down", 8), ("move_left", 5)],
        gated=(11,),
        ops_rows=[(11, "R1", [{"op": "add", "name": rope["name"], "until": rope["until"]}],
                   [MAP_ENTRY, rope])],
        r3_plan=[
            (1, "missing", [41, 32]),    # the corner the walk turns at, reached at 10
            (10, "reached", [41, 40]),   # the next corner
            (11, "event", [38, 40]),     # the note's asks name another cell: replaced
            (21, "reached", [10, 10]),   # named at 21 and never ended: open at 22
        ],
        summary={
            "errands_completed": False, "cells_reached": 0, "steps_survived": 22,
            "died": False, "first_errand_step": None, "note_to_first_errand_steps": None,
            "after_errands": None, "invalid_replies": {}, "defaulted_replies": {},
            "focus_is_errand_fraction": None,
            "destinations_named": None, "destinations_chosen": 4,
            "n_calls": 27, "wall_s": 61.0,
        })


CELLS = {
    "focus_s7_completed": focus_s7_completed,
    "flat_s10_died": flat_s10_died,
    "focus_s10_disagrees": focus_s10_disagrees,
    "flat_s7_ledger": flat_s7_ledger,
    "sliced_s11_holds": sliced_s11_holds,
}


def write_all(parent):
    """Write all four cells under `parent`; `{name: Path}`."""
    parent = Path(parent)
    return {name: build(parent / name) for name, build in CELLS.items()}


if __name__ == "__main__":
    where = Path(sys.argv[1] if len(sys.argv) > 1 else ".")
    for name, path in write_all(where).items():
        rows = {f.name: len(f.read_text().splitlines())
                for f in sorted(path.glob("*.jsonl"))}
        print(name, json.dumps(rows, sort_keys=True))
