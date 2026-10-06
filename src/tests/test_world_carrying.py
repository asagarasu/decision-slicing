"""A §1.3: arriving on an errand cell is told in the world's sentence,
and the item stays in `carrying`."""
from p3focus import world as world_mod


def test_the_pickup_is_told_once_and_carried_after(monkeypatch):
    # errand cells beside the spawn so the walk is short: visit south, visit south again, return
    monkeypatch.setitem(world_mod.K.ERRANDS, 7, ((32, 33), (32, 34), (32, 32)))
    w = world_mod.World(7); w.reset()
    for _ in range(10):
        w.step("move_left" if _ % 2 else "move_right")   # let the note land (after step 10)
    # walk back to the spawn column then south
    pos = w.last_frame["player"]["pos"]
    while pos[0] != 32:
        _, said, _ = w.step("move_left" if pos[0] > 32 else "move_right"); pos = w.last_frame["player"]["pos"]
    while pos[1] != 32:
        _, said, _ = w.step("move_up" if pos[1] > 32 else "move_down"); pos = w.last_frame["player"]["pos"]
    _, said1, ev1 = w.step("move_down")
    assert any(e["kind"] == "arrival" for e in ev1)
    assert said1.endswith("; you picked up the pickaxe: it is on you now"), said1
    assert w.carrying == ["pickaxe"]
    _, said2, _ = w.step("move_down")
    assert said2.endswith("; you picked up the rope: it is on you now"), said2
    assert w.carrying == ["pickaxe", "rope"]
    _, said3, _ = w.step("move_up")
    assert "picked up" not in said3
    _, said4, ev4 = w.step("move_up")
    assert any(e["kind"] == "errands_completed" for e in ev4)
    assert said4.endswith("; you have reached your human player with the pickaxe and the rope: the errands are done"), said4


def test_the_return_cell_without_both_is_told_every_step_after_the_note(monkeypatch):
    """A §1.3 (#99): standing where the human said to come without both items is told on
    every such step after the note, naming what is carried and what is missing; not before
    the note, not on the step it lands, and not once the errands are done."""
    # the return cell IS the spawn; a visit cell beside it
    monkeypatch.setitem(world_mod.K.ERRANDS, 7, ((32, 33), (32, 34), (32, 32)))
    w = world_mod.World(7); w.reset()
    clause = "you are standing where your human player said to come"
    # before the note: bump around the spawn and come back to it — no clause
    for verb in ("move_down", "move_up", "move_down", "move_up", "move_down", "move_up",
                 "move_down", "move_up", "move_down"):
        w.step(verb)
    _, said10, ev10 = w.step("move_up")            # step 10: back on [32, 32]; the note lands now
    assert any(e["kind"] == "note_landed" for e in ev10)
    assert tuple(w.last_frame["player"]["pos"]) == (32, 32)
    assert clause not in said10, "not on the step the note lands"
    # step 11: still on the spawn (a bump into whatever is left of it, or a return) — told, with nothing carried
    _, said11, _ = w.step("move_left")
    if tuple(w.last_frame["player"]["pos"]) != (32, 32):
        _, said11, _ = w.step("move_right")
    assert said11.endswith(world_mod.return_without_both([])), said11
    assert "you have nothing yet and still need the pickaxe and the rope" in said11
    # it repeats while the body stays
    _, said12, _ = w.step("move_left")
    if tuple(w.last_frame["player"]["pos"]) == (32, 32):
        assert clause in said12
    else:
        _, said12, _ = w.step("move_right")
        assert clause in said12
    # pick up the pickaxe and come back: told again, naming the rope as missing
    _, said_pick, _ = w.step("move_down")
    assert "picked up the pickaxe" in said_pick
    _, said_back, _ = w.step("move_up")
    assert said_back.endswith("; you are standing where your human player said to come, but they are stuck "
                              "down below and will not come up until you bring both: you have the pickaxe "
                              "and still need the rope"), said_back
    # both items, then the return: the completion clause and not this one
    w.step("move_down"); _, said_rope, _ = w.step("move_down")
    assert "picked up the rope" in said_rope
    w.step("move_up"); _, said_done, ev_done = w.step("move_up")
    assert any(e["kind"] == "errands_completed" for e in ev_done)
    assert "the errands are done" in said_done and clause not in said_done
    # and after completion, standing there says nothing more
    _, said_after, _ = w.step("move_left")
    if tuple(w.last_frame["player"]["pos"]) != (32, 32):
        _, said_after, _ = w.step("move_right")
    assert clause not in said_after


def test_the_return_clause_names_the_rope_first_when_the_rope_came_first():
    assert world_mod.return_without_both(["rope"]).endswith("you have the rope and still need the pickaxe")
    assert world_mod.return_without_both([]).endswith("you have nothing yet and still need the pickaxe and the rope")
