#!/usr/bin/env python3.12
"""The reader (A §6's reader row): one cell's log files in, the numbers and the
seed × arm table out.

    from p3focus import reader
    summary = reader.read_cell("runs/focus_s7_20260924T031500")
    print(reader.table([summary]))
    print(reader.trajectory("runs/focus_s7_20260924T031500"))

It reads A §4's rows and nothing else: no model, no world, no vendored Crafter.
Every number below is **recomputed from the rows**. A cell's own `summary.json`
is read only to be disagreed with (`summary_disagreements`), never to be
believed — the same rule A §1.1 states for the arrival ledger, which this module
re-derives from positions in `frames.jsonl` and compares with the `arrival`
rows (`ledger_check`).

COORDINATES. Every coordinate in a log row is the WORLD axis, +y down (A §4),
and every coordinate this module computes with or prints in a map is the world
axis too. The one place the shown axis appears is the errand-entry rule below,
because the note the body read named its cells in the shown axis and so does an
entry the body wrote about them. `axis.shown_pos` is the involution that carries
one to the other.

THE READER'S OWN RULES, which the rows cannot state for themselves (each is
written down here, applied uniformly, and pinned by a test):

    R1  AN ERRAND ENTRY is a list entry whose `name`, `why`, `until` or `when`
        contains one of the note's three cells, shown axis, formatted `[x, y]`
        (spacing inside the brackets is free), or one of the words `pickaxe`,
        `rope`, `come to me`, `human`, case-insensitively. Nothing else is
        consulted — not the id, not the step it was added on. `errand_matches`
        returns what matched, so a reading is always auditable.
    R2  AN ENTRY'S SPAN comes from the `list_after` snapshots of `ops_applied`
        rows, not from replaying the ops: `list_after` is the list the harness
        actually held, ids included, and an `add` op does not carry the id the
        harness gave it. An entry in the FIRST such row that the row's own
        `add` ops cannot account for was on the list before it — the dawn entry
        (A §2) — and is recorded as added at step 0. Ids are assigned in order
        and never reused, so the ones that row added are the highest-numbered
        of those new to the reader. An id the first row deletes without ever
        showing it was on the list before it too, and is recorded the same way,
        with A §2's words where A §2 names it.
    R3  THE SEEN SET is recomputed from `frames.jsonl`: for every frame, every
        cell of the 9×9 window whose name is a walkable material, plus the
        body's own cell via the frame's `standing_on` (the window draws the
        body over it). It only grows. A cell the window showed as an OBJECT —
        `cow`, `plant`, `fence` — is not counted on that frame, because the
        window does not say what is under the object; it joins the set on the
        first frame that shows its material. This is the one place the reader's
        set can lag the world's, which reads the material map (A §6, D2).
    R4  A NONE FOCUS is an `actions.jsonl` row whose `focus_id` is null or the
        string `none`; a SWITCH is a step whose `focus_id` differs from the
        previous step's, to and from `none` included.
    R5  A DESTINATION EPISODE (A §3.1, the hold) is one `destination_chosen`
        row and the first `destination_reached` or `destination_cleared` row
        for the same cell after it, in file order; a closing row closes the
        EARLIEST episode still open for its cell, so a cell named twice is two
        episodes and not one. `end` is `reached` or the clearing's own `reason`
        (`no_way`, `replaced`, `dropped`), and `held_steps` is the closing
        row's own field, which is `end_step - step`: R4 walked toward the cell
        on the naming step and on every step up to but not including the step
        that ended the hold, because a hold ends at the START of its step.
        An episode with no closing row is OPEN — the cell ended while the body
        still held it. Then `end` is `open`, `end_step` is the cell's last
        step, and `held_steps` is `last_step - step + 1`, one more than the
        closed form, because no step ended the hold: R4 walked toward it on the
        last step too. `steps_per_destination` is the mean of `held_steps` over
        every episode, the open one included, and None where there are none.
    R6  AN R3 ASK is a `calls.jsonl` row of round `R3` with `attempt` 1: a
        second attempt is the same ask sent again with a reason line (A §3.4),
        not another ask. Its OCCASION is read off that step, by these rules in
        this order and no other: `reached` if a `destination_reached` row has
        the step; `no_way` if a `destination_cleared` row with reason `no_way`
        has it; `event` if any R1 call has it — the gate opened the step's asks
        and the hold stood; else `missing`, nothing was held. The order is the
        controller's own (A §3.1, `trace._occasion`): a step that both reached
        the held cell and ran the gate's asks is a `reached`. `r3_occasions`
        counts the occasions of the steps that asked, so an occasion no step
        had is absent, which is the same claim as a count of 0 (`_normalise`),
        and the counts sum to `r3_asks` unless a cell logged two first attempts
        on one step.

WHAT THIS MODULE DOES NOT DO. It never writes into a cell directory, never
touches `__main__.py` (the chair wires `main` into `python -m p3focus read`),
and never repairs a row it finds wrong — it reports the disagreement and leaves
both readings in the output.
"""
from __future__ import annotations

import json
import re
import sys
from collections import Counter
from pathlib import Path

from p3focus import axis, constants

#: Walkable material names for R3: the vendor's own three plus water, which
#: this line pins walkable (A §1.1). `test_reader.py` pins this against
#: `world.WALKABLE`, which is the same set read off the vendored Crafter —
#: the reader keeps its own copy so that reading a log needs no world at all.
WALKABLE = frozenset({"grass", "path", "sand", "water"})

#: R1's words, beside the note's three cells. From the note itself (A §1.1):
#: "my pickaxe is there", "my rope is there", "then come to me at …", "a note
#: from your human player".
#:
# A-QUESTION: the return cell IS the spawn in every seed (`constants.ERRANDS`),
# so one of the rule's three coordinates — seed 7's `[32, 31]`, shown axis — is
# also the cell the body started on and may write about for its own reasons. An
# entry that says "go back to [32, 31] and map outward from there" reads as an
# errand entry here. The brief fixes the three cells, so all three are kept; if
# the chair would rather the return were dropped from the words, it is one line.
ERRAND_WORDS = ("pickaxe", "rope", "come to me", "human")

#: The entry fields R1 reads (A §2, minus `id`).
ENTRY_TEXT_FIELDS = ("name", "at", "why", "until", "when")   # `at` renders as "[x, y]" (A §2)

#: A §2's dawn list — the one list the reader may name without having seen it,
#: because A §2 seeds it on every trace arm. Used in the two places where no
#: snapshot can show it: a cell with no `ops_applied` row at all, and an id the
#: first snapshot's own ops delete before that snapshot is taken. Everywhere
#: else the entries come from the rows (R2).
DAWN_ENTRIES = ({"id": "e1", "name": "map_world", "until": "every walkable cell mapped"},)

#: The arms that keep a list (A §2). chat has none.
TRACE_ARMS = ("flat", "focus", "sliced")

#: The arm whose rows carry a focus (A §4.3: "focus arm; else null").
FOCUS_ARM = "focus"

#: The arms that hold a destination between asks (A §3.1, the hold, and A §4.2's
#: three rows). chat names one a turn and holds nothing; flat joined them
#: (A §7 D9, E2: the control for the hold itself), holding one without an
#: R3 to re-open it.
HOLD_ARMS = ("flat", "focus", "sliced")

#: The arms that ask R3 (A §3.1). flat holds a destination and has no R3, so its
#: `R3 asks` and its occasions are empty rather than 0 — there is no round to
#: count — and `destinations_named`, which the other holding arms have not got,
#: is the flat reply's own (A §4.4).
R3_ARMS = ("focus", "sliced")

#: The dawn entry's name, for `after_errands`' summary of what was in force.
MAP_WORLD = "map_world"

#: A §4.4's fields, and the only ones compared against a cell's `summary.json`.
#:
# A-QUESTION: `wall_s` is not here, and cannot be. A §4.4 ends "nothing in
# `summary.json` is needed that the rows cannot reproduce", but no row carries
# wall-clock time: `calls.jsonl` has `elapsed_s` per call, which sums to time
# spent waiting on the server, not to the cell's wall time, and the manifest has
# `started_at` with no matching end. Either the sentence has one exception or a
# row wants a finished-at stamp. The reader neither computes it nor judges it.
SUMMARY_FIELDS = (
    "errands_completed", "cells_reached", "steps_survived", "died",
    "first_errand_step", "note_to_first_errand_steps", "after_errands",
    "invalid_replies", "defaulted_replies", "focus_is_errand_fraction",
    "destinations_named", "destinations_chosen", "n_calls",
)

#: The two fields where a top-level null in `summary.json` against a 0 from the
#: rows is agreement and not a disagreement. A §4.4 gives `destinations_named`
#: to flat and chat, and `destinations_chosen` to every arm that holds one
#: (flat, A §7 D9), and the harness writes `null` for the arm each
#: does not apply to (`trace.summary`);
#: the reader counts rows for every arm and finds none, which is the same claim
#: about the same cell. Nowhere else: for every other field a null against a 0
#: is two different readings and is reported.
NULL_IS_ZERO_FIELDS = ("destinations_named", "destinations_chosen")

#: `trajectory`'s marks, highest precedence first (a cell gets the first that
#: applies). Death outranks everything because it happened once; the errand
#: digits outrank the spawn because for every seed in `constants.ERRANDS` the
#: return cell IS the spawn, and "3" is the more informative of the two.
MAP_UNSEEN, MAP_SEEN, MAP_WALKED, MAP_SPAWN, MAP_DIED = ".", ":", "#", "S", "X"


# -- reading the files ---------------------------------------------------------

def _read_json(path):
    """A JSON file, or None if it is not there."""
    path = Path(path)
    return json.loads(path.read_text()) if path.exists() else None


def _read_jsonl(path):
    """A `.jsonl` file as a list of rows, in file order; [] if it is not there.

    Blank lines are skipped; a line that will not parse raises, naming the file
    and the line number, because a reader that silently drops a row reports a
    number nobody can check.
    """
    path = Path(path)
    if not path.exists():
        return []
    rows = []
    for n, line in enumerate(path.read_text().split("\n"), 1):
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}:{n}: not JSON ({exc})") from exc
    return rows


class Cell:
    """One cell directory's rows (A §4), read once and held in file order.

    `manifest.json` is required: it carries the arm and the seed, and the reader
    does not guess either from the directory's name. Everything else may be
    missing — a cell that died before its first call has no `calls.jsonl` — and
    reads as no rows at all.
    """

    def __init__(self, cell_dir):
        self.dir = Path(cell_dir)
        manifest = _read_json(self.dir / "manifest.json")
        if manifest is None:
            raise FileNotFoundError(
                f"{self.dir}/manifest.json is not there; A §4 gives every cell one, and "
                f"the reader takes the arm and the seed from it rather than from a name")
        self.manifest = manifest
        self.arm = manifest["arm"]
        self.seed = int(manifest["seed"])
        self.events = _read_jsonl(self.dir / "events.jsonl")
        self.actions = _read_jsonl(self.dir / "actions.jsonl")
        self.frames = _read_jsonl(self.dir / "frames.jsonl")
        self.calls = _read_jsonl(self.dir / "calls.jsonl")
        self.summary = _read_json(self.dir / "summary.json")

    def of_kind(self, kind):
        """This cell's `events.jsonl` rows of one kind, in file order."""
        return [r for r in self.events if r.get("kind") == kind]

    @property
    def last_step(self):
        """The last frame's step — the body's survival in world steps (A §4.4).
        0 when there are no frames, which is a cell that never reset."""
        return int(self.frames[-1]["step"]) if self.frames else 0

    def frame_at(self, step):
        """The frame for a step, or None. Frames are one per step from 0 up
        (A §4.4), but this does not assume the file is complete."""
        for f in self.frames:
            if int(f["step"]) == int(step):
                return f
        return None


# -- R1: the errand-entry rule -------------------------------------------------

def errand_cells_shown(seed):
    """The seed's three errand cells in the SHOWN axis, formatted as the note
    writes them (A §1.1): `["[42, 23]", "[22, 39]", "[32, 31]"]` for seed 7."""
    return [f"[{p[0]}, {p[1]}]" for p in
            (axis.shown_pos(c) for c in constants.ERRANDS[int(seed)])]


def entry_text(entry):
    """One entry's readable text (A §2's four model-written fields), lowercased
    and joined. `id` is not in it: an id is the harness's word, not the body's."""
    parts = []
    for f in ENTRY_TEXT_FIELDS:
        v = entry.get(f)
        if v in (None, ""):
            continue
        # an `at` is a position, not prose: written as the note writes cells, so R1's
        # coordinate pattern reads it (A §2)
        parts.append(f"[{int(v[0])}, {int(v[1])}]" if isinstance(v, (list, tuple)) else str(v))
    return " ".join(parts).lower()


def errand_matches(entry, seed):
    """What of the note this entry's text carries — rule R1, as a list.

    Empty means it is not an errand entry. A coordinate matches with any spacing
    inside its brackets (`[42,23]` and `[42, 23]` are the same cell written by
    two hands); a bare `42, 23` does not, because two numbers with a comma
    between them are not a claim about a cell.
    """
    text = entry_text(entry)
    hits = []
    for cell in constants.ERRANDS[int(seed)]:
        x, y = axis.shown_pos(cell)
        if re.search(rf"\[\s*{x}\s*,\s*{y}\s*\]", text):
            hits.append(f"[{x}, {y}]")
    hits.extend(w for w in ERRAND_WORDS if w in text)
    return hits


def _id_order(entry_id):
    """Sort key for `e1`, `e2`, … — numeric where the id has A §2's shape, and
    after every such id where it has not."""
    m = re.fullmatch(r"e(\d+)", str(entry_id))
    return (0, int(m.group(1)), "") if m else (1, 0, str(entry_id))


# -- the list, from the ops rows (R2) ------------------------------------------

def list_events(cell):
    """Every list entry the rows show, with the steps it arrived and left on.

    One dict per entry, in id order:

        {"id", "added_step", "seeded", "removed_step", "steps_on_list",
         "is_errand", "matched", "name"}

    `added_step` is the step of the `ops_applied` row that first shows the id,
    or 0 for a dawn entry (R2); `removed_step` is the step of the first row that
    no longer shows it, or None if it was still on the list when the cell ended;
    `steps_on_list` runs from `added_step` to `removed_step` or to the last
    frame. `is_errand` is R1 over every version of the entry that was ever on
    the list — an entry edited away from the errand still counted as one while
    it stood — and `matched` is the union of what matched. `name` is the last
    version's.

    This is the plan's "how long the errand stays on the list", per entry.
    """
    rows = [r for r in cell.events if r.get("kind") == "ops_applied"]
    end = cell.last_step
    records = {}

    def note(entry, step, seeded):
        rec = records.get(entry["id"])
        if rec is None:
            rec = records[entry["id"]] = {
                "id": entry["id"], "added_step": 0 if seeded else int(step),
                "seeded": bool(seeded), "removed_step": None, "steps_on_list": None,
                "is_errand": False, "matched": [], "name": None}
        rec["name"] = entry.get("name")
        for hit in errand_matches(entry, cell.seed):
            if hit not in rec["matched"]:
                rec["matched"].append(hit)
        rec["is_errand"] = rec["is_errand"] or bool(rec["matched"])
        return rec

    if not rows and cell.arm in TRACE_ARMS:
        # no snapshot exists, so the only list this cell ever had is A §2's dawn
        for entry in DAWN_ENTRIES:
            note(dict(entry), 0, seeded=True)
    for i, row in enumerate(rows):
        step = int(row.get("step", 0))
        after = {e["id"]: e for e in (row.get("list_after") or [])}
        fresh = sorted((eid for eid in after if eid not in records), key=_id_order)
        if i == 0:
            # R2: the ids this row's adds produced are the highest-numbered of
            # the ones new to me; anything below them was on the list already.
            n_added = sum(1 for op in (row.get("ops") or []) if op.get("op") == "add")
            seeded = set(fresh[:max(0, len(fresh) - n_added)])
            # …and an id this very row edits or deletes that its snapshot no
            # longer shows was also on the list before it, though the reader
            # never sees it there. A body that deletes the map task on its first
            # ask would otherwise leave no trace of having had one; the step it
            # went is set by the loop below, like any other removal.
            for op in row.get("ops") or []:
                gone = op.get("id")
                if op.get("op") in ("edit", "delete") and gone and gone not in after:
                    note(_dawn_entry(gone), 0, seeded=True)
        else:
            seeded = set()   # every earlier snapshot has been read; new here means added here
        for entry_id in fresh:
            note(after[entry_id], step, seeded=entry_id in seeded)
        for entry in after.values():
            note(entry, step, seeded=False)      # edits: keep the latest text
        for entry_id, rec in records.items():
            if entry_id not in after and rec["removed_step"] is None:
                rec["removed_step"] = step
    for rec in records.values():
        gone = rec["removed_step"]
        rec["steps_on_list"] = (end if gone is None else gone) - rec["added_step"]
    return [records[k] for k in sorted(records, key=_id_order)]


def _dawn_entry(entry_id):
    """A §2's dawn entry with that id, or a bare record of an entry whose words
    no snapshot ever showed. The dawn list is the one list the reader may name
    without having seen it: A §2 seeds it on every trace arm."""
    for entry in DAWN_ENTRIES:
        if entry["id"] == entry_id:
            return dict(entry)
    return {"id": entry_id}


def _by_id(entries):
    return {rec["id"]: rec for rec in entries}


def _focus_class(focus_id, entries_by_id):
    """`after_errands`' four buckets for one step's `focus_id`: an errand entry,
    the seeded map task, something the body made itself, or nothing in force.
    An id no snapshot ever showed reads as `other` — the reader will not guess
    what it said."""
    if focus_id in (None, "none"):
        return "none"
    rec = entries_by_id.get(focus_id)
    if rec is None:
        return "other"
    if rec["is_errand"]:
        return "errand"
    if str(rec.get("name") or "").strip().lower() == MAP_WORLD:
        return "map_world"
    return "other"


# -- R3: the seen set, recomputed from the frames ------------------------------

def seen_growth(frames):
    """`(sizes, seen)` — the seen set after every frame, and the set itself.

    Rule R3. `sizes` maps a step to the size of the set after that step's frame,
    so "new cells between step a and step b" is `sizes[b] - sizes[a]`. WORLD
    axis: window row `r`, column `c` of a frame at `(px, py)` with a window of
    side `n` is the cell `(px + c - n//2, py + r - n//2)`.
    """
    seen = set()
    sizes = {}
    for frame in frames:
        px, py = (int(v) for v in frame["player"]["pos"])
        window = frame.get("window") or []
        r = len(window) // 2
        for row_i, row in enumerate(window):
            for col_i, name in enumerate(row):
                if name in WALKABLE:
                    seen.add((px + col_i - r, py + row_i - r))
        if frame.get("standing_on") in WALKABLE:
            seen.add((px, py))     # the window draws the body over its own cell
        sizes[int(frame["step"])] = len(seen)
    return sizes, seen


def _size_at(sizes, step):
    """The seen set's size after `step`, or after the last step before it when
    that frame is missing; 0 if no frame reaches it."""
    if step in sizes:
        return sizes[step]
    earlier = [s for s in sizes if s <= step]
    return sizes[max(earlier)] if earlier else 0


# -- the arrival ledger, re-derived from positions (A §1.1) --------------------

def derive_arrivals(cell, note_step):
    """The arrivals the positions in `frames.jsonl` support, in step order.

    A §1.1's rule, from the rows alone: a visit counts the first time the body
    stands on its cell, the two visits in any order, the return only after both
    of them, and nothing counts on or before the step the note landed (no errand
    exists for the body before it). `note_step` None means no note row and no
    manifest to fall back on, and then nothing can be derived.
    """
    cells = [tuple(int(v) for v in c) for c in constants.ERRANDS[cell.seed]]
    reached, rows = {}, []
    if note_step is None:
        return rows
    for frame in cell.frames:
        step = int(frame["step"])
        if step <= int(note_step):
            continue
        pos = tuple(int(v) for v in frame["player"]["pos"])
        for index, errand in enumerate(cells):
            if errand != pos or index in reached:
                continue
            is_return = index == len(cells) - 1
            if is_return and any(i not in reached for i in range(len(cells) - 1)):
                continue
            reached[index] = step
            rows.append({"index": index, "cell": list(errand), "step": step})
    return rows


def ledger_check(cell, note_step):
    """A §1.1's check: the ledger from positions, beside the ledger from rows.

    The reader never replaces `events.jsonl`'s `arrival` rows with its own
    reading — it reports both and the differences between them:

        missing_in_events   the positions support an arrival no row claims
        missing_in_frames   a row claims an arrival the positions do not support
        step_mismatch       both have it, on different steps
        cell_mismatch       the row's `cell` is not the seed's cell for its index
        completed_mismatch  `errands_completed` and the derived completion differ

    An `arrival` row's `first` field is not read here: A §4.2 says a cell gets
    one row, on the step it first counts, so every row is a first.
    """
    # A-QUESTION: `arrival`'s `first` field — two merged pieces disagree.
    # `cell.EVENT_FIELDS["arrival"]` is `("cell", "index", "first")` and
    # `EventLog.event` raises unless all three are given; `world._arrivals`
    # writes `cell` and `index` and goes through `JsonlLog.append` instead, so
    # a live cell's rows would have no `first` while the gate's tests pass one.
    # The reader reads both shapes and ignores the field. A §4.2's own line
    # names neither — it says the return's row "also carries
    # `errands_completed` beside it", which this reads as the separate row
    # `world._arrivals` writes and `EVENT_FIELDS` lists as its own kind.
    derived = derive_arrivals(cell, note_step)
    logged = [{"index": int(r["index"]), "cell": list(r.get("cell") or []),
               "step": int(r["step"])} for r in cell.of_kind("arrival")]
    cells = [list(c) for c in constants.ERRANDS[cell.seed]]
    by_frames = {r["index"]: r for r in derived}
    by_events = {r["index"]: r for r in logged}
    differences = []
    for index in sorted(set(by_frames) | set(by_events)):
        seen_now, said = by_frames.get(index), by_events.get(index)
        if said is None:
            differences.append({"kind": "missing_in_events", "index": index,
                                "frames_step": seen_now["step"], "events_step": None})
        elif seen_now is None:
            differences.append({"kind": "missing_in_frames", "index": index,
                                "frames_step": None, "events_step": said["step"]})
        elif seen_now["step"] != said["step"]:
            differences.append({"kind": "step_mismatch", "index": index,
                                "frames_step": seen_now["step"], "events_step": said["step"]})
        if said is not None and 0 <= index < len(cells) and said["cell"] != cells[index]:
            differences.append({"kind": "cell_mismatch", "index": index,
                                "events_cell": said["cell"], "seed_cell": cells[index]})
        if said is not None and not 0 <= index < len(cells):
            differences.append({"kind": "index_out_of_range", "index": index,
                                "events_step": said["step"], "n_errands": len(cells)})
    completed_derived = len(derived) == len(cells)
    completed_logged = bool(cell.of_kind("errands_completed"))
    if completed_derived != completed_logged:
        differences.append({"kind": "completed_mismatch",
                            "frames": completed_derived, "events": completed_logged})
    manifest_cells = [list(c) for c in (cell.manifest.get("errand_cells") or [])]
    return {
        "note_step": None if note_step is None else int(note_step),
        "derived": derived, "logged": logged,
        "agrees": not differences, "differences": differences,
        "errands_completed_derived": completed_derived,
        "errands_completed_logged": completed_logged,
        "manifest_errand_cells_agree": manifest_cells == cells,
    }


# -- R5, R6: the destination the body held (A §3.1) ----------------------------

def destination_episodes(cell):
    """Every destination the body held, one record per `destination_chosen` row
    in step order — rule R5:

        {"cell", "step", "end_step", "end", "held_steps"}

    `end` is `reached`, `no_way`, `replaced`, `dropped` or `open`. `cell` is
    the world axis, as the row writes it.
    """
    episodes = []
    open_for = {}      # cell -> the indexes of its still-open episodes, earliest first
    for row in cell.events:
        kind = row.get("kind")
        if kind not in ("destination_chosen", "destination_reached", "destination_cleared"):
            continue
        where = tuple(int(v) for v in (row.get("cell") or ()))
        if kind == "destination_chosen":
            episodes.append({"cell": list(where), "step": int(row.get("step", 0)),
                             "end_step": None, "end": None, "held_steps": None})
            open_for.setdefault(where, []).append(len(episodes) - 1)
            continue
        waiting = open_for.get(where) or []
        if not waiting:
            # a reached or a clearing with no choice of that cell open before
            # it: the rows are the harness's, and the reader reports the
            # episodes they do support rather than inventing one they do not
            continue
        record = episodes[waiting.pop(0)]
        record["end_step"] = int(row.get("step", 0))
        record["end"] = "reached" if kind == "destination_reached" else str(row["reason"])
        record["held_steps"] = int(row["held_steps"])     # R5: the row's own count
    end = cell.last_step
    for record in episodes:
        if record["end"] is None:
            # R5's open rule: no row ended this hold, so it ran to the cell's
            # last step and R4 walked toward it on that step too — one more
            # step than a closed episode of the same span.
            record["end"] = "open"
            record["end_step"] = end
            record["held_steps"] = end - record["step"] + 1
    return episodes


def _r3_steps(cell):
    """The steps R3 was asked on, in order, and the number of asks (R6). The two
    differ only if a cell logged two first attempts on one step."""
    steps = [int(r.get("step", 0)) for r in cell.calls
             if r.get("round") == "R3" and int(r.get("attempt", 1)) == 1]
    return sorted(set(steps)), len(steps)


def r3_occasions(cell):
    """Why R3 was asked, counted by occasion over the steps that asked (R6).

    An occasion no step had is absent, as in every other counts dict here
    (`_counts_by`).
    """
    steps, _ = _r3_steps(cell)
    reached = {int(r["step"]) for r in cell.of_kind("destination_reached")}
    no_way = {int(r["step"]) for r in cell.of_kind("destination_cleared")
              if r.get("reason") == "no_way"}
    asked = {int(r.get("step", 0)) for r in cell.calls if r.get("round") == "R1"}
    counts = Counter()
    for step in steps:
        if step in reached:
            counts["reached"] += 1
        elif step in no_way:
            counts["no_way"] += 1
        elif step in asked:
            counts["event"] += 1
        else:
            counts["missing"] += 1
    return dict(counts)


# -- the summary (A §4.4), recomputed ------------------------------------------

def _counts_by(rows, key):
    """`{value: n}` over a key of some event rows; a value no row carries is
    simply absent, which is the same claim as a count of 0 (`_normalise`)."""
    return dict(Counter(str(r.get(key)) for r in rows))


def _destinations_named(cell):
    """A §4.4's `destinations_named`: the replies that named a cell.

    In chat the action row's `destination` is what that turn's reply named, so
    the rows are the count. In flat, since the hold (A §7 D9), the row
    carries the cell **in force** on that step — one row per step held, and none
    at all on the step a reply names one, because the body acted before it
    answered. So flat's count comes from the replies themselves, `calls.jsonl`'s
    `parsed`: one accepted `flat` reply a step, its `destination` not null. That
    counts the held cell named again, which writes no `destination_chosen` row —
    the two fields are two quantities, and this is the one A §4.4 names.
    """
    if cell.arm == "flat":
        return sum(1 for r in cell.calls
                   if r.get("round") == "flat" and r.get("valid")
                   and isinstance(r.get("parsed"), dict)
                   and r["parsed"].get("destination") is not None)
    return sum(1 for r in cell.actions if r.get("destination") is not None)


def _note_step(cell):
    """The step the note landed: the `note_landed` row if there is one, else the
    manifest's `note_step` (A §4.4 puts it there so a reader never guesses)."""
    rows = cell.of_kind("note_landed")
    if rows:
        return int(rows[0]["step"])
    value = cell.manifest.get("note_step")
    return None if value is None else int(value)


def _after_errands(cell, sizes, entries_by_id):
    """A §4.4's `after_errands`, or None when the errands were never completed.

    What the body did with the steps it had left: how many there were, how many
    cells it saw in them that it had not seen before (R3), and — focus only —
    what was in force on each of them, as counts of the four kinds. After the
    errands the body should return to the mapping task, and this is the
    indicator.
    """
    done = cell.of_kind("errands_completed")
    if not done:
        return None
    at = int(done[0]["step"])
    end = cell.last_step
    rows = [r for r in cell.actions if at < int(r.get("step", -1)) <= end]
    focus_ids = None
    if cell.arm == FOCUS_ARM:
        focus_ids = {"errand": 0, "map_world": 0, "other": 0, "none": 0}
        for row in rows:
            focus_ids[_focus_class(row.get("focus_id"), entries_by_id)] += 1
    return {
        "completed_step": at,
        "steps": max(0, end - at),
        "new_cells": _size_at(sizes, end) - _size_at(sizes, at),
        "focus_ids": focus_ids,
    }


def _focus_numbers(cell, entries_by_id):
    """The focus arm's three (A §4.4, and the plan's "how often the entry in
    force is an errand"). None for every other arm, whose rows carry no focus.

    The fraction's denominator is the steps the cell ran — `actions.jsonl` rows
    — so a body that held an errand for ten of forty steps reads 0.25 whether
    the other thirty were spent on the map task or on nothing (rule R4).
    """
    if cell.arm != FOCUS_ARM:
        return {"focus_is_errand_fraction": None, "focus_is_errand_steps": None,
                "focus_none_steps": None, "focus_switches": None}
    ids = [r.get("focus_id") for r in cell.actions]
    errand = sum(1 for i in ids if _focus_class(i, entries_by_id) == "errand")
    none = sum(1 for i in ids if i in (None, "none"))
    switches = sum(1 for a, b in zip(ids, ids[1:]) if a != b)
    return {
        "focus_is_errand_fraction": (errand / len(ids)) if ids else None,
        "focus_is_errand_steps": errand,
        "focus_none_steps": none,
        "focus_switches": switches,
    }


def _empty_count(value):
    """A dict entry that claims nothing: a zero count or a missing value. `False`
    is not one of them, even though it equals 0."""
    return value is None or (isinstance(value, int) and not isinstance(value, bool)
                             and value == 0)


def _normalise(value):
    """Two readings of the same field, made comparable: counts dicts lose their
    zeros (a round with no invalid reply and a round not named are the same
    claim) and tuples become lists, as JSON would have them."""
    if isinstance(value, dict):
        return {k: _normalise(v) for k, v in value.items() if not _empty_count(v)}
    if isinstance(value, (list, tuple)):
        return [_normalise(v) for v in value]
    return value


def _same(a, b):
    if isinstance(a, float) or isinstance(b, float):
        try:
            return abs(float(a) - float(b)) <= 1e-9
        except (TypeError, ValueError):
            return False
    return _normalise(a) == _normalise(b)


def _null_against_zero(a, b):
    """One of the two is None and the other is a count of 0. `False` is not a
    count, though it equals one (`_empty_count`'s rule, held here too)."""
    values = [a, b]
    return (None in values
            and any(isinstance(v, int) and not isinstance(v, bool) and v == 0
                    for v in values))


def summary_disagreements(mine, theirs):
    """Where the cell's own `summary.json` differs from the rows (A §4.4).

    Only A §4.4's fields, and only those the file actually carries: a field it
    leaves out is not a disagreement, and `wall_s`, which no row records, is
    never judged. The rows' reading is `rows`; the file's is `summary_json`.

    `NULL_IS_ZERO_FIELDS` is the one loosening: for those two fields, and only
    for them, a top-level null beside a 0 is agreement.
    """
    if not theirs:
        return []
    out = []
    for field in SUMMARY_FIELDS:
        if field not in theirs or field not in mine:
            continue
        if field in NULL_IS_ZERO_FIELDS and _null_against_zero(mine[field], theirs[field]):
            continue
        if not _same(mine[field], theirs[field]):
            out.append({"field": field, "rows": mine[field], "summary_json": theirs[field]})
    return out


def read_cell(cell_dir):
    """One cell's numbers, every one of them recomputed from A §4's rows.

    Returns a JSON-ready dict: A §4.4's `summary.json` fields, plus the reader's
    own `list_events`, `ledger_check`, `retries`, `note_step`, the focus counts
    and the hold's — `destination_episodes`, `steps_per_destination`, `r3_asks`
    and `r3_occasions` (R5, R6) — plus `summary_disagreements`, where the cell's
    own summary file disagrees with the rows. The file is never believed (A
    §1.1's rule for the ledger, held here for every field).
    """
    cell = Cell(cell_dir)
    arrivals = cell.of_kind("arrival")
    note_step = _note_step(cell)
    first_errand = min((int(r["step"]) for r in arrivals), default=None)
    entries = list_events(cell)
    entries_by_id = _by_id(entries)
    sizes, _ = seen_growth(cell.frames)
    episodes = destination_episodes(cell)
    held = [e["held_steps"] for e in episodes]
    _, r3_asks = _r3_steps(cell)
    out = {
        "cell_dir": str(cell.dir),
        "arm": cell.arm,
        "seed": cell.seed,
        "steps_budget": int(cell.manifest.get("steps", 0)),
        "errands_completed": bool(cell.of_kind("errands_completed")),
        "cells_reached": len({int(r["index"]) for r in arrivals}),
        "steps_survived": cell.last_step,
        "died": bool(cell.of_kind("death")),
        "first_errand_step": first_errand,
        "note_step": note_step,
        "note_to_first_errand_steps": (None if first_errand is None or note_step is None
                                       else first_errand - int(note_step)),
        "invalid_replies": _counts_by(cell.of_kind("reply_invalid"), "round"),
        "defaulted_replies": _counts_by(cell.of_kind("reply_defaulted"), "round"),
        "n_calls": len(cell.calls),
        "retries": sum(1 for r in cell.calls if int(r.get("attempt", 1)) == 2),
        # A-QUESTION: A §4.4 gates this field to "(flat, chat)". It is counted
        # here for every arm, because the count is a fact of the rows and a
        # trace row that named a destination would be a defect worth seeing (A
        # §4.3 gives `destination` to flat and chat and null to the rest). The
        # cost: if the harness writes `"destinations_named": null` in a focus
        # cell's summary.json, this reports a disagreement against its own 0.
        # Say the word and it becomes None for every arm but flat and chat.
        "destinations_named": _destinations_named(cell),
        # the hold (A §3.1), rules R5 and R6. Counted for every arm for the
        # same reason as `destinations_named` above — the rows are the fact —
        # and a bare arm, which holds nothing, reads 0 rows, [] episodes and
        # no asks. A §4.4 writes null for such an arm and the two readings are
        # held to agree (`NULL_IS_ZERO_FIELDS`), there and nowhere else.
        "destinations_chosen": len(cell.of_kind("destination_chosen")),
        "destination_episodes": episodes,
        "steps_per_destination": (sum(held) / len(held)) if held else None,
        "r3_asks": r3_asks,
        "r3_occasions": r3_occasions(cell),
        "list_events": entries,
    }
    out.update(_focus_numbers(cell, entries_by_id))
    out["after_errands"] = _after_errands(cell, sizes, entries_by_id)
    out["ledger_check"] = ledger_check(cell, note_step)
    out["summary_json_present"] = cell.summary is not None
    out["summary_disagreements"] = summary_disagreements(out, cell.summary)
    return out


# -- the table (the plan, "Reading") -------------------------------------------

_COLUMNS = ("arm", "seed", "errands completed", "cells reached", "steps survived",
            "died", "first errand step", "invalid replies", "focus is errand",
            "destinations", "R3 asks", "steps / dest")
_ALIGN = (":---", "---:", ":---:", "---:", "---:", ":---:", "---:", "---:", "---:",
          "---:", "---:", "---:")


def _arm_order(arm):
    return (constants.ARMS.index(arm), "") if arm in constants.ARMS else (len(constants.ARMS), arm)


def _row_cells(cell):
    frac = cell.get("focus_is_errand_fraction")
    # `destinations` is one column over two fields, because chat names one a
    # turn (`destinations_named`, A §4.3) and the three arms that hold one
    # choose it when they are asked (`destinations_chosen`, A §3.1); the numbers
    # are not the same quantity and the arm column says which is which. flat
    # holds one and has no R3 (A §7 D9), so its chosen count and its mean are
    # filled and its `R3 asks` is empty.
    holds = cell.get("arm") in HOLD_ARMS
    asks_r3 = cell.get("arm") in R3_ARMS
    destinations = cell.get("destinations_chosen" if holds else "destinations_named")
    per = cell.get("steps_per_destination")
    return (
        str(cell.get("arm")),
        str(cell.get("seed")),
        "✓" if cell.get("errands_completed") else "✗",
        str(cell.get("cells_reached")),
        str(cell.get("steps_survived")),
        "yes" if cell.get("died") else "no",
        "—" if cell.get("first_errand_step") is None else str(cell["first_errand_step"]),
        str(sum((cell.get("invalid_replies") or {}).values())),
        "—" if frac is None else f"{frac:.2f}",
        "—" if destinations is None else str(destinations),
        str(cell.get("r3_asks")) if asks_r3 else "—",
        "—" if not holds or per is None else f"{per:.1f}",
    )


def table(cells):
    """The plan's seed × arm table, as Markdown: one row per cell, then one line
    per arm with the cells that finished the errands over the cells that ran.

    `cells` are `read_cell` results. Rows are ordered by arm (A §5's order:
    flat, focus, chat, sliced) and then by seed, so two runs of the same panel
    print the same table. `invalid replies` is the total over the rounds;
    `focus is errand` is the fraction of steps whose entry in force was an
    errand entry (R1), and is empty for every arm but focus. The last three are
    the hold (A §3.1): `destinations` is the cells chosen in the arms that hold
    one — flat, focus and sliced — and the cells named in chat, two different
    quantities under one heading, and the arm column says which; `steps / dest`
    is the holding arms' (R5) and `R3 asks` the arms that ask R3 (R6), which is
    focus and sliced — flat holds without one (A §7 D9).

    At n=5 this shows direction, not significance (the plan, "Reading").
    """
    cells = sorted(cells, key=lambda c: (_arm_order(c.get("arm")), int(c.get("seed", 0))))
    lines = ["| " + " | ".join(_COLUMNS) + " |", "|" + "|".join(_ALIGN) + "|"]
    lines += ["| " + " | ".join(_row_cells(c)) + " |" for c in cells]
    lines.append("")
    for arm in sorted({c.get("arm") for c in cells}, key=_arm_order):
        of_arm = [c for c in cells if c.get("arm") == arm]
        done = sum(1 for c in of_arm if c.get("errands_completed"))
        lines.append(f"- {arm}: {done}/{len(of_arm)} cells completed the errands")
    return "\n".join(lines)


# -- the trajectory ------------------------------------------------------------

_ACTION_COLUMNS = ("step", "action", "pos", "drink", "health", "focus_id")
_ACTION_HEAD_TAIL = 20


def _map_grid(cell, seen):
    """The 64×64 character map: one char per world cell, marks as documented."""
    side = constants.WORLD_SIZE
    grid = [[MAP_UNSEEN] * side for _ in range(side)]
    for x, y in seen:
        if 0 <= x < side and 0 <= y < side:
            grid[y][x] = MAP_SEEN
    for frame in cell.frames:
        x, y = (int(v) for v in frame["player"]["pos"])
        if 0 <= x < side and 0 <= y < side:
            grid[y][x] = MAP_WALKED
    sx, sy = constants.SPAWN
    if 0 <= sx < side and 0 <= sy < side:
        grid[sy][sx] = MAP_SPAWN
    for index, errand in enumerate(constants.ERRANDS[cell.seed]):
        x, y = (int(v) for v in errand)
        if 0 <= x < side and 0 <= y < side:
            grid[y][x] = str(index + 1)
    deaths = cell.of_kind("death")
    if deaths:
        frame = cell.frame_at(int(deaths[0]["step"]))
        if frame is not None:
            x, y = (int(v) for v in frame["player"]["pos"])
            if 0 <= x < side and 0 <= y < side:
                grid[y][x] = MAP_DIED
    return grid


def _action_line(row):
    pos = row.get("pos_after")
    pos = "—" if pos is None else f"[{int(pos[0])}, {int(pos[1])}]"
    focus = row.get("focus_id")
    return ", ".join([
        str(row.get("step")), str(row.get("action")), pos,
        str(row.get("drink_after")), str(row.get("health_after")),
        "none" if focus is None else str(focus)])


def trajectory(cell_dir):
    """One cell as a map and its first and last twenty steps.

    The map is the world, 64×64, **world axis (+y down)**: row 0 is the top of
    the printed block and x runs right, which is the orientation of the frame's
    own window. It is NOT the shown axis the model read — `axis.shown_pos`
    carries one to the other, and the note's cells in shown coordinates are the
    same cells as the digits here.

        .  never seen        #  the body stood here     S  the spawn
        :  seen, not walked  1 2 3  the seed's errand cells, in order
        X  where it died

    A cell gets the first mark that applies, death first, then the errand
    digits, then the spawn: for every seed in `constants.ERRANDS` the return
    cell IS the spawn, and the digit is the more informative of the two, so `S`
    shows only where a seed puts them apart.
    """
    cell = Cell(cell_dir)
    _, seen = seen_growth(cell.frames)
    grid = _map_grid(cell, seen)
    shown = [f"{axis.shown_pos(c)}" for c in constants.ERRANDS[cell.seed]]
    head = [
        f"cell: {cell.dir.name}",
        f"arm: {cell.arm}   seed: {cell.seed}   steps survived: {cell.last_step}   "
        f"died: {'yes' if cell.of_kind('death') else 'no'}",
        f"map: {constants.WORLD_SIZE}×{constants.WORLD_SIZE}, WORLD axis (+y down): "
        f"row 0 at the top, x to the right. The model read these cells in the shown "
        f"axis (+y up): {', '.join(shown)}.",
        f"marks: {MAP_UNSEEN} unseen   {MAP_SEEN} seen   {MAP_WALKED} walked   "
        f"1 2 3 errand cells   {MAP_SPAWN} spawn   {MAP_DIED} died",
        "",
        "    " + "".join(str((x // 10) % 10) if x % 10 == 0 else " "
                         for x in range(constants.WORLD_SIZE)),
    ]
    head += [f"{y:3d} " + "".join(row) for y, row in enumerate(grid)]
    head += ["", f"actions (world axis; pos is pos_after): {', '.join(_ACTION_COLUMNS)}"]
    rows = cell.actions
    if len(rows) <= 2 * _ACTION_HEAD_TAIL:
        head += [f"  {_action_line(r)}" for r in rows]
    else:
        head += [f"  {_action_line(r)}" for r in rows[:_ACTION_HEAD_TAIL]]
        head += [f"  … {len(rows) - 2 * _ACTION_HEAD_TAIL} steps not shown …"]
        head += [f"  {_action_line(r)}" for r in rows[-_ACTION_HEAD_TAIL:]]
    return "\n".join(head)


# -- the command ---------------------------------------------------------------

USAGE = ("usage: reader <cell_dir>...          each cell's summary as JSON, then the table\n"
         "       reader --trajectory <cell_dir>...   the map and the first and last steps")


def main(argv=None):
    """`reader <cell_dir>...` and `reader --trajectory <cell_dir>`.

    Exit 0 on success, 3 on bad arguments — A §5's code for that, kept so the
    chair can wire this into `python -m p3focus read` without a second rule.
    """
    argv = list(sys.argv[1:] if argv is None else argv)
    trajectories = bool(argv) and argv[0] == "--trajectory"
    dirs = argv[1:] if trajectories else argv
    if not dirs or any(str(d).startswith("-") for d in dirs):
        print(USAGE, file=sys.stderr)
        return 3
    try:
        if trajectories:
            for i, cell_dir in enumerate(dirs):
                if i:
                    print()
                print(trajectory(cell_dir))
        else:
            cells = [read_cell(d) for d in dirs]
            for cell in cells:
                print(json.dumps(cell, sort_keys=True, indent=1))
            print()
            print(table(cells))
    except (FileNotFoundError, NotADirectoryError, ValueError, KeyError) as exc:
        print(f"reader: {exc}", file=sys.stderr)
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
