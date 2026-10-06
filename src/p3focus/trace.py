"""The trace controller: flat, focus and sliced, one cell at a time.

B §3 owns the rounds of a step, A §3.4 the validation, the one retry and the
defaults, A §4 the rows. This module is the only place that decides *when* the
body is asked; nothing here ever decides *what* it holds (A §7, D6).

**Axis, at every boundary.** The world is +y down and every log row is world
axis (A §4). The model reads and writes +y up, so R3's `target` and flat's
`destination` come back through `axis.shown_pos` — the involution — before they
reach the route hint, the action row or the event rows. `pages.py` does the
other direction, for the page. No world-axis number is ever put on a page here
and no shown-axis number is ever logged.

One call: `run_trace_cell(arm, seed, steps, client, out_dir)`.
"""

import dataclasses
import json
import time

from p3focus import axis, cell, client as client_mod, constants, gate as gate_mod, grammars
from p3focus import list_store, pages, route, texts, world as world_mod

#: The arms this controller runs (A §5); `chat` is the other controller's.
ARMS = ("flat", "focus", "sliced")

#: The rounds each arm runs, in page order — the `grammar_ids` its manifest
#: carries (A §4.4) and the grammars its calls name (A §4.1).
ARM_ROUNDS = {
    "flat": ("flat",),
    "focus": ("R1", "R1.5", "R2", "R3", "R4"),
    "sliced": ("R1", "R1.5", "R3", "R4"),      # B §3.7: no R2
}

#: A §3.4's defaults, by the name `reply_defaulted.default` carries
DEFAULT_NAMES = {"R1": "no", "R1.5": "false", "R3": "target: null",
                 "R4": constants.NOOP, "flat": constants.NOOP}

#: The old line's one retry hint (`loop.py` ~5353), ported by name: one line,
#: the plain reason, appended to the same page (A §3.4).
# B-QUESTION: B quotes every block of a page but not this line, and A §3.4 says
# only "one reason line appended". The old repo's wording is kept so the two
# lines read alike; the exact bytes to change live in this one constant.
RETRY_LINE = "your last reply was not accepted: {reason}; reply with one JSON object"


class TraceCell:
    """One cell of one trace arm (A §4: one directory, one world, one gate, one
    list). Built and run by `run_trace_cell`; a class only so a test can read
    the pieces afterwards."""

    def __init__(self, arm, seed, steps, client, out_dir, quiet=False):
        if arm not in ARMS:
            raise ValueError(f"{arm!r} is not a trace arm; they are {ARMS}")
        self.arm = arm
        self.seed = int(seed)
        self.steps = int(steps)
        self.client = client
        self.quiet = bool(quiet)
        self.world = world_mod.World(self.seed)
        self.gate = gate_mod.Gate()
        self.store = list_store.ListStore(dawn=True)
        if arm != "focus":
            # A §2: the entry in force is focus's alone. flat and sliced keep the
            # dawn entry and hold nothing, so no `focus_*` row is ever theirs.
            self.store.focus = None
        self.dir = cell.cell_dir(out_dir, arm, self.seed)
        self.calls = client_mod.CallLog(self.dir / "calls.jsonl")
        self.events = cell.EventLog(self.dir / "events.jsonl")
        self.actions = cell.ActionLog(self.dir / "actions.jsonl")
        self.frames = cell.FrameLog(self.dir / "frames.jsonl")
        #: history lines (B §1.2), oldest first, the note's among them
        self.history = []
        #: per-step bookkeeping the rows and the summary read
        self.invalid_replies = {}
        self.defaulted_replies = {}
        self.destinations_named = 0
        self._focus_deleted_id = None       # B §3.3's second `{previous line}`
        #: the hold (A §3.1): the destination between asks — focus's and sliced's
        #: between R3 asks, flat's between its own replies (A §7 D9 since 09-25,
        #: E2) — a `pages.Destination` (cell WORLD axis), or None when none is
        #: held and the step explores
        self.dest = None
        self.destinations_chosen = 0
        self._errands_step = None
        self._seen_at_errands = None
        self._focus_after_errands = []
        self.summary = None

    # -- the cell -----------------------------------------------------------

    def run(self):
        """Run the whole cell and return `summary.json`'s body (A §4.4).

        Death ends it early (A §4.4, `died`); the command's exit code is 0
        either way (A §5).
        """
        started = time.perf_counter()
        cell.write_manifest(self.dir / "manifest.json", self.arm, self.seed, self.steps,
                            _server_of(self.client), _model_of(self.client),
                            ARM_ROUNDS[self.arm])
        frame = self.world.reset()
        self.frames.frame(frame)
        fired = set()
        world_events = []
        if self.arm != "flat":
            # the gate is observed once per step, in order, from the reset frame
            # (A §4.2: step N's events open step N+1's asks)
            fired = self.gate.observe(0, len(self.world.seen), ())
            self._emit_rows(self.gate.last_rows)
        steps_taken = 0
        for step in range(1, self.steps + 1):
            frame = self._step(step, frame, fired, world_events)
            steps_taken = step
            world_events = list(self.world.events)
            if self.arm != "flat":
                fired = self.gate.observe(step, len(self.world.seen), world_events)
                self._emit_rows(self.gate.last_rows)
            if self.world.died:
                break
        self.summary = self._summary(steps_taken, round(time.perf_counter() - started, 3))
        cell.write_summary(self.dir / "summary.json", self.summary)
        return self.summary

    def _step(self, step, frame, fired, world_events):
        """One world step: its state, its rounds, its action, its rows (B §3).

        `frame` is the frame the page shows — the world's record of step N−1,
        WORLD axis. `fired` is what the gate answered for step N−1 and
        `world_events` are that step's world rows, which B §3.1 renders.
        """
        calls_before = self.calls.n_rows
        base = pages.State(arm=self.arm, frame=frame, mapped=self.world.mapped_bits(frame),
                           history=tuple(self.history[-constants.K_HISTORY:]),
                           carrying=tuple(self.world.carrying))
        self._focus_deleted_id = None
        pos_before = [int(v) for v in frame["player"]["pos"]]

        if self.arm == "flat":
            action, intent, target_world, destination_world, route_first = \
                self._flat_round(step, base, pos_before)
        else:
            asked = self._asks(step, base, fired, world_events)
            action, intent, target_world, route_first = \
                self._acting_rounds(step, base, pos_before, asked)
            destination_world = None

        focus_id = self.store.focus if self.arm == "focus" else None
        new_frame, said, events = self.world.step(action)
        self.frames.frame(new_frame)
        self.history.append(texts.trace_action_line(new_frame["step"], action, intent, said))
        for row in events:
            self._emit(row)
            if row["kind"] == "note_landed":
                # A §1.3: the note's line is appended after the step's own
                # action line and counts toward K like any other line
                self.history.append(self.world.note_line)
            if row["kind"] == "errands_completed":
                self._errands_step = step
                self._seen_at_errands = len(self.world.seen)
        if self._errands_step is not None and step > self._errands_step:
            self._focus_after_errands.append(focus_id)

        pos_after = [int(v) for v in new_frame["player"]["pos"]]
        self.actions.action(
            step=step, arm=self.arm, action=action, intent=intent, focus_id=focus_id,
            target=target_world, destination=destination_world, route_first_step=route_first,
            pos_before=pos_before, pos_after=pos_after, moved=pos_after != pos_before,
            standing_on_after=new_frame["standing_on"],
            drink_after=int(new_frame["player"]["drink"]),
            health_after=int(new_frame["player"]["health"]),
            list_size=len(self.store), n_calls=self.calls.n_rows - calls_before)
        if not self.quiet:
            print(f"step {step:>4}  {action:<11} {json.dumps(axis.shown_pos(pos_after))}"
                  f"  drink {new_frame['player']['drink']}  list {len(self.store)}"
                  f"  {said}", flush=True)
        return new_frame

    # -- the asks (B §3.1, §3.2, §3.3) --------------------------------------

    def _asks(self, step, base, fired, world_events):
        """R1, its R1.5s and R2, for focus and sliced (B §3.1–§3.3, §3.7).

        Two occasions bring R1: the gate (A §4.2) and the no-focus rule (B §3.1
        — focus: no entry in force at the start of R3; sliced: an empty list).
        **One R1 page per occasion, at most two a step:** when the body is
        already without an entry in force as the gated R1 renders, the no-focus
        line rides that page; a second page carrying only that line renders only
        when the gated R1 itself emptied the list.

        Returns whether an ask ran this step — R3's `event` occasion (A §3.1).
        """
        missing_at_start = self._no_focus()
        rode_with_gate = False
        if fired:
            lines = pages.event_lines(
                world_events, stalled=gate_mod.STALL in fired,
                no_focus=(pages.no_focus_line(self.arm, len(self.store) == 0)
                          if missing_at_start else None))
            rode_with_gate = missing_at_start
            self._r1_block(step, base, lines)
        if not self._no_focus():
            return bool(fired)
        if fired and (rode_with_gate or len(self.store) > 0):
            # either the line already rode the gated page, or the entry in force
            # went missing because R2 defaulted — which B §3.3 answers on the
            # next step, not with a second page on this one
            return True
        self._r1_block(step, base, [pages.no_focus_line(self.arm, len(self.store) == 0)])
        return True

    def _no_focus(self):
        """Is the no-focus rule's condition true right now? focus: no entry in
        force (B §3.1). sliced: an empty list, which is the same occasion for an
        arm that holds no entry (B §3.7)."""
        if self.arm == "sliced":
            return len(self.store) == 0
        return self.store.focus is None

    def _r1_block(self, step, base, lines):
        """One R1 page, its held deletes' R1.5s, and R2 when the list is not
        empty once they are done (B §3.1, §3.2, §3.3's one rule)."""
        def on_invalid(parsed, reason):
            """A §4.2's `ops_rejected`: a reply that meant to change the list
            and could not."""
            if isinstance(parsed, dict) and parsed.get("maintain") == "yes":
                self.events.event(step, "ops_rejected", source="R1",
                                  ops=parsed.get("ops"), reason=reason)

        page = pages.page_r1(self._state(base), lines)
        parsed, valid = self._call(step, "R1", page, self._check_r1, on_invalid=on_invalid)
        held = []
        if valid and parsed.get("maintain") == "yes":
            row, held = self.store.apply(parsed["ops"], "R1", hold=True)
            self.events.event(step, "ops_applied", **row)
        for entry_id in held:
            self._r1_5(step, base, entry_id)
        if self.arm == "focus" and len(self.store):
            self._r2(step, base)

    def _r1_5(self, step, base, entry_id):
        """One confirmation (B §3.2). A confirmed deletion applies at once, so
        the next R1.5's page shows the list without it."""
        entry = self.store.get(entry_id)
        if entry is None:
            return          # an earlier confirmation in this reply removed it
        page = pages.page_r1_5(self._state(base), entry)
        parsed, valid = self._call(step, "R1.5", page, self._check_r1_5)
        if not (valid and parsed.get("delete") is True):
            self.events.event(step, "delete_declined", id=entry_id)
            return
        was_empty_focus = self.store.focus is None
        _, cleared = self.store.confirm_delete(entry_id)
        self.events.event(step, "delete_confirmed", id=entry_id)
        if cleared:
            self._focus_deleted_id = entry_id
            self.events.event(step, "focus_missing", reason="deleted")
        elif was_empty_focus and len(self.store) == 0 and self.arm == "focus":
            # A-QUESTION: A §4.2 gives `focus_missing` the two reasons `deleted`
            # and `empty`, and A §2 names three ways the entry in force can be
            # missing at the start of R3. The row is written here at the moment
            # of loss, where the reason is knowable: `deleted` when a confirmed
            # deletion removed it, `empty` when a confirmed deletion emptied a
            # list that already had nothing in force. The third way — R2
            # defaulted with nothing to keep — is named by `focus_none`'s own
            # `r2_defaulted`, on the step it happened, so it is not repeated
            # here as a reason this row has no word for.
            self.events.event(step, "focus_missing", reason="empty")

    def _r2(self, step, base):
        """The entry in force (B §3.3). The harness never picks: a second
        invalid reply keeps what was in force if it is still on the list, and
        otherwise leaves nothing (A §3.4, D6)."""
        previous = self.store.focus
        line = pages.previous_line(previous if previous is not None else self._focus_deleted_id,
                                   deleted=previous is None and self._focus_deleted_id is not None)
        page = pages.page_r2(self._state(base), line)
        parsed, valid = self._call(step, "R2", page, self._check_r2)
        if valid:
            self.store.set_focus(parsed["focus"])
            self.events.event(step, "focus_chosen", id=parsed["focus"])
            return
        # A §3.4's default: the previous entry if it is still on the list, else
        # none. `store.focus` is already None when R1.5 deleted it.
        keep = previous if previous is not None and self.store.get(previous) else None
        self.store.focus = keep

    # -- the acting rounds (B §3.4, §3.5) -----------------------------------

    def _acting_rounds(self, step, base, pos_before, asked):
        """R3 on its occasions, then R4 every step, toward the held destination
        (A §3.1 "the hold"; B §3.4, §3.5, §6 checker 9).

        `asked` is whether an ask ran this step — the `event` occasion. Returns
        `(action, intent, target_world, route_first_step)`; the target is the
        destination held during R4, WORLD axis for the rows, or None on a step
        that explored.
        """
        if self.arm == "focus" and self.store.focus is None:
            self.events.event(step, "focus_none",
                              reason="empty" if len(self.store) == 0 else "r2_defaulted")
        pos = (int(pos_before[0]), int(pos_before[1]))
        occasion, about = self._occasion(step, pos, asked)
        fresh = occasion is not None
        valid = True
        need = why = ""
        if fresh:
            page = pages.page_r3(self._state(base), pages.destination_line(occasion, about))
            parsed, valid = self._call(step, "R3", page, self._check_r3)
            target_shown = parsed.get("target") if valid else None
            # the old round one's prose crosses to R4 (B §3.5); a reply that parsed
            # keeps its need even when its position was refused
            need = str(parsed.get("need", "")) if isinstance(parsed, dict) else ""
            why = str(parsed.get("why", "")) if isinstance(parsed, dict) and valid else ""
            self._take_destination(step, target_shown, need, why)

        target_world = None
        route_sentence = None
        route_first = None
        if self.dest is not None:
            target_world = list(self.dest.cell)
            if self.dest.cell != pos:
                # A §6: no hint, and no row, for the cell the body stands on
                result = route.route(pos, self.dest.cell, self.world.seen)
                route_sentence = result.sentence
                route_first = result.first_step
                self._emit(route.route_event(step, target_world, result))

        page = pages.page_r4(self._state(base), route_sentence, fresh=fresh,
                             defaulted=fresh and not valid, need=need, why=why)
        parsed4, valid4 = self._call(step, "R4", page, self._check_r4)
        action = parsed4["action"] if valid4 else constants.NOOP
        intent = str(parsed4.get("intent", "")) if valid4 else ""
        return action, intent, target_world, route_first

    # -- the hold (A §3.1; B §3.4) ------------------------------------------

    def _occasion(self, step, pos, asked):
        """Why R3 renders this step, or `(None, None)` when it does not (B §3.4's
        table). Returns `(occasion, destination)`: the destination the line is
        about — the one reached or cleared here, or the one still held on the
        event occasion. `pos` is the body's cell, WORLD axis.

        flat calls this too, with `asked` False: it has no R3 and no ask, so only
        the two ends that need no question can happen there — the body standing
        on the held cell, and no way to it over cells it has seen — and the same
        two rows are written by the same rules (A §7 D9 since 09-25, E2). flat
        ignores what comes back: `missing` means only that its page carries no
        destination block.
        """
        dest = self.dest
        if dest is None:
            return "missing", None
        if dest.cell == pos:
            self.events.event(step, "destination_reached", cell=list(dest.cell),
                              held_steps=step - dest.step)
            self.dest = None
            return "reached", dest
        if route.route(pos, dest.cell, self.world.seen).first_step is None:
            self._clear_destination(step, "no_way")
            return "no_way", dest
        if asked:
            return "event", dest
        return None, None

    def _take_destination(self, step, target_shown, need, why):
        """Hold R3's answer (A §3.1): the same cell keeps the hold — its step and
        its prose; another cell replaces it; null, or a defaulted reply, drops it
        and the step explores. `target_shown` is the reply's cell in the SHOWN
        axis, or None.

        flat comes here only with a cell (A §3.2 since the hold: its `null` keeps
        what is held rather than dropping it, so the null branch below is R3's
        alone), and with no `need` and no `why` to carry.
        """
        held = self.dest
        if target_shown is None:
            if held is not None:
                self._clear_destination(step, "dropped")
            return
        cell = tuple(int(v) for v in axis.shown_pos(target_shown))
        if held is not None and held.cell == cell:
            # kept: the step, the need and the why that named it stay (B §3.4); the
            # re-affirming reply's own words are in calls.jsonl
            return
        if held is not None:
            self._clear_destination(step, "replaced")
        self.dest = pages.Destination(cell, step, need, why)
        self.destinations_chosen += 1
        self.events.event(step, "destination_chosen", cell=list(cell))

    def _clear_destination(self, step, reason):
        """`destination_cleared` (A §4.2) for the held destination, and the hold
        emptied. `held_steps` is the steps R4 walked toward it."""
        dest = self.dest
        self.events.event(step, "destination_cleared", cell=list(dest.cell),
                          held_steps=step - dest.step, reason=reason)
        self.dest = None

    # -- flat (B §3.6) ------------------------------------------------------

    def _flat_round(self, step, base, pos_before):
        """flat's one page and one reply (B §3.6, A §3.2), under the hold.

        **flat holds its destination** (A §7 D9 since 09-25, E2: the control for
        the hold itself). It gets the hold and nothing else — the same one page,
        the same one reply, the same list on it. So:

        - the two ends that need no question are checked at the step's start, by
          the same `_occasion` focus uses: standing on the held cell writes
          `destination_reached`, no way to it writes `destination_cleared`
          (`no_way`), and either way nothing is held when the page renders;
        - the route hint answers **this** page's held cell, not last step's
          named one (the departure from A §3.2's "answered on the next step",
          recorded there and in D9): so the row and `route_first_step` are the
          hint the body actually read, as focus's are;
        - the reply then keeps what is held (`null`), replaces it (another cell)
          or names one; a reply refused twice keeps it too, the way R2's default
          keeps what was in force (A §3.4).

        Returns A §4.3's row values: `target` is null in flat, and `destination`
        is the cell held while the body acted — the one the page carried — so it
        and `route_first_step` are the same step's reading.
        """
        pos = (int(pos_before[0]), int(pos_before[1]))
        self._occasion(step, pos, asked=False)
        destination_world = None
        route_sentence = None
        route_first = None
        if self.dest is not None:
            destination_world = list(self.dest.cell)
            if self.dest.cell != pos:
                # A §6: no hint, and no row, for the cell the body stands on
                result = route.route(pos, self.dest.cell, self.world.seen)
                route_sentence = result.sentence
                route_first = result.first_step
                self._emit(route.route_event(step, destination_world, result))
        page = pages.page_flat(self._state(base), route_sentence)
        parsed, valid = self._call(step, "flat", page, self._check_flat,
                                   on_invalid=lambda p, r: self._flat_rejected(step, p, r))
        if not valid:
            # A §3.4: noop, and a flat reply's ops are dropped. The hold is not
            # dropped with them: flat's `null` keeps what is held, so a reply
            # that named nothing — because it was refused twice — keeps it too.
            return constants.NOOP, "", None, destination_world, route_first
        if parsed["ops"]:
            row, _ = self.store.apply(parsed["ops"], "flat", hold=False)
            self.events.event(step, "ops_applied", **row)
        destination_shown = parsed.get("destination")
        if destination_shown is not None:
            # A §4.4: `destinations_named` counts the replies that named a cell,
            # the held one named again among them; `destinations_chosen` counts
            # the rows, which that one does not write (`_take_destination`)
            self.destinations_named += 1
            self._take_destination(step, destination_shown, "", "")
        return (parsed["action"], str(parsed.get("intent", "")), None,
                destination_world, route_first)

    def _flat_rejected(self, step, parsed, reason):
        if isinstance(parsed, dict) and parsed.get("ops"):
            self.events.event(step, "ops_rejected", source="flat", ops=parsed["ops"],
                              reason=reason)

    # -- one model call, with A §3.4's retry and default --------------------

    def _call(self, step, round_id, page, check, on_invalid=None):
        """One round: the page, at most two semantic attempts, one row a call
        (A §3.4, A §4.1).

        Returns `(parsed, valid)`. `parsed` is the last reply that parsed at all
        — which a caller may still read, the way R3 keeps its `do` — and `valid`
        says whether it passed. On a second failure `reply_defaulted` is written
        and the caller applies A §3.4's default.
        """
        prompt = page
        parsed = None
        for attempt in (1, 2):
            setter = getattr(self.client, "set_round", None)
            if setter is not None:
                setter(round_id)      # A §5: a scripted policy asserts its round
            messages = [{"role": "user", "content": prompt}]
            reply = self.client.complete(messages, grammar=grammars.grammar(round_id))
            parsed, reason = _parse(reply.text)
            if parsed is not None:
                if round_id in ("R3", "R4") and "ops" in parsed:
                    # A §4.2's defect detector: the acting rounds have no path to
                    # the list, so this must never fire. Nothing is applied — no
                    # branch below this one reads `ops` — and the row, and the
                    # call's own `parsed`, keep the evidence.
                    self.events.event(step, "ops_in_acting_reply", round=round_id,
                                      ops=parsed["ops"])
                reason = check(parsed)
            self.calls.append({
                "call_no": self.calls.n_rows + 1, "step": step, "round": round_id,
                "attempt": attempt, "transport_tries": reply.attempt, "prompt": prompt,
                "page_sha256": client_mod.messages_sha256(messages),
                # A §4.1: a trace arm's page is the whole message, so there is no
                # prefix to hash; the column is chat's.
                "prefix_sha256": None, "grammar_id": round_id, "reply_text": reply.text,
                "parsed": parsed, "valid": reason is None, "reason": reason,
                "elapsed_s": reply.elapsed_s, "tokens": reply.tokens})
            if reason is None:
                return parsed, True
            self.events.event(step, "reply_invalid", round=round_id, attempt=attempt,
                              reason=reason)
            self.invalid_replies[round_id] = self.invalid_replies.get(round_id, 0) + 1
            if on_invalid is not None:
                on_invalid(parsed, reason)
            prompt = page + "\n\n" + RETRY_LINE.format(reason=reason)
        self.events.event(step, "reply_defaulted", round=round_id,
                          default=DEFAULT_NAMES.get(round_id, "none"))
        self.defaulted_replies[round_id] = self.defaulted_replies.get(round_id, 0) + 1
        return parsed, False

    # -- A §3.4's semantic checks -------------------------------------------
    #
    # The grammar makes every live reply the right shape (A §7, D1), so these
    # answer only what a grammar cannot: ids that exist, coordinates on the map.
    # The shape is checked too, because `--policy scripted:` replies (A §5) are
    # authored and reach no grammar at all, and a malformed one must come back
    # as a reason the body can read rather than as a crash.

    def _check_r1(self, parsed):
        """R1: `no`, or `yes` with one to five ops whose ids exist (A §3.1, §3.4)."""
        if not isinstance(parsed.get("why"), str):
            return '"why" must be text'
        maintain = parsed.get("maintain")
        if maintain == "no":
            return '"maintain": "no" carries no operations' if "ops" in parsed else None
        if maintain != "yes":
            return '"maintain" must be "no" or "yes"'
        return self.store.validate(parsed.get("ops"))

    def _check_r1_5(self, parsed):
        """R1.5: one boolean (A §3.1)."""
        return None if isinstance(parsed.get("delete"), bool) else '"delete" must be true or false'

    def _check_r2(self, parsed):
        """R2: an id that is on the list (A §3.4)."""
        if not isinstance(parsed.get("why"), str):
            return '"why" must be text'
        entry_id = parsed.get("focus")
        if not isinstance(entry_id, str):
            return '"focus" must be an id from the list'
        return self.store.validate_focus(entry_id)

    def _check_r3(self, parsed):
        """R3: a need and a why as text, a target and candidates inside the world,
        or null; and a target the body can see must be a cell it can stand on
        (A §3.4; added 09-24 after the first show run,
        registrations/20260924_show_run_focus_s7_98b.md)."""
        for key in ("need", "why"):
            if not isinstance(parsed.get(key), str):
                return f'"{key}" must be text'
        reason = _check_coord(parsed.get("target"), "your target", allow_null=True)
        if reason:
            return reason
        target = parsed.get("target")
        if target is not None:
            reason = self._visible_and_not_walkable(target)
            if reason:
                return reason
        candidates = parsed.get("candidates")
        if not isinstance(candidates, list) or len(candidates) > constants.R3_CANDIDATES:
            return f'"candidates" is a list of at most {constants.R3_CANDIDATES} positions'
        for i, candidate in enumerate(candidates):
            reason = _check_coord(candidate, f"candidate {i + 1}")
            if reason:
                return reason
        return None

    def _visible_and_not_walkable(self, target_shown):
        """The reason a visible, non-walkable target is refused, or None. Reads
        the frame the page read (the world's last frame): the 9×9 window, world
        axis, centred on the body. Unseen cells are not judged; the body's own
        cell is allowed."""
        frame = self.world.last_frame
        px, py = (int(v) for v in frame["player"]["pos"])
        tx, ty = axis.shown_pos(target_shown)
        half = len(frame["window"]) // 2
        dx, dy = tx - px, ty - py
        if abs(dx) > half or abs(dy) > half or (dx, dy) == (0, 0):
            return None
        material = frame["window"][dy + half][dx + half]
        if material in world_mod.WALKABLE:
            return None
        shown = json.dumps([int(target_shown[0]), int(target_shown[1])])
        return (f"{shown} is {material}; you cannot stand on it — name a cell you can stand on, "
                "or a cell beside it")

    def _check_r4(self, parsed):
        """R4: one of the four verbs, and an `intent` that may be empty (A §3.1)."""
        if parsed.get("action") not in constants.VERBS:
            return '"action" must be one of ' + ", ".join(constants.VERBS)
        return None if isinstance(parsed.get("intent"), str) else '"intent" must be text'

    def _check_flat(self, parsed):
        """flat: R4's checks, plus zero to five ops and a destination on the map
        (A §3.2, §3.4)."""
        reason = self._check_r4(parsed)
        if reason:
            return reason
        ops = parsed.get("ops")
        if not isinstance(ops, list):
            return '"ops" must be a list, [] when nothing changed'
        if ops:
            reason = self.store.validate(ops)
            if reason:
                return reason
        return _check_coord(parsed.get("destination"), "your destination", allow_null=True)

    # -- plumbing -----------------------------------------------------------

    def _state(self, base):
        """This round's `State`: the step's world half unchanged, the list and
        the entry in force as they stand now.

        A-QUESTION: A §1.3 says the State is "built once per step … and handed
        to every round of that step unchanged", and B §3.2 says R1.5's page
        shows the adds and edits R1 just made. Both hold if "unchanged" is about
        the world half — the same window, the same history, the same meters, for
        every round of the step, which is what R4's "the same cells, unmoved"
        promises — and the list half is the store's, read at each round. That is
        the reading built here.
        """
        return dataclasses.replace(
            base, entries=tuple(self.store.entries), focus_id=self.store.focus,
            destination=self.dest)

    def _emit(self, row):
        """One row another module built — the world's (A §6), the gate's, the
        route hint's — written to `events.jsonl` verbatim."""
        kind = row.get("kind")
        if kind not in cell.EVENT_FIELDS:
            raise ValueError(f"unknown event kind {kind!r} (A §4.2)")
        fields = {k: v for k, v in row.items() if k not in ("step", "kind")}
        if set(fields) == set(cell.EVENT_FIELDS[kind]):
            return self.events.event(row["step"], kind, **fields)
        # MODULE-QUESTION: `cell.EVENT_FIELDS["arrival"]` carries a `first` that
        # neither A §4.2 nor `world.py` has — the world writes an arrival row
        # only the first time a cell counts, so the flag would be constant. A's
        # shape is kept and the row goes through verbatim; the kind is still
        # checked above.
        return self.events.append(dict(row))

    def _emit_rows(self, rows):
        for row in rows:
            self._emit(row)

    def _summary(self, steps_taken, wall_s):
        """`summary.json` (A §4.4). Nothing here is needed that the rows cannot
        reproduce; it is the reader's convenience, not its evidence."""
        arrivals = sorted(self.world.errands_reached.items())
        first = min((s for _, s in arrivals), default=None)
        after = None
        if self._errands_step is not None:
            after = {"steps": steps_taken - self._errands_step,
                     "new_cells_seen": len(self.world.seen) - self._seen_at_errands}
            if self.arm == "focus":
                after["focus_ids"] = list(self._focus_after_errands)
        return {
            "arm": self.arm, "seed": self.seed, "steps": self.steps,
            "errands_completed": bool(self.world.errands_completed),
            "cells_reached": len(self.world.errands_reached),
            "steps_survived": steps_taken, "died": bool(self.world.died),
            "first_errand_step": first,
            "note_to_first_errand_steps": None if first is None else first - constants.NOTE_STEP,
            "after_errands": after,
            "invalid_replies": dict(self.invalid_replies),
            "defaulted_replies": dict(self.defaulted_replies),
            # A §4.4: "by a reader's rule, not the harness's" — the harness does
            # not decide which entry names an errand, so the key is present and
            # empty rather than guessed at.
            "focus_is_errand_fraction": None,
            # A §4.4: flat has both since the hold (A §7 D9) — the replies that
            # named a cell, and the rows a new cell wrote — and they differ
            # whenever a reply names the cell it already holds
            "destinations_named": self.destinations_named if self.arm == "flat" else None,
            "destinations_chosen": self.destinations_chosen,
            "n_calls": self.calls.n_rows, "wall_s": wall_s,
            "list_size": len(self.store), "seen_cells": len(self.world.seen),
        }


def run_trace_cell(arm, seed, steps, client, out_dir, quiet=False):
    """Run one trace cell and return `(cell_dir, summary)` (A §4, §5).

    `arm` is `flat`, `focus` or `sliced`; `out_dir` is A §5's `--out`, the
    **parent**, under which `<arm>_s<seed>_<stamp>/` is created. `client` is a
    `Client` or a `ScriptedClient`; nothing here talks to a server directly.
    """
    # A §6: the grammar probe before the cell's first real call — and before the
    # cell's directory exists, so a server that fails it leaves nothing behind.
    # A scripted client has no server and answers None.
    client.probe()
    run = TraceCell(arm, seed, steps, client, out_dir, quiet=quiet)
    summary = run.run()
    return run.dir, summary


# -- small pure helpers ---------------------------------------------------


def _parse(text):
    """One reply's JSON object, or `(None, reason)` (A §3.4). Under a live
    grammar this cannot fail; a `--policy scripted:` reply reaches no grammar."""
    try:
        parsed = json.loads(text)
    except ValueError as err:
        return None, f"that was not one JSON object ({err})"
    if not isinstance(parsed, dict):
        return None, "a reply is one JSON object"
    return parsed, None


def _check_coord(value, what, allow_null=False):
    """One position out of a reply: `[x, y]`, two whole numbers, inside the
    world (A §3.4). SHOWN axis, but the check is the same in either — the world
    is square and the involution keeps 0..63 inside itself. Ported from the old
    `loop._reply_coord`, whose messages are the retry's reason."""
    if value is None:
        return None if allow_null else f"{what} must be a position [x, y]"
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return f"{what} must be a position [x, y] — two numbers, got {value!r}"
    for n in value:
        if isinstance(n, bool) or not isinstance(n, int):
            return f"{what} must be two whole numbers, got {value!r}"
        if not 0 <= n < constants.WORLD_SIZE:
            return (f"{what} is off the map: the world is {constants.WORLD_SIZE} by "
                    f"{constants.WORLD_SIZE}, so x and y are 0..{constants.WORLD_SIZE - 1}; "
                    f"got {value!r}")
    return None


def _server_of(client):
    """What the manifest's `server` says (A §4.4). A scripted client names its
    policy file there, so a scripted cell can never be read as a live one."""
    return getattr(client, "server", None) or "scripted"


def _model_of(client):
    """The model as the server reports it (A §4.4), or the client's own name."""
    props = getattr(client, "props", None)
    if props is not None:
        try:
            body = props() or {}
        except Exception:
            body = {}
        for key in ("model_path", "model"):
            if isinstance(body.get(key), str):
                return body[key]
        settings = body.get("default_generation_settings")
        if isinstance(settings, dict) and isinstance(settings.get("model"), str):
            return settings["model"]
    return getattr(client, "model", "unknown")
