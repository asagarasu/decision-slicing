"""What the chat body reads: the system message to the byte against B §7, and
the user turn's line order.

The system message is read out of `design/pages.md` the way
`test_texts_state.py` reads the trace blocks, so B is the pin and this file
holds no copy of it. The turn is tested here as a pure function of a frame; the
same turn, rendered by a scripted run and logged as `calls.jsonl`'s `prompt`, is
tested as B §6's properties in `test_chat_cell.py`.
"""
import json
import pathlib
import re

from p3focus import chat, constants, texts

PAGES = pathlib.Path(__file__).resolve().parents[2] / "design" / "pages.md"


def _b7_block(index=0):
    """A fenced block of B §7 — 0 the system message, 1 the user turn sketch."""
    doc = PAGES.read_text()
    start = doc.index("## 7. Chat")
    return re.findall(r"```\n(.*?)```", doc[start:], flags=re.S)[index].rstrip("\n")


def _frame(step=14, pos=(33, 32), drink=7):
    """A frame of A §1.2's shape, world axis (+y down), with one tree above the
    body and sand to its left so `near` and `faced` are not all one word."""
    window = [["grass"] * 9 for _ in range(9)]
    window[4][4] = "player"
    window[3][4] = "tree"
    window[4][3] = "sand"
    return {"schema_version": "2", "step": step, "daylight": 0.98,
            "player": {"pos": list(pos), "facing": [1, 0], "sleeping": False,
                       "health": 9, "food": 9, "drink": drink, "energy": 9},
            "inventory": {}, "window": window, "achievements": {},
            "deltas": {}, "standing_on": "grass"}


MAPPED = {"here": True, "up": True, "down": True, "left": True, "right": False}


# -- the system message (B §7) -------------------------------------------------

def test_the_system_message_is_b_7s_block_to_the_byte():
    assert chat.system_message() == _b7_block(0)


def test_the_system_message_shares_its_state_sentence_with_the_trace_manual():
    """B §7 differs from B §1.3 in two places and no others: the world's law
    rides `step (the clock; …)` and the world's size rides `player {pos …}`,
    because chat has no background paragraph to put them in. Everything from
    `; daylight` on is one text, so the two manuals cannot drift apart."""
    tail = texts.state_description("turn").split("; daylight", 1)[1]
    chat_tail = chat.state_paragraph().split("; daylight", 1)[1]
    assert chat_tail == tail.replace("player {pos [x, y] (",
                                     "player {pos [x, y] in a world of 64 by 64 cells (", 1)
    assert texts.STANDING_ON_CLAUSE in chat.state_paragraph()


def test_the_system_message_names_no_progress_count_and_no_list():
    """B, P2: no progress meter on any page — arm O as built showed
    `mapped.count` every turn. B §4: chat has no list, so no manual for one."""
    message = chat.system_message()
    assert "count" not in message
    assert "THE LIST" not in message and '"op"' not in message and "ops" not in message


def test_the_system_message_carries_her_safe_line_and_the_destination_key():
    """The other two of B §7's three changes against arm O as built."""
    message = chat.system_message()
    assert texts.SAFE_LINE in message
    assert '"destination": [x, y] or null}' in message


# -- the user turn (B §7) ------------------------------------------------------

def test_a_turn_with_everything_is_in_b_7s_line_order():
    turn = chat.user_turn(_frame(), MAPPED, outcome="moved to [33, 31]",
                          note_line='step 10: a note from your human player arrived: "…"',
                          route_sentence="The way there, over cells you have seen, begins with move_right.")
    assert turn.split("\n") == [
        "outcome of your last action: moved to [33, 31]",
        'step 10: a note from your human player arrived: "…"',
        "The way there, over cells you have seen, begins with move_right.",
        "you are carrying nothing.",
        texts.AXIS_LINE,
        turn.rsplit("\n", 1)[1],
    ]


def test_the_first_turn_has_no_outcome_line_and_no_route_line():
    """Turn 1 has no last action (B §7, the outcome reports steps 1 on) and
    answers no destination. What is left is the axis line and the state."""
    turn = chat.user_turn(_frame(step=0, pos=(32, 32), drink=3), MAPPED)
    assert turn.split("\n")[0] == "you are carrying nothing."
    assert turn.split("\n")[1] == texts.AXIS_LINE
    assert len(turn.split("\n")) == 3


def test_the_axis_line_rides_every_turn_and_the_state_json_is_last():
    """B, P6: the axis line rides R4, flat and every chat turn. The state JSON
    last is what `omit_window` relies on."""
    for kwargs in ({}, {"outcome": "waited"},
                   {"outcome": "waited", "route_sentence": "No way there over cells you have seen yet."}):
        lines = chat.user_turn(_frame(), MAPPED, **kwargs).split("\n")
        assert lines[-2] == texts.AXIS_LINE
        assert json.loads(lines[-1])["step"] == 14


def test_the_state_json_is_b_5s_object_with_no_count_and_sorted_keys():
    body = json.loads(chat.user_turn(_frame(), MAPPED).split("\n")[-1])
    assert list(body) == sorted(body)
    assert body["player"]["pos"] == [33, 31]            # shown axis, +y up
    assert body["mapped"] == MAPPED and "count" not in body["mapped"]
    assert body["standing_on"] == "grass" and len(body["window"]) == 10
    for banned in ("food", "energy", "inventory", "achievements"):
        assert banned not in body


# -- trimming's one text operation (A §3.3, B §7) ------------------------------

def test_omit_window_replaces_only_the_window_and_leaves_the_other_lines():
    turn = chat.user_turn(_frame(), MAPPED, outcome="moved to [33, 31]")
    omitted = chat.omit_window(turn)
    assert omitted.split("\n")[:-1] == turn.split("\n")[:-1]
    was, now = (json.loads(t.split("\n")[-1]) for t in (turn, omitted))
    assert now["window"] == chat.OMITTED_WINDOW
    assert {k: v for k, v in now.items() if k != "window"} == \
           {k: v for k, v in was.items() if k != "window"}


def test_omitting_a_window_twice_is_still_one_omitted_window():
    """`trim` never re-omits a turn, but the function itself must be safe: the
    state JSON is still one object with `(omitted)` in it."""
    once = chat.omit_window(chat.user_turn(_frame(), MAPPED))
    assert chat.omit_window(once) == once


# -- the reply shape the system message teaches --------------------------------

def test_the_reply_shape_names_the_three_keys_of_a_3_3():
    shape = chat.REPLY_SHAPE
    for key in ("action", "why", "destination"):
        assert f'"{key}"' in shape
    assert "intent" not in shape and "ops" not in shape       # those are the trace arms'
    assert shape.index('"action"') < shape.index('"why"') < shape.index('"destination"')


def test_the_actions_the_manual_teaches_are_the_four_verbs_and_not_noop():
    """A §1.1: `noop` exists only inside the harness, for a defaulted reply, and
    is never offered to the model."""
    message = chat.system_message()
    for verb in constants.VERBS:
        assert verb in message
    assert constants.NOOP not in message
