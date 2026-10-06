#!/usr/bin/env python3.12
"""The world (A §1, and the world row of A §6).

`World(seed)` wraps the vendored Crafter env with this line's rules fixed in
code — no flags. Three things vary between cells: arm, seed, steps (A §5, D8).

    w = World(7)
    frame0 = w.reset()
    frame, said, events = w.step("move_right")

What the world owns, and nothing else owns: the rules below, the frame
(A §1.2), the outcome sentences (A §1.3), the human's note and the errand
ledger (A §1.1), the seen set and the `mapped` bits (A §6, D2).

THE RULES (A §1.1), each ported from the original repo with its call site:

    water is walkable   `pin_water_walkable` before every step and before
                        frame 0, because `respawn` builds a fresh Player
    hot sand            `accrue_hot_ground` after the env step, 1 drink, once
    lava swept          `sweep_lava` once at reset; lava -> stone
    food, energy pinned `pin_food` / `pin_energy` to 9 with the hidden hunger
                        and fatigue counters at 0, before every step
    no monsters         `remove_monsters` once at reset
    verbs               move_left, move_right, move_up, move_down; plus `noop`,
                        which the model is never offered and which a defaulted
                        reply becomes

COORDINATES (A §1.1, a design ruling of 09-15). The world stores and logs **+y down** —
the vendor's own frame — everywhere: `frame["player"]["pos"]`, every event's
`cell`, the seen set, `constants.ERRANDS`. The model reads **+y up**:
`shown_y(y) = 63 - y`, an involution, applied at exactly two boundaries in this
module — `outcome()`'s `moved to [x, y]` and `errand_note()`'s cells. Every
other coordinate that leaves this module is world axis.

WHAT THIS MODULE DELIBERATELY DOES NOT HAVE (the project brief's "do not
bring"): the goal slot, the courier, the chat and trace renderers, the memory
store, `mapped.count`, `walked_rug`, `water_offset`, binary vision, `goto`, and
every flag the original line carried. The frame is the world's record; the pages are
`pages.md`'s and are built from a `State`, not from this.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
_VENDOR = ROOT / "src" / "vendor"
if str(_VENDOR) not in sys.path:
    sys.path.insert(0, str(_VENDOR))

import numpy as np  # noqa: E402

import crafter  # noqa: E402  (from src/vendor — never pip-installed)
from crafter import constants as vendor  # noqa: E402
from crafter import engine, objects  # noqa: E402

from . import constants as K  # noqa: E402
from . import axis as _axis  # noqa: E402

SCHEMA_PATH = Path(__file__).resolve().parent / "frame_schema.json"

# -- constants this module defines, because `p3focus/constants.py` is shared and
#    four branches merge into it. Each is listed in the project's design notes. ----

#: the material a step may END on and be charged for (original `store.HOT_GROUND_MATERIAL`)
HOT_GROUND_MATERIAL = "sand"
#: what one hot step costs, in drink, charged at once (original `store.HOT_GROUND_DRINK`;
#: a design ruling of 09-15: a hazard whose price the body cannot observe is one it invents)
HOT_GROUND_DRINK = 1
#: the sweep, once at reset (original `store.LAVA` / `LAVA_BECOMES`). Stone is
#: non-walkable as lava was, so the walkable census does not move.
LAVA = "lava"
LAVA_BECOMES = "stone"
#: what `pin_food` / `pin_energy` hold (original `store.FOOD_PIN` / `ENERGY_PIN`)
FOOD_PIN = 9
ENERGY_PIN = 9
#: the material that is walkable only because this line pins it so
WATER = "water"
#: the walkable set for the SEEN SET and for `mapped_bits` (A §6, D2): the
#: vendor's own walkable materials plus water, which is walkable here.
WALKABLE = frozenset(vendor.walkable) | {WATER}
#: removed once at reset (original `store.MONSTER_TYPES`); cows and plants stay
MONSTER_TYPES = (objects.Zombie, objects.Skeleton, objects.Arrow)

# DESIGN NOTE (design A is silent on what the meters start at): every battery in
#: the original record ran the original `store.DEFAULT_START_NEEDS`, and no driver
#: overrode it, so this is the reading that keeps the original run an answer key —
#: the identity test compares against a run made under it. `food` is pinned to 9 a
#: moment later and never shows; only `drink: 3` is observable, and it sets how
#: hard the first hundred steps are. To use the vendor's own 9/9/9/9 instead, this
#: dict and the identity fixture are the whole change.
START_NEEDS = {"drink": 3, "food": 5}

#: the four verbs the model is offered (A §1.1). `noop` is not among them: it
#: exists only inside the harness, for a defaulted reply, and its outcome reads
#: "waited". A body that wants to stay in water has to keep moving inside it.
VERBS = K.VERBS           # one copy, constants.py (the grammars read the same tuple)
NOOP = K.NOOP
#: verb -> the vendor's own action index (original `store.ACTION_INDEX`, built from
#: `crafter.constants.actions`; the original harness's table was the same names)
ACTION_INDEX = {name: i for i, name in enumerate(vendor.actions)}

#: window cell names that are not materials or object classes
OUT_OF_BOUNDS = "out_of_bounds"  # cell outside `world.area`
NO_MATERIAL = "none"  # semantic id 0; worldgen fills every in-world cell

#: object types for OUR SemanticView. Order fixes the ids: the stock list
#: (env.py:47-49) gives Player 13 .. Plant 18; Fence appended last is 19.
SEM_OBJECT_TYPES = [
    objects.Player, objects.Cow, objects.Zombie,
    objects.Skeleton, objects.Arrow, objects.Plant, objects.Fence,
]

#: the outcome sentence's direction words, screen relative and carrying no sign
#: (A §1.1; original `loop._DIRS`). +y is DOWN in the world, so (0, -1) is up the screen.
_DIRS = _axis.DIRS
#: the `mapped` bits' four neighbours, same words, same signs (original `loop.FACING_OFFSETS`)
_NEIGHBOURS = {"up": (0, -1), "down": (0, 1), "left": (-1, 0), "right": (1, 0)}

#: the honest result clause for a step that ENDED on hot ground, to the byte
#: (original `loop.HOT_GROUND_CLAUSE`). A design ruling of 09-15: the heat must name its price.
HOT_GROUND_CLAUSE = "; the ground here is hot, drink fell 1"
#: the same, for the step where there was nothing left to take
HOT_GROUND_CLAUSE_EMPTY = ("; the ground here is hot, but your drink is already empty, "
                           "so nothing fell")

#: the note's number words (original `loop._NUMBER_WORDS`), for the count of numbered steps
_NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}


# -- coordinates (A §1.1) ------------------------------------------------------

# The axis lives in `axis.py` (one implementation); re-exported here because the
# world is where the two boundaries are (`outcome`, `errand_note`).
shown_y = _axis.shown_y
shown_pos = _axis.shown_pos


def pin_food(env):
    """Hold inventory `food` at 9 and the hidden hunger counter at 0.

    A §1.1: food is pinned before every world step and before frame 0, so hunger
    can never reach the vendor's 25 and food never moves. It is never shown and
    never named on any page. Ported from the original `store.pin_food`.
    """
    env._player.inventory["food"] = FOOD_PIN
    env._player._hunger = 0
    return env


def pin_energy(env):
    """Hold inventory `energy` at 9 and the hidden fatigue counter at 0, so
    fatigue can never reach the vendor's 30. A §1.1; original `store.pin_energy`."""
    env._player.inventory["energy"] = ENERGY_PIN
    env._player._fatigue = 0
    return env


def pin_water_walkable(env):
    """Mark the live player as able to walk on — and so to drink by standing in —
    water. A §1.1; original `store.pin_water_walkable`.

    Re-applied before every step, not set once: `respawn` builds a NEW `Player`
    after death, which would drop the attribute silently while the manual went
    on promising water is walkable. That is the one failure mode this must not
    have, and `test_world_water.py` tests it through `World.step`.
    """
    env._player.water_walkable = True
    return env


def standing_on(env, pos=None):
    """The material of the cell the body is ON — its own cell by default. WORLD axis.

    Read from the material map, never from the window: the semantic window
    renders the player OVER their own cell, so the window cannot answer this at
    all. That is why the frame carries it (A §1.2, D4). The original `store.standing_on`.
    """
    p = env._player.pos if pos is None else pos
    material, _ = env._world[(int(p[0]), int(p[1]))]
    return material


def on_hot_ground(env, pos=None):
    """Whether the cell under `pos` — the body's own by default, WORLD axis — is
    hot ground. Out of bounds is False (the vendor returns no material there).
    A §1.1; original `store.on_hot_ground`."""
    p = env._player.pos if pos is None else pos
    material, _ = env._world[(int(p[0]), int(p[1]))]
    return material == HOT_GROUND_MATERIAL


def accrue_hot_ground(env, pos=None):
    """Charge one world step for the heat and return what it ACTUALLY took.

    A §1.1: a step that ENDED on sand costs `HOT_GROUND_DRINK` drink, at once,
    charged after the env step — the cell that charges is the one the body ended
    on, which is not known before. Returns 1 normally and 0 when the meter was
    already empty; the outcome sentence is keyed on that number, because a charge
    nothing reports is a charge the body cannot learn from (a design ruling of 09-15).

    The original `store.accrue_hot_ground`. The meter cannot go negative: `min()` holds
    the floor and a subtraction cannot reach the ceiling.
    """
    if not on_hot_ground(env, pos):
        return 0
    inv = env._player.inventory
    fell = min(HOT_GROUND_DRINK, int(inv.get("drink", 0)))
    if fell:
        inv["drink"] = int(inv["drink"]) - fell
    return fell


def remove_monsters(env):
    """Remove every `Zombie`, `Skeleton` and `Arrow` worldgen put in the world.

    A §1.1: once, at reset, before anything is logged — so every frame descends
    from a monster-free world. Cows and plants stay. Returns the count by kind,
    e.g. `{"zombie": 15, "skeleton": 5, "arrow": 0}` on seed 7. The original
    `store.remove_monsters`.
    """
    world = env._world
    removed = {cls.__name__.lower(): 0 for cls in MONSTER_TYPES}
    for obj in world.objects:  # a fresh list: removing while iterating is safe
        if isinstance(obj, MONSTER_TYPES):
            world.remove(obj)
            removed[type(obj).__name__.lower()] += 1
    return removed


def sweep_lava(env):
    """Every lava cell becomes stone, one pass over the material map.

    A §1.1: once, at reset, beside `remove_monsters`. Lava kills on contact and
    would make a near-blind run too much of a worldgen dice roll (a design concern:
    too much of the outcome left to luck). Stone is non-walkable as lava was, so the
    walkable census does not move. Nothing but the material map is touched: no object
    moves and the world RNG is not drawn from. Returns the number of cells changed
    (40 on seed 7). The original `store.sweep_lava`.
    """
    world = env._world
    hot = world._mat_map == world._mat_ids[LAVA]
    world._mat_map[hot] = world._mat_ids[LAVA_BECOMES]
    return int(hot.sum())


def apply_start_needs(env, needs=None):
    """Set the body's starting meters (`START_NEEDS`) on the live player.

    The vendor's `Player.__init__` starts every meter at 9; this overrides it at
    reset, before frame 0. See `START_NEEDS` for the design note. The original
    `store.apply_start_needs`, without its validator — the dict is ours, not a
    flag a caller can pass.
    """
    for name, value in (START_NEEDS if needs is None else needs).items():
        env._player.inventory[name] = int(value)
    return env


def is_dead(env):
    """Health at or below 0. A §4.2's `death`. The original `store.is_dead`."""
    return int(env._player.health) <= 0


# -- the frame (A §1.2) --------------------------------------------------------

class _NoBalanceEnv(crafter.Env):
    """`Env` with NPC spawn/despawn balancing disabled.

    `_balance_chunk` runs every 10 steps and spawns/despawns zombies, skeletons
    and cows (env.py:90-95, 141-180). Off is what every battery in the original record
    ran, and it is what makes `remove_monsters` hold for a whole run rather than
    for ten steps.
    """

    def _balance_chunk(self, chunk, objs):
        return


def make_env(seed, balancer=False, **kw):
    """Return an unreset `crafter.Env` (call `.reset()` yourself).

    `balancer=False` (the default, and this line's rule) returns the
    `_balance_chunk`-no-op subclass. `length=None` by default: a run has no
    `done`-at-10000, as the original `Battery.fresh_env` had none. The original
    `telemetry.make_env`, whose `balancer` argument survives only because
    `test_frame_schema.py` uses it to show the flag is not a no-op.
    """
    kw.setdefault("length", None)
    cls = crafter.Env if balancer else _NoBalanceEnv
    return cls(seed=seed, **kw)


def semantic_id_names(world, sem_view):
    """id -> name for every value a `SemanticView` canvas can hold. The original
    `telemetry.semantic_id_names`; serves A §1.2's `window`."""
    names = {int(i): (n if n is not None else NO_MATERIAL)
             for i, n in world._mat_names.items()}
    names.update({int(i): c.__name__.lower() for c, i in sem_view._obj_ids.items()})
    return names


def semantic_window(sem_map, pos, size, id_to_name):
    """`size`x`size` names around `pos`, player-centred, padded at world edges.

    WORLD axis throughout: rows run north->south (+y DOWN), columns west->east
    (+x), which is the orientation of the rendered frame (`Env.render` transposes
    (x,y)->(y,x)). So `rows[size//2][size//2]` is the body's own cell, `rows[0]`
    is the row farthest ABOVE it on screen, and printing the rows reads like the
    picture. A §1.2; original `telemetry.semantic_window`.
    """
    if size < 1 or size % 2 == 0:
        raise ValueError(f"window must be a positive odd number of cells, got {size}")
    r = size // 2
    px, py = int(pos[0]), int(pos[1])
    w, h = sem_map.shape
    rows = []
    for y in range(py - r, py + r + 1):
        row = []
        for x in range(px - r, px + r + 1):
            inside = 0 <= x < w and 0 <= y < h
            row.append(id_to_name[int(sem_map[x, y])] if inside else OUT_OF_BOUNDS)
        rows.append(row)
    return rows


class TelemetryExtractor:
    """Typed frames from a running `crafter.Env` — A §1.2's frame, schema "2".

    The original `telemetry.TelemetryExtractor` with one field added,
    `standing_on` (A §7, D4): it is computed here rather than at render time so
    that the reader and the identity test see it too.

    The env must already be reset. `frame0()` and `step()` commit a frame (later
    deltas are measured from it); `frame()` is read-only and never commits, so
    calling it twice returns the same frame.
    """

    def __init__(self, env, window=K.WINDOW):
        if window < 1 or window % 2 == 0:
            raise ValueError(f"window must be a positive odd number of cells, got {window}")
        if getattr(env, "_step", None) is None:
            raise RuntimeError(
                "env has not been reset; call env.reset() before constructing "
                "TelemetryExtractor (Env._step is None until reset, env.py:50,73)")
        self.env = env
        self.window = window
        self.sem_view = engine.SemanticView(env._world, SEM_OBJECT_TYPES)
        self.id_to_name = semantic_id_names(env._world, self.sem_view)
        #: last values from `Env.step`; not part of the frame, but the world needs them
        self.done = False
        self.reward = 0.0
        self._prev = None  # (inventory, achievements) of the last committed frame

    # -- public API ---------------------------------------------------------

    def frame0(self):
        """The frame for the post-reset state. `Env.reset` returns no info, so we
        compute it ourselves. Deltas are empty. A §1.2."""
        self._prev = None
        frame = self.frame()
        self._commit(frame)
        return frame

    def step(self, action_idx, between=None):
        """`env.step(action_idx)`, then the frame for the NEW state. A §1.2.

        `between`, if given, runs after the env step and before the frame is
        read: the world's hot-ground charge (A §1.1, "after the step and before
        the frame is logged"). When it runs, the frame is read from the live
        env rather than from `info`'s copy, so the frame shows the charge the
        outcome sentence names (settled 09-24; the original code logged it one frame
        late, and this was measured during development)."""
        n = len(vendor.actions)
        if not isinstance(action_idx, (int, np.integer)) or isinstance(action_idx, bool):
            raise TypeError(
                f"action_idx must be an int index into constants.actions, got {action_idx!r}")
        if not 0 <= int(action_idx) < n:
            raise ValueError(f"action_idx {action_idx} out of range 0..{n - 1}")
        _obs, reward, done, info = self.env.step(int(action_idx))
        self.reward = float(reward)
        self.done = bool(done)
        if between is not None:
            between()
            info = None
        frame = self.frame(info)
        self._commit(frame)
        return frame

    def frame(self, info=None):
        """Read-only extraction. `info` is the dict from `Env.step`; without it the
        same values are read from `env._player` (they are the same objects — the
        env only `.copy()`s them). Coordinates in the frame are WORLD axis."""
        env = self.env
        player = env._player
        src = info if info is not None else {
            "inventory": player.inventory, "achievements": player.achievements}
        inventory = {k: int(v) for k, v in src["inventory"].items()}
        achievements = {k: int(v) for k, v in src["achievements"].items()}
        return {
            "schema_version": K.FRAME_SCHEMA_VERSION,
            "step": int(env._step),
            "daylight": float(env._world.daylight),
            "player": {
                "pos": [int(player.pos[0]), int(player.pos[1])],
                "facing": [int(player.facing[0]), int(player.facing[1])],
                "sleeping": bool(player.sleeping),
                "health": inventory["health"],
                "food": inventory["food"],
                "drink": inventory["drink"],
                "energy": inventory["energy"],
            },
            "inventory": inventory,
            "window": semantic_window(
                self.sem_view(), player.pos, self.window, self.id_to_name),
            # schema "2"'s one addition: the window draws the body over its own
            # cell, so this is the one cell the window cannot report
            "standing_on": standing_on(env),
            "achievements": achievements,
            "deltas": self._deltas(inventory, achievements),
        }

    # -- internals ----------------------------------------------------------

    def _deltas(self, inventory, achievements):
        if self._prev is None:
            return {"inventory": {}, "achievements": {}}
        prev_inv, prev_ach = self._prev
        return {
            "inventory": {k: v - prev_inv[k] for k, v in inventory.items()
                          if v != prev_inv[k]},
            "achievements": {k: v - prev_ach[k] for k, v in achievements.items()
                             if v != prev_ach[k]},
        }

    def _commit(self, frame):
        self._prev = (dict(frame["inventory"]), dict(frame["achievements"]))


def load_schema():
    """The frame schema (A §1.2), parsed. Version "2"."""
    return json.loads(SCHEMA_PATH.read_text())


def vendor_digest_of(vendor_dir=None):
    """sha256 over a vendored crafter tree: relative path + bytes, sorted, every
    `.py` and `data.yaml`, not the assets. Ours by default.

    The original `store.vendor_digest`, kept because the identity test (A §1.1)
    needs to say out loud that the vendored substrate is exactly the one recorded —
    a frame match against a different Crafter would mean nothing.
    """
    import hashlib
    root = _VENDOR / "crafter" if vendor_dir is None else Path(vendor_dir)
    h = hashlib.sha256()
    files = sorted(p for p in root.rglob("*")
                   if p.is_file() and (p.suffix == ".py" or p.name == "data.yaml")
                   and "__pycache__" not in p.parts)
    for p in files:
        h.update(str(p.relative_to(root)).encode())
        h.update(b"\0")
        h.update(p.read_bytes())
        h.update(b"\0")
    return h.hexdigest()


# -- the outcome sentences (A §1.3) --------------------------------------------

def hot_ground_clause(fell):
    """Which half of the heat's sentence this step earned, from what it ACTUALLY
    took (`accrue_hot_ground`'s return), not from a reading of the meter: this
    reports an event, it does not decide one. A §1.3; original `loop.hot_ground_clause`."""
    return HOT_GROUND_CLAUSE if fell else HOT_GROUND_CLAUSE_EMPTY


#: A §1.3: the clause for standing on the return cell without both items, after the
#: note. The `{have}` names what is on the body and what is still missing.
RETURN_WITHOUT_BOTH = ("; you are standing where your human player said to come, but they are stuck "
                       "down below and will not come up until you bring both: {have}")


def return_without_both(carrying):
    """The return-cell clause for what the body carries (A §1.3; B §1.2)."""
    items = list(carrying)
    missing = [item for item in K.ERRAND_ITEMS if item not in items]
    if not items:
        have = "you have nothing yet and still need the " + " and the ".join(missing)
    else:
        have = ("you have the " + " and the ".join(items) + " and still need the "
                + " and the ".join(missing))
    return RETURN_WITHOUT_BOTH.format(have=have)


def outcome(verb, before, after, hot=False, fell=0):
    """What the action did, from the frame before it and the frame after it.

    A §1.3, to the byte, for the cases THIS world can produce — four moves and
    `noop`, and nothing else, because nothing else is a verb here:

        moved to [x, y]                                       (SHOWN axis)
        did not move; the cell <above you|below you|to your left|to your right> is <material>
        waited

    with `HOT_GROUND_CLAUSE` or `HOT_GROUND_CLAUSE_EMPTY` appended when the step
    ended on sand. `hot` is the caller's `on_hot_ground` — the frame cannot say
    it, because the window renders the body over its own cell — and `fell` is
    what the heat actually took, which chooses the clause.

    Proprioception the frame itself does not carry: a 7B model once pressed
    `move_right` into a lake for sixty steps because nothing told it the body had
    not moved. Pure; no rules about what to do next. The original `loop.outcome` /
    `loop._outcome_text`, with the branches for verbs this world has not got
    (do, sleep, make_*, place_*) dropped rather than ported dead.
    """
    return _outcome_text(verb, before, after) + ("" if not hot else hot_ground_clause(fell))


def _outcome_text(verb, before, after):
    """`outcome` without the heat's clause. The `moved to` coordinate is the only
    SHOWN-axis value this module puts in a sentence; everything else here is a
    name, not a coordinate."""
    b, a = before["player"], after["player"]
    if verb.startswith("move_"):
        if list(a["pos"]) != list(b["pos"]):
            p = shown_pos(a["pos"])
            return f"moved to [{p[0]}, {p[1]}]"
        # the cell that stopped it: the one the body now faces, read out of the
        # window it just got. World axis, so dy = -1 is the row above on screen.
        dx, dy = (int(v) for v in a["facing"])
        n = len(after["window"])
        row, col = n // 2 + dy, n // 2 + dx
        cell = after["window"][row][col] if 0 <= row < n and 0 <= col < n else "?"
        return f"did not move; the cell {_DIRS.get((dx, dy), 'in front of you')} is {cell}"
    if verb == NOOP:
        return "waited"
    raise ValueError(f"no outcome sentence for {verb!r}; the verbs are {VERBS + (NOOP,)}")


# -- the human's note (A §1.1) -------------------------------------------------

def errand_note(errands):
    """The human's note, in the coordinates the body reads (SHOWN axis, +y up).

    `errands` is a seed's row of `constants.ERRANDS`, WORLD axis: the visits
    first, the meeting place last. One flavour item per visit, in order, from
    `constants.ERRAND_ITEMS`.

    Ported from the original `loop.errand_note` for the `steps=True, stakes=True`
    form only — the shape one arm ran (errand-stakes and errand-steps both on) —
    with `errand_drink` and the un-numbered branch dropped. A §1.1 quotes seed 7's
    line; `test_world_note.py` pins it to the byte.
    """
    visits, ret = list(errands[:-1]), errands[-1]

    def cell(pos):
        p = shown_pos(pos)
        return f"[{p[0]}, {p[1]}]"

    lines = [f"({i + 1}) stand on {cell(pos)}, my {K.ERRAND_ITEMS[i % len(K.ERRAND_ITEMS)]} is there"
             for i, pos in enumerate(visits)]
    what = "it" if len(visits) == 1 else ("both" if len(visits) == 2 else "all of them")
    lines.append(f"({len(lines) + 1}) then come to me at {cell(ret)} with {what}")
    head = (f"{_NUMBER_WORDS.get(len(lines), str(len(lines))).capitalize()} things: "
            + "; ".join(lines) + ".")
    them = "it" if len(visits) == 1 else "them"
    return head + f" I am stuck down here without {them}. The map can wait for that; I can't."


def trace_note_line(step, text):
    """The step a note lands: ONE history line in the world's voice, the note
    quoted (A §1.3). It is a line like any other and leaves the page with the
    rest — nothing anywhere repeats it. The original `loop.trace_note_line`."""
    return f'step {int(step)}: a note from your human player arrived: "{text}"'


# -- the world -----------------------------------------------------------------

class World:
    """One seed's world, with this line's rules fixed in code (A §1.1).

        w = World(7)
        frame0 = w.reset()                       # frame 0, after reset
        frame, said, events = w.step("move_up")  # one world step

    `step` returns the frame (A §1.2), the outcome sentence (A §1.3) and the
    step's events (A §4.2: `note_landed`, `arrival`, `errands_completed`,
    `drink_crossing`, `death` — the five kinds the world writes). The same list
    is `World.events` until the next step.

    Coordinates on this object are WORLD axis (+y down) without exception:
    `pos`, `seen`, every event's `cell`, `errand_cells`. The two shown-axis
    strings the world produces are `outcome()`'s `moved to` and the note.
    """

    def __init__(self, seed):
        if seed not in K.ERRANDS:
            raise ValueError(f"no errand cells for seed {seed}; the seeds are {tuple(K.ERRANDS)}")
        self.seed = int(seed)
        #: the seed's two visits and the return, WORLD axis (A §1.1)
        self.errand_cells = tuple(tuple(int(v) for v in c) for c in K.ERRANDS[self.seed])
        self.env = None
        self.extractor = None
        #: what reset's two sweeps did, for the report and for the tests
        self.monsters_removed = None
        self.lava_swept = None
        #: the seen set (A §6, D2): WORLD-axis (x, y) of every WALKABLE cell
        #: inside the 9x9 around every cell the body has stood on. Water is in it,
        #: because water is walkable here.
        self.seen = set()
        #: errand index -> the step it was first reached on; the ledger A §1.1
        #: calls a convenience the reader checks against, never the measurement
        self.errands_reached = {}
        self.errands_completed = False
        self.note_text = None
        self.note_line = None
        self.note_delivered = False
        self.died = False
        #: what the heat took on the last step, for the caller that wants the
        #: number without re-reading the sentence
        self.last_hot_fell = 0
        self.last_frame = None
        self.events = []
        self._walkable_cells = None

    # -- the run ------------------------------------------------------------

    def reset(self):
        """Build the world and return frame 0 (A §1.2).

        The order is the original line's dawn, and it matters for identity: fresh env
        -> `remove_monsters` -> `sweep_lava` -> `apply_start_needs` -> the three
        pins -> frame 0. The sweeps come first so every frame descends from a
        world with no monsters and no lava; the pins come before frame 0 so the
        first frame is already in the world the body is told about.
        """
        env = make_env(self.seed, balancer=False)
        env.reset()
        self.monsters_removed = remove_monsters(env)
        self.lava_swept = sweep_lava(env)
        apply_start_needs(env)
        pin_food(env)
        pin_energy(env)
        pin_water_walkable(env)
        self.env = env
        self.extractor = TelemetryExtractor(env, window=K.WINDOW)
        self._walkable_cells = None
        self.seen = set()
        self.errands_reached = {}
        self.errands_completed = False
        #: the items picked up so far, in order (A §1.3 `carrying`; a design note of
        #: 09-24: the body needs a signal that it has the pickaxe, on it)
        self.carrying = []
        self.note_text = errand_note(self.errand_cells)
        self.note_line = None
        self.note_delivered = False
        self.died = False
        self.last_hot_fell = 0
        self.events = []
        frame = self.extractor.frame0()
        # the body is standing on the spawn at frame 0, so the spawn's 9x9 is
        # seen before the first step — the original `_log_frame` marked frame 0 too
        self._see(frame)
        self.last_frame = frame
        return frame

    def step(self, verb):
        """Take one world step and return `(frame, outcome, events)`.

        `verb` is one of `VERBS`, or `NOOP` for a defaulted reply. The order is
        the original `store.Session.step`'s, and every line of it is load-bearing for
        identity:

        1. the three pins, BEFORE the env step (`pin_water_walkable` because
           `respawn` builds a fresh Player; the other two because hunger and
           fatigue must never reach the vendor's counters);
        2. the env step, and the frame extracted from its `info`;
        3. `accrue_hot_ground`, AFTER the step, because the cell that charges is
           the one the body ENDED on;
        4. the seen set grows (A §6, D2);
        5. the step's events, then its sentence.

        Settled 09-24 (an open question during development): the original code
        built the frame from `info`'s copy BEFORE the charge, so its logged frames
        showed a sand charge one step late while the sentence named it at once.
        Here the charge runs between the env step and the frame (`between`), so the
        frame the body reads shows the fall. The identity test compares against the
        original repo's LIVE meter after each step, which is what the original
        frames should have said; positions, windows and health are unchanged by this.
        """
        self._require_reset()
        if verb not in VERBS and verb != NOOP:
            raise ValueError(f"unknown verb {verb!r}; the verbs are {VERBS} (and {NOOP!r})")
        before = self.last_frame
        pin_food(self.env)
        pin_energy(self.env)
        pin_water_walkable(self.env)
        fell = []
        # the charge runs between the env step and the frame, so the frame the
        # body reads shows the fall the sentence beside it names (settled 09-24)
        frame = self.extractor.step(ACTION_INDEX[verb],
                                    between=lambda: fell.append(accrue_hot_ground(self.env)))
        self.last_hot_fell = fell[0]
        self._see(frame)
        self.last_frame = frame
        self.events = self._step_events(before, frame)
        said = outcome(verb, before, frame,
                       hot=on_hot_ground(self.env), fell=self.last_hot_fell)
        # A §1.3 (a design note of 09-24): arriving on an errand cell is told, once, in the
        # world's own sentence, and the item stays in `carrying` from then on
        for row in self.events:
            if row["kind"] == "arrival" and row["index"] < len(self.errand_cells) - 1:
                item = K.ERRAND_ITEMS[row["index"] % len(K.ERRAND_ITEMS)]
                self.carrying.append(item)
                said += f"; you picked up the {item}: it is on you now"
        if any(row["kind"] == "errands_completed" for row in self.events):
            said += (f"; you have reached your human player with the {' and the '.join(self.carrying)}: "
                     "the errands are done")
        elif self._at_the_human_without_both(frame):
            # A §1.3 (a design note of 09-24): the other half of the pickup signal. Standing
            # where the human said to come, after the note and without both items, is
            # told on every step it is true, the way "did not move" is told on every
            # bump: three focus cells stood there with one item and were told nothing.
            said += return_without_both(self.carrying)
        return frame, said, self.events

    def _at_the_human_without_both(self, frame):
        """Is the body on the return cell, after the note has landed (not on the step it
        lands, as for arrivals), with the errands not done and fewer than both items?"""
        if not self.note_delivered or self.errands_completed:
            return False
        if any(row["kind"] == "note_landed" for row in self.events):
            return False
        pos = tuple(int(v) for v in frame["player"]["pos"])
        return pos == self.errand_cells[-1] and len(self.carrying) < len(self.errand_cells) - 1

    # -- what the page reads (A §1.3) ---------------------------------------

    def mapped_bits(self, frame):
        """`{here, up, down, left, right}` booleans for the state (A §1.3).

        Derived from the seen set and nothing else (A §6, D2), and there is no
        count: no progress meter is on any page (B, P2). The four direction words
        are SCREEN relative, so `up` is the cell above the body on screen, which
        is `y - 1` in the WORLD axis this reads.

        A cell counts as mapped when it is in the seen set, or when it is not
        walkable at all — there is nothing left to map on stone, and a False
        would send the body chasing it (the original `MappedTracker.is_mapped` rule).
        Outside the world the same answer falls out, which is right for the same
        reason.
        """
        px, py = (int(v) for v in frame["player"]["pos"])
        bits = {"here": self.is_mapped(px, py)}
        for name, (dx, dy) in _NEIGHBOURS.items():
            bits[name] = self.is_mapped(px + dx, py + dy)
        return bits

    def is_mapped(self, x, y):
        """Whether the WORLD-axis cell `(x, y)` is mapped: in the seen set, or not
        walkable (nothing to map there). A §1.3's `mapped`."""
        cell = (int(x), int(y))
        return cell in self.seen or cell not in self._walkable()

    def walkable_at(self, x, y):
        """Whether the WORLD-axis cell `(x, y)` is one the body may stand on:
        grass, path, sand — the vendor's own set — or water, which this line pins
        walkable (A §1.1). Outside the world is False. Serves the seen set and
        the route hint's BFS (A §6)."""
        return (int(x), int(y)) in self._walkable()

    # -- internals ----------------------------------------------------------

    def _require_reset(self):
        if self.env is None:
            raise RuntimeError("World.reset() has not been called")

    def _walkable(self):
        """The whole world's walkable cells, WORLD axis, computed once.

        Constant for a run: this line's verbs are four moves and a noop, none of
        which changes a material, and the one material change there is — the lava
        sweep — happens at reset, before this is first read.
        """
        if self._walkable_cells is None:
            world = self.env._world
            names = {int(i): n for i, n in world._mat_names.items()}
            mat = world._mat_map
            self._walkable_cells = {
                (x, y)
                for x in range(mat.shape[0]) for y in range(mat.shape[1])
                if names[int(mat[x, y])] in WALKABLE}
        return self._walkable_cells

    def _see(self, frame):
        """Grow the seen set by the 9x9 around the body: every cell in reach whose
        material the body may stand on, water included (A §6, D2).

        Every step, not only the steps that routed. That is what "cells you have
        seen" says, and the original trace's narrower rule made the sentence false for
        cells the body walked past (the project brief, decision 6). The original
        `loop.Loop._see`. WORLD axis.
        """
        px, py = (int(v) for v in frame["player"]["pos"])
        r = K.WINDOW // 2
        w, h = self.env._world.area
        walkable = self._walkable()
        for x in range(max(0, px - r), min(w, px + r + 1)):
            for y in range(max(0, py - r), min(h, py + r + 1)):
                if (x, y) in walkable:
                    self.seen.add((x, y))

    def _step_events(self, before, frame):
        """The step's event rows (A §4.2), in the order the world writes them:
        the note, then the ledger, then what the step cost.

        Every row carries `step` and `kind`, and every coordinate in one is WORLD
        axis (A §4). `drink_crossing` and `death` are read off the two LOGGED
        frames rather than off the live env, so the reader can re-derive every
        row from `frames.jsonl` — which is the check A §1.1 asks it to make.
        """
        step = int(frame["step"])
        events = []
        if not self.note_delivered and step >= K.NOTE_STEP:
            # the note lands after the world step numbered NOTE_STEP, so its asks
            # render on the next step (A §4.2: step N's events gate step N+1)
            self.note_delivered = True
            self.note_line = trace_note_line(step, self.note_text)
            events.append({"step": step, "kind": "note_landed"})
        elif self.note_delivered:
            # no errand exists for the body before the note, so no arrival does
            # either — not even on the step the note itself lands
            events.extend(self._arrivals(step, frame))
        events.extend(self._vitals(step, before, frame))
        return events

    def _arrivals(self, step, frame):
        """Arrival rows for this step, and `errands_completed` when the last one
        lands (A §1.1, §4.2).

        Its caller does not call it before the note has landed, nor on the step
        it lands: no errand exists for the body before then. Visits count in any
        order, each once; the meeting place is not an arrival at all until every
        visit is done.

        One row per cell, on the step it first counts (A §4.2, settled 09-24: an
        open question was whether `arrival` repeats; it does not, because the gate
        opens on it and a re-crossing would open an ask for nothing, the original
        ledger's rule). `errands_completed` rides the return's row.
        """
        pos = tuple(int(v) for v in frame["player"]["pos"])
        rows = []
        visits_left = any(i not in self.errands_reached
                          for i in range(len(self.errand_cells) - 1))
        for index, cell in enumerate(self.errand_cells):
            if cell != pos:
                continue
            is_return = index == len(self.errand_cells) - 1
            if is_return and visits_left:
                continue  # the return counts only after both visits
            # A §4.2 (settled 09-24 on this module's open question): once per cell,
            # the original ledger's rule; a repeat would re-open the gate for nothing.
            first = index not in self.errands_reached
            if not first:
                continue
            self.errands_reached[index] = step
            rows.append({"step": step, "kind": "arrival", "cell": list(cell), "index": index})
            if is_return and not self.errands_completed:
                self.errands_completed = True
                rows.append({"step": step, "kind": "errands_completed"})
        return rows

    def _vitals(self, step, before, frame):
        """`drink_crossing` and `death` for this step (A §4.2).

        `drink_crossing` is the original gate's E1 at its default (`vital_drink_at` 0,
        which rounds 38 and 39 ran): drink reaching 0 from above it, OR health
        falling. It carries all four values so a reader never has to guess which
        half fired. `death` fires once, on the first frame whose health is 0.
        """
        rows = []
        now, was = frame["player"], before["player"]
        crossed = (int(now["drink"]) <= K.DRINK_CROSSING_AT
                   and int(was["drink"]) > K.DRINK_CROSSING_AT)
        if crossed or int(now["health"]) < int(was["health"]):
            rows.append({"step": step, "kind": "drink_crossing",
                         "drink_from": int(was["drink"]), "drink_to": int(now["drink"]),
                         "health_from": int(was["health"]), "health_to": int(now["health"])})
        if not self.died and int(now["health"]) <= 0:
            self.died = True
            rows.append({"step": step, "kind": "death"})
        return rows
