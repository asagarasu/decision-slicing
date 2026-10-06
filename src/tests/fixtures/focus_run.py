"""The scripted focus cell the trace tests read: 44 steps on `World(7)`.

The action sequence is fixed per step, so the world's trajectory — and with it
every gate step — does not move when the plan around it changes. It walks east
for ten steps, then repeats nine steps that see nothing new and two that do, so
the gate opens on the note (step 10, asks on 11) and on a stall three times
(18, 30, 41; asks on 19, 31, 42).

The plan then exercises, once each: an add at the note, an edit, a delete
confirmed, a delete declined, a delete that empties the list, a choice, a
destination named, reached, kept at an event, replaced and dropped, an invalid
reply in every round kind, and a second invalid reply in R1, R1.5, R2, R3 and R4
so each default of A §3.4 fires.

R3 runs on its occasions (A §3.1, B §3.4), not every step: step 1 (missing),
step 4 (the first destination, three cells east, is reached), the ask steps 11,
19, 31, 32, 42, 43 (event), and 44 (missing, after 43 dropped the hold).
"""

from fixtures import scripted as s

STEPS = 44
SEED = 7


def verb(step):
    """The action R4 gives on this step (see the module docstring)."""
    if step <= 10:
        return "move_right"
    cycle = (step - 11) % 11
    if cycle in (9, 10):
        return "move_down"
    return "move_left" if cycle % 2 == 0 else "move_right"


#: the gate's own steps, measured once and pinned by `test_trace_focus.py`
GATED_ASK_STEPS = (11, 19, 31, 42)

PLAN = {
    # -- step 1: the first destination, three cells east of the spawn; the walk
    #    reaches it at step 4, which brings R3 back (the reached occasion) ------
    (1, "R3"): [s.r3(target=(35, 31), candidates=[(35, 31)], need="get going", why="east first")],
    # -- an invalid reply in each acting round, answered on the retry; R3's on
    #    the reached occasion, R4's on a held step -------------------------------
    (4, "R3"): [s.r3(target=(99, 99)), s.r3(target=(30, 31), do="go and stand on it")],
    (6, "R4"): ['{"action": "fly", "intent": "up and away"}', s.r4("move_right")],
    # -- step 11, the note's event: the held [30, 31] is replaced by the pickaxe --
    (11, "R3"): [s.r3(target=(42, 23), candidates=[(42, 23)], need="the pickaxe", why="the note")],

    # -- step 11, the note's gate: add one entry and edit the seeded one ------
    (11, "R1"): [s.r1_ops(s.op_add("fetch_pickaxe", "standing on [42, 23]",
                                   when="the note arrived", why="my human is stuck"),
                          s.op_edit("e1", why="the standing task"))],
    (11, "R2"): [s.r2("e2")],

    # -- step 19, a stall's gate: R1 invalid once; R1.5 invalid twice, so the
    #    deletion defaults to false and is declined; R2 invalid once ----------
    (19, "R1"): [s.r1_ops(s.op_delete("e99")), s.r1_ops(s.op_delete("e1"))],
    (19, "R1.5"): ['{"delete": "maybe"}', '{"delete": null}'],
    (19, "R2"): [s.r2("e99"), s.r2("e2")],

    # -- step 31, a stall's gate: both entries deleted and confirmed, which
    #    empties the list and leaves nothing in force; the second R1 page of
    #    the step carries only the no-focus line and adds nothing -------------
    (31, "R1"): [s.r1_ops(s.op_delete("e1"), s.op_delete("e2")), s.r1_no()],
    (31, "R1.5"): ['{"delete": "yes"}', s.r1_5(True), s.r1_5(True)],

    # -- step 32, no gate: the empty list brings R1 by itself ----------------
    (32, "R1"): [s.r1_ops(s.op_add("map_again", "every walkable cell mapped"),
                          s.op_add("meet_human", "standing on [32, 31]"))],
    (32, "R2"): [s.r2("e3")],

    # -- step 42, a stall's gate: the entry in force is deleted and R2 then
    #    fails twice with nothing to keep, so the acting pages show none ------
    (42, "R1"): [s.r1_ops(s.op_delete("e3"))],
    (42, "R1.5"): [s.r1_5(True)],
    (42, "R2"): [s.r2("e99"), s.r2("e77")],

    # -- step 43, no gate: no entry in force, list not empty; R1 fails twice
    #    and defaults to no, and R2 still runs after it ------------------------
    (43, "R1"): ['{"maintain": "maybe"}', '{"maintain": "perhaps"}'],
    (43, "R2"): [s.r2("e4")],

    # -- step 43's R3 (the event occasion) answers null: the hold is dropped and
    #    step 44 opens with no destination ---------------------------------------
    (43, "R3"): [s.r3(target=None, need="nothing helps", why="looked")],
    # -- step 44: both acting rounds fail twice and take their defaults -------
    (44, "R3"): [s.r3(target=(70, 2)), s.r3(target=(64, 0))],
    (44, "R4"): ['{"action": "dance", "intent": ""}', '{"action": "dance", "intent": ""}'],
}

#: the steps R3 renders on, by occasion (pinned by `test_trace_focus.py`)
R3_STEPS = {1: "missing", 4: "reached", 11: "event", 19: "event", 31: "event", 32: "event",
            42: "event", 43: "event", 44: "missing"}


def script():
    """The `Script` for the run: one action a step, and `PLAN` over it."""
    defaults = {
        "R1": s.r1_no(),
        "R1.5": s.r1_5(False),
        "R2": s.r2("e1"),
        "R3": s.r3(target=(42, 23), do="go toward it", candidates=[(42, 23), (22, 39)]),
        "R4": s.r4("move_right"),
    }
    plan = {(step, "R4"): [s.r4(verb(step), intent=f"step {step}")]
            for step in range(1, STEPS + 1)}
    plan.update(PLAN)
    return s.Script(defaults, plan)
