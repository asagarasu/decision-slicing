"""The trace arms' pages (B), block by block.

Pure functions from a `State` bundle to text. One user message, no system
message, rebuilt from scratch for every round (B §0): the asks are rolled back
by never being rendered again. Blocks are separated by one blank line, in B §0's
order:

    BACKGROUND · HISTORY · CONSOLE MANUAL · [LIST MANUAL] · ASK or COMMAND ·
    LIST LINE or FOCUS LINE · STATE LINE

**Axis.** Every coordinate a page prints is the SHOWN axis, +y up (A §1.1,
B §0): the target block echoes back what the model wrote, already shown-axis;
an arrival's event line and the state line's position are read out of the world
(+y down) through `axis.shown_pos`. Nothing in this module writes a world-axis
number onto a page, and nothing here logs.

The shared blocks (background, console manual, history grammar, axis line) are
`texts.py`'s and the state line is `state.py`'s; this module owns B's trace-arm
blocks and the assemblers.
"""

import dataclasses
import json

from p3focus import axis, constants, list_store, state, texts

# --------------------------------------------------------------------------
# The bundle a page reads (A §1.3)
# --------------------------------------------------------------------------


@dataclasses.dataclass(frozen=True)
class Destination:
    """The held destination (A §1.3, §3.1 "the hold"): R3's last answer, kept by the
    controller between asks the way the entry in force is kept. `cell` is WORLD axis
    (+y down), as every held coordinate is; the pages show it through
    `axis.shown_pos`. `step` is the world step it was named on — the step the pages
    quote as `named at step N` — and `need` and `why` are the reply's, which ride
    R4's block on every step the destination is held (B §3.5).

    In flat, which holds one without an R3 (A §7 D9, E2), it is the
    cell the one reply last named; that reply has no `need` and no `why`, so both
    are empty and the block drops their lines."""

    cell: tuple
    step: int
    need: str = ""
    why: str = ""

    @property
    def shown(self):
        """The cell as the body reads it, SHOWN axis, as `[x, y]`."""
        return axis.shown_pos(self.cell)


@dataclasses.dataclass(frozen=True)
class State:
    """What one step's pages are built from (A §1.3), built once by the
    controller and handed to every round of the step unchanged.

    `frame` is the world's frame (A §1.2) as it stood **before** this step's
    world step — the window the model reads and acts on — so its coordinates are
    the WORLD axis and the pages show them through `axis.shown_pos`. `mapped`
    is `World.mapped_bits(frame)`. `history` is the last `K_HISTORY` trace lines,
    oldest first, the note's line among them (B §1.2). `entries` is the list in
    id order and `focus_id` the entry in force, or None.
    """

    arm: str
    frame: dict
    mapped: dict
    history: tuple = ()
    entries: tuple = ()
    focus_id: str | None = None
    carrying: tuple = ()
    destination: Destination | None = None

    @property
    def focus_entry(self):
        """The entry in force, or None (B §4)."""
        for entry in self.entries:
            if entry["id"] == self.focus_id:
                return entry
        return None

    @property
    def pos_shown(self):
        """Where the body stands, SHOWN axis (+y up, A §1.1), as `[x, y]`."""
        return axis.shown_pos(self.frame["player"]["pos"])


# --------------------------------------------------------------------------
# B §1.2 — history
# --------------------------------------------------------------------------


def history_block(lines):
    """The last K = 5 trace lines, oldest first (B §1.2).

    Empty only on the first step, where the block says so rather than leaving a
    hole. A partial trim says nothing (the old `--trace-keep 5` behaviour, kept
    so pages stay comparable). List changes never appear here (A, D3).
    """
    lines = list(lines)[-constants.K_HISTORY:]
    return "\n".join(lines) if lines else texts.FIRST_STEP_LINE


# --------------------------------------------------------------------------
# B §2 — the list manual (R1, R1.5, R2 and flat only)
# --------------------------------------------------------------------------

LIST_MANUAL = "\n".join([
    "THE LIST: what it is",
    "",
    "An entry is not a note about the world, and not a reminder. It is a thing you keep, and it "
    "has two parts: a reason to exist, and a condition under which you stop needing it. Those two "
    "parts are what make it one. If you cannot say why a line is there, or what would end it, it "
    "is probably not one of these.",
    "",
    "THE FIELDS of an entry:",
    "- id — given to it when it is added; you use it to name the entry in an operation.",
    "- name — your own handle for it.",
    "- at — optional: the position it is about, as [x, y] in the same coordinates your own "
    "position is given in.",
    "- when — optional: what makes it matter right now.",
    "- until — what would release it. A try that fails is not a release.",
    "- why — optional: one line — what it is for.",
    "",
    "The list has no ranking: nothing in it stands over anything else. Entries are shown in the "
    "order they were added.",
    "",
    '"when", "until" and "why" are in your own words and nothing here reads them: you are the one '
    "who decides, each step, whether a condition you wrote has come true.",
    "",
    "An entry is a note you left yourself, not an order you have to obey. What you wrote may turn "
    "out to be wrong, or impossible in this world, or simply no longer what you want — and if it "
    "does, rewrite it. Changing an entry is as ordinary as keeping one.",
    "",
    "HOW IT WORKS. The list is held for you. Whenever it is on your page it is exactly as you "
    "last left it, and you never write it back yourself. You change it with operations, and only "
    "with operations:",
    '  {"op": "add", "name": ..., "at": [x, y], "when": ..., "until": ..., "why": ...}',
    '  {"op": "edit", "id": ..., and any of name, at, when, until, why}',
    '  {"op": "delete", "id": ...}',
    "An entry stays until you delete it. An action that fails, or changes nothing, leaves the "
    "list as it was, and the entry is still there the next step.",
])


def list_manual():
    """B §2, to the byte. On R1, R1.5, R2 and flat's pages and nowhere else
    (B §6, checkers 1, 3, 8, 10)."""
    return LIST_MANUAL


# --------------------------------------------------------------------------
# B §3.1 — the event lines and R1
# --------------------------------------------------------------------------

#: the second sentence requires one entry per numbered step. Without it, a sliced run
#: wrote a single merged entry for the three errands and, having reached the first cell,
#: had nothing to release and nowhere next to go.
EVENT_NOTE = ("A note from your human player has just arrived. It is the last line of your "
              "history above. The note has three numbered steps. Write one entry for each step, "
              "in the note's order: three entries.")
EVENT_DRINK = "Your drink has just reached 0."
EVENT_HEALTH = "Your health has just dropped."
#: focus: the entry in force is gone and there is nothing left to choose
NO_FOCUS_EMPTY = "The one you were on is gone, and your list is empty."
#: sliced: the same occasion, with no entry in force to speak of (B §3.7)
NO_LIST_EMPTY = "Your list is empty."
#: focus: R2 defaulted with nothing to keep, and the list is not empty
NO_FOCUS_NONE = "You are on none of your entries."


def event_line_arrival(cell_world):
    """B §3.1's arrival line, the cell in the SHOWN axis (+y up)."""
    x, y = axis.shown_pos(cell_world)
    return f"You are standing on [{x}, {y}], a cell your human player's note named."


def event_line_stall(length=constants.STALL_LENGTH):
    """B §3.1's stall line; the number is the manifest's `stall_length`."""
    return f"In the last {int(length)} steps you have not seen a single new cell."


def no_focus_line(arm, list_is_empty):
    """B §3.1's no-focus line for this arm and this list (B §3.7 for sliced)."""
    if arm == "sliced":
        return NO_LIST_EMPTY
    return NO_FOCUS_EMPTY if list_is_empty else NO_FOCUS_NONE


def event_lines(world_events=(), stalled=False, no_focus=None):
    """B §3.1's event lines, one per event that fired, in the gate's order:
    note, arrival, drink, stall — and the no-focus line last, when one rides
    this page (B §3.1, "the no-focus line rides that same page after the gated
    lines").

    `world_events` are the rows of the world step that opened these asks (A
    §4.2: step N's events gate step N+1), WORLD axis; `stalled` is whether the
    gate's own `stall` kind is among them. A `drink_crossing` row becomes one
    line, or two when both halves fired — drink first (B §3.1).
    """
    lines = []
    rows = list(world_events or ())
    if any(row.get("kind") == "note_landed" for row in rows):
        lines.append(EVENT_NOTE)
    for row in rows:
        if row.get("kind") == "arrival":
            lines.append(event_line_arrival(row["cell"]))
    for row in rows:
        if row.get("kind") != "drink_crossing":
            continue
        if int(row["drink_to"]) <= constants.DRINK_CROSSING_AT < int(row["drink_from"]):
            lines.append(EVENT_DRINK)
        if int(row["health_to"]) < int(row["health_from"]):
            lines.append(EVENT_HEALTH)
    if stalled:
        lines.append(event_line_stall())
    if no_focus:
        lines.append(no_focus)
    return lines


ASK_R1_HEAD = "THIS ROUND CHANGES ONLY YOUR LIST. It asks one question and takes no game action."
ASK_R1_BODY = "\n".join([
    "This round asks about your list, not about this step; the step itself is decided after this, "
    "on this same window. Does the list need maintaining? Look at what just happened, at the "
    "window and at your own state, and at each entry's \"until\". If something you now intend has "
    "no entry, or an entry's end-condition has come true, or an entry is wrong, then the list "
    "needs to change: reply with the operations, exactly as the list's own page describes them. "
    "If the list as it stands is what you mean, reply no. Both are whole answers, and no is the "
    "usual one.",
    "",
    "REPLY with exactly one JSON object and nothing else:",
    '{"why": "<what you looked at, and what you concluded, in one line>", "maintain": "no"}   or   '
    '{"why": "<…>", "maintain": "yes", "ops": [<one to five of the operations above>]}',
])


def ask_r1(lines):
    """B §3.1's ask, with the event lines in place of `{event lines}`. It never
    renders with an empty event block (B §3.1), so an empty `lines` is a bug in
    the controller and is refused here."""
    if not lines:
        raise ValueError("R1 never renders with an empty event block (B §3.1)")
    return "\n\n".join([ASK_R1_HEAD, "\n".join(lines), ASK_R1_BODY])


# --------------------------------------------------------------------------
# B §3.2 — R1.5
# --------------------------------------------------------------------------

ASK_R1_5_TAIL = "\n".join([
    "Is that what you mean? An entry deleted is gone, and there is nothing left to read. If its "
    "end-condition has come true, or you no longer want it, true. If you would rather keep or "
    "rewrite it, false, and it stays as it is.",
    "",
    "REPLY with exactly one JSON object and nothing else:",
    '{"delete": true or false}',
])


def ask_r1_5(entry):
    """B §3.2's ask for one held delete. The entry renders as B §4 prints it,
    indented two spaces; `add` and `edit` have already applied, so the list line
    below shows them and the entry to be deleted is still there."""
    return "\n\n".join([
        ASK_R1_HEAD,
        "Your last reply deletes this entry:\n  " + list_store.render_entry(entry)
        + "\n" + ASK_R1_5_TAIL,
    ])


# --------------------------------------------------------------------------
# B §3.3 — R2
# --------------------------------------------------------------------------

ASK_R2_HEAD = ("THIS ROUND CHANGES NOTHING ON YOUR LIST. It asks one question and takes no game "
               "action.")
ASK_R2_BODY = "\n".join([
    "Of the entries on your list below, which one has to be done FIRST, from where you stand right "
    "now? Not the one that matters most in the end: the one your next steps are for. An entry whose "
    "\"when\" is not yet true is not the one you are on. Say first, in one line, why this one and "
    "not the others — what you are carrying, and what each entry's \"when\" and \"until\" say — "
    "and then its id. An entry that is not on the list is not available here; you have already had "
    "this step's chance to add one.",
    "",
    "Between now and the next time you are asked, that is the one you are on, and it is the only "
    "one you will see when you act.",
    "",
    "REPLY with exactly one JSON object and nothing else:",
    '{"why": "<why this one, now, in one line>", "focus": "<an id from the list>"}',
])
#: B §3.3's `{previous line}`, one of three
PREVIOUS_NONE = "You were on none of them."


def previous_line(previous_id, deleted=False):
    """B §3.3's `{previous line}`: the entry in force, the one this step's R1.5
    has just removed, or none at all."""
    if previous_id is None:
        return PREVIOUS_NONE
    if deleted:
        return f'The one you were on until now, "{previous_id}", has just been deleted.'
    return f'The one you were on until now: "{previous_id}".'


def ask_r2(previous):
    """B §3.3's ask, with `{previous line}` filled in."""
    return "\n\n".join([ASK_R2_HEAD, previous, ASK_R2_BODY])


# --------------------------------------------------------------------------
# B §3.4 — R3
# --------------------------------------------------------------------------

ASK_R3_HEAD = "THIS ROUND CHOOSES A DESTINATION, NOT A MOVE."
ASK_R3_BODY = "\n".join([
    "Where are you going, for the one you are on? Name the position you are heading for — the "
    "place where what has to be solved right now gets solved. One may be in your window — the nine "
    "by nine cells you can see — or it may be somewhere you have already been, or a position the "
    "entry you are on names. A destination is a position in the WORLD, not only one on the screen, "
    "and it may be far off the screen: you will be walked toward it one step at a time, and you "
    "will not be asked this again until you stand on it, or something happens, or there is no way "
    "there over cells you have seen. Choose one as your destination.",
    "",
    'A need is not an answer. "I am thirsty, I need water" names the need and stops there; this '
    "round ends on a position.",
    "For anything you cannot walk into, the destination is a cell beside it that you can stand on "
    "and act from — never the thing itself.",
    "If nothing you can see and nothing you know of helps, send target null. That is the "
    "exploring answer, and nothing else means it; you will be asked again next step.",
    "",
    "YOUR DESTINATION — reply with exactly one JSON object and nothing else:",
    '{"need": "<what has to be solved now>", "candidates": [[x, y], ...], "target": [x, y] or '
    'null, "why": "<what the destination is for>"}',
    'Positions are [x, y] in the same coordinates your own position is given in. "candidates" is '
    "at most three — the positions you actually considered, not a survey of the window — and [] "
    'when you found none. "target" is the destination you chose, or null.',
    "This round outputs no game action. You are not moving yet: the move is the next round's, on "
    "this same window.",
])
#: B §3.4's table: R3's four occasions, and the line each puts between the head and
#: the question. `missing` has no line.
OCCASIONS = ("missing", "reached", "no_way", "event")


def _named(dest):
    return f"{json.dumps(list(dest.shown))}, named at step {int(dest.step)}"


def destination_line(occasion, dest):
    """B §3.4's `{destination line}` for this occasion, or None on `missing`.
    `dest` is the `Destination` the occasion is about — the one just reached or
    cleared, or the one still held — with its cell in the WORLD axis; the line
    shows it in the SHOWN axis."""
    if occasion not in OCCASIONS:
        raise ValueError(f"unknown R3 occasion {occasion!r}; B §3.4 names {OCCASIONS}")
    if occasion == "missing":
        return None
    if occasion == "reached":
        return f"You are standing on your destination, {_named(dest)}."
    if occasion == "no_way":
        return (f"There is no way over cells you have seen to your destination, {_named(dest)}; "
                "it is no longer held.")
    return (f"Your destination until now: {_named(dest)} — the need you named then: {dest.need}; "
            f"what it was for: {dest.why}. Keeping it is an answer: name it again. Changing it is "
            "an answer too: name another, or null to explore.")

#: the two phrases B §3.4 and B §3.7 move, and what each arm puts there
_R3_SOLVED_FOR = ", for the one you are on"
_R3_NAMED_BY = ", or a position the entry you are on names"
_R3_SOLVED_FOR_SLICED = ", for what you keep on your list"
_R3_NAMED_BY_SLICED = ", or a position an entry on your list names"


def ask_r3(arm, has_focus=True, line=None):
    """B §3.4's ask, in the one wording this arm and this step want, with the
    occasion's `{destination line}` between the head and the question when the
    occasion has one (`destination_line`).

    focus with an entry in force: B §3.4 to the byte. focus with `none` (B
    §3.4's last paragraph): the two phrases that point at the entry are dropped,
    so the first question reads "Where are you going?"; nothing else moves.
    sliced (B §3.7): the same two phrases read "for what you keep on your list"
    and "or a position an entry on your list names", and `has_focus` does not
    apply — sliced has no entry in force.
    """
    body = ASK_R3_BODY
    if arm == "sliced":
        body = body.replace(_R3_SOLVED_FOR, _R3_SOLVED_FOR_SLICED).replace(
            _R3_NAMED_BY, _R3_NAMED_BY_SLICED)
    elif not has_focus:
        body = body.replace(_R3_SOLVED_FOR, "").replace(_R3_NAMED_BY, "")
    return "\n\n".join([ASK_R3_HEAD, *([line] if line else []), body])


# --------------------------------------------------------------------------
# B §3.5 — R4's three blocks
# --------------------------------------------------------------------------

_SAME_WINDOW = "This is the same window you just read — the same cells, unmoved."
DEST_TAIL_HELD = ("Work out what the first step toward that position is. Then give your action. "
                  "This step goes toward your destination; it is not an exploring step.")
DEST_TAIL_CHOSEN = _SAME_WINDOW + " " + DEST_TAIL_HELD
DEST_TAIL_NULL = (_SAME_WINDOW + " Nothing in it is usable, so this step explores: move to "
                  "bring cells you have not seen into view. Then give your action.")
DEST_HEAD = "THE DESTINATION YOU CHOSE: "
DEST_NULL_HEAD = (DEST_HEAD + "none — you read the window and found no position in it "
                  "that helps.")
DEST_DEFAULTED_HEAD = (DEST_HEAD + "none — the position you named was refused twice, so this "
                       "step explores.")
DEST_TAIL_DEFAULTED = (_SAME_WINDOW + " No usable position was named, so this step explores: move "
                       "to bring cells you have not seen into view. Then give your action.")


#: B §3.5: when the destination is one of the
#: four cells beside the body, the bearing line also names it the way the `near` field does
NEIGHBOUR_WORDS = {"move_up": "above you", "move_down": "below you",
                   "move_left": "to your left", "move_right": "to your right"}


def bearing_line(pos_shown, target_shown, near=None):
    """The bearing line: the two subtractions between here and the target, rendered
    as the move keys that close them. Both positions SHOWN axis (+y up), as the body
    reads them. It exists because, without it, a body sat in a lake for 300 steps
    calling a cell twenty below it "North".

    `near` is the state's `{up, down, left, right}` of cell names. When it is given
    and the destination is exactly one of those four cells, the line goes on to name
    it — `: it is the cell above you, sand.` — tying the coordinate to the field the
    body reads its neighbours from (B §3.5; measured: at one cell's range a
    third of the vertical moves went the wrong way, at two cells' range one in ten)."""
    dx = int(target_shown[0]) - int(pos_shown[0])
    dy = int(target_shown[1]) - int(pos_shown[1])
    if dx == 0 and dy == 0:
        return "You are standing on that position."
    parts = []
    if dy:
        parts.append(f"{abs(dy)} x move_{'up' if dy > 0 else 'down'}")
    if dx:
        parts.append(f"{abs(dx)} x move_{'right' if dx > 0 else 'left'}")
    line = "From where you stand, that position is " + " and ".join(parts) + " away."
    if near and len(parts) == 1 and abs(dx) + abs(dy) == 1:
        verb = parts[0][4:]                       # "1 x move_up" -> "move_up"
        material = near.get(verb[5:])
        if material:
            line = line[:-1] + f": it is the cell {NEIGHBOUR_WORDS[verb]}, {material}."
    return line


def destination_block(dest, need="", why="", route_sentence=None, defaulted=False, bearing=None,
                      fresh=True, kept=False):
    """B §3.5's destination block: the
    destination, the need the body named and what the destination is for, as
    prose, then the bearing line and the route sentence (`candidates` does not
    cross, B, P7). Empty `need`/`why` drop their lines.

    `dest` is the held `Destination` (its cell WORLD axis; shown here through
    `axis.shown_pos`) or None for the exploring branch, whose `need` and `why`
    are this step's R3 reply's. `fresh` says R3 ran this step: the tail then
    opens with "This is the same window you just read", and the first line ends
    "named this step" — or, with `kept`, "named at step N, kept this step",
    when R3 named the held cell again at an event and its naming step stood
    (B §3.4, §3.5). On a held step (not fresh) the line ends "named at step N"
    and the sentence goes (P10). The exploring shapes are always fresh — no
    destination held means R3 was asked.
    `route_sentence` is one of the route hint's three (A §6) and rides only a
    destination that is not the cell the body stands on (B §3.5).
    """
    need_line = [f"The need you named: {need}"] if need else []
    if defaulted:
        # B §3.5's third shape (A §3.4): the position was refused twice; the
        # page says so rather than that the body chose to explore
        return "\n".join([DEST_DEFAULTED_HEAD, *need_line, "", DEST_TAIL_DEFAULTED])
    if dest is None:
        found = [f"What you found: {why}"] if why else []
        return "\n".join([DEST_NULL_HEAD, *need_line, *found, "", DEST_TAIL_NULL])
    if fresh and not kept:
        when = "named this step"
    elif fresh:
        when = f"named at step {int(dest.step)}, kept this step"
    else:
        when = f"named at step {int(dest.step)}"
    lines = [f"{DEST_HEAD}{json.dumps(list(dest.shown))}, {when}."]
    if dest.need:
        lines.append(f"The need you named: {dest.need}")
    if dest.why:
        lines.append(f"What the destination is for: {dest.why}")
    if bearing:
        lines.append(bearing)
    if route_sentence:
        lines.append(route_sentence)
    return "\n".join(lines + ["", DEST_TAIL_CHOSEN if fresh else DEST_TAIL_HELD])


COMMAND_R4 = "\n".join([
    "YOUR COMMAND — reply with exactly one JSON object and nothing else:",
    '{"action": "<action name>", "intent": "<what you are doing this for, in your own words>"}',
    "One game action is required, every step.",
    '"intent" is yours, in your own words: it is what comes back in the line for this step when '
    "you read your own history next step.",
])

COMMAND_FLAT = "\n".join([
    "YOUR COMMAND — reply with exactly one JSON object and nothing else:",
    '{"action": "<action name>", "intent": "<what you are doing this for, in your own words>", '
    '"ops": [<zero to five of the operations above>], "destination": [x, y] or null}',
    'One game action is required, every step. "ops" is part of every reply: send [] when nothing '
    "changed. List changes and no list changes are both whole replies.",
    '"destination": the position you are heading for, held for you from step to step and shown '
    "above; send null to keep the one you hold (or to name none), send [x, y] to change it or to "
    "name one; the way there begins with the move the line above says.",
    '"intent" is yours, in your own words: it is what comes back in the line for this step when '
    "you read your own history next step.",
])


def command_block(arm_or_round):
    """B §3.5's command block for R4, or B §3.6's for flat. R4's has no ops
    clause and no ops key: the acting rounds never maintain the list (B §3.5,
    §6 checker 2)."""
    return COMMAND_FLAT if arm_or_round == "flat" else COMMAND_R4


def axis_line():
    """B §3.5, §3.6: the axis reminder, on R4 and flat and nowhere else (B, P6)."""
    return texts.AXIS_LINE


# --------------------------------------------------------------------------
# B §4 — the list line and the focus line
# --------------------------------------------------------------------------


def list_line(entries):
    """B §4's line for R1, R1.5, R2 and flat. An empty list is `[]`."""
    return "current list: " + list_store.render_list(entries)


def readonly_list_line(entries):
    """B §4's line for sliced's R3 and R4 — the whole list, read-only."""
    return ("current list (this round you can read it and not change it): "
            + list_store.render_list(entries))


def focus_line(entry):
    """B §4's line for focus's R3 and R4: the one entry in force, or `none` in
    the two cases B §3.3 names (the list emptied and, asked once more, nothing
    added; or R2 invalid twice with nothing to keep)."""
    if entry is None:
        return "the one you are on: none"
    return "the one you are on: " + list_store.render_entry(entry)


# --------------------------------------------------------------------------
# B §5 — the state line
# --------------------------------------------------------------------------

#: B §5's clause table, as the tail of `respond with …`. R1's colon rides
#: "respond with", which is why `state_line` below has one substitution in it.
RESPOND_CLAUSES = {
    "R1": ": no, or your operations on the list.",
    "R1.5": "your confirmation: true or false.",
    "R2": "your choice: an id from the list.",
    "R3": "your target: one position, or null.",
    "R4": "your command: one game action (required).",
    # the destination clause follows the hold (B §5): `null` keeps the cell
    # the body holds, so "null when none" would say the opposite of the command
    # block two blocks above it
    "flat": ("your command: one game action (required); list changes ([] when none); a "
             "destination (null keeps the one you hold)."),
}


def state_line(st, round_id):
    """B §5's last line of every trace page, with this round's clause.

    The frame is the WORLD axis and `state.render_state` puts the position on
    the page in the SHOWN axis; nothing is converted here.
    """
    line = state.state_line(st.frame, st.mapped, RESPOND_CLAUSES[round_id], st.carrying)
    return line


# --------------------------------------------------------------------------
# B §0 — the page assemblers
# --------------------------------------------------------------------------


def _assemble(*blocks):
    """B §0: the blocks of one page, in order, one blank line between them.
    A block that is empty (a flat page with no route sentence) is not a block."""
    return "\n\n".join(block for block in blocks if block)


def _top(st):
    """The three blocks every trace-arm page opens with (B §0, §6 checker 4)."""
    return (texts.BACKGROUND_TRACE, history_block(st.history), texts.console_manual())


def page_r1(st, lines):
    """R1's whole page (B §0's order; the ask is B §3.1)."""
    return _assemble(*_top(st), list_manual(), ask_r1(lines),
                     list_line(st.entries), axis_line(), state_line(st, "R1"))


def page_r1_5(st, entry):
    """R1.5's whole page (B §3.2)."""
    return _assemble(*_top(st), list_manual(), ask_r1_5(entry),
                     list_line(st.entries), axis_line(), state_line(st, "R1.5"))


def page_r2(st, previous):
    """R2's whole page (B §3.3). `previous` is `previous_line(...)`."""
    return _assemble(*_top(st), list_manual(), ask_r2(previous),
                     list_line(st.entries), axis_line(), state_line(st, "R2"))


def page_r3(st, line=None):
    """R3's whole page (B §3.4): no list manual, no list line in focus — the one
    entry in force (B §6, checkers 1 and 5) — and sliced's read-only list line
    with sliced's wording (B §3.7, §6 checker 10). `line` is the occasion's
    `{destination line}` (`destination_line`), or None on the missing occasion."""
    if st.arm == "sliced":
        return _assemble(*_top(st), ask_r3("sliced", line=line),
                         readonly_list_line(st.entries), axis_line(), state_line(st, "R3"))
    entry = st.focus_entry
    return _assemble(*_top(st), ask_r3(st.arm, has_focus=entry is not None, line=line),
                     focus_line(entry), axis_line(), state_line(st, "R3"))


def page_r4(st, route_sentence=None, fresh=True, defaulted=False, need="", why=""):
    """R4's whole page (B §3.5): the destination block (with the bearing line
    when a destination is held), the command block, then the focus line (sliced:
    the read-only list line), the axis line and the state line. The destination
    is `st.destination`; `need` and `why` are read only when none is held — the
    exploring shapes, whose prose is this step's R3 reply's."""
    dest = st.destination
    bearing = (bearing_line(st.pos_shown, dest.shown, state.near_cells(st.frame["window"]))
               if dest is not None and not defaulted else None)
    # the page that decides world step N shows frame N-1 (A §1.3); a destination named on
    # this step carries N, an earlier one a smaller step: that is the kept form (B §3.5)
    kept = fresh and dest is not None and int(dest.step) != int(st.frame["step"]) + 1
    below = (readonly_list_line(st.entries) if st.arm == "sliced"
             else focus_line(st.focus_entry))
    return _assemble(*_top(st),
                     destination_block(dest, need, why, route_sentence, defaulted, bearing, fresh, kept),
                     command_block("R4"), below, axis_line(), state_line(st, "R4"))


def page_flat(st, route_sentence=None):
    """flat's one page (B §3.6): the list manual and the whole list as R1 has
    them, the destination block when one is held, a command block as R4 has it,
    the axis line beside the map, and no event line (B §6 checker 8).

    **The hold** (A §7 D9, E2): flat holds a destination as focus
    does, and the block is B §3.5's, in its held shape — flat has no R3, so the
    reply that names a cell comes after the page and the block first says
    `named at step N` on the next step; it never says "named this step", never
    says "kept this step", and never carries "This is the same window you just
    read" (P10: no round preceded it). The exploring shapes are focus's alone: a
    step with nothing held carries no block at all. `route_sentence` is the hint
    for the held cell and rides inside the block as it does on R4's page; with
    nothing held there is nothing to route to and it is ignored.
    """
    dest = st.destination
    block = ""
    if dest is not None:
        bearing = bearing_line(st.pos_shown, dest.shown, state.near_cells(st.frame["window"]))
        block = destination_block(dest, route_sentence=route_sentence, bearing=bearing,
                                  fresh=False)
    return _assemble(*_top(st), list_manual(), block,
                     command_block("flat"), list_line(st.entries), axis_line(), state_line(st, "flat"))
