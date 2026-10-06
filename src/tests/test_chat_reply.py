"""A §3.4 for chat: what counts as an answer, what gets one retry, and what
never retries.

Under the grammar (A §7 D1) only the coordinate branch can fire on a real
server; the shape branches are for a scripted policy, whose replies are authored
rather than decoded, and for a reply that somehow arrived without a grammar.
"""
import json

from p3focus import chat, constants


def _reply(action="move_right", why="east", destination=None):
    return json.dumps({"action": action, "why": why, "destination": destination})


def test_a_reply_with_the_three_keys_is_an_answer():
    parsed, reason = chat.read_reply(_reply(destination=[42, 23]))
    assert reason is None
    assert parsed == {"action": "move_right", "why": "east", "destination": [42, 23]}


def test_a_null_destination_is_an_answer_and_never_a_reason():
    """A §3.4, the bare arms brief's decision 7: `null` is a whole answer."""
    parsed, reason = chat.read_reply(_reply(destination=None))
    assert reason is None and parsed["destination"] is None


def test_an_empty_why_is_an_answer():
    """A §3.1's rule for `intent` is chat's for `why`: required, and may be ""."""
    assert chat.read_reply(_reply(why=""))[1] is None


def test_a_destination_outside_0_63_is_the_one_check_a_3_4_names():
    high = constants.WORLD_SIZE - 1
    for off in ([64, 23], [42, -1], [-1, -1], [23, 64]):
        parsed, reason = chat.read_reply(_reply(destination=off))
        assert parsed is not None, "the object parsed; only its coordinate is wrong"
        assert reason is not None and f"0..{high}" in reason
        assert json.dumps(off) in reason


def test_every_cell_of_the_world_is_a_destination_not_only_one_in_the_window():
    """A §3: chat's destination may be any cell of the world — the errand cells
    are far, and the old panels ran `--far-target` for the same reason."""
    for corner in ([0, 0], [63, 63], [0, 63], [63, 0], [32, 31]):
        assert chat.read_reply(_reply(destination=corner))[1] is None


def test_an_action_that_is_not_one_of_the_four_verbs_is_refused():
    for action in ("drink", "noop", "do", "", "MOVE_RIGHT"):
        parsed, reason = chat.read_reply(_reply(action=action))
        assert reason is not None and "action" in reason


def test_a_missing_destination_key_is_refused_rather_than_read_as_null():
    """The grammar requires the key (B §7: "`null` is the usual value"), so a
    reply without it is a reply this arm did not produce."""
    parsed, reason = chat.read_reply(json.dumps({"action": "move_up", "why": "north"}))
    assert reason is not None and "destination" in reason


def test_a_why_that_is_not_text_is_refused():
    assert chat.read_reply(json.dumps(
        {"action": "move_up", "why": 3, "destination": None}))[1] is not None


def test_a_destination_that_is_not_two_integers_is_refused():
    for bad in ([1, 2, 3], [1], "somewhere", {"x": 1}, [1.5, 2], [True, False]):
        parsed, reason = chat.read_reply(_reply(destination=bad))
        assert reason is not None, bad


def test_text_that_holds_no_json_object_parses_to_nothing():
    for text in ("", "move_right", "[1, 2]", '{"action":', "null"):
        parsed, reason = chat.read_reply(text)
        assert parsed is None and reason == "the reply is not one JSON object"


def test_the_retry_line_names_the_reason_and_asks_for_one_object():
    """The old `_complete`'s habit, which is chat's retry (A §3.4): the reason
    arrives as a new user turn, not as a line appended to a re-rendered page."""
    reason = chat.read_reply(_reply(destination=[64, 0]))[1]
    line = chat.RETRY_LINE.format(reason=reason)
    assert line.startswith("your last reply was not accepted: ")
    assert line.endswith("; reply with one JSON object")
    assert reason in line
