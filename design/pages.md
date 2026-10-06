# B. Pages

*Written by the chair (#98b), 2026-09-24, against her five questions and their two
glosses in `focus_experiment_plan.md`, and `interfaces.md` (A). This page says what the
model reads, block by block, round by round, arm by arm. Where a block is the old
line's text, it is quoted from `loop.py` and marked **kept**; where it is new, it is
marked **new** and says why. The independent check reads §6 against the five questions
and reports every mismatch; the chair does not check this page alone. Checks so far:
opus-5, 09-24, `reports/check_B_1_98b.md` (21 items), `check_B_2_98b.md` (14) and
`check_B_3_98b.md` (13), `check_B_4_98b.md` (15) and `check_B_5_98b.md` (9); every item
is answered in this revision or is a decision of §8 she has seen, and the answers that
changed a schema are in A too. The fifth check found no new reading of the questions; the
checks stop here and this page is the build's spec.*

**The two rules this page is built on**, both hers:

1. **The world is on every page.** Window, meters, position, what you stand on, the
   last five history lines. No round
   is blind. History counts as world, including the body's own intent clauses (her trace
   grammar of 09-12 puts them there) and the human's note (the human speaking is the
   world; her cut of 09-22). Neither is list content.
2. **A round's 「只」 is about motivation.** Rounds 1, 1.5 and 2 see the list and its
   manual and may change the list. Rounds 3 and 4 see the one entry in force, no list,
   no manual, and have no way to change anything. flat sees everything in one pass.

## 0. What every page in a trace arm is made of

**Coordinates on a page** are always in the axis the body reads, +y up (A §1.1: `y_shown
= 63 − y_world`); the logs keep the world's +y down. "Shown axis" below means that, and
nothing about the axis reminder line, which rides on every trace page beside the state line
(§5, P6).

**"Step", not "turn", on trace pages.** The old manuals said "turn" for a world step; on a
page that is one of several rounds in a step the word is ambiguous, so the trace-arm
manuals below say "step" wherever the old text said "turn" (marked where it happens).
Chat keeps "turn": there a turn is a step.

**Where the list line sits.** Below the ask or command block and above the state line, on
every page that has one (§0's order). The asks therefore say "the list below", not the
old text's "above".

One user message, no system message, rebuilt from scratch for every round (the old
trace regime's `_open_trace_turn`: the asks are rolled back by never being rendered
again). Blocks are separated by a blank line, in this order, her sketched order from
`trace_context_spec.md` with the most alive things nearest the reply:

```
BACKGROUND            §1   world law, once                                every round
HISTORY               §1   the last 5 trace lines                         every round
CONSOLE MANUAL        §1   how to read the state, the verbs, water        every round
LIST MANUAL           §2   what the list is, the fields, the ops          R1 · R1.5 · R2 · flat
ASK or COMMAND        §3   the round's own question, or the target block + command block
LIST LINE / FOCUS LINE §4  the whole list, or the one entry in force      every round
AXIS LINE             §3.5 the axis, beside the map                       every round
STATE LINE            §5   step current: … respond with …                 every round
```

## 1. The blocks every round carries

### 1.1 Background — **kept**

The old `trace_background` under this line's rules (no monsters, hot ground, rich
vision, no stakes sentence, task off the page):

```
You are a bot player in a survival world. Your human player has gone mining.

The world is 64 by 64 cells. You see the 9 by 9 around you and nothing farther. The clock runs whether you act or not: your drink falls as it runs, drink at 0 drains your health, and health at 0 is death.
```

Nothing about the map task, nothing about water existing (the hot world's law: what
sand does, the world demonstrates), nothing about daylight (no monsters hunt by it).

### 1.2 History — **kept**

The last K = 5 trace lines, oldest first, in her grammar (`trace_action_line`):

```
step 12: you took action "move_right" on "heading for the pickaxe at [42, 23]", and moved to [34, 31].
step 13: you took action "move_right" on "heading for the pickaxe at [42, 23]", and did not move; the cell to your right is tree.
```

The intent clause is the body's own `intent` (trace arms), quoted. The key is required
by every grammar that has it and may be the empty string; an empty intent gets no clause.
On the step the body first stands on an errand cell the result gains a clause (the body
needs a signal that it has the pickaxe, on it): `; you picked up the
pickaxe: it is on you now`; on the return with both, `; you have reached your human player
with the pickaxe and the rope: the errands are done`. The state's `carrying` then lists the
items on every page after (§5). Chat's outcome line carries the same clause. **And the return
cell without both** (#99, 09-24 evening; A §1.3): after the note, every step that ends on the
human's cell with fewer than both items gains `; you are standing where your human player said
to come, but they are stuck down below and will not come up until you bring both: you have the
pickaxe and still need the rope` (or `you have nothing yet and still need the pickaxe and the
rope`; or the rope's form) — on every such step, the way a bump is told on every step, in every
arm alike. Three focus cells of the first panel on the held destination went to the human with
one item and stood there, told nothing, until they died (`registrations/20260924_panel_held_destination_99.md`). The result is the world's sentence (A §1.3). The note is appended
after step 10's own action line, as a line of its own, and counts toward K like any
other (the old rule: "a line like any other and leaves the page with the rest"); so on
step 11's page it is the last line of history, and on step 16's it is gone:

```
step 10: a note from your human player arrived: "Three things: (1) stand on [42, 23], my pickaxe is there; (2) stand on [22, 39], my rope is there; (3) then come to me at [32, 31] with both. I am stuck down here without them. The map can wait for that; I can't."
```

On the first step the block reads
`(nothing has happened yet — this is your first step.)` ("step" for the old "turn", §0). A partial trim says nothing
(the old `--trace-keep 5` behaviour, kept so pages stay comparable). **List changes
never appear here** (A, D3).

### 1.3 Console manual — **kept, one clause removed, "turn" → "step"**

The old `trace_console_manual` with water walkable, the safe line, +y up, rich vision,
no monsters. Two changes: the `mapped` clause loses `count` (the old `--task-off-page`
did the same on trace pages; here chat loses it too, §7), and "turn" reads "step" (§0).
Text:

```
HOW TO USE THIS CONSOLE

Your state comes back at the bottom of this page as one JSON object: step (the clock); daylight (1 noon, 0 deep night); player {pos [x, y] (x 0..63, +x is right; y 0..63, +y is up); facing up/down/left/right — the cell your actions act on; health, drink, each 0..9}; near {up, down, left, right: the cell beside you, by name}; faced (the one you face); standing_on (the cell you are standing ON, by name — the window draws YOU over your own cell, so this is the one cell the window cannot tell you about); carrying (the items you have picked up, by name); window (9 rows of 9 cells around you, top row to bottom row, each row left to right; the centre cell, YOU, is yourself; the first line gives each column's x and every row begins with its own y, so a cell's [x, y] can be read off directly); mapped {here, up, down, left, right: whether that cell is already mapped}; deltas (what changed since your last step).

WINDOW CODES: Wa=water Gr=grass St=stone Pa=path Sa=sand Tr=tree La=lava Co=coal Ir=iron Di=diamond Tb=table Fu=furnace YOU=yourself (the centre cell) Cw=cow Pl=plant Fe=fence ??=none XX=out_of_bounds. Walkable: grass, sand, path, water.

ACTIONS — exactly one per step, by name:
- move_up / move_down / move_left / move_right: one cell that way; into a non-walkable cell it only turns you to face it
- water: a water cell is walkable, like grass or sand — you step INTO it. While you stand in one your drink rises by 1 each step, up to 9. There is no verb to press: being there is drinking.
- water and grass are safe to stand on
- at drink 9 the meter is full; standing in water then changes nothing and costs nothing
- there is nothing to break, pick up or craft here: the four moves are everything you can do

The console does not flatter you and it does not hint. When an action does nothing, the line for that step says plainly what stopped it — "did not move; the cell to your right is tree". That is the world saying what is there, not a verdict on you.
```

The two last ACTIONS lines are new (09-24; the full-meter line after her question whether
the page said anything happens at drink 9 — it had not — and two bodies sat in water at 9
wanting out "to reduce drink level"; the no-craft line after the first show run: the body spent 204 steps
trying to "break through the stone wall", `design/registrations/20260924_show_run_focus_s7_98b.md`);
the old line answered the same class of invention with one sentence. It is on every arm's
page. The legend line is generated from the old `LEGEND` minus the hidden names (zombie,
skeleton, arrow, and the unplaceables) exactly as the old code does; the world piece
owns that list and a test pins the line above. `La=lava` stays in the legend although no
lava exists (the old page had it too; removing it would be a new variable).

## 2. The list manual — R1, R1.5, R2 and flat only — **new wording on her old sentences**

The old `trace_slot_manual` said `motives`, taught `insert/retire/move` by position or
`add/remove/rerank` by name, carried a `rank` field and the `holding:` bookmark. This one
says `list`, teaches `add/edit/delete` by id (A §2), has no rank (the
triad paragraph loses its middle part, and the old focus manual's "not in any order"
sentence comes to every arm), drops the bookmark (#93b: 176 entries formed and 175
retired in 216 steps, every one a bookmark), and since 09-24 evening has the `at` field
(A §2: a field for the position, after a focus cell wrote its errands without
one and lost the pickaxe's cell when the note left history). Text:

```
THE LIST: what it is

An entry is not a note about the world, and not a reminder. It is a thing you keep, and it has two parts: a reason to exist, and a condition under which you stop needing it. Those two parts are what make it one. If you cannot say why a line is there, or what would end it, it is probably not one of these.

THE FIELDS of an entry:
- id — given to it when it is added; you use it to name the entry in an operation.
- name — your own handle for it.
- at — optional: the position it is about, as [x, y] in the same coordinates your own position is given in.
- when — optional: what makes it matter right now.
- until — what would release it. A try that fails is not a release.
- why — optional: one line — what it is for.

The list has no ranking: nothing in it stands over anything else. Entries are shown in the order they were added.

"when", "until" and "why" are in your own words and nothing here reads them: you are the one who decides, each step, whether a condition you wrote has come true.

An entry is a note you left yourself, not an order you have to obey. What you wrote may turn out to be wrong, or impossible in this world, or simply no longer what you want — and if it does, rewrite it. Changing an entry is as ordinary as keeping one.

HOW IT WORKS. The list is held for you. Whenever it is on your page it is exactly as you last left it, and you never write it back yourself. You change it with operations, and only with operations:
  {"op": "add", "name": ..., "at": [x, y], "when": ..., "until": ..., "why": ...}
  {"op": "edit", "id": ..., and any of name, at, when, until, why}
  {"op": "delete", "id": ...}
An entry stays until you delete it. An action that fails, or changes nothing, leaves the list as it was, and the entry is still there the next step.
```

No last line naming the task: the task is an entry (§4), not a sentence.

## 3. The round's own block

### 3.1 focus, R1 — maintain — **new**

Runs once on a gated step (A §4.2: the note landed, an arrival, a drink crossing, which
is drink reaching 0 or health falling, a stall). The events of step N's world step gate
step N+1's asks: the note lands after step 10's world step, so its R1 renders on step 11,
when the note is the last line of history. An arrival counts only once the note has
landed (before it, no errand exists for the body; A §4.2). It also runs on any step where the entry in
force is missing at the start of the acting rounds — before R3 or R4, on every step, whether
or not R3 renders (the list is empty, or R2 defaulted, §3.3) — with the no-focus line from the
table below. **One R1 page per occasion:** on a gated step whose
list is already empty (or focus already missing) when R1 renders, the no-focus line rides
that same page after the gated lines; a second R1, carrying only the no-focus line, renders
only when the gated R1 itself emptied the list. At most two R1 pages a step. It never
renders with an empty event block. An op in the reply that names an id not on the list
makes the whole reply invalid: one retry with the reason, then the round defaults to `no`
and no op is applied (A §3.4). The event lines are the world's, in the body's terms, one per
event that fired, in this order:

| event | line |
|---|---|
| note | `A note from your human player has just arrived. It is the last line of your history above. The note has three numbered steps. Write one entry for each step, in the note's order: three entries.` (the second sentence is the old panel C's `--entry-per-step` line, restored 09-24: a body that merges the three errands into one entry has nothing to release at the first cell and nowhere next to go, `registrations/20260924_the_break_need_and_why_98b.md`) |
| arrival | `You are standing on [42, 23], a cell your human player's note named.` (the cell in the shown axis, §0) |
| drink reached 0 this step | `Your drink has just reached 0.` (**kept**) |
| health fell this step | `Your health has just dropped.` (**kept**; both lines when both happened, drink first) |
| stall | `In the last 8 steps you have not seen a single new cell.` (the number is the manifest's `stall_length`, interpolated) |
| no entry in force, list empty | focus: `The one you were on is gone, and your list is empty.` · sliced: `Your list is empty.` |
| no entry in force, list not empty (R2 defaulted, §3.3) | focus only: `You are on none of your entries.` |

Then:

```
THIS ROUND CHANGES ONLY YOUR LIST. It asks one question and takes no game action.

{event lines}

This round asks about your list, not about this step; the step itself is decided after this, on this same window. Does the list need maintaining? Look at what just happened, at the window and at your own state, and at each entry's "until". If something you now intend has no entry, or an entry's end-condition has come true, or an entry is wrong, then the list needs to change: reply with the operations, exactly as the list's own page describes them. If the list as it stands is what you mean, reply no. Both are whole answers, and no is the usual one.

REPLY with exactly one JSON object and nothing else:
{"why": "<what you looked at, and what you concluded, in one line>", "maintain": "no"}   or   {"why": "<…>", "maintain": "yes", "ops": [<one to five of the operations above>]}
```

**`why` first** (as on R2 and R3): a focus cell wiped its whole list, the map
task included, at its first stall ask and confirmed all four deletions; the body now writes
one line of what it looked at before it answers. The harness reads `maintain` and `ops`.

The grammar admits `why` then `"no"` with no other key, or `why` then `"yes"` with one to
five ops; `"yes"` with `[]` and a sixth op cannot be produced (A §3.1). The last paragraph before REPLY is
the old `STEER_ASK_A`'s question with the old Ask B folded in: her round 1 is one round
(plan, "Round 1's shape"). "no is the usual one" is the old `FOCUS_ASK_ADD`'s sentence,
kept because a question asked at an event invites a change for the sake of answering.

### 3.2 focus, R1.5 — confirm a deletion — **new**

One round per `delete` in R1's reply, in op order; `add` and `edit` have already been
applied when this page renders, so the list line (§4) shows them, and the entry to be
deleted is still there. A confirmed deletion is applied at once, so the next R1.5 page,
if there is one, shows the list without it.

```
THIS ROUND CHANGES ONLY YOUR LIST. It asks one question and takes no game action.

Your last reply deletes this entry:
  {"id": "e2", "name": "...", "when": "...", "until": "...", "why": "..."}
Is that what you mean? An entry deleted is gone, and there is nothing left to read. If its end-condition has come true, or you no longer want it, true. If you would rather keep or rewrite it, false, and it stays as it is.

REPLY with exactly one JSON object and nothing else:
{"delete": true or false}
```

A reply that is invalid twice defaults to `false` (A §3.4): the entry stays, and the next
page's list line shows it.

### 3.3 focus, R2 — choose the one in force — **kept, ids for names**

One rule: **R2 runs after every R1 of a step whenever the list is not empty once R1 and
any R1.5 are done**; on a step with no R1 it does not run. The entry in force goes
missing in two ways: its entry was deleted in R1.5 (R2 follows on the same step), or this
round itself failed twice and had no previous entry to keep (below). At the start of the
acting rounds a missing focus therefore means the list is empty, or R2 defaulted last step. Either way the
plan's "add then choose" runs: R1 with the no-focus line (§3.1), then any R1.5, then this
round if the list is not empty. If the list is still empty, R3 and R4 show `none` (§4) and
`focus_none` is logged with `reason: "empty"`: the body was asked again and added nothing.
The sentence "you have already had this step's chance to add one" is true every time this
page renders.

**Invalid replies.** An id that is not on the list is a semantic error: the page is sent
once more with the reason (A §3.4). If the second reply is invalid too, the entry in force
**stays what it was** when it is still on the list; if there was none, the acting pages
show `none` and `focus_none` is logged with `reason: "r2_defaulted"`, and the next step's
R1 opens with the no-focus line. The harness never picks an entry (A, D6). The old `FOCUS_ASK_CHOOSE`, with `id` where it said
`name`, "below" where it said "above", "step" where it said "turn", and one word in the
header:

```
THIS ROUND CHANGES NOTHING ON YOUR LIST. It asks one question and takes no game action.

{previous line}

Of the entries on your list below, which one has to be done FIRST, from where you stand right now? Not the one that matters most in the end: the one your next steps are for. An entry whose "when" is not yet true is not the one you are on. Say first, in one line, why this one and not the others — what you are carrying, and what each entry's "when" and "until" say — and then its id. An entry that is not on the list is not available here; you have already had this step's chance to add one.

Between now and the next time you are asked, that is the one you are on, and it is the only one you will see when you act.

REPLY with exactly one JSON object and nothing else:
{"why": "<why this one, now, in one line>", "focus": "<an id from the list>"}
```

**"Which one FIRST"**, with the `when` sentence: the question had been
"which one are you ON right now? Not which matters most in the abstract" and four focus cells
of the held-destination panels, why-first and `carrying nothing` on the page, still chose the
delivery entry at the note — R2's `why` in the second panel's focus s7: "my goal is to retrieve
the pickaxe and rope … which matches the conditions for e4 once I'm" — the right reasoning and
the goal's id. Asked for the first thing to do, with its own `when` held against it.
**`why` before `focus`**: six focus cells that day chose the entry in
force at the note, and three of them chose the last entry, `deliver`, with an empty backpack
and their own `when` saying otherwise; those three reached nothing. The body now writes one
line of reason before the id, the way R3 writes `need` before the target; the harness reads
only `focus`, the line goes to `calls.jsonl`. `{previous line}` is one of three: `The one you were on until now: "e1".` when an entry
is in force; `The one you were on until now, "e2", has just been deleted.` when this
step's R1.5 removed it; `You were on none of them.` when there was no entry in force (the list had been empty,
or R2 defaulted).

### 3.4 focus, R3 — the destination — **the old round one, restored, asked as "where are you going"** · *built 09-24 evening (#99) from `registrations/20260924_held_destination_proposal_98b.md`*

**Asked on occasions, not every step.** R3 renders on a step exactly when one of these
holds at its start (A §3.1), and the harness holds its answer between asks the way it
holds the entry in force:

| occasion | when | `{destination line}` |
|---|---|---|
| missing | no destination is held: the first step; the step after a `null` or defaulted answer; the step after a clearing below | no line |
| reached | the body stands on the held destination | `You are standing on your destination, [42, 23], named at step 12.` (and it is no longer held) |
| no way | the route hint's answer for the held destination is its first sentence, `No way there over cells you have seen yet.` | `There is no way over cells you have seen to your destination, [42, 23], named at step 12; it is no longer held.` |
| event | an ask ran this step — the gate opened it (the note, an arrival, a drink crossing, a stall) or the no-focus rule did — and a destination is held | `Your destination until now: [42, 23], named at step 12 — the need you named then: <need>; what it was for: <why>. Keeping it is an answer: name it again. Changing it is an answer too: name another, or null to explore.` |

The line sits between the head and the question, where R2's `{previous line}` sits; on the
missing occasion the ask has no such block. **One occasion a step, the first that holds in the
table's order**: reached before no way before event (a body that steps onto an errand cell it
was heading for opens the arrival's asks on the next step and stands on its destination at
that step's start — the page says reached, the hold is cleared, and the asks that ran do not
make it event as well); missing when nothing is held. **On the event occasion the hold
stands**: naming the held cell again keeps it — its `named at step`, its `need` and its `why`
stay what they were, and the re-affirming reply's own words go to `calls.jsonl` and nowhere
on a page; naming another replaces it; `null` drops it and the step explores. **On the reached
and no-way occasions the hold is already cleared when the question is asked**: whatever the
reply names, the same cell included, is a new choice, with a new row and this step as its
naming step. A reply invalid twice defaults to `target: null` as before (A §3.4): the step
explores (with the second attempt's `need`, the last reply that parsed), a held destination
is dropped, and R3 is asked again next step because none is held. On every other step R4
alone acts, toward the held destination (§3.5).

**Step numbers on these lines** are the world step the naming page decided — the number that
step's own action line carries in history (`step 12: you took action …`), one more than the
`"step"` in the state JSON that page showed (§5). The rows carry the same number (A §4.2).

The event occasion is "an ask ran this step": the gate's four events and the no-focus rule's
asks alike, which is one occasion more than the proposal listed — P11 has the reason.

*Why:* the old question, 「本 step 要對某格子
幹什麼」, asks for this step's cell, so the body answered with a cell this step could
reach: across the day's focus and sliced cells on seed 7, R3 named a target more than two
cells away on 4, 4, 4, 12 and 20 steps out of 216–400, and the one cell that reached two
errand cells named far targets on 145. When a far cell was named, R4 followed the route
hint on 76–94% of the steps it was given. The pathfinder was fine; it was asked, almost
every step, how to reach the cell beside the body. The 27B named far cells unasked; the 9B
lacks the question the 27B did not need — which is the bet: structure buys the small model
the horizon.

The text is the old `ROUND_ONE_ASK` in its far-target wording, her 09-15 design, with two
changes: the far-target sentence points at the entry in force rather than at "somewhere you
wrote down" (list content this page does not carry), and the question asks for a
destination that will be held and walked toward, not this step's cell. **The reply is the
old round one's four keys, in its order: `need`, `candidates`, `target`, `why`** — the key
stays `target`, the grammar is unchanged, and the page says what the key holds.

*History of this block, 09-24.* The morning's B dropped `need` (the entry in force is on
the page) and turned `why` into a free-text `do` for her question 3's 幹什麼; seed 7's
cells then locked in every trace arm, with the body contradicting its own target in that
sentence and R4 obeying it half the time; `do` was cut, leaving a bare cell. Because the
other arms did not lock, the work returned to the
old panel C's pages, rendered with the old code on the same world: the completing arm's
round one wrote a `need` sentence **before** choosing the target and a `why` after, and
both crossed to round two as prose. That is the text the body reasons in before it
commits to a cell; removing it left the 9B choosing coordinates cold. Restored to the
byte (`registrations/20260924_seed7_four_arms_98b.md`; the old panel C completed all
three cells on this seed). The 幹什麼 of her question 3 is `why`, what the target is
for; the 這個 of question 4 is the target.

```
THIS ROUND CHOOSES A DESTINATION, NOT A MOVE.

Where are you going, for the one you are on? Name the position you are heading for — the place where what has to be solved right now gets solved. One may be in your window — the nine by nine cells you can see — or it may be somewhere you have already been, or a position the entry you are on names. A destination is a position in the WORLD, not only one on the screen, and it may be far off the screen: you will be walked toward it one step at a time, and you will not be asked this again until you stand on it, or something happens, or there is no way there over cells you have seen. Choose one as your destination.

A need is not an answer. "I am thirsty, I need water" names the need and stops there; this round ends on a position.
For anything you cannot walk into, the destination is a cell beside it that you can stand on and act from — never the thing itself.
If nothing you can see and nothing you know of helps, send target null. That is the exploring answer, and nothing else means it; you will be asked again next step.

YOUR DESTINATION — reply with exactly one JSON object and nothing else:
{"need": "<what has to be solved now>", "candidates": [[x, y], ...], "target": [x, y] or null, "why": "<what the destination is for>"}
Positions are [x, y] in the same coordinates your own position is given in. "candidates" is at most three — the positions you actually considered, not a survey of the window — and [] when you found none. "target" is the destination you chose, or null.
This round outputs no game action. You are not moving yet: the move is the next round's, on this same window.
```

On the reached, no-way and event occasions the `{destination line}` from the table above
is a block of its own between the first line and the question, so the page reads head,
blank line, the destination line, blank line, "Where are you going …".

The grammar has exactly these four keys and no ops key; it admits zero to three
candidates, so a fourth cannot be produced. With `target: null` the step explores (R4's
null block, §3.5): her exploration branch of 09-15, "a branch, not a shortcut". A reply
that is invalid twice (a position off the map, or a cell in the window the body cannot
stand on, twice) defaults to `target: null` (A §3.4); R4's page then carries the third
shape of the destination block (§3.5), which says the position was refused rather than
that the body chose to explore, and keeps the `need` of a reply that parsed.

**When the entry in force is `none`** (§3.3), two phrases change: "for the one you are on"
is dropped, so the first question reads "Where are you going?", and "or a position the
entry you are on names" is dropped. Nothing else moves.

### 3.5 focus, R4 — the action — **kept, with two changes; every step, toward the held destination**

Runs every step; after R3 on the steps R3 ran (§3.4), alone on the others, which are most
of them. The old `trace_target_line` and the old command block, with one change: the
command block has no ops clause and no ops key (her rounds 3 and 4 never maintain the
list). The axis line, which the old line placed between the two, now sits beside the map at
the foot of every page (§0, P6). The destination block is the old `trace_target_line`: the
destination, the need the body named and what the destination is for, as prose, then
**the bearing line** (the old `--bearing`): the two subtractions between the body and the destination as the keys
that close them, `From where you stand, that position is 8 x move_down and 9 x move_right
away.`; `You are standing on that position.` when they coincide; restored 09-24 after a
body called a cell twenty below it "North" for 300 steps), then the route hint's sentence;
`candidates` does not cross (§3.4). Her question 4 says 上一個回覆, the previous reply, and
the old pages under her two-round design (`design/two_round_turn_brief.md` in the old repo,
§6: "the target is the only field round two consumes") rendered the
target, the need and the why and not the candidates; this page keeps that reading (P7).
Under the hold the "previous reply" is R3's last answer, however many steps ago; its
`need` and `why` ride the block on every step the destination is held. The route sentence
is on this page as the locomotion aid she kept (09-22: "locomotion is not the capability
under test"); it is not motivation.

Destination named this step (R3 ran):
```
THE DESTINATION YOU CHOSE: [42, 23], named this step.
The need you named: <need>
What the destination is for: <why>
From where you stand, that position is 8 x move_down and 9 x move_right away.
The way there, over cells you have seen, begins with move_right.

This is the same window you just read — the same cells, unmoved. Work out what the first step toward that position is. Then give your action. This step goes toward your destination; it is not an exploring step.
```
Destination held from an earlier step (R3 did not run): the first line ends `named at step
12.` instead, and the tail loses its first sentence — "This is the same window you just
read" is true only when a round preceded this one on the step — so it opens `Work out what
the first step toward that position is.`; the four lines between are the same.
Destination kept (R3 ran on the event occasion and named the held cell again): the first
line ends `named at step 12, kept this step.` and the tail keeps its first sentence, a round
having preceded; the four lines between are the destination's own, from the step that named
it (§3.4). So the first line's ending says exactly one of three things — named this step,
named at step N, named at step N and kept this step — and the same-window sentence rides
exactly when R3 ran.
The bearing line drops a term that is zero: `From where you stand, that position is 4 x
move_up away.` when the two cells share an x (the old `--bearing` did the same; a body reads
"0 x move_down" as an instruction). **When the destination is one of the four cells beside the
body, the line goes on to name it as the `near` field does** (#99, 09-25 00:45): `From where you stand, that position is 1 x move_up away: it is the cell
above you, sand.` (`below you` / `to your left` / `to your right`; the material is the state's
`near` entry for that side). Why: over 2,069 vertical steps of the third panel the +y-up page was
followed nine times in ten at two cells' range and two times in three at one cell — the body names
its neighbours by material more than by the bearing, and one wrong reading at range one, being
deterministic, becomes a two-cell orbit of fifty to two hundred steps. Locomotion aid, not
motivation, as the rest of the line.
A reply invalid twice defaults to `noop` (A §3.4): the world waits, the step's history line
reads `waited`, and the page's "One game action is required, every step" stands as the
rule the body is held to, not as what the harness does when it is broken twice.
Destination null (R3 ran and answered null):
```
THE DESTINATION YOU CHOSE: none — you read the window and found no position in it that helps.
The need you named: <need>
What you found: <why>

This is the same window you just read — the same cells, unmoved. Nothing in it is usable, so this step explores: move to bring cells you have not seen into view. Then give your action.
```
R3 defaulted (invalid twice; A §3.4):
```
THE DESTINATION YOU CHOSE: none — the position you named was refused twice, so this step explores.
The need you named: <need>

This is the same window you just read — the same cells, unmoved. No usable position was named, so this step explores: move to bring cells you have not seen into view. Then give your action.
```
(The third shape said "was not on the map, twice" until 09-24 evening; since the morning's
visible-obstacle check a refusal can also be a cell the body cannot stand on, and the page
does not say what is not so.)
The route sentence is one of the route hint's three (A §6), verbatim from the old line:
`No way there over cells you have seen yet.` · `The way there, over cells you have seen,
begins with <verb>.` · `Over cells you have seen, the way toward it begins with <verb>;
past the cells you know, the rest is unseen.` It rides only a chosen target, and not when
the target is the cell the body stands on (nothing to route; the old line printed "No way
there" for that case, which was untrue). Then:
```
YOUR COMMAND — reply with exactly one JSON object and nothing else:
{"action": "<action name>", "intent": "<what you are doing this for, in your own words>"}
One game action is required, every step.
"intent" is yours, in your own words: it is what comes back in the line for this step when you read your own history next step.
```

Her question 4 says 只看得見 slot 和上一個回覆: the entry in force (§4) and R3's answer
(the target block) are the only motivational content; the route sentence is aid, above.
There is no ops key in the command block and none in the grammar.

### 3.6 flat — one round — **kept, assembled; holding its destination since 09-25**

No R1–R4. One page with the list manual (§2), then — on every step a destination is held
— **§3.5's destination block**, and then the command block.

**The hold** (#99, 09-25, experiment E2; A §3.2, A §7 D9): flat holds the cell its reply
names, the way focus holds R3's answer, and the block carries it with its bearing line and
the route sentence until the body stands on it or there is no way there over cells it has
seen. The block is §3.5's, unchanged, in the shape a step that asked nothing renders: the
first line ends `named at step 12.`, the tail opens `Work out what the first step toward
that position is.`, and the same-window sentence is not there (P10: no round preceded this
page). flat has no R3, so three of §3.5's shapes never render on it — "named this step" and
"kept this step", because the reply comes after the page, so a cell named on step 12 first
appears on step 13's page; and the null and defaulted blocks, which say what an asked round
answered. A step holding nothing carries no block at all, and the page is then the flat page
as it was before the hold. `need` and `why` are R3's keys and flat's reply has neither, so
the block's two prose lines are absent with them and it reads: the destination line, the
bearing line, the route sentence, then the tail.

```
YOUR COMMAND — reply with exactly one JSON object and nothing else:
{"action": "<action name>", "intent": "<what you are doing this for, in your own words>", "ops": [<zero to five of the operations above>], "destination": [x, y] or null}
One game action is required, every step. "ops" is part of every reply: send [] when nothing changed. List changes and no list changes are both whole replies.
"destination": the position you are heading for, held for you from step to step and shown above; send null to keep the one you hold (or to name none), send [x, y] to change it or to name one; the way there begins with the move the line above says.
"intent" is yours, in your own words: it is what comes back in the line for this step when you read your own history next step.
```

The ops sentence is the old gbnf-mode wording (`trace_reply_shape`, `gbnf="ops_last"`),
because the reply is grammar-bound (A, D1) and a manual teaching "leave it out" against
a grammar that requires the key would be a confound. The destination paragraph was chat's
`CHAT_ROUTE_LINE` in the trace's voice, which said a destination named now is answered next
step; since the hold it says what the two answers now mean. The key's grammar has not moved
(`coord-or-null`, A §3.2): what changed is that `null` keeps the cell the body holds instead
of naming none for this step.

### 3.7 sliced — R1, R1.5, R3, R4

R1 and R1.5 as focus: the same events, the same empty-list rule (R1 runs on any step
whose list is empty at the start of the acting rounds, once, with sliced's own line from
§3.1's table).
No R2. R3 and R4 as focus — R3 on §3.4's occasions, the destination held between them, R4
every step — with the list line of §4 in its read-only form instead of the focus line. The asks' text is focus's, with these differences and no
others: the empty-list event line (§3.1), and two phrases in R3's ask, "for the one you
are on" reading "for what you keep on your list" and "or a position the entry you are on
names" reading "or a position an entry on your list names". R1.5's text is byte-identical to
focus's; R1's is, except the no-focus line named above.

## 4. The list line and the focus line

One line, just above the axis line (which sits above the state line, §0, §5). Entries render
in the field order the manual teaches, `id` first, `ensure_ascii` off so a name reads here as it reads in history:

| where | line |
|---|---|
| R1, R1.5, R2, flat | `current list: [{"id": "e1", "name": "map_world", "until": "every walkable cell mapped"}, …]` (id order; an entry with a position renders it as `"at": [42, 23]` after its name; wherever an entry renders, on a list line, a focus line or inside R1.5's ask, an optional field the body did not set is absent, never `null`) |
| focus R3, R4 | `the one you are on: {"id": "e2", "name": "…", "when": "…", "until": "…", "why": "…"}` or `the one you are on: none`, in the two cases §3.3 names (the list emptied and, asked once more, nothing added; or R2 invalid twice with nothing to keep), each logged with its reason |
| sliced R3, R4 | `current list (this round you can read it and not change it): [ … ]` |
| chat | no line; chat has no list |

An empty list renders as `current list: []` (and the read-only form the same way); only
focus's acting pages have the word `none`, for the entry in force.

**Dawn.** Every trace arm's list starts with one entry, the old `seed_goals(shape=2)`
without rank: `{"id": "e1", "name": "map_world", "until": "every walkable cell mapped"}`, and
in focus the entry in force starts as `e1` (the old `focus_name`, "seeded at dawn with
the task"). The given task is the human's, not the body's choice; seeding it is the flat
control's definition (architecture §3), and the errand's job is to displace it and then
give it back; the return to the map task is the indicator. The body
may delete it (R1 then R1.5) like any entry.

## 5. The state line — **kept**

The last line of every trace page, the old `trace_state_line` with two words added: `step
current: you are at [x, y], carrying <nothing | the pickaxe | the pickaxe and the rope>, your
state {…}. respond with <clause>.` (seed 10's body chose `deliver_items` with nothing on it). The JSON is the old roomba
`render_frame` plus `standing_on` and `mapped` without `count`, keys sorted:

```
step current: you are at [33, 31], carrying nothing, your state {"carrying": [], "daylight": 0.98, "deltas": {}, "faced": "grass", "mapped": {"down": true, "here": true, "left": true, "right": false, "up": true}, "near": {"down": "grass", "left": "sand", "right": "grass", "up": "tree"}, "player": {"drink": 7, "facing": "right", "health": 9, "pos": [33, 31]}, "standing_on": "grass", "step": 14, "window": ["x=29 30 31 32 33 34 35 36 37", "y=35: Gr Gr Tr Tr Gr Gr Gr Gr Gr", …nine rows, the body's row "y=31: Gr Gr Gr Gr YOU Gr Gr Gr Gr", down to "y=27: …"]}. respond with your command: one game action (required).
```

**The window's labels** (the frame's own window is
unlabelled): the first string is `x=` and the nine columns' shown x; each row begins with its
shown y, the top row the largest. A body dying of thirst four cells from water had read the
water's cell as `[37, 48]` from an unlabelled window and walked the other way.

The `"step"` in the state JSON is the frame's: the page that decides world step N renders
frame N−1 and says `"step": N-1` (A §1.3; the history lines above it are numbered by the
step acted, so step 11's page ends with `step 10: …` in history and `"step": 10` here).

**On a retry** (A §3.4) the page is the same page with one more block after the state
line, separated by a blank line: `your last reply was not accepted: <reason>; reply with
one JSON object`. The reason is one plain sentence naming what failed (an id not on the
list and the ids that are; a position outside 0..63; a verb not among the four).

**The axis line** (`Remember: +y is up and -y is down. To reach a cell with a LARGER y than yours, press move_up; a SMALLER y, move_down. +x is right, -x is left.`) is the block immediately above this one on every trace page.

The clause, per round:

| round | clause |
|---|---|
| R1 | `respond with: no, or your operations on the list.` |
| R1.5 | `respond with your confirmation: true or false.` |
| R2 | `respond with your choice: an id from the list.` |
| R3 | `respond with your target: one position, or null.` |
| R4 | `respond with your command: one game action (required).` |
| flat | `respond with your command: one game action (required); list changes ([] when none); a destination (null keeps the one you hold).` (the last clause read `(null when none)` until 09-25; under the hold `null` keeps what is held, §3.6, and a page does not say two things) |

## 6. Her five questions, traced

The table is the **focus** arm. sliced differs by definition (plan, "Arms") in having no
R2 and the whole list, read-only, on R3 and R4 where focus has the one entry; and in the
three wording consequences §3.7 lists. Its rows 1 and 1.5 are focus's.

| her question | round | what the page shows that is motivation | what it does not show | the reply | where on the page |
|---|---|---|---|---|---|
| 1 要不要maintain motivation slots | R1 | the whole list, the list manual, the event | — | one line of `why`, then `no` or `yes` + ops | §3.1, §2, §4 |
| 1.5 確定要刪除嗎？ | R1.5 | the whole list, the manual, the entry to be deleted | — | `true`/`false` | §3.2, §2, §4 |
| 2 選擇目前focus的slot | R2 | the whole list, the manual, the previous focus | — | one line of `why`, then an id | §3.3, §2, §4 |
| 3 （只看得見slot了）… 決定本step要對某格子幹什麼 | R3 | the one entry in force; the destination line of the occasion (the held one at an event; the one just reached or found unreachable) | the list, the manual, any ops | `need`, `candidates`, `target`, `why` — the destination, held until it is reached, unreachable, dropped by a `null` or a default, or replaced at an event | §3.4, §4 |
| 4 （只看得見slot和上一個回覆）… 輸出遊戲ops | R4 | the one entry in force, R3's last answer (the held destination with its `need` and `why`) | the list, the manual, any ops key | `action`, `intent` | §3.5, §4 |

Also on R4, and not motivation: the route sentence, her locomotion exception (§3.5).
R4 runs every step; R3 on §3.4's occasions (09-24 evening: the question 「本 step 要對某格子
幹什麼」 asked every step got the cell beside the body every step; asked as "where are you
going" and held, it is her question 3 with a horizon); R1, R1.5 and R2 run as §3.1–§3.3 say.

This holds on every row: the background, history, console manual and state line
are on every page (§1, §5). History is world by rule 1: the body's earlier intent clauses
and, for five steps, the note's line are on acting pages too (P8, §8); the
"what it does not show" column is about the list, the manual and ops. Her second settled point holds on row 1: one round, `no` a
first-class answer with its own shape.

**Checker: what to verify on this page and on rendered pages.**
1. focus: R3 and R4 pages contain no `current list:` line, no `THE LIST` manual, no `"op"`.
2. R4's command block and grammar have no key but `action` and `intent`; R3's grammar
   has no key but `need`, `candidates`, `target`, `why`.
3. R1, R1.5, R2 pages contain the manual and the whole list.
4. Every trace-arm page contains the background, a history block, the console manual
   and a `step current:` line with `window`, `player`, `standing_on`; every chat turn, as
   sent on its own step, contains the state JSON with the same three keys (trimming later
   replaces `window` in old turns with `(omitted)`, §7).
5. focus: `the one you are on:` appears on R3 and R4 pages and on no other page.
6. The asks of R1, R1.5, R2 leave no trace line and no conversation.
7. The note's line is byte-identical across arms on the step it shows.
8. flat's page carries the list manual and the whole list (as R1 does) and the axis
   line and a command block (as R4 does), and no event line and no ask. It carries
   §3.5's destination block, in its held shape — first line `named at step N.`, no
   "This is the same window you just read" — on exactly the steps that start with a
   destination held, and no block on the steps that do not; never the "named this step",
   "kept this step", null or defaulted shapes, which belong to a step that asked (§3.6).
9. focus and sliced: R4 runs on every step; R3 runs on a step exactly when §3.4's table
   says (no destination held at its start; the body standing on the held one; the route
   hint's first sentence for it; an ask ran this step), and on no other; R2 never renders
   on a step where R1 did not.
10. sliced: R3 and R4 pages carry the read-only list line and no `THE LIST` manual and no
    `"op"`; their grammars are focus's R3 and R4 grammars.
11. focus and sliced: on a step where R3 did not run, R4's destination block ends its first
    line `named at step N.` and does not say "This is the same window you just read"; on a
    step where it did and a destination is held after it, the first line ends `named this
    step.` (a new choice) or `named at step N, kept this step.` (the held cell named again)
    and the tail opens with that sentence; the null and defaulted forms render only on a
    step where R3 ran. An R3 page on the event occasion carries the held destination's
    line; on the reached and no-way occasions, theirs; on the missing occasion, none. One
    occasion a step, in the table's order.

## 7. Chat — arm O as built, three lines changed

**System message**, once, the old `roomba_system_prompt(task=map_world, places="none",
water_walkable, y_up, route_hint)`, with `count` removed from the mapped clause:

```
You are a bot player in a survival world. Your human player has gone mining and has left you to map the surface — every cell you can walk on. They are waiting for the map.

Each turn you get one line saying what your last action did, then your state as JSON: step (the clock; drink falls as it runs; drink at 0 drains health; health 0 is death); daylight (1 noon, 0 deep night); player {pos [x, y] in a world of 64 by 64 cells (x 0..63, +x is right; y 0..63, +y is up); facing up/down/left/right — the cell your actions act on; health, drink, each 0..9}; near {up, down, left, right: the cell beside you, by name}; faced (the one you face); standing_on (the cell you are standing ON, by name — the window draws YOU over your own cell, so this is the one cell the window cannot tell you about); carrying (the items you have picked up, by name); window (9 rows of 9 cells around you, top row to bottom row, each row left to right; the centre cell, YOU, is yourself; the first line gives each column's x and every row begins with its own y, so a cell's [x, y] can be read off directly); mapped {here, up, down, left, right: whether that cell is already mapped}; deltas (what changed since your last turn).

WINDOW CODES: Wa=water Gr=grass St=stone Pa=path Sa=sand Tr=tree La=lava Co=coal Ir=iron Di=diamond Tb=table Fu=furnace YOU=yourself (the centre cell) Cw=cow Pl=plant Fe=fence ??=none XX=out_of_bounds. Walkable: grass, sand, path, water.

ACTIONS (exactly one per turn, by name):
- move_up / move_down / move_left / move_right: one cell that way; into a non-walkable cell it only turns you to face it
- water: a water cell is walkable, like grass or sand — you step INTO it. While you stand in one your drink rises by 1 each step, up to 9. There is no verb to press: being there is drinking.
- water and grass are safe to stand on
- at drink 9 the meter is full; standing in water then changes nothing and costs nothing
- there is nothing to break, pick up or craft here: the four moves are everything you can do

ROUTE (optional): add "destination": [x, y] to your reply, and the next turn tells you which move the way there begins with, over cells you have seen.

REPLY with exactly one JSON object and nothing else:
{"action": "<action name>", "why": "<= 15 words", "destination": [x, y] or null}
```

The three changes against arm O as built: the safe line (plan, "Held equal"; arm O
never had it), `count` gone from `mapped` (§1.3's reason: no progress meter on any
arm's page), and `destination` printed in the reply shape (the grammar requires the
key; `null` is the usual value).

**User turn**, one per step, the old `user_message` order:

```
outcome of your last action: moved to [33, 31]                 ← the outcome of the last step; absent on turn 1
step 10: a note from your human player arrived: "…"          ← the step after the note lands, once
The way there, over cells you have seen, begins with move_right.   ← if the last reply named a destination
you are carrying nothing.                                       ← or: you are carrying the pickaxe.
Remember: +y is up and -y is down. To reach a cell with a LARGER y than yours, press move_up; a SMALLER y, move_down. +x is right, -x is left.
{"daylight": …, "deltas": …, "faced": …, "mapped": {…no count…}, "near": …, "player": …, "standing_on": …, "step": …, "window": […]}
```

The conversation is kept whole. When it passes 90,000 tokens, the oldest turns' `window`
fields become `(omitted)` first, never the system message and never the newest 20
turns; then whole old turns are dropped (`conversation_trimmed`). The note's line is the
trace's to the byte, `step 10:` prefix included.

## 8. Decisions made on this page, with reasons (hers to strike)

- **P1. The map task stays, off the page, as the seeded entry.** The note says 「The map
  can wait for that; I can't」: the errand is an interruption of a standing task, and
  without the task there is nothing to interrupt. This is what the old `--task-off-page`
  did and what the plan means by "the task lives only in the list".
- **P2. No progress meter on any page**: `mapped.count` is gone from trace and chat
  alike. The old trace pages dropped it; arm O as built still showed it every turn,
  because chat ignored the flag. A meter is what round fourteen's body promoted to rank
  1 on its own.
- **P3. The `holding:` bookmark is not taught.** #93b's count.
- **P4. Retired 09-24: no rank in any arm.** The chair had kept it for one
  manual across arms; the digit was never meaningful to the model. The manual is
  still one for all arms, without it.
- **P5. R2 runs on every gated step**, not only when the focus is missing. An event is
  when a body might switch what it is on; asking only on loss would make the seeded task
  the focus until the body deletes it.
- **P7. R4 shows `target`, `need` and `why`, not `candidates`.** Her question 4 grants the previous
  reply; the old pages under her 09-15 two-round design showed the target and its
  reasons and not the candidate list, and the candidates are the positions considered,
  not the decision. If she wants the whole reply on R4, it is one line.
- **P8. History is world, and the note's line is history.** The body's intent clauses
  and the human's note ride the history lines onto every page, acting pages included
  (rule 1 above). They are what happened, in her trace grammar; the list is what is held.
  For
  steps 11–15 the acting pages show the errands through the note's line, beside the one
  entry in force, in every trace arm alike.
- **P6. Retired 09-24:** the axis line sits immediately above the state line, the
  block that carries the window, on every trace page; in chat it is already the line above
  the state JSON.** The chair had kept it to R4's command block as the old line did; a body
  sat in a lake for 300 steps calling a cell twenty below it "North" on R3's page, where the
  axis was stated only inside the console manual.
- **P9. The held destination rides R3 (the occasion's line: the held one at an event, the one
  just reached or found unreachable) and R4, and no ask page** (#99, 09-24 evening). It is neither world nor list: rule 1 puts
  the world on every page and rule 2 confines the list to the asks; the destination is the
  body's own acting-level choice, and the proposal says "written to the page every step",
  which R4 does. The ask pages stay byte-for-byte what the five checks read, so the hold
  changes one thing on the pages it touches and nothing on the others.
- **P10. R4's tail says "the same window you just read" only when a round preceded it on
  the step** (#99). On a held step R4 is the first page the body reads; the sentence would
  be false, and the page does not say what is not so.
- **P11. The no-focus rule's asks are an event occasion too** (#99; the proposal's list had
  the gate's four events and "only when"). Those asks run exactly when the entry in force
  went missing without a gate — the list emptied, or R2 defaulted — and end with R2 choosing
  again; a destination chosen under the entry that is gone was chosen for it, and the body
  should be asked where it is going now that it is on something else. So the rule is one
  sentence, "an ask ran this step", rather than two lists that agree except there.