"""The conversation and its trimming (A §3.3, B §7).

The conversation is the only place a chat body's own words are kept, so what
trimming takes and in what order is the whole of this arm's memory policy: the
oldest turns' windows first, then whole old turns, never the newest
`CHAT_KEEP_TURNS`, never the system message.
"""
import json
import math

from p3focus import chat, constants

MAPPED = {"here": True, "up": True, "down": True, "left": True, "right": False}
REPLY = '{"action": "move_right", "why": "east", "destination": null}'


def _frame(step):
    """A frame of A §1.2's shape, world axis; the window is what trimming omits."""
    window = [["grass"] * 9 for _ in range(9)]
    window[4][4] = "player"
    return {"schema_version": "2", "step": step, "daylight": 0.9,
            "player": {"pos": [32 + step, 32], "facing": [1, 0], "sleeping": False,
                       "health": 9, "food": 9, "drink": 5, "energy": 9},
            "inventory": {}, "window": window, "achievements": {},
            "deltas": {}, "standing_on": "grass"}


def _conversation(n_turns, system="SYSTEM", reply=REPLY):
    """`n_turns` finished turns: one user turn and one reply each, as a run
    leaves them. `open_turn` trims against the real budget, which 90,000 tokens
    is far too large to reach here."""
    conv = chat.Conversation(system)
    for step in range(1, n_turns + 1):
        conv.open_turn(step, chat.user_turn(_frame(step), MAPPED, outcome="waited"))
        conv.append("assistant", reply)
    return conv


def _windowless(conv):
    """The steps of the turns whose window has been omitted, in turn order."""
    return [t["step"] for t in conv.turns if t["window_omitted"]]


# -- the shape of the conversation ---------------------------------------------

def test_a_step_adds_exactly_two_messages_and_one_turn():
    conv = _conversation(3)
    assert len(conv.messages) == 1 + 2 * 3
    assert [m["role"] for m in conv.messages] == \
        ["system", "user", "assistant", "user", "assistant", "user", "assistant"]
    assert [len(t["members"]) for t in conv.turns] == [2, 2, 2]


def test_the_system_message_is_the_first_message_and_stays_there():
    conv = _conversation(25)
    conv.trim(budget=1, keep=20)
    assert conv.messages[0] == {"role": "system", "content": "SYSTEM"}
    assert [m["role"] for m in conv.messages[1:]].count("system") == 0


def test_a_retried_step_keeps_the_rejected_reply_and_the_reason_in_its_turn():
    """A §3.4 in chat's shape: the refused reply stays in the conversation and
    the reason follows it as a user turn, so a retried step is four messages."""
    conv = _conversation(1)
    conv.append("user", chat.RETRY_LINE.format(reason="the destination [64, 0] is off the map"))
    conv.append("assistant", REPLY)
    assert [m["role"] for m in conv.turns[-1]["members"]] == \
        ["user", "assistant", "user", "assistant"]
    assert len(conv.messages) == 1 + 4


def test_the_estimate_is_the_bytes_of_every_content_over_the_ratio():
    """The old `estimate_tokens`, at the old `BYTES_PER_TOKEN` of 3.5 and without
    its calibration: where the trim falls is a fact about the conversation and
    not about the server that happened to serve it."""
    conv = _conversation(2)
    total = sum(len(m["content"].encode()) for m in conv.messages)
    assert conv.est_tokens() == math.ceil(total / chat.BYTES_PER_TOKEN)
    assert chat.estimate_tokens([{"content": "x" * 7}], bytes_per_token=3.5) == 2
    assert chat.estimate_tokens([{"content": "水"}], bytes_per_token=3.5) == 1   # bytes, not characters


# -- trimming (A §3.3) ---------------------------------------------------------

def test_under_the_budget_nothing_is_trimmed_and_no_row_is_returned():
    conv = _conversation(25)
    before = [dict(m) for m in conv.messages]
    assert conv.trim(budget=10 ** 6, keep=20) is None
    assert conv.messages == before


def test_over_the_budget_with_too_few_turns_trims_nothing():
    """Fewer turns than `keep` means nothing is eligible: the newest turns are
    never trimmed, and a conversation that is only newest turns is untouched
    however far over it is."""
    conv = _conversation(constants.CHAT_KEEP_TURNS)
    before = [dict(m) for m in conv.messages]
    assert conv.trim(budget=1) is None
    assert conv.messages == before


def test_the_oldest_window_goes_first_and_nothing_is_dropped_for_it():
    """The budget here is exactly what the conversation measures with one window
    omitted, so the first pass is enough and the second must not run."""
    probe = _conversation(25)
    probe.turns[0]["user"]["content"] = chat.omit_window(probe.turns[0]["user"]["content"])
    budget = probe.est_tokens()

    conv = _conversation(25)
    row = conv.trim(budget=budget, keep=20)
    assert row["windows_omitted"] == [1] and row["dropped_turns"] == []
    assert row["still_over"] is False
    assert len(conv.turns) == 25 and len(conv.messages) == 51
    assert json.loads(conv.turns[0]["user"]["content"].split("\n")[-1])["window"] == "(omitted)"


def test_windows_go_oldest_first_and_then_whole_turns_oldest_first():
    conv = _conversation(25)
    row = conv.trim(budget=1, keep=20)
    assert row["windows_omitted"] == [1, 2, 3, 4, 5]
    assert row["dropped_turns"] == [1, 2, 3, 4, 5]
    assert [t["step"] for t in conv.turns] == list(range(6, 26))
    assert row["still_over"] is True                      # honest: 1 token is unreachable


def test_the_newest_keep_turns_keep_their_windows_whatever_the_budget():
    conv = _conversation(40)
    conv.trim(budget=1, keep=constants.CHAT_KEEP_TURNS)
    kept = conv.turns[-constants.CHAT_KEEP_TURNS:]
    assert len(conv.turns) == constants.CHAT_KEEP_TURNS
    for turn in kept:
        assert turn["window_omitted"] is False
        assert len(json.loads(turn["user"]["content"].split("\n")[-1])["window"]) == 10


def test_dropping_a_turn_removes_every_message_of_that_turn():
    conv = _conversation(25)
    conv.append("user", "a reason line")                  # a fifth message on turn 25
    conv.append("assistant", REPLY)
    doomed = [id(m) for m in conv.turns[0]["members"]]
    conv.trim(budget=1, keep=20)
    assert [id(m) for m in conv.messages if id(m) in doomed] == []
    assert len(conv.messages) == 1 + 2 * 20 + 2          # the system message and twenty turns


def test_a_turn_dropped_never_takes_a_later_verbatim_equal_reply_with_it():
    """The old line dropped messages with `list.remove`, which compares dicts:
    two bodies that answer the same way twice would have lost the wrong one.
    Here the drop is by identity, so an equal reply twenty turns later stays."""
    conv = _conversation(25, reply=REPLY)                 # every reply is the same bytes
    kept = [id(m) for t in conv.turns[5:] for m in t["members"]]
    conv.trim(budget=1, keep=20)
    assert [id(m) for m in conv.messages[1:]] == kept
    assert sum(1 for m in conv.messages if m["content"] == REPLY) == 20


def test_a_window_is_never_omitted_twice_and_the_row_says_so():
    conv = _conversation(25)
    first = conv.trim(budget=1, keep=20)
    assert first["windows_omitted"] == [1, 2, 3, 4, 5]
    for step in range(26, 31):                            # five more turns, five more eligible
        conv.open_turn(step, chat.user_turn(_frame(step), MAPPED, outcome="waited"))
        conv.append("assistant", REPLY)
    second = conv.trim(budget=1, keep=20)
    assert second["windows_omitted"] == [6, 7, 8, 9, 10]  # the already-omitted are not re-read
    assert _windowless(conv) == []                        # each of those was then dropped


def test_the_row_a_run_logs_is_the_dropped_turns_field_of_a_4_2():
    conv = _conversation(25)
    row = conv.trim(budget=1, keep=20)
    assert set(row) == {"est_tokens_before", "est_tokens_after", "budget",
                        "windows_omitted", "dropped_turns", "still_over"}
    assert row["est_tokens_after"] < row["est_tokens_before"]
    assert isinstance(row["dropped_turns"], list)
