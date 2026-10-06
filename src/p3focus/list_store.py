"""The list the body keeps (A §2), and the entry in force.

The harness holds the list; the model changes it only through ops and never
re-emits it (A §2). Ids are `e1`, `e2`, … in the order entries were added, never
reused in a run, and entries render in id order because that is the order they
are held in.

**Validation is the whole reply's** (A §3.4): an `edit` or `delete` naming an id
that did not exist *before this reply* makes the reply invalid, and nothing is
applied — not even the ops before the bad one. The store reports the reason; the
controller sends the page again with it and then defaults.

**Deletes are held** in focus and sliced (A §2): `apply` returns the ids a reply
asked to delete and removes nothing, and R1.5 confirms them one at a time
through `confirm_delete`. In flat there is no R1.5, so `apply(..., hold=False)`
removes them as written (A §7, D5).

No coordinates cross this module: an entry is five strings and nothing here
reads the world, so neither axis (world +y down, shown +y up) appears.
"""

import json

#: the wire order of an entry's fields (A §2: id first, then the fields in the
#: order a page prints them; there is no rank). Rendering follows it, on a list
#: line, a focus line and inside R1.5's ask alike (B §4).
ENTRY_FIELDS = ("id", "name", "at", "when", "until", "why")
#: the three the model may leave unset; absent when unset, never null (B §4).
#: `at` (A §2) is the position the entry is about,
#: `[x, y]` in the SHOWN axis as the body wrote it — list content is the body's
#: and is never converted; it is checked to lie inside the world (A §3.4).
OPTIONAL_FIELDS = ("at", "when", "why")
#: what an `add` must carry
REQUIRED_FIELDS = ("name", "until")
#: what an `edit` may change — at least one of them (A §2, the grammar's rule)
EDITABLE_FIELDS = ("name", "at", "when", "until", "why")
#: the one field that is a position, not text
COORD_FIELDS = ("at",)

#: B §4: every trace arm's list starts here, with this single entry and no rank.
#: The body may delete it like any entry.
DAWN_ENTRY = {"name": "map_world", "until": "every walkable cell mapped"}

OPS = ("add", "edit", "delete")


class ListStore:
    """One cell's list (A §2). `entries` are dicts in id order; `focus` is the
    entry in force (an id or None), which only the focus arm reads (B §4).

    Dawn (B §4): the list starts with `e1 = map_world`, and the entry in force
    starts as `e1`. `ListStore(dawn=False)` starts empty, which no arm does and
    the tests want.
    """

    def __init__(self, dawn=True):
        self._entries = []
        self._next_id = 1
        self.focus = None
        if dawn:
            entry = self.add(**DAWN_ENTRY)
            self.focus = entry["id"]

    # -- reading ------------------------------------------------------------

    @property
    def entries(self):
        """The list, id order, as copies: nothing outside this module edits an
        entry in place (A §2, the harness holds the list)."""
        return [dict(e) for e in self._entries]

    @property
    def ids(self):
        """The ids on the list, id order (A §2: `e1`, `e2`, … in the order
        they were added)."""
        return [e["id"] for e in self._entries]

    def __len__(self):
        return len(self._entries)

    def get(self, entry_id):
        """The entry with this id (A §2), as a copy, or None."""
        for entry in self._entries:
            if entry["id"] == entry_id:
                return dict(entry)
        return None

    @property
    def focus_entry(self):
        """The entry in force, as a copy, or None (A §2). B §4 renders it on
        focus's acting pages, and `none` when it is missing."""
        return None if self.focus is None else self.get(self.focus)

    # -- the three ops (A §2) ----------------------------------------------

    def add(self, name, until, when=None, why=None, at=None):
        """Add an entry and give it the next id (A §2; ids are never reused).
        `at`, `when` and `why` are absent when unset, never null (B §4)."""
        entry = {"id": f"e{self._next_id}", "name": name, "until": until}
        if at is not None:
            entry["at"] = [int(at[0]), int(at[1])]
        if when is not None:
            entry["when"] = when
        if why is not None:
            entry["why"] = why
        self._next_id += 1
        self._entries.append(_ordered(entry))
        return dict(self._entries[-1])

    def edit(self, entry_id, **fields):
        """Change the named fields of one entry (A §2). Unknown id -> KeyError;
        the controller never reaches here, because `validate` refused first."""
        for i, entry in enumerate(self._entries):
            if entry["id"] == entry_id:
                merged = dict(entry)
                for key, value in fields.items():
                    if key not in EDITABLE_FIELDS:
                        raise ValueError(f"an edit may not set {key!r}; A §2 has {EDITABLE_FIELDS}")
                    if value is None:
                        merged.pop(key, None)
                    elif key in COORD_FIELDS:
                        merged[key] = [int(value[0]), int(value[1])]
                    else:
                        merged[key] = value
                self._entries[i] = _ordered(merged)
                return dict(self._entries[i])
        raise KeyError(entry_id)

    def delete(self, entry_id):
        """Remove one entry (A §2), and clear the entry in force when it was
        the one deleted. Returns True when something was removed, False when
        the id was already gone — which happens when one reply deletes the same
        id twice. Clearing the focus is the caller's cue to log `focus_missing`
        with reason `deleted` (A §4.2)."""
        for i, entry in enumerate(self._entries):
            if entry["id"] == entry_id:
                del self._entries[i]
                if self.focus == entry_id:
                    self.focus = None
                return True
        return False

    def set_focus(self, entry_id):
        """R2's answer: the entry in force (A §2). Refuses an id that is not on
        the list — `validate_focus` is the controller's check, and reaching here
        with a bad id is a bug, not a bad reply."""
        if entry_id is not None and self.get(entry_id) is None:
            raise KeyError(entry_id)
        self.focus = entry_id
        return entry_id

    # -- a whole reply (A §3.4) --------------------------------------------

    def validate(self, ops):
        """Why this reply's ops cannot be applied, or None (A §3.4).

        The whole reply is refused before anything is applied, so every id is
        checked against the ids that exist **before** the reply: an `add` in the
        same reply does not make an id an `edit` later in it may name (A §2,
        "an `edit` or `delete` may only name an id that existed before this
        reply"). The string returned is the reason line the page is sent again
        with, and `ops_rejected.reason` (A §4.2).
        """
        if not isinstance(ops, list) or not ops:
            return "an operation list must be one to five operations"
        known = set(self.ids)
        for i, op in enumerate(ops):
            reason = _op_shape(op, i)
            if reason:
                return reason
            if op["op"] in ("edit", "delete") and op["id"] not in known:
                return (f'operation {i + 1} names the id "{op["id"]}", which is not on your '
                        f"list; the ids are {', '.join(sorted(known)) or 'none — the list is empty'}")
        return None

    def validate_focus(self, entry_id):
        """Why R2's id cannot be taken, or None (A §3.4: ids exist)."""
        if self.get(entry_id) is None:
            return (f'"{entry_id}" is not an id on your list; the ids are '
                    f"{', '.join(self.ids) or 'none — the list is empty'}")
        return None

    def apply(self, ops, source, hold=True):
        """Apply a **validated** reply's ops in order and return
        `(ops_applied_row, held_delete_ids)` (A §2, A §4.2).

        `source` is `R1` or `flat`. With `hold` (focus and sliced) every
        `delete` is held for R1.5 and the ids come back in op order; with
        `hold=False` (flat, A §7 D5) they are removed as written. `add` and
        `edit` always apply at once, so R1.5's page already shows them (B §3.2).

        The row's `list_after` is the list as it stands when this returns —
        which, with held deletes, still carries the entries R1.5 has yet to
        confirm. A confirmed deletion writes its own `delete_confirmed` row.
        """
        held = []
        for op in ops:
            kind = op["op"]
            if kind == "add":
                self.add(**{k: v for k, v in op.items() if k != "op"})
            elif kind == "edit":
                self.edit(op["id"], **{k: v for k, v in op.items() if k not in ("op", "id")})
            elif hold:
                if op["id"] not in held:
                    # A-QUESTION: A §2 orders one R1.5 per `delete`, in op order,
                    # and does not say what a reply that deletes one id twice
                    # means. The repeat is dropped here: the second R1.5 would
                    # render an entry that the first one's confirmation had
                    # already removed, and there is nothing left to confirm.
                    held.append(op["id"])
            else:
                self.delete(op["id"])
        row = {"source": source, "ops": [dict(op) for op in ops], "list_after": self.entries}
        return row, held

    def confirm_delete(self, entry_id):
        """R1.5 said true: remove the held entry (A §2, B §3.2). Returns
        `(removed, focus_cleared)` — `focus_cleared` is the controller's cue for
        `focus_missing` with reason `deleted` (A §4.2)."""
        was_focus = self.focus == entry_id
        removed = self.delete(entry_id)
        return removed, bool(removed and was_focus)

    # -- rendering (B §4) ---------------------------------------------------

    def render_entry(self, entry):
        """One entry as the page prints it (B §4): fields in `ENTRY_FIELDS`
        order, an optional field the body did not set absent and never null,
        `ensure_ascii` off so a name reads here as it reads in history."""
        return json.dumps(_ordered(entry), ensure_ascii=False)

    def render_list(self):
        """The whole list as the page prints it (B §4): id order, an empty list
        as `[]`."""
        return json.dumps([_ordered(e) for e in self._entries], ensure_ascii=False)


def render_entry(entry):
    """One entry as a page prints it (B §4). The module-level form, for the page
    builders, which have an entry and no store."""
    return json.dumps(_ordered(entry), ensure_ascii=False)


def render_list(entries):
    """A list of entries as a page prints it (B §4)."""
    return json.dumps([_ordered(e) for e in entries], ensure_ascii=False)


def _ordered(entry):
    """An entry's fields in `ENTRY_FIELDS` order, unset optionals dropped."""
    return {k: entry[k] for k in ENTRY_FIELDS if entry.get(k) is not None}


def _op_shape(op, i):
    """Why this op is not one of A §2's three, or None. The grammar cannot be
    reached by a scripted reply (A §5), so the shape is checked here too and a
    malformed op is a reason rather than a crash."""
    if not isinstance(op, dict):
        return f"operation {i + 1} is not an object"
    kind = op.get("op")
    if kind not in OPS:
        return f'operation {i + 1} has no "op" among {list(OPS)}'
    keys = set(op) - {"op"}
    if kind == "add":
        missing = [f for f in REQUIRED_FIELDS if not isinstance(op.get(f), str)]
        if missing:
            return f'operation {i + 1} is an add without {" and ".join(missing)}'
        spare = keys - set(EDITABLE_FIELDS)
        if spare:
            return f"operation {i + 1} is an add with the spare field {sorted(spare)[0]!r}"
        return _coord_shape(op, i)
    if not isinstance(op.get("id"), str):
        return f'operation {i + 1} is a {kind} without an "id"'
    if kind == "delete":
        if keys - {"id"}:
            return f"operation {i + 1} is a delete with more than an id"
        return None
    changed = keys & set(EDITABLE_FIELDS)
    if not changed:
        return f"operation {i + 1} is an edit that changes no field"
    spare = keys - set(EDITABLE_FIELDS) - {"id"}
    if spare:
        return f"operation {i + 1} is an edit with the spare field {sorted(spare)[0]!r}"
    if any(not isinstance(op[f], str) for f in changed - set(COORD_FIELDS)):
        return f"operation {i + 1} is an edit whose fields must be text"
    return _coord_shape(op, i)


def _coord_shape(op, i):
    """An `at`, when the op carries one, is `[x, y]`: two whole numbers inside the
    world (A §2, A §3.4). The grammar guarantees this for a live reply; a scripted
    one reaches no grammar."""
    for f in COORD_FIELDS:
        if f not in op:
            continue
        v = op[f]
        ok = (isinstance(v, (list, tuple)) and len(v) == 2
              and all(isinstance(n, int) and not isinstance(n, bool) and 0 <= n < 64 for n in v))
        if not ok:
            return (f'operation {i + 1} has an "{f}" that is not a position [x, y] inside the '
                    f"world (x and y are 0..63), got {v!r}")
    return None
