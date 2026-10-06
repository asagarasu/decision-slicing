"""The chat controller — arm O as B §7 has it (A §3.3, A §4, A §6).

One `World`, one conversation, one model call a step (two when a reply is
refused). No list, no gate, no asks: in chat the only place the body's
motivation can live is what it said in its own earlier turns, which are still in
the conversation, and the harness holds nothing for it. That is the arm the other
three are measured against.

**How a step is numbered.** The turn that decides world step N renders frame
N−1 — the frame the last action produced — and its own action produces frame N.
So the state JSON of turn N says `"step": N-1`, `calls.jsonl` says `step: N`
("the world step this call serves", A §4.1), and the note, which lands with
frame 10, rides turn 11's page (B §7, B §1.2: "the step after the note lands").
The outcome line therefore reports steps 1, 2, … on turns 2, 3, …; turn 1 has no
last action and no outcome line (B §7, "from step 1 on").

**Coordinates.** The model reads and writes the SHOWN axis, +y up; every log row
is the WORLD axis, +y down; `axis.shown_pos` is the involution between them
(A §1.1). Exactly three coordinates cross in this module:

* the state JSON's `pos` — shown, written by `state.render_state`;
* the `destination` the body writes — shown, read back to the world axis by
  `axis.shown_pos` before it reaches `route` (world axis only, by that module's
  contract) or any row of `actions.jsonl` / `events.jsonl`;
* the outcome sentence's `moved to [x, y]` — shown, the world's own.

Nothing else in here is a coordinate, and the console line says which axis it
prints.

**What chat has not got**, and what its absence is for: no list and no list
manual (B §4: "chat has no list"), no gate and so no `gate_fired`, no asks, no
history block — the conversation *is* the history, and trimming it is the only
thing that ever takes a step's own words away (A §3.3).
"""

import dataclasses
import json
import math
import time
from pathlib import Path

from p3focus import axis, cell, client as clientlib, constants, grammars, route, state, texts
from p3focus.world import World

#: A §4.3's `arm`, A §4.1's `round`, and `grammars.grammar`'s key — one word for
#: all three, because in chat a step is a turn is a round.
ARM = "chat"
ROUND = "chat"

#: A §3.4: the first semantic try and the one retry that follows it.
MAX_ATTEMPTS = 2

#: The token estimate, the old line's (`loop.BYTES_PER_TOKEN`, 3.5, its
#: `estimate_tokens` over the bytes of every message's content). Not in
#: constants.py: only this module estimates anything. The old line then
#: calibrated the ratio from the server's `usage.prompt_tokens`; this one does
#: not, so where the trim falls is a fact about the conversation and not about
#: the server that happened to serve it.
BYTES_PER_TOKEN = 2.75   # measured 09-24 on a local inference server running Qwen3.5-9B: 98,148 prompt tokens for
                         # a 279-turn conversation of ~271 KB; the old line's 3.5 under-counted
                         # by a quarter and the first chat cell hit the server's context at step
                         # 279 (HTTP 400 exceed_context_size). Calibrated live from every call.
#: the calibrated ratio is kept inside these bounds; outside them the server's
#: number is more likely a template quirk than a tokenizer fact
BYTES_PER_TOKEN_BOUNDS = (1.5, 6.0)

#: What an old turn's `window` becomes when the conversation passes the budget
#: (A §3.3, B §7; the old `_omit_window`).
OMITTED_WINDOW = "(omitted)"

#: A §3.4's reason line, in chat's shape: the rejected reply stays in the
#: conversation and this is the user turn that follows it (the old `_complete`).
RETRY_LINE = "your last reply was not accepted: {reason}; reply with one JSON object"

#: B §7's own two paragraphs, quoted: the ROUTE key and the reply shape. The
#: `<= 15 words` is advisory, as the old `WHY_WORDS` was — the grammar bounds
#: `why` by characters, not words (`grammars.TEXT_MAX`).
WHY_WORDS = 15
ROUTE_LINE = ('ROUTE (optional): add "destination": [x, y] to your reply, and the next turn tells '
              "you which move the way there begins with, over cells you have seen.")
REPLY_SHAPE = ('{"action": "<action name>", "why": "<= %d words", "destination": [x, y] or null}'
               % WHY_WORDS)

#: B §7's state sentence differs from the trace console manual's
#: (`texts.state_description`) in exactly two places, both of them things the
#: trace says elsewhere and chat has no elsewhere for: the world's law rides
#: `step (the clock; …)` where the trace has a background paragraph
#: (`texts.WORLD_LAW`), and the world's size rides `player {pos …}` for the same
#: reason. Everything from `; daylight` on is `state_description("turn")`'s, so
#: the two manuals cannot drift apart where they agree.
_CHAT_STATE_HEAD = ("Each turn you get one line saying what your last action did, then your state "
                    "as JSON: step (the clock; drink falls as it runs; drink at 0 drains health; "
                    "health 0 is death)")
_CHAT_STATE_SIZE = "player {pos [x, y] in a world of %d by %d cells (" % (
    constants.WORLD_SIZE, constants.WORLD_SIZE)


def _sub(text, old, new):
    """`text.replace(old, new)`, once, refusing a needle that is not there: a
    silent no-op here would ship a manual that reads almost right."""
    if old not in text:
        raise AssertionError(f"{old!r} is no longer in texts.state_description(); B §7 moved")
    return text.replace(old, new, 1)


def state_paragraph():
    """B §7's state sentence, built from `texts.state_description("turn")` with
    the world's law and the world's size folded in, as the old
    `roomba_system_prompt` had them."""
    tail = texts.state_description("turn").split("; daylight", 1)[1]
    return _CHAT_STATE_HEAD + "; daylight" + _sub(tail, "player {pos [x, y] (", _CHAT_STATE_SIZE)


def system_message():
    """The system message, sent once (B §7).

    The human's framing sentence with the task in it (`texts.HUMAN_FRAME_CHAT`), the state
    sentence, the legend, the three action lines, the ROUTE paragraph and the
    reply shape. B §7's three changes against arm O as built are all upstream of
    here: the safe line is `texts.SAFE_LINE`, `mapped` has no `count` because
    `texts.state_description` has none, and `destination` is printed in
    `REPLY_SHAPE`.
    """
    return "\n".join([
        texts.HUMAN_FRAME_CHAT,
        "",
        state_paragraph(),
        "",
        texts.legend_line(),
        "",
        "ACTIONS (exactly one per turn, by name):",
        texts.MOVE_LINE,
        texts.WATER_LINE,
        texts.SAFE_LINE,
        texts.FULL_LINE,
        texts.NO_CRAFT_LINE,
        "",
        ROUTE_LINE,
        "",
        "REPLY with exactly one JSON object and nothing else:",
        REPLY_SHAPE,
    ])


def user_turn(frame, mapped_bits, outcome=None, note_line=None, route_sentence=None, carrying=()):
    """One step's user turn (B §7), in B's line order and no other:

        outcome of your last action: <the world's sentence>   from step 1 on
        step 10: a note from your human player arrived: "…"   turn 11, once
        <one of the route hint's three sentences>             if the last reply named a cell
        <the axis reminder>                                   every turn
        <the state JSON>                                      every turn, last

    `frame` is the world's frame (A §1.2) for the step *before* this one, world
    axis; `state.render_state` puts its `pos` on the page in the SHOWN axis, and
    the state JSON is the last line so that `omit_window` can find it. The first
    three lines are each absent when their argument is None: turn 1 has no
    outcome, only turn 11 has the note, and a turn answers a destination only
    when the last reply named one (A §1.3).
    """
    lines = []
    if outcome is not None:
        lines.append(f"outcome of your last action: {outcome}")
    if note_line is not None:
        lines.append(note_line)
    if route_sentence is not None:
        lines.append(route_sentence)
    lines.append(f"you are carrying {state.carrying_words(carrying)}.")
    lines.append(texts.AXIS_LINE)
    lines.append(state.dumps(state.render_state(frame, mapped_bits, carrying)))
    return "\n".join(lines)


def omit_window(content):
    """The same user turn with the state JSON's `window` replaced by
    `(omitted)` (A §3.3, B §7; the old `_omit_window`). The state JSON is the
    turn's last line, which is what makes this a line operation and not a
    re-render: the turn the body actually read is the only thing there is."""
    head, sep, body = content.rpartition("\n")
    obj = json.loads(body)
    obj["window"] = OMITTED_WINDOW
    return head + sep + state.dumps(obj)


def estimate_tokens(messages, bytes_per_token=BYTES_PER_TOKEN):
    """The conversation's size in tokens, estimated (A §3.3): the bytes of every
    message's content over `BYTES_PER_TOKEN`, the old `estimate_tokens`."""
    total = sum(len(m["content"].encode()) for m in messages)
    return int(math.ceil(total / float(bytes_per_token)))


class Conversation:
    """The conversation and its trimming (A §3.3, B §7).

        conv = Conversation(system_message())
        conv.open_turn(1, user_turn(...))      # appends, then trims
        conv.append("assistant", reply_text)   # the reply, verbatim

    `messages` is what goes to the client, oldest first, the system message at
    index 0 and never anywhere else. `turns` is one record per step — the user
    message, every message that followed it that step, and whether its window
    has already been omitted — because trimming works on turns and the client
    works on messages.
    """

    def __init__(self, system):
        self.messages = [{"role": "system", "content": system}]
        self.turns = []
        #: bytes per token, `BYTES_PER_TOKEN` until the first call reports its
        #: prompt tokens; then the server's own ratio (`calibrate`)
        self.bytes_per_token = BYTES_PER_TOKEN

    def calibrate(self, prompt_tokens, messages):
        """Set `bytes_per_token` from what the server counted for `messages`
        (the request that was just sent), the old line's calibration. Bounded by
        `BYTES_PER_TOKEN_BOUNDS`; ignored when the server reported nothing."""
        if not prompt_tokens:
            return self.bytes_per_token
        total = sum(len(m["content"].encode()) for m in messages)
        ratio = total / float(prompt_tokens)
        lo, hi = BYTES_PER_TOKEN_BOUNDS
        self.bytes_per_token = min(hi, max(lo, ratio))
        return self.bytes_per_token

    def open_turn(self, step, content):
        """Start step `step`'s turn and keep the conversation under the budget
        (A §3.3). Returns `trim`'s payload when something was trimmed, else
        None — the caller logs `conversation_trimmed` (A §4.2)."""
        message = {"role": "user", "content": content}
        self.messages.append(message)
        self.turns.append({"step": int(step), "user": message, "members": [message],
                           "window_omitted": False})
        return self.trim()

    def append(self, role, content):
        """Append one message to the turn that is open — the reply verbatim, or
        A §3.4's reason line. Never trims: a step's own words are the ones it is
        answering with."""
        message = {"role": role, "content": content}
        self.messages.append(message)
        self.turns[-1]["members"].append(message)
        return message

    def est_tokens(self):
        """The conversation's estimated size (A §3.3), at the calibrated ratio."""
        return estimate_tokens(self.messages, self.bytes_per_token)

    def trim(self, budget=None, keep=None):
        """Bring the conversation under the budget, oldest first (A §3.3, B §7).

        Two passes over the turns that are neither the newest `keep` nor the
        system message, which is never touched at all: first their `window`
        becomes `(omitted)`, oldest turn first, and only if that is not enough
        are whole turns dropped, oldest first again. Each pass stops the moment
        the estimate is under the budget, so a conversation loses the least it
        can.

        `budget` and `keep` default to `constants.CHAT_BUDGET_TOKENS` and
        `constants.CHAT_KEEP_TURNS`, read at call time so a test can move them.
        Returns None when nothing needed trimming, else the payload whose
        `dropped_turns` is A §4.2's field.
        """
        budget = constants.CHAT_BUDGET_TOKENS if budget is None else int(budget)
        keep = constants.CHAT_KEEP_TURNS if keep is None else int(keep)
        before = self.est_tokens()
        if before <= budget:
            return None
        eligible = self.turns[:-keep] if len(self.turns) > keep else []
        omitted, dropped = [], []
        for turn in eligible:
            if self.est_tokens() <= budget:
                break
            if turn["window_omitted"]:
                continue
            turn["user"]["content"] = omit_window(turn["user"]["content"])
            turn["window_omitted"] = True
            omitted.append(turn["step"])
        gone = []
        for turn in eligible:
            if self.est_tokens() <= budget:
                break
            # by identity, not by value: the old line's `list.remove` compares
            # dicts, so two verbatim-equal replies would drop the wrong one.
            ids = {id(m) for m in turn["members"]}
            self.messages = [m for m in self.messages if id(m) not in ids]
            gone.append(turn)
            dropped.append(turn["step"])
        if gone:
            leaving = {id(t) for t in gone}
            self.turns = [t for t in self.turns if id(t) not in leaving]
        if not omitted and not dropped:
            return None
        after = self.est_tokens()
        return {"est_tokens_before": before, "est_tokens_after": after, "budget": budget,
                "windows_omitted": omitted, "dropped_turns": dropped,
                "still_over": after > budget}


def read_reply(text):
    """`(parsed, reason)` for one chat reply (A §3.3, §3.4).

    `parsed` is the object the text held, or None when it held none; `reason` is
    why the reply is not an answer, or None when it is one. Both come back on an
    object that parsed but does not pass, so `calls.jsonl` can show a reader the
    object it refused (A §4.1: `parsed` object or null, `valid` a separate bool).

    A §3.4 asks chat to check one thing the grammar cannot, a `destination`
    inside 0..63. In this arm the grammar in fact can: `coord-int` admits 0..63
    and nothing else, and the three keys are required in order. So on a server
    that enforces the grammar, and `Client.probe` refuses to run against one that
    does not, none of the branches below can fire, and a real cell's
    `invalid_replies` will read 0. They are here for the scripted policy, whose
    replies are authored rather than decoded, and because a reply that somehow
    arrived without a grammar must be refused rather than guessed at.
    """
    try:
        obj = json.loads(text)
    except (TypeError, ValueError):
        return None, "the reply is not one JSON object"
    if not isinstance(obj, dict):
        return None, "the reply is not one JSON object"
    return obj, reply_reason(obj)


def reply_reason(obj):
    """Why this reply object is not an answer (A §3.4), or None.

    A §3.4's own check for chat is the one coordinate: a `destination` inside
    0..63, in the shown axis the body wrote it in. `null` is an answer and never
    a reason (A §3.4, the bare arms brief's decision 7).
    """
    if obj.get("action") not in constants.VERBS:
        return '"action" must be one of ' + ", ".join(constants.VERBS)
    if not isinstance(obj.get("why"), str):
        return '"why" must be a string, in your own words'
    if "destination" not in obj:
        return '"destination" is required; send null on a turn you are not naming a cell'
    cell_named = obj["destination"]
    if cell_named is None:
        return None
    if (not isinstance(cell_named, (list, tuple)) or len(cell_named) != 2
            or not all(isinstance(v, int) and not isinstance(v, bool) for v in cell_named)):
        return '"destination" must be [x, y] or null, not %s' % json.dumps(cell_named)
    high = constants.WORLD_SIZE - 1
    if not all(0 <= int(v) <= high for v in cell_named):
        return "the destination %s is off the map; x and y are 0..%d" % (
            json.dumps(list(cell_named)), high)
    return None


@dataclasses.dataclass(frozen=True)
class ChatCell:
    """What `run_chat_cell` hands back: where the cell's files are (A §4), the
    `summary.json` body it wrote, the conversation as it ended, and the world it
    ran, so a test can read the seen set and the errand ledger without
    re-deriving them."""

    dir: Path
    summary: dict
    conversation: Conversation
    world: World


def run_chat_cell(seed, steps, client, out_dir, quiet=False):
    """One chat cell: arm O as B §7 has it (A §3.3, §4, §5, §6).

    `seed` is one of `constants.ERRANDS`' keys, `steps` the budget, `client` a
    `client.Client` or `client.ScriptedClient`, `out_dir` the parent the cell
    directory is created under (A §4). `quiet` silences the per-step console
    line (A §5).

    One step, in order:

    1. the hint for the cell the *last* reply named, if there was one and it is
       not the cell the body now stands on (A §4.2's `route` row, B §7's line);
    2. the user turn (B §7), appended to the conversation, which is then trimmed
       if it has passed the budget (A §3.3);
    3. the call, `grammars.grammar("chat")`, A §3.4's one retry, and the `noop`
       default (A §3.4's table: chat defaults to `noop`);
    4. the world step, its frame, its events, and the action row (A §4.3);
    5. the console line, unless `quiet`.

    Death ends the cell (A §5: exit 0, death included). Returns a `ChatCell`.
    """
    started = time.perf_counter()
    world = World(seed)                       # validates the seed before anything is opened
    grammar = grammars.grammar(ROUND)
    client.probe()                            # A §6, before the first real call
    out = cell.cell_dir(out_dir, ARM, seed)
    calls = clientlib.CallLog(out / "calls.jsonl")
    events = cell.EventLog(out / "events.jsonl")
    actions = cell.ActionLog(out / "actions.jsonl")
    frames = cell.FrameLog(out / "frames.jsonl")
    # A §4.4's `model` is "as the server reports it"; A §6 gives `/props` to the
    # drivers, so the run command is expected to build its `Client` with the name
    # it read there and this reads it back off the client.
    cell.write_manifest(out / "manifest.json", ARM, seed, steps,
                        getattr(client, "server", None), getattr(client, "model", None),
                        [ROUND])
    frames.frame(world.reset())

    conv = Conversation(system_message())
    last_outcome = None        # the world's sentence for the step before this one
    note_line = None           # the world's note line, on the turn after it landed, once
    destination = None         # WORLD axis: the cell the last reply named, answered next turn
    n_calls = invalid = defaulted = destinations_named = 0
    completed_at = seen_at_completion = None

    for step in range(1, int(steps) + 1):
        frame = world.last_frame                                   # frame step-1
        pos_world = [int(v) for v in frame["player"]["pos"]]
        hint = None
        if destination is not None and list(destination) != pos_world:
            # A §4.2: no hint and no row for the cell the body is standing on.
            hint = route.route(pos_world, destination, world.seen)
            # A-QUESTION: A §4.2 does not say which step a chat `route` row is
            # stamped with, and in this arm the naming and the answering are
            # different steps. This is the step whose turn carried the sentence,
            # which is the step whose `actions.jsonl` row carries the same
            # `route_first_step`; the step that named the cell is the row before.
            events.append(route.route_event(step, destination, hint))
        destination = None                                         # answered, and dropped
        turn = user_turn(frame, world.mapped_bits(frame), outcome=last_outcome,
                         note_line=note_line,
                         route_sentence=(hint.sentence if hint is not None else None),
                         carrying=tuple(world.carrying))
        note_line = None
        trimmed = conv.open_turn(step, turn)
        if trimmed is not None:
            # A §4.2 (settled 09-24 on this module's A-question): both passes are
            # in the row, the windows omitted and the turns dropped.
            events.event(step, "conversation_trimmed", dropped_turns=trimmed["dropped_turns"],
                         windows_omitted=trimmed["windows_omitted"])

        parsed, tries = _complete(conv, client, grammar, calls, events, step)
        n_calls += tries
        invalid += tries - (1 if parsed is not None else 0)
        if parsed is None:
            defaulted += 1
            verb, why = constants.NOOP, ""
        else:
            verb, why = parsed["action"], parsed["why"]
            if parsed["destination"] is not None:
                # shown axis -> world axis, the involution (A §1.1)
                destination = axis.shown_pos(parsed["destination"])
                destinations_named += 1

        frame_after, said, world_events = world.step(verb)
        frames.frame(frame_after)
        for row in world_events:
            # the world's rows are A §4.2 rows; `event` checks their fields too
            events.event(row["step"], row["kind"], **{k: v for k, v in row.items() if k not in ("step", "kind")})
        if any(row["kind"] == "note_landed" for row in world_events):
            note_line = world.note_line
        if world.errands_completed and completed_at is None:
            completed_at, seen_at_completion = step, len(world.seen)
        last_outcome = said

        after = frame_after["player"]
        actions.action(
            step=step, arm=ARM, action=verb, intent=why,
            focus_id=None, target=None,                    # chat has no list and no R3
            destination=(list(destination) if destination is not None else None),
            route_first_step=(hint.first_step if hint is not None else None),
            pos_before=pos_world, pos_after=[int(v) for v in after["pos"]],
            moved=[int(v) for v in after["pos"]] != pos_world,
            standing_on_after=frame_after["standing_on"],
            drink_after=int(after["drink"]), health_after=int(after["health"]),
            # A-QUESTION: A §4.3 qualifies `focus_id`, `target` and `destination`
            # by arm but not `list_size`, and chat has no list (B §4). 0 is the
            # number of entries it holds; null would say "no such thing".
            list_size=0, n_calls=tries)
        if not quiet:
            shown = state.dumps(axis.shown_pos(after["pos"]))
            print(f"{ARM} s{seed} step {step}/{steps} {verb} -> {shown} (shown axis) "
                  f"drink {int(after['drink'])} health {int(after['health'])} :: {said}")
        if world.died:
            break

    steps_survived = frames.n_rows - 1                     # frame 0 is not a step
    first_errand = min(world.errands_reached.values()) if world.errands_reached else None
    summary = cell.write_summary(out / "summary.json", {
        "errands_completed": bool(world.errands_completed),
        "cells_reached": len(world.errands_reached),
        "steps_survived": steps_survived,
        "died": bool(world.died),
        "first_errand_step": first_errand,
        "note_to_first_errand_steps": (None if first_errand is None
                                       else first_errand - constants.NOTE_STEP),
        "after_errands": (None if completed_at is None else {
            "steps": steps_survived - completed_at,
            "new_cells": len(world.seen) - seen_at_completion}),
        "invalid_replies": {ROUND: invalid},
        "defaulted_replies": {ROUND: defaulted},
        "destinations_named": destinations_named,
        "n_calls": n_calls,
        "wall_s": round(time.perf_counter() - started, 3),
    })
    return ChatCell(dir=out, summary=summary, conversation=conv, world=world)


def _complete(conv, client, grammar, calls, events, step):
    """One step's reply: the call, A §3.4's one retry, A §3.4's default.

    The old `_complete`'s habit, which is chat's own: every attempt's reply is
    appended to the conversation verbatim, and a refused one is followed by a
    user turn carrying the reason, so the retry is the conversation plus two
    messages rather than the same page sent again (that is the trace arms').
    Returns `(parsed | None, attempts)`; None is the `noop` default, and every
    refused attempt has left a `reply_invalid` row behind it (A §4.2).
    """
    recovered = False
    for attempt in range(1, MAX_ATTEMPTS + 1):
        messages = [dict(m) for m in conv.messages]
        try:
            reply = client.complete(messages, grammar=grammar)
        except clientlib.ClientError as err:
            # The server's context is the one budget the estimate cannot see
            # past. On the first overflow of a step: take the server's own
            # count as the ratio, trim under the budget, log it, and try once
            # more; a second overflow is the run's exit 2 (A §5). Measured
            # 09-24: the first chat cell died this way at step 279.
            n_prompt = _exceeded_context(err)
            if n_prompt is None or recovered:
                raise
            conv.calibrate(n_prompt, messages)
            trimmed = conv.trim()
            events.event(step, "conversation_trimmed",
                         dropped_turns=(trimmed or {}).get("dropped_turns", []),
                         windows_omitted=(trimmed or {}).get("windows_omitted", []))
            recovered = True
            messages = [dict(m) for m in conv.messages]
            reply = client.complete(messages, grammar=grammar)
        if reply.tokens and reply.tokens.get("prompt"):
            conv.calibrate(reply.tokens["prompt"], messages)
        parsed, reason = read_reply(reply.text)
        calls.append({
            "call_no": calls.n_rows + 1, "step": int(step), "round": ROUND,
            "attempt": attempt, "transport_tries": reply.attempt,
            # A §4.1: chat's `prompt` is the new user turn only, and its hash
            # column is `prefix_sha256` — everything before that turn, the
            # cache-hit check. `page_sha256` is the trace arms'.
            "prompt": messages[-1]["content"],
            "page_sha256": None,
            "prefix_sha256": clientlib.prefix_sha256(messages),
            "grammar_id": ROUND, "reply_text": reply.text, "parsed": parsed,
            "valid": reason is None, "reason": reason,
            "elapsed_s": reply.elapsed_s, "tokens": reply.tokens,
        })
        conv.append("assistant", reply.text)
        if reason is None:
            return parsed, attempt
        # A-QUESTION: A §3.4 names `reply_invalid` for attempt 1 only, but its
        # row carries an `attempt` field (A §4.2), so a second refusal is logged
        # too and `summary.json`'s `invalid_replies` counts every refused reply.
        events.event(step, "reply_invalid", round=ROUND, attempt=attempt, reason=reason)
        if attempt < MAX_ATTEMPTS:
            conv.append("user", RETRY_LINE.format(reason=reason))
    events.event(step, "reply_defaulted", round=ROUND, default=constants.NOOP)
    return None, MAX_ATTEMPTS


def _exceeded_context(err):
    """The server's `n_prompt_tokens` when `err` is llama.cpp's context-size
    refusal (HTTP 400, `exceed_context_size_error`), else None."""
    if err.status != 400 or not isinstance(err.body, str) or "exceed_context" not in err.body:
        return None
    try:
        return int(json.loads(err.body)["error"]["n_prompt_tokens"])
    except (ValueError, KeyError, TypeError):
        return 1  # the refusal is certain even when the count is not
