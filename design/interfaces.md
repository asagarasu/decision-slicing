# A. Interfaces

*Written by the chair (#98b, fable 5.1), 2026-09-24, from the plan
(`focus_experiment_plan.md`) and the old repo's design pages
(`coordinates.md`, `trace_context_spec.md`, `two_round_turn_brief.md`,
`steering_by_isolated_questions_brief.md`, `bare_arms_brief_97.md`,
`telemetry_frame_schema.json`). Everything in wave one and wave two is built against
this page and `pages.md`. Decisions not fixed by the plan are made here and listed in §7 with their reason. Facts
about the old world were read off the old code (a sonnet scout's map with file:line,
then the chair's own reading of the cited lines) on 09-24 before this page was closed.*

## 0. Words

- **cell**: one run, one arm × one seed × N steps. (The old line said battery.)
- **step**: one world step. Exactly one game action advances the world.
- **round**: one model call inside a step. R1, R1.5, R2 are **asks**; R3 and R4 are the
  **acting rounds**. flat and chat have one round per step.
- **page**: the whole text sent to the model for one round (trace arms), or the new user
  turn (chat). `pages.md` owns their contents; this page owns what they are built from.
- **list**: the motivation list the body keeps. **entry**: one item in it. **focus**: the
  entry in force. The old line said slots and motives; the wire word here is `list`.
- **history**: the trace lines a trace-arm page shows, the last K = 5 steps.

## 1. The world, and the state the pages read

### 1.1 The world

Vendored Crafter, the same pin as the old repo (danijar/crafter@e04542a2 + PR #32), 64×64,
a 9×9 window centred on the body. This line's rules are fixed in code, not flags:

| rule | behaviour |
|---|---|
| water is walkable | the body may step onto water; while it stands on water its drink rises by 1 each step, up to 9; there is no `drink` verb (old: `pin_water_walkable`, re-applied before every step because `respawn` builds a fresh player) |
| hot sand | a step that **ends** on sand costs 1 drink, charged once, after the step and before the frame is logged; if the meter was already 0 nothing falls and the outcome says so (old: `accrue_hot_ground`) |
| lava swept | every lava cell becomes **stone** at the first step, one pass (seed 7: 40 cells); stone is non-walkable as lava was, so the walkable census does not move (old: `sweep_lava`) |
| food and energy pinned | inventory `food` and `energy` set to 9 and the hidden hunger and fatigue counters to 0 before every world step; never shown, never named |
| no monsters | every Zombie, Skeleton and Arrow object is removed from the world before the first step (seed 7: 15 zombies, 5 skeletons); cows stay (old: `remove_monsters`) |
| verbs | `move_left`, `move_right`, `move_up`, `move_down`. Nothing else. The old roomba had `drink`, stripped under water-walkable; `noop` exists only inside the harness, for a defaulted reply, and its outcome reads `waited`. **A body that wants to stay in water has to keep moving inside it or bump.** That is the old world's behaviour and the identity test keeps it |

Only three things vary between cells: the **arm**, the **seed**, and the **step budget**.

**Where the meters start** (settled 09-24 on the world builder's question): the old
record's `{"drink": 3, "food": 5}` before the pins, so drink starts at 3 and food is pinned
to 9 a moment later. Every finished battery ran this; the vendor's own 9 would make the
first hundred steps a different world. **The seen set** starts with the spawn's own 9×9 at
reset, as the old `_log_frame` marked frame 0. **The hot-ground charge and the frame** (settled 09-24): the
old code extracted the frame before charging, so its logged frames showed a sand charge one
step late while the outcome sentence named it at once (measured by the world builder). Here
the charge runs between the env step and the frame, so the frame shows the fall; the
identity test compares drink against the old repo's live meter, positions and windows to
the byte.

**Seeds and errands.** The five panel seeds and their errand cells, world axis, as the
old drivers carry them (`generated/run_arm_o_98.sh`, `errands_for`), spawn is [32, 32]:

| seed | visit 1 | visit 2 | return |
|---|---|---|---|
| 7 | [42, 40] | [22, 24] | [32, 32] |
| 10 | [42, 44] | [14, 30] | [32, 32] |
| 11 | [47, 40] | [16, 25] | [32, 32] |
| 12 | [36, 51] | [19, 22] | [32, 32] |
| 13 | [48, 38] | [18, 28] | [32, 32] |

The note lands at **step 10** as one history line, its text the old
`errand_note(stakes=True, steps=True)` to the byte, coordinates in the shown axis:

    step 10: a note from your human player arrived: "Three things: (1) stand on [42, 23], my pickaxe is there; (2) stand on [22, 39], my rope is there; (3) then come to me at [32, 31] with both. I am stuck down here without them. The map can wait for that; I can't."

(the numbers above are seed 7's cells, shown-axis). **Arrival** = the body's position
equals an errand cell; visits count in any order, each once; the return counts only
after both visits. **Errands completed** = the return reached. The arrival ledger is
`events.jsonl` (§4.2); the reader re-derives it from positions in `frames.jsonl` as a
check, never instead (the old `errands_read.py` rule).

**Identity.** Same seed, same action sequence → same positions, meters and window as
the old repo, step for step. This is a test in the world piece: a scripted policy run
through both repos, frames compared. It is what makes the old repo the answer key.

**Coordinates** (`coordinates.md`). Stored **+y down**, the world's
own frame, in every log. Shown **+y up** to the model: `y_shown = 63 − y_world`, x
unchanged. The map is an involution, so a coordinate the model writes is read back
with the same function. Direction words (`left/right/up/down`, `facing`) are screen
relative and carry no sign.

### 1.2 The frame: the world's own record of a step

One frame per step, after the step, plus frame 0 after reset. It is the old telemetry
frame schema **verbatim** (`telemetry_frame_schema.json`, `schema_version` "1": `step`,
`daylight`, `player{pos, facing, sleeping, health, food, drink, energy}`, `inventory`,
`window` 9×9 of cell names, `achievements`, `deltas`) **plus one field**:

| added | type | meaning |
|---|---|---|
| `standing_on` | cell name | the material under the body, which the window cannot show because its centre is `player` |

That makes it `schema_version` "2". Nothing else moves. The old schema's tests come with
it.

### 1.3 State: what a page is built from

A page never reads the frame directly. It reads a `State`, built once per step by the
controller and handed to every round of that step unchanged in its **world half** (frame,
window, meters, history: "the same cells, unmoved"); the **list half** (entries, entry in
force) is read from the store at each round, so R1.5 shows R1's adds and R2 shows R1.5's
deletions (settled 09-24 on the trace builder's question). The fields, and which arms and rounds see them, are:

| field | from | flat | chat | focus R1/1.5/2 | focus R3 | focus R4 | sliced R3/R4 |
|---|---|---|---|---|---|---|---|
| `step` | frame | ● | ● | ● | ● | ● | ● |
| `pos` (shown axis) | frame | ● | ● | ● | ● | ● | ● |
| `facing` (word) | frame | ● | ● | ● | ● | ● | ● |
| `standing_on` | frame | ● | ● | ● | ● | ● | ● |
| `health`, `drink` | frame | ● | ● | ● | ● | ● | ● |
| `window` (9 rows of names) | frame | ● | ● | ● | ● | ● | ● |
| `mapped` {here, up, down, left, right} (booleans; no count) | seen set | ● | ● | ● | ● | ● | ● |
| `carrying` (the errand items picked up so far, in order) | world | ● | ● | ● | ● | ● | ● |
| `history` (K = 5 trace lines) | trace | ● | — (chat keeps its own turns) | ● | ● | ● | ● |
| `note` (once, at step 10) | world | as a trace line | as part of the step-11 turn | as a trace line | ↑ | ↑ | ↑ |
| `list` (all entries) | list store | ● + manual | — | ● + manual | — | — | ● read-only, no manual |
| `focus` (one entry) | list store | — | — | R2: the previous one, by id | ● | ● | — |
| `r3_reply` (R3's last answer: under the hold, the destination's `need` and `why`, however many steps ago; on an exploring step, this step's reply's) | R3 | — | — | — | — | ● | R4 only |
| `route` (one sentence) | route hint | ● the held destination | answers last step's `destination` | — | — | ● the held destination | R4 only |
| `destination` (the held cell, world axis; the step it was named on; the `need` and `why` of the reply that named it) | trace controller (§3.1, the hold; §3.2 in flat) | ● the destination block, when one is held | — | — | ● as the occasion's line, when one is held | ● the destination block | R3 / R4 as focus |
| the axis line | text | ● | ● every turn | ● | ● | ● | ● |
| the bearing line (two subtractions to the destination) | page | ● under the destination | — | — | — | ● under the destination | R4 only |

`food`, `energy`, `inventory`, `achievements` are never on any page; `daylight` is in
the state JSON as the old renderer had it. There is no task sentence on a trace page and
no progress count anywhere: the given task is the seeded list entry (§2), the errands
reach the body only through the note.

**The trace line** (history grammar, from `trace_context_spec.md`), one per world step:

    step N: you took action "<verb>" on "<the model's own intent>", and <honest result>.

**Numbering.** The world step that produces frame N is step N; its action line reads
`step N: …`, the note's line reads `step 10:` and is appended after frame 10's action line
(the old line numbered by the clock before the step; this line numbers by the frame, and
the controller must agree with the world).
Honest results are the old `outcome()` sentences, kept to the byte:
`moved to [x, y]` · `did not move; the cell to your left is tree` (above you / below
you / to your left / to your right; the material by name) · `waited` (a defaulted
reply) · with `; the ground here is hot, drink fell 1` or `; the ground here is hot,
but your drink is already empty, so nothing fell` appended when the step ended on sand.
The note is one extra line appended after step 10's action line, the same bytes in every
arm, and it counts toward K like any line. **Arrival is told** (the body needs a signal that it has the pickaxe, on it): the result of the step that first stands
on a visit cell gains `; you picked up the <item>: it is on you now`, and the return's,
once both are carried, `; you have reached your human player with the pickaxe and the
rope: the errands are done`; from the pickup on, the state's `carrying` names the items.
**Standing where the human said to come without both is told too** (#99, 09-24 evening, the
other half of that signal: three focus cells of the first panel stood on the return cell with
one item, told nothing, until they died): after the note has landed (not on the step it
lands) and until the errands are done, every step that ends on the return cell with fewer
than both items gains `; you are standing where your human player said to come, but they are
stuck down below and will not come up until you bring both: you have the pickaxe and still
need the rope` (`you have nothing yet and still need the pickaxe and the rope` with an empty
backpack; `you have the rope and still need the pickaxe` the other way round). It repeats on
every such step, as `did not move` repeats on every bump; it is the world's sentence, in every
arm, chat's outcome line included. **List changes are not history** in any arm
(§7, D3). Intent for the line comes from `intent` (trace arms)
or `why` (chat).

## 2. The list entry

The harness holds the list. The model changes it only through ops, and never re-emits
it. Fields are the old line's v2 set without rank (a reason to exist, and a condition
under which it stops), plus an id.

| field | type | set by | meaning |
|---|---|---|---|
| `id` | `"e1"`, `"e2"`, … | harness, on add; never reused in a run | how R1.5 and R2 name an entry |
| `name` | text ≤ 80 chars | model | what it is |
| `at` | `[x, y]`, shown axis, inside the world, optional | model | the position it is about, if it has one (#99, 09-24 evening — the second panel's focus s7 wrote `when: "human needs pickaxe"` and, once the note left history, no page in the focus arm said where the pickaxe was; the completing sliced cell had written "human needs pickaxe at [42, 23]". A field makes the position a thing the body fills rather than a thing it may or may not mention, and the acting pages then carry it) |
| `when` | text ≤ 160 chars, optional | model | a trigger, if it has one |
| `until` | text ≤ 160 chars | model | the condition under which it is no longer needed |
| `why` | text ≤ 160 chars, optional | model | the reason it exists |

**No `rank`** (the one-digit integer was never meaningful to the model, and in focus the choice is R2's). The list is a set with
stable ids; on the page entries render in id order. This is also the wire order of the
fields (the old `RULE_KEYS` minus rank, id first, `at` after `name`). **Dawn:** every trace arm's list starts
as `[{"id": "e1", "name": "map_world", "until": "every walkable cell mapped"}]`, the old
`seed_goals(shape=2)` without its rank, and focus's entry in force starts as `e1`
(`pages.md` §4). The task stays because the return is the indicator the reader measures (§4.4).

**Limits.** No cap on the list's length; the old line had none and the bodies never
needed one. A reply carries at most 5 ops (the grammar). Field lengths are enforced by
the grammar, not by truncation.

**Ops** (the whole language of change):

```
{"op": "add",    "name": …, "at"?: [x, y], "when"?: …, "until": …, "why"?: …}
{"op": "edit",   "id": "e3", "name"?: …, "at"?: [x, y], "when"?: …, "until"?: …, "why"?: …}
{"op": "delete", "id": "e3"}
```

An `edit` names at least one field (the grammar requires it; an edit that names none
would change nothing). In **focus** and **sliced**, every `delete` is held until R1.5 confirms it (one R1.5 per
delete, in op order); `add` and `edit` apply at once. In **flat** there is no R1.5:
ops apply as written (§7, D5). Ops are applied in order; an `edit` or `delete` may only
name an id that existed before this reply; a second `delete` of the same id in one reply is
dropped (one R1.5 per entry).

**The focus** (focus arm only) is an id or `none`. R2 sets it, on every gated step whose
list is not empty after R1 and R1.5. It persists across steps until its entry is deleted;
an `edit` leaves it in force. Missing at the start of the acting rounds (checked every step, before R3 or R4) means the
list is empty, or R2 defaulted last step with nothing to keep; then R1 runs with the no-focus event line (the
plan's "add then choose"), then any R1.5, then R2 if the list is not empty; if it is still
empty, R3 and R4 render `none` and `focus_none` is logged (`reason`: `empty` or
`r2_defaulted`). At most two R1 pages a step (`pages.md` §3.1). **Nothing in the harness
ever chooses an entry.**

## 3. The reply schema for each round

Every round's reply is **grammar-constrained** (GBNF, one grammar per round, generated
from the schemas below and stored with the code; §7, D1). So a reply is always the right
shape, and "malformed" means semantically wrong: an id that does not exist, a target
off the map. Free-text fields are bounded in length by the grammar. Coordinates are in
the **shown** axis. R3's target and flat's and chat's destination may be **any cell of
the world**, not only one in the window: the errand cells are far, and the old panels
ran `--far-target` for the same reason.

### 3.1 focus (and sliced, without R2)

| round | question (B has the wording) | reply |
|---|---|---|
| **R1** maintain | 要不要 maintain | `{"why": …, "maintain": "no"}` **or** `{"why": …, "maintain": "yes", "ops": [op, …]}` (1–5 ops); one line of reason first, the harness reads the rest |
| **R1.5** confirm | 確定要刪除嗎 (the entry shown) | `{"delete": true}` or `{"delete": false}` |
| **R2** focus | 選擇目前 focus 的 slot — asked as "which one has to be done first, from where you stand" (four focus cells had chosen the delivery entry with an empty backpack) | `{"why": …, "focus": "e3"}` — one line of reason first, then the id; the harness reads only `focus` |
| **R3** destination | 為了達成這個目的，結合情況決定本 step 要對某格子幹什麼 — asked as "where are you going", on occasions (below) | `{"need": …, "candidates": [[x,y], …] (0–3), "target": [x,y] or null, "why": …}` (the old round one, to the key; `target` is the destination) |
| **R4** act | 為了幹這個，輸出遊戲 ops — every step, toward the held destination | `{"action": <verb>, "intent": …}` (`intent` required, may be `""`) |

**The hold (09-24 evening, #99, from `registrations/20260924_held_destination_proposal_98b.md`).**
The trace controller holds R3's answer — the cell (world axis), the step it was named on,
and the reply's `need` and `why` — between asks, as it holds the entry in force. R3 renders
on a step exactly when, at its start: no destination is held (**missing**: the first step,
the step after a `null` or defaulted answer, the step after a clearing); the body stands on
the held cell (**reached**: `destination_reached` is written and the hold cleared); the
route hint's answer for the held cell is its first sentence (**no way**: `destination_cleared`
with reason `no_way`, the hold cleared); or an ask ran this step (**event**: the gate or the
no-focus rule, §7 D11; the hold stands and the page shows it). One occasion a step, the first
that holds in that order (reached, no way, event; missing when nothing is held). At an event,
naming the held cell again keeps it — its step, its `need` and its `why`; naming another
writes `destination_cleared` (`replaced`) then `destination_chosen`; `null`, or a default,
writes `destination_cleared` (`dropped`) when one was held, and the step explores. After
reached or no way nothing is held, so any cell named is a new choice with a new row. On both
end rows `held_steps` is this step minus the naming step: the steps whose R4 walked toward it
(a reached destination named at 12 and stood on at the start of 20 was walked on 12–19,
eight steps; one replaced or dropped at 20's R3 the same). R4 runs every step; on the steps R3
did not run it is the step's only acting call. `pages.md` §3.4 has the lines and §3.5 the
block.

R3's shape is her two-round design (`two_round_turn_brief.md` §6) **to the key**: `need`
(what has to be solved now) before the decision, `candidates` capped at three, `target`,
and `why` (what the target is for) after. On 09-24 the chair first dropped `need` and
replaced `why` with a free-text `do`, then dropped `do` too; seed 7's cells locked in every
trace arm, and the old panel C's pages, rendered with the old code on the same world,
showed what the completing arm had that ours did not: the sentence the body writes before
it commits to a cell (`registrations/20260924_seed7_four_arms_98b.md`). Restored. `target:
null` is the exploration branch and the only thing that licenses R4 to explore. R1's
`ops` is one to five; `"yes"` with `[]` is not in the grammar. **Built 09-24 evening (#99, `registrations/20260924_held_destination_proposal_98b.md`):** R3 is asked only when a destination is missing or an event re-opens it; the destination is held by the harness and written to R4's page every step; R4 every step is the next step toward it (the hold, above). **Neither R3's nor R4's grammar has an `ops` field.** The parser has no path
from the acting rounds to the list; if a future grammar ever admits one,
`ops_in_acting_reply` fires and nothing is applied (§4.2).

### 3.2 flat

One reply per step:

```
{"action": <verb>, "intent": …, "ops": [op, …] or [], "destination": [x,y] or null}
```

`ops` is zero to five, `[]` when nothing changed.

**flat holds its destination** (#99, 09-25; experiment E2, D9 rewritten). `destination` is
the cell the body is heading for, and the harness holds it from step to step as it holds
focus's (§3.1, "the hold"): it rides every page with its bearing line and its route
sentence until the body stands on it (`destination_reached`, the hold cleared) or the route
hint has no first step for it at a step's start (`destination_cleared`, `no_way`). `[x, y]`
names one — the cell already held is **kept**, with the step it was named on; another
**replaces** it. **`null` keeps what is held**, and names none when none is held; a reply
refused twice keeps it too (§3.4). flat has no R3 and therefore no occasion that re-opens
the question: its one reply is the question, every step, and no `dropped` is ever written
for it.

**The route sentence is no longer answered one step late** (the departure from this page's
older rule, which chat keeps: plan, "Not equal, by construction"). flat's page now carries
the destination it holds, so the sentence on it is the way to **that** cell from where the
body stands now, computed for this page as R4's is, and the `route` row is stamped with the
step whose page carried it. What stays one step late is only the naming: the reply comes
after the page, so a cell named at step N first appears on step N+1's page as `named at step
N`, and step N+1 is the first step walked toward it. `held_steps` on the end rows is this
step minus the naming step, the same arithmetic as focus's, and therefore counts the naming
step, which in flat was walked under the previous hold or under none.

### 3.3 chat (arm O as built)

```
{"action": <verb>, "why": …, "destination": [x,y] or null}
```

The system message once; one user turn per step; the whole conversation kept, trimmed
oldest-first only if it passes the budget in the manifest. `destination` answered on the
next turn.

### 3.4 Semantic validation, retry, default

After parse, each round checks what the grammar cannot: ids exist (`edit`, `delete`,
R2), coordinates are inside 0..63 (R3, `destination`, an entry's `at`), and, for R3 only, **a target the
body can see is a cell it can stand on**: a target inside the window whose material is not
walkable (grass, sand, path, water) is refused with the reason (`[33, 26] is stone; you
cannot stand on it — name a cell you can stand on, or a cell beside it`). This enforces the
rule R3's page states (her 09-15: never the thing itself) using only what the body can see;
an unseen target is not judged. Added 09-24 after the first show run
(`registrations/20260924_show_run_focus_s7_98b.md`: 204 steps into a stone cell). On the
first failure the same page is sent again with **one reason line** appended after a blank
line, the old line's own words, `your last reply was not accepted: <reason>; reply with
one JSON object`, and
`reply_invalid` is logged with `attempt` 1; a second failure logs `reply_invalid` with
`attempt` 2 and the round **defaults**, with `reply_defaulted` logged (so `invalid_replies`
in the summary counts every refused reply, not every refused first reply):

| round | default |
|---|---|
| R1 | `"no"` |
| R1.5 | `false` (nothing deleted) |
| R2 | the previous entry in force if it is still on the list; else `none` (the harness does not pick) |
| R3 | `target: null` — the step explores; a held destination is dropped (`destination_cleared`, `dropped`), and R3 is asked again next step |
| R4, flat, chat | `noop`; a flat reply's ops are dropped. **A held destination stays held** in flat: `null` is that reply's own way of keeping it (§3.2), so a reply nobody could read keeps it too, the way R2's default keeps what was in force. D10's rule is R3's, where `null` means the opposite |

`"destination": null` and `"target": null` are valid answers and never retry (the bare
arms brief, decision 7).

## 4. The log rows

One directory per cell. Every row is one JSON object per line. Coordinates in logs are
**world** axis (§1.1); the shown-axis text the model saw is in the page itself.

```
runs/<arm>_s<seed>_<yyyymmddThhmmss>/
  manifest.json   calls.jsonl   events.jsonl   actions.jsonl   frames.jsonl   summary.json
```

### 4.1 `calls.jsonl`: one row per model call

| key | type | note |
|---|---|---|
| `call_no` | int | 1, 2, … within the cell |
| `step` | int | the world step this call serves: the page or turn that decides step N renders frame N−1 and its state JSON says `"step": N-1` |
| `round` | `R1` `R1.5` `R2` `R3` `R4` `flat` `chat` | |
| `attempt` | 1 or 2 | the semantic try (§3.4): 2 = the same page sent again with the reason line |
| `transport_tries` | 1 or 2 | how many HTTP tries the client needed for this reply (§6: one retry on a transport failure) |
| `prompt` | text | trace arms: the whole page. chat: the new user turn only |
| `page_sha256` | hex or null | trace arms: sha256 of the page sent; null in chat |
| `prefix_sha256` | hex or null | chat: sha256 of every message before the newest turn, the cache-hit check; null in trace arms |
| `grammar_id` | text | which GBNF |
| `reply_text` | text | raw |
| `parsed` | object or null | |
| `valid` | bool | passed §3.4 |
| `reason` | text or null | why not |
| `elapsed_s` | float | wall clock |
| `tokens` | `{prompt, eval}` or null | as the server reports them |

### 4.2 `events.jsonl`: one row per thing that happened

Every row has `step` and `kind`. Kinds and their fields:

| kind | fields | who writes |
|---|---|---|
| `note_landed` | — | world |
| `arrival` | `cell`, `index` (0–2); once per cell, on the step it first counts; only after `note_landed` (no errand exists for the body before the note); the return's row also carries `errands_completed` beside it | world |
| `errands_completed` | — | world |
| `drink_crossing` | `drink_from`, `drink_to`, `health_from`, `health_to` — fires when drink goes from above 0 to 0, or health falls (the old E1 at its default, `vital_drink_at` 0, which rounds 38 and 39 ran) | world |
| `stall_start` / `stall_end` | `since_step`, `length` — a stall is the seen set (§7, D2) not growing for **8** consecutive steps (the old `DEFAULT_UNCHANGED_STEPS`); it fires once per stall, and the gate's history window is 9 counts, one longer than the stall (commit `3e1a822`'s lesson). Both rows carry both fields: `since_step` is the stall's first still step; `length` is 8 on `stall_start` (the crossing is the eighth still step) and the whole stall on `stall_end`. A stall still open when the cell ends has no `stall_end`; the reader reads that from its absence | gate |
| `death` | — | world |
| `gate_fired` | `events` (the kinds above that opened it, in the order note, arrival, drink, stall) | gate; focus/sliced only, at most once per step. **Stamped N**, the step whose world step produced the events; those open step N+1's asks (the note lands after step 10, its asks render on step 11), so the R1 rows in `calls.jsonl` sit one step after the `gate_fired` row that opened them. The controller hands the gate that step's world rows (or bare kinds) and the seen set's size after the step (settled 09-24 on the gate builder's A-questions) |
| `ops_applied` | `source` (`R1` or `flat`), `ops`, `list_after` | list |
| `ops_rejected` | `source`, `ops`, `reason` | list |
| `delete_confirmed` / `delete_declined` | `id` | R1.5 |
| `focus_chosen` | `id` | R2 |
| `focus_missing` | `reason` (`deleted`: a confirmed deletion removed the entry in force; `empty`: it emptied a list that had nothing in force). Written at the moment of loss; the third way, R2 defaulting with nothing to keep, is `focus_none`'s own `r2_defaulted` | controller |
| `focus_none` | `reason` (`empty`, `r2_defaulted`) | controller; the acting pages rendered `none` |
| `route` | `target`, `first_step` or null, `sentence_id` (1–3); stamped with the step whose page or turn carried the sentence (in chat that is the step after the naming one; in flat, since the hold, the page carries the cell in force and the row is that step's) | route hint. Not written, and no route line rendered, when the target is the cell the body stands on: there is nothing to route, and the old line's "No way there" for that case was untrue (bare arms brief, decision 9; the route builder's A-question). In flat, focus and sliced the target is the held destination, so one row on every step that carries one and none on a step that holds none; the no-way check at a step's start reads the hint and writes nothing |
| `destination_chosen` | `cell` (world axis) — a cell named that was not the held one (the first choice included): R3's `target` in focus and sliced, the one reply's `destination` in flat (§3.2); the row's `step` is the step it is named on, which the pages quote as `named at step N` | trace controller (the hold, §3.1) |
| `destination_reached` | `cell`, `held_steps` (this step minus the naming step: the steps R4 walked toward it; in flat the naming step is counted too, §3.2) — the body stands on the held cell at the start of the step; the hold is cleared and R3 asked, and in flat, which has no R3, the page simply carries no destination block and the reply may name one | trace controller |
| `destination_cleared` | `cell`, `held_steps`, `reason` (`no_way`: the route hint's first sentence for it at the start of the step; `replaced`: another cell named — R3's at an event, or flat's reply; `dropped`: R3 answered `null`, or defaulted, at an event — never flat's, whose `null` keeps, §3.2) | trace controller |
| `reply_invalid` | `round`, `attempt`, `reason` | §3.4 |
| `reply_defaulted` | `round`, `default` | §3.4 |
| `ops_in_acting_reply` | `round`, `ops` | defect detector; must never fire |
| `conversation_trimmed` | `windows_omitted` (the steps of the turns whose `window` became `(omitted)` this time), `dropped_turns` (the steps of whole turns dropped; a 400-step 9B cell never gets this far, the chat builder measured: the budget bites at step ~348 and windows alone absorb it) | chat |

### 4.3 `actions.jsonl`: one row per world step

| key | note |
|---|---|
| `step`, `arm` | |
| `action` | the verb the world received |
| `intent` | trace arms' `intent`, chat's `why` |
| `focus_id` | focus arm; else null |
| `target` | focus/sliced: the destination held during this step's R4 (world axis), null on a step that explored; else null |
| `destination` | flat: the destination held while the body acted — the cell its page carried (world axis), null on a step that carried none, the step a reply first names one among them (§3.2); chat: the cell that turn's reply named; else null |
| `route_first_step` | the move the hint named, or null |
| `pos_before`, `pos_after`, `moved` | world axis |
| `standing_on_after`, `drink_after`, `health_after` | |
| `list_size`, `n_calls` | after the step; calls this step, retries included. chat has no list and writes `list_size` 0 |

### 4.4 `frames.jsonl`, `manifest.json`, `summary.json`

`frames.jsonl`: one frame (§1.2) per step, frame 0 first.

`manifest.json`: `arm`, `seed`, `steps`, `model` (as the server reports it), `server`,
`code_sha`, `started_at`, `errand_cells`, `note_step` (10), `k_history` (5),
`stall_length` (8), `chat_budget_tokens` (90000), `chat_keep_turns` (20), `max_tokens`
(600), `timeout_s` (600), `grammar_ids`.
Every constant a reader might otherwise have to guess is here.

`summary.json` (also `arm`, `seed`, `steps`, `list_size`, `seen_cells`, so the file names
its own cell): `errands_completed`, `cells_reached` (0–3), `steps_survived`, `died`,
`first_errand_step`, `note_to_first_errand_steps`, `after_errands` (steps survived after
`errands_completed`, new cells seen in them, and, focus only, the entry in force on each
of them; after the errands the body should return to the mapping task,
and this is the indicator), `invalid_replies` by round,
`defaulted_replies` by round, `focus_is_errand_fraction` (focus: steps whose focus entry
names an errand, by a reader's rule, not the harness's), `destinations_named` (flat,
chat: the replies that named a cell — in flat, since the hold, a reply naming the cell it
already holds is one of them), `destinations_chosen` (every arm that holds one — flat,
focus, sliced: the `destination_chosen` rows; the reader
also derives steps per destination from the chosen/reached/cleared rows), `n_calls`, `wall_s`. The reader (build piece 5) computes the seed × arm table from
these and from the rows above; nothing in `summary.json` is needed that the rows cannot
reproduce.

## 5. The command that runs one cell

```
python -m p3focus run --arm {flat,focus,chat,sliced} --seed 7 --steps 400 \
                      --server http://127.0.0.1:8080 --out runs/
python -m p3focus run --arm focus --seed 7 --steps 40 --policy scripted:tests/fixtures/x.jsonl --out /tmp/x
```

| flag | meaning |
|---|---|
| `--arm`, `--seed`, `--steps` | the only experimental parameters |
| `--server` | the llama.cpp server (the tower, through mp2013's tunnel) |
| `--out` | parent directory; the cell directory is created under it (§4) |
| `--policy scripted:<file>` | no server; replies come from the file in call order, one JSON object a line, `{"reply": "<text>"}` with an optional `"round"` the runner asserts. For tests and for the five-question check on rendered pages |
| `read <cell_dir>...` | the reader (§4.4 recomputed from the rows; the seed × arm table; `--trajectory` for the map) |
| `--quiet` | no per-step console line |

Nothing else is a flag. K, the stall length, the note step, token caps and timeouts
are constants in `p3focus/constants.py` and are copied into the manifest.
Exit 0 on completion (death included), 2 on a server failure that survives the client's
retry, 3 on bad arguments. The drivers (build piece 6) call this command and nothing
else.

## 6. The pieces, and which parts of this page each one owns

| piece | owns | reads |
|---|---|---|
| world | §1.1, §1.2, `arrival`, `note_landed`, `drink_crossing`, `death`, `errands_completed`; the **seen set** (D2: the walkable cells, water included, inside the 9×9 around every cell the body has stood on, grown every step) and the `mapped` bits derived from it | — |
| model client | one call: page or messages + grammar → reply text, `elapsed_s`, `tokens`; one retry on a transport failure; the `calls.jsonl` row. `POST /v1/chat/completions` with `model`, `messages`, `temperature` 0, `seed` 42, `max_tokens` 600, `stream` false, `grammar`; timeout 600 s. Before a cell's first real call it sends the old line's grammar probe (a one-token grammar `root ::= "GRAMMAR-HELD"`) and refuses to run if the server does not echo it: a server that ignores `grammar` answers 200 | §4.1 |
| gate | `gate_fired`, `stall_start`/`stall_end`; the window logic, tested through a loop | the world's events and the seen set's size, step by step |
| route hint | `route`; the BFS over the world's seen set; the three sentences. The controller does not call it when the named cell is the body's own | `target`/`destination`, the seen set |
| list | §2, `ops_applied`/`ops_rejected`, the focus id | ops |
| trace controller (flat, focus, sliced) | the rounds of a step, `State`, rollback, §3.4, `actions.jsonl`; **the hold** (§3.1): the destination, its occasions, `destination_chosen` / `destination_reached` / `destination_cleared` | everything above, `pages.md` |
| chat controller | the conversation, trimming, §3.3 | `pages.md` |
| reader | the table from §4 | §4 only |
| drivers | §5 on mp2013, the body and idle checks, a watcher | §5 only |

## 7. Decisions made on this page, with reasons (hers to strike)

- **D1. Grammar-constrained replies in every arm.** The plan says flat must not lose on
  JSON alone; a grammar removes that failure mode for every arm equally, and leaves
  "invalid" meaning something (§3.4). The tower already serves every Qwen3.5 with
  `--reasoning off` (`garden_tower.md`, measured 09-20: with it on, 600 tokens of
  thinking and empty content on a one-object prompt), so the grammar applies to the
  reply itself. The client asserts this on its first call by rejecting a reply that
  opens with `<think>`.
- **D2. One seen-cell rule: the seen set grows on every step**, to the 9×9 around every
  cell the body has stood on. That is what "cells you have seen" says; the old trace grew
  it only on steps that routed, which made the sentence false for cells the body walked
  past (bare arms brief, decision 6). Chat already does this.
- **D3. List changes are not history lines** in any arm. On focus's acting pages history
  is visible and the list is not; a `[list] you added …` line would put list content
  where only the entry in force belongs. flat keeps the same history grammar so the
  control differs from the treatment in one thing.
- **D4. `standing_on` joins the frame** (schema "2") rather than being computed at render
  time, so the reader and the identity test see it too.
- **D5. flat deletes without confirmation.** A 1.5 would be a second round, and flat is
  the one-pass control.
- **D6. Defaults never let the harness choose for the body** (§3.4): R2's default is
  `none`, not the top-ranked entry. The steering brief's rule, kept: the harness decides
  when to ask, never what to hold.
- **D7. The map task stays as the standing task, seeded onto the list at dawn and
  stated once in chat's system message; no progress count is on any page.** The note
  says the map can wait: the errand is an interruption of a standing task, and without
  the task there is nothing to interrupt. The old trace pages already dropped `count`
  under `--task-off-page`; arm O as built still showed it every turn because chat
  ignored the flag, so chat loses it here too (`pages.md`, P1, P2).
- **D8. Constants, not flags** (§5). The old code piled flag on flag. Three
  parameters vary; everything else is written down once and copied into the manifest.
- **D9. flat holds its destination** (#99, 09-25; experiment E2). It was one-shot until
  09-25, on the reading that the control is the same content in one pass and that the hold
  is harness structure belonging to the treatment; that entry ended "if a focus win needs
  the hold ruled out as its cause, holding flat's `destination` the same way is one
  afternoon and five cheap cells". Panel 3 made the win real (focus 4/5, sliced 2/5, chat
  2/5, flat 0/5) and the question live: the treatment carries both slicing and the hold, so
  a win says nothing about which of them bought it. flat now gets **the hold and nothing
  else** — the same one page, the same one reply a step, the same list and manual on it,
  the same command block but for its `destination` sentence, no confirmation round (D5
  stands), no R3. A flat cell that completes the chain says the hold bought it; one that
  does not says the slicing did. What the hold changed in flat: `null` keeps the held cell
  instead of naming none for the step (§3.2, §3.4); the route sentence answers the page's
  own destination instead of last step's, so the hint the body reads is this step's; and
  §4.2's three rows are flat's too, `dropped` excepted. Cells run before 09-25 ran the
  one-shot arm: a panel's arms are the code that ran it (`code_sha` in every manifest).
- **D11. The no-focus rule's asks are an event occasion** (#99; `pages.md` P11 has the
  reason): the rule is "an ask ran this step", one sentence for the gate's four events and
  the no-focus asks alike, because both end with the body possibly on a different entry.
- **D10. A defaulted R3 drops a held destination** (#99). D6 says defaults never let the
  harness choose; keeping the old cell would be the harness holding what the body twice
  tried to change. The step explores and the question returns next step.

## 8. Read off the old code, 09-24 (was the open list)

All items are now in §1 and §4: drink +1 per step in water; sand −1 once per step
ending on it; lava → stone; monsters removed as objects; four move verbs; the note's
text and the per-seed cells; the completion rule; the outcome sentences; no list cap;
drink crossing at 0 or a health fall; stall length 8. The two long texts that belong to
`pages.md` — the chat system message and the trace background, console manual and list
manual — are quoted there from `loop.py`, with what changed and why.
