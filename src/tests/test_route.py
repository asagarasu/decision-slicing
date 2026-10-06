"""The route hint's search, its three sentences and its event row (A §6, §4.2).

Hand-built seen sets, WORLD axis (+y down) throughout: these tests say what the
hint answers for a set of cells, not how the world grows one. The walk that
grows a set and asks a route on every step is `test_route_walk.py`.

The first three claims are the old line's, ported with their sets from
`p3_crafter_body_errands_94/src/tests/test_route_hint.py`.
"""
import json

import pytest

from p3focus.route import (MOVE_VERBS, SENTENCES, RouteResult, route, route_event,
                           route_first_step, route_hint_line)


# -- the search ------------------------------------------------------------------------

def test_a_tree_in_the_way_is_walked_around_not_bounced_off():
    """The way bends around a cell that is not in the seen set, and the first
    step is the bend, not the wall."""
    # a column x=5 from y=0 to y=6 with a tree at (5, 3); walkable cells beside it
    cells = {(5, y) for y in range(7) if y != 3} | {(4, 2), (4, 3), (4, 4), (6, 2), (6, 3), (6, 4)}
    assert route_first_step((5, 0), (5, 6), cells) == ("move_down", True)
    # standing right above the tree: the first step is sideways, not into it
    verb, direct = route_first_step((5, 2), (5, 6), cells)
    assert direct and verb in ("move_left", "move_right")


def test_an_unseen_target_routes_toward_the_nearest_seen_cell_and_is_not_direct():
    cells = {(x, 0) for x in range(6)}          # a seen row; the target is far off it
    assert route_first_step((0, 0), (9, 9), cells) == ("move_right", False)
    # already standing on the nearest seen cell: no hint
    assert route_first_step((5, 0), (9, 9), cells) == (None, False)


def test_no_way_when_the_set_is_empty_or_broken_and_none_when_the_target_is_here():
    assert route_first_step((0, 0), (0, 0), {(0, 0)}) == (None, False)
    assert route_first_step((0, 0), (2, 0), {(0, 0), (2, 0)}) == (None, False)   # a gap
    assert route_first_step((0, 0), (1, 0), set()) == (None, False)


def test_a_seen_but_unreachable_target_is_no_way_and_not_direct():
    """The target is in the set, so it is seen; nothing connects it, so there
    is no verb — and with no verb there is no way to be direct about."""
    cells = {(0, 0), (0, 1), (5, 5)}
    assert route_first_step((0, 0), (5, 5), cells) == (None, False)


def test_up_is_minus_y_because_the_input_is_the_world_axis():
    """A §1.1: stored +y down, and the verbs are screen words. So over a seen
    column the way to a SMALLER y begins with move_up."""
    column = {(5, y) for y in range(10)}
    row = {(x, 5) for x in range(10)}
    assert route_first_step((5, 5), (5, 1), column) == ("move_up", True)
    assert route_first_step((5, 5), (5, 9), column) == ("move_down", True)
    assert route_first_step((5, 5), (9, 5), row) == ("move_right", True)
    assert route_first_step((5, 5), (1, 5), row) == ("move_left", True)


def test_the_verb_is_always_one_of_the_four_moves():
    field = {(x, y) for x in range(4) for y in range(4)}
    verbs = {route_first_step((0, 0), t, field)[0] for t in field if t != (0, 0)}
    assert verbs and verbs <= set(MOVE_VERBS)


def test_two_seen_cells_equally_near_the_target_tie_to_the_lower_one():
    """The nearest-cell rule breaks ties by the cell itself, so the same set
    and target always give the same verb: (0, 4) < (4, 0), and (0, 4) is down."""
    arms = {(0, y) for y in range(5)} | {(x, 0) for x in range(5)}
    assert route_first_step((0, 0), (5, 5), arms) == ("move_down", False)
    assert route_first_step((0, 0), (5, 5), arms) == route_first_step((0, 0), (5, 5), arms)


def test_the_hint_never_changes_the_seen_set():
    """The world owns the set (A §6); the search only looks inside it."""
    cells = {(x, 0) for x in range(6)}
    before = set(cells)
    route((0, 0), (9, 9), cells)
    assert cells == before


def test_a_seen_set_handed_as_a_list_of_pairs_reads_the_same():
    """A merge-boundary courtesy: a list would fail every membership test in
    silence, and silence here reads as "no way there"."""
    cells = [(x, 0) for x in range(6)]
    assert route((0, 0), (5, 0), cells) == route((0, 0), (5, 0), set(cells))
    assert route((0, 0), (5, 0), cells).first_step == "move_right"


# -- the sentences ---------------------------------------------------------------------

def test_the_three_sentences_are_the_old_line_s_to_the_byte():
    assert route_hint_line(None, False) == "No way there over cells you have seen yet."
    assert route_hint_line("move_left", True) == \
        "The way there, over cells you have seen, begins with move_left."
    assert route_hint_line("move_up", False) == \
        ("Over cells you have seen, the way toward it begins with move_up; past the cells "
         "you know, the rest is unseen.")


def test_every_verb_renders_in_both_sentences_that_carry_one():
    for verb in MOVE_VERBS:
        assert route_hint_line(verb, True).endswith(f"begins with {verb}.")
        assert route_hint_line(verb, False).startswith(
            f"Over cells you have seen, the way toward it begins with {verb};")
    assert len(SENTENCES) == 3


def test_the_sentence_id_is_1_no_way_2_the_target_3_the_nearest_cell():
    row = {(x, 0) for x in range(6)}
    assert route((0, 0), (9, 9), set())[2:] == (1, SENTENCES[0])
    direct = route((0, 0), (5, 0), row)
    assert (direct.first_step, direct.direct, direct.sentence_id) == ("move_right", True, 2)
    indirect = route((0, 0), (9, 9), row)
    assert (indirect.first_step, indirect.direct, indirect.sentence_id) == ("move_right", False, 3)


def test_the_result_carries_the_sentence_its_own_first_step_names():
    row = {(x, 0) for x in range(6)}
    for target in [(5, 0), (9, 9), (0, 0)]:
        r = route((0, 0), target, row)
        assert isinstance(r, RouteResult)
        assert r.sentence == route_hint_line(r.first_step, r.direct)
        assert r.sentence == SENTENCES[r.sentence_id - 1].format(verb=r.first_step)


# -- the event row ---------------------------------------------------------------------

def test_the_event_row_is_A_4_2_s_and_its_target_is_the_world_axis():
    row = {(x, 0) for x in range(6)}
    result = route((0, 0), (5, 0), row)
    event = route_event(3, (5, 0), result)
    assert event == {"step": 3, "kind": "route", "target": [5, 0],
                     "first_step": "move_right", "sentence_id": 2}
    assert json.loads(json.dumps(event)) == event


def test_the_event_row_says_null_where_there_was_no_way():
    result = route((0, 0), (9, 9), set())
    event = route_event(0, (9, 9), result)
    assert (event["first_step"], event["sentence_id"]) == (None, 1)
    assert json.dumps(event).count("null") == 1


@pytest.mark.parametrize("target,first_step,sentence", [((5, 0), "move_right", 2),
                                                        ((9, 9), "move_right", 3),
                                                        ((0, 0), None, 1)])
def test_every_answer_the_hint_can_give_has_a_row(target, first_step, sentence):
    row = {(x, 0) for x in range(6)}
    event = route_event(7, target, route((0, 0), target, row))
    assert (event["first_step"], event["sentence_id"]) == (first_step, sentence)
    assert event["target"] == list(target)
