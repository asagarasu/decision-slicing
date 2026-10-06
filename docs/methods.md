# Methods

A concise description of the experiment. The authoritative specifications are
`design/interfaces.md` (the state, schemas, log rows, and the run command) and
`design/pages.md` (the exact text of every page, round by round and arm by arm).

## The question

Every arm is given the same information. Does serving each step's decision in
single-purpose slices — ending with only the one motivation in force on the page that
acts — let a small model finish a chain of errands, where a single pass over everything
does not?

## The two tasks

The body plays a Crafter world (64×64, a 9×9 window centred on it) under this line's
rules: water is walkable and standing in it restores drink; sand costs drink; food and
energy are pinned; monsters are removed; lava is swept to stone. The only actions are the
four moves.

- **The standing task — map the surface.** From the start the body's job is to map every
  walkable cell. In the trace arms this task lives only as an entry on the motivation
  list; in chat it is stated once, in the system message.

- **The interrupting errand chain.** At step 10 a note arrives as one line of history:
  stand on a first named cell to pick up an item, stand on a second for a second item,
  then return to a third cell carrying both. The note is explicit that the map can wait.
  The errand chain is therefore an interruption of a standing task — without the standing
  task there is nothing to interrupt.

Arrival at an errand cell is counted once, in any order; the return counts only once both
items are carried. **Errands completed** is the return reached; **errand cells reached**
is 0–3.

## The four arms

All arms run the same world, the same seeds, and the same note. They differ only in how a
step's decision is produced.

- **flat** — a trace arm with one forward pass per step. The motivation list and its
  manual are on the page, and a single reply carries any list edits, a destination, and
  the action. This is the control for layering: the same content, not sliced.
- **focus** — a trace arm whose step is split into the rounds below. The treatment.
- **chat** — the conversational regime: the body is told the task once in a system
  message and the whole conversation is kept and re-sent each turn. This is where an
  everyday agent loop lands.
- **sliced** — focus without the choosing round (R2): the step is sliced, but the whole
  motivation list stays visible, read-only, on the acting rounds. It separates the effect
  of slicing from the effect of narrowing to a single entry.

## The rounds

In **focus**, one step is up to five model calls (rounds). The world — window, meters,
position, recent history — is on every round's page. What a round restricts is the
*motivational* content.

- **R1 — maintain.** Asks whether the motivation list needs changing. The reply is either
  "no" or a set of one to five operations (add / edit / delete an entry). The list and its
  manual are visible and may be edited here. R1 runs on a gated step (see below) and
  whenever no entry is in force at the start of the acting rounds.
- **R1.5 — confirm a deletion.** One round per deletion requested in R1, confirming it
  before it is applied. Adds and edits apply at once; deletions wait for confirmation.
- **R2 — choose the one in force.** Asks which single entry has to be done first, from
  where the body stands now. From here until the next ask, that is the only motivation the
  acting rounds will see. (sliced omits R2 and keeps the whole list read-only instead.)
- **R3 — the destination.** Shows only the one entry in force (plus the world) and asks
  where the body is going: a cell to head for. The chosen destination is held by the
  harness and walked toward; R3 is not asked again until the body stands on it, a new
  event re-opens it, or there is no path to it over cells already seen.
- **R4 — the action.** Shows the one entry in force and the previous round's answer (the
  held destination, with a bearing line and a route hint), and asks for one game action.
  R4 runs every step; on steps where R3 did not run it is the step's only acting round.

Neither R3 nor R4 can edit the list: in the acting rounds the list, its manual, and the
power to change it are absent. In **flat** and **chat** there is one round per step, which
carries everything at once.

The maintenance rounds open on **events** (the "gate"): the note landing, arrival at an
errand cell, a drink crossing (drink reaching 0 or health falling), and a stall (no new
cell seen for a fixed number of steps, fired once per stall).

## How context is carried

- **The world is on every page, in every arm.** The window, meters, position, what the
  body stands on, and the last five history lines appear on every round. History counts as
  world, including the body's own past intent lines and the human's note. No round is
  blind to the world.
- **The restriction is on motivation only.** Rounds R1/R1.5/R2 see the whole list and its
  manual and may change it. Rounds R3/R4 see only the one entry in force (in sliced, the
  whole list, read-only) and cannot change anything. flat sees everything in one pass.
- **Trace arms vs chat.** In the trace arms (flat, focus, sliced) each page is rebuilt from
  scratch for every round; the asks leave no trace and the task is off the page, living
  only on the list. In chat the task is stated once and the entire conversation is kept;
  there is no page from which to take the task off. When the conversation exceeds its token
  budget, the oldest turns' window fields are dropped first, then whole old turns.
- **The route hint.** A seen-cells route hint gives the first move toward a named
  destination. In the trace arms the destination is held and answered within the same step;
  in chat a destination named on one turn is answered on the next.

## Held equal, and not

Held equal across arms: the world's own text (the water line and the "water and grass are
safe to stand on" line); the single rule for which cells count as "seen" by the route
hint; and, for focus and sliced, the events that open the maintenance rounds.

Not equal, by construction: chat states the task once and keeps the whole conversation,
so there is no page to take the task off; and chat's route hint answers one step late,
where the trace arms answer within the step.

## What is measured

- **Primary:** errands completed, and errand cells reached (0–3).
- **Secondary, to read the failures:** how long an errand stays on the list; in focus, how
  often the entry in force is an errand rather than a motive the body formed itself; steps
  from the note to the first errand cell; steps survived; malformed replies per arm (every
  arm's reply is grammar-constrained, so "malformed" means a semantic error, not a format
  one); and, in chat and flat, how often the body names a destination.

A per-step cost is also recorded: per model call, the prompt-token count the server saw
and the wall-clock seconds. For chat this is per step; for a trace arm it is the size of
one decision page.

## Models, seeds, and reading

The headline panel runs every arm on one model (Qwen3.5-9B) on a single load, with five
seeds (7, 10, 11, 12, 13), their errand cells, and the same note at step 10. A size ladder
(2B through 35B) repeats the panel across models. Replies are grammar-constrained (one
grammar per round) so that no arm loses on formatting alone.

At five seeds per arm the results show direction, not statistical significance. The
reproduction procedure and the pinned results are in `REPRODUCE.md`.
