"""Every block B quotes is rendered to the byte, and every page kind is B §0's
blocks in B §0's order.

The expected bytes are read out of `design/pages.md` itself, the way
`test_texts_state.py` does it, so a page cannot drift from its spec without one
of these failing. Where B writes a placeholder (`{event lines}`, `<do>`,
`[42, 23]`), the fixture's value is substituted here.
"""
import dataclasses
import json
import pathlib
import re

from p3focus import axis, constants, list_store, pages, route, state, texts

DOC = pathlib.Path(__file__).resolve().parents[2].joinpath("design", "pages.md").read_text()


def _b_block(heading_needle, fence_index=0):
    """A fenced block of design/pages.md, found after a heading needle."""
    start = DOC.index(heading_needle)
    blocks = re.findall(r"```\n(.*?)```", DOC[start:], flags=re.S)
    return blocks[fence_index].rstrip("\n")


def _b_ticks(needle):
    """Every `backticked` span on the first line at or after `needle` — B's
    tables and its prose quote one-line blocks that way."""
    start = DOC.index(needle)
    line = DOC[start:DOC.index("\n", start)]
    return re.findall(r"`([^`]+)`", line)


def _b_paragraph_ticks(needle, count):
    """The first `count` backticked spans at or after `needle`, across lines —
    B §3.3's three `{previous line}` forms run over two lines."""
    return re.findall(r"`([^`]+)`", DOC[DOC.index(needle):])[:count]


# -- the state a page is built from ----------------------------------------

DAWN = {"id": "e1", "name": "map_world", "until": "every walkable cell mapped"}
ENTRY = {"id": "e2", "name": "fetch_pickaxe", "when": "the note arrived",
         "until": "standing on [42, 23]", "why": "my human is stuck"}


def _frame():
    window = [["grass"] * 9 for _ in range(9)]
    window[4][4] = "player"
    window[3][4] = "tree"
    return {"schema_version": "2", "step": 14, "daylight": 0.98,
            "player": {"pos": [33, 32], "facing": [1, 0], "sleeping": False,
                       "health": 9, "food": 9, "drink": 7, "energy": 9},
            "inventory": {}, "window": window, "achievements": {}, "deltas": {},
            "standing_on": "grass"}


MAPPED = {"here": True, "up": True, "down": True, "left": True, "right": False}


def _state(arm="focus", entries=(DAWN, ENTRY), focus_id="e2", history=("step 13: a line.",)):
    return pages.State(arm=arm, frame=_frame(), mapped=MAPPED, history=history,
                       entries=tuple(entries), focus_id=focus_id)


# -- B §1.2, the history block ---------------------------------------------


def test_the_first_step_says_so_and_a_partial_trim_says_nothing():
    assert pages.history_block([]) == texts.FIRST_STEP_LINE
    assert pages.history_block([]) == _b_paragraph_ticks("On the first step the block reads", 1)[0]
    lines = [f"step {n}: you took action \"move_right\", and waited." for n in range(1, 9)]
    assert pages.history_block(lines) == "\n".join(lines[-constants.K_HISTORY:])


# -- B §2, the list manual --------------------------------------------------


def test_the_list_manual_is_the_text_b_2_quotes():
    assert pages.list_manual() == _b_block("## 2. The list manual")


# -- B §3.1, the event lines and R1 ----------------------------------------


def test_every_event_line_is_the_text_b_3_1_quotes():
    assert pages.EVENT_NOTE == _b_ticks("| note | ")[0]
    assert pages.event_line_arrival([42, 40]) == _b_ticks("| arrival | ")[0]
    assert pages.EVENT_DRINK == _b_ticks("| drink reached 0 this step |")[0]
    assert pages.EVENT_HEALTH == _b_ticks("| health fell this step |")[0]
    assert pages.event_line_stall() == _b_ticks("| stall | ")[0]
    empty = _b_ticks("| no entry in force, list empty |")
    assert pages.no_focus_line("focus", True) == empty[0]
    assert pages.no_focus_line("sliced", True) == empty[1]
    assert pages.no_focus_line("focus", False) == _b_ticks("| no entry in force, list not empty")[0]


def test_the_event_lines_come_in_the_gates_order_with_the_no_focus_line_last():
    rows = [{"kind": "drink_crossing", "drink_from": 1, "drink_to": 0,
             "health_from": 9, "health_to": 8},
            {"kind": "arrival", "cell": [42, 40], "index": 0},
            {"kind": "note_landed"}]
    assert pages.event_lines(rows, stalled=True, no_focus=pages.NO_FOCUS_NONE) == [
        pages.EVENT_NOTE, pages.event_line_arrival([42, 40]), pages.EVENT_DRINK,
        pages.EVENT_HEALTH, pages.event_line_stall(), pages.NO_FOCUS_NONE]


def test_a_drink_crossing_that_only_fell_in_health_says_only_that():
    rows = [{"kind": "drink_crossing", "drink_from": 0, "drink_to": 0,
             "health_from": 9, "health_to": 8}]
    assert pages.event_lines(rows) == [pages.EVENT_HEALTH]


def test_r1s_ask_is_the_text_b_3_1_quotes_with_the_event_lines_in_place():
    assert pages.ask_r1(["{event lines}"]) == _b_block("### 3.1 focus, R1")


def test_r1_never_renders_with_an_empty_event_block():
    try:
        pages.ask_r1([])
    except ValueError:
        return
    raise AssertionError("R1 rendered with no event line (B §3.1)")


# -- B §3.2, R1.5 -----------------------------------------------------------


def test_r1_5s_ask_is_the_text_b_3_2_quotes_with_the_entry_in_place():
    placeholder = {"id": "e2", "name": "...", "when": "...", "until": "...", "why": "..."}
    assert pages.ask_r1_5(placeholder) == _b_block("### 3.2 focus, R1.5")


def test_r1_5_renders_an_unset_optional_field_as_absent_not_null():
    assert '"when"' not in pages.ask_r1_5(DAWN)
    assert "null" not in pages.ask_r1_5(DAWN)


# -- B §3.3, R2 -------------------------------------------------------------


def test_r2s_ask_is_the_text_b_3_3_quotes_with_the_previous_line_in_place():
    assert pages.ask_r2("{previous line}") == _b_block("### 3.3 focus, R2")


def test_the_previous_line_is_one_of_b_3_3s_three():
    want = _b_paragraph_ticks("`{previous line}` is one of three", 4)[1:]
    assert pages.previous_line("e1") == want[0]
    assert pages.previous_line("e2", deleted=True) == want[1]
    assert pages.previous_line(None) == want[2]


# -- B §3.4, R3 -------------------------------------------------------------


def test_r3s_ask_is_the_text_b_3_4_quotes():
    assert pages.ask_r3("focus") == _b_block("### 3.4 focus, R3")


DEST = pages.Destination(tuple(axis.shown_pos([42, 23])), 12, "<need>", "<why>")


def test_r3s_destination_lines_are_the_text_b_3_4s_table_quotes():
    """B §3.4's four occasions: no line on `missing`, and one line each on the others,
    between the head and the question."""
    assert pages.destination_line("missing", None) is None
    assert pages.destination_line("reached", DEST) == _b_ticks("| reached |")[0]
    assert pages.destination_line("no_way", DEST) == _b_ticks("| no way |")[1]
    assert pages.destination_line("event", DEST) == _b_ticks("| event | an ask ran this step")[0]
    line = pages.destination_line("event", DEST)
    assert pages.ask_r3("focus", line=line) == "\n\n".join(
        [pages.ASK_R3_HEAD, line, pages.ASK_R3_BODY])
    assert pages.ask_r3("focus") == "\n\n".join([pages.ASK_R3_HEAD, pages.ASK_R3_BODY])
    assert DEST.shown == [42, 23]


def test_r3_with_nothing_in_force_drops_the_two_phrases_that_point_at_it():
    asked = pages.ask_r3("focus", has_focus=False)
    assert "Where are you going? Name the position you are heading for" in asked
    assert "or a position the entry you are on names" not in asked
    assert "you have already been. A destination is a position in the WORLD" in asked
    # nothing else moves (B §3.4)
    assert asked == pages.ask_r3("focus").replace(", for the one you are on", "").replace(
        ", or a position the entry you are on names", "")


def test_sliced_r3_says_the_list_where_focus_says_the_one_you_are_on():
    asked = pages.ask_r3("sliced")
    assert "for what you keep on your list?" in asked
    assert "or a position an entry on your list names." in asked
    assert "the one you are on" not in asked


# -- B §3.5, R4 -------------------------------------------------------------


def test_the_destination_block_is_the_text_b_3_5_quotes_for_a_fresh_destination():
    sentence = route.SENTENCES[1].format(verb="move_right")
    bearing = pages.bearing_line([33, 31], [42, 23])
    assert bearing == "From where you stand, that position is 8 x move_down and 9 x move_right away."
    assert pages.destination_block(DEST, route_sentence=sentence, bearing=bearing, fresh=True) \
        == _b_block("### 3.5 focus, R4", 0)
    assert pages.bearing_line([5, 5], [5, 5]) == "You are standing on that position."
    assert pages.bearing_line([5, 5], [5, 9]) == "From where you stand, that position is 4 x move_up away."
    # B §3.5 (09-25): a neighbouring destination is named as `near` names it; farther ones are not
    near = {"up": "sand", "down": "grass", "left": "tree", "right": "water"}
    assert pages.bearing_line([5, 5], [5, 6], near) == \
        "From where you stand, that position is 1 x move_up away: it is the cell above you, sand."
    assert pages.bearing_line([5, 5], [5, 4], near).endswith("1 x move_down away: it is the cell below you, grass.")
    assert pages.bearing_line([5, 5], [4, 5], near).endswith("1 x move_left away: it is the cell to your left, tree.")
    assert pages.bearing_line([5, 5], [6, 5], near).endswith("1 x move_right away: it is the cell to your right, water.")
    assert pages.bearing_line([5, 5], [6, 6], near) == "From where you stand, that position is 1 x move_up and 1 x move_right away."
    assert pages.bearing_line([5, 5], [5, 7], near) == "From where you stand, that position is 2 x move_up away."
    assert pages.bearing_line([5, 5], [5, 6]) == "From where you stand, that position is 1 x move_up away."


def test_a_held_destination_block_names_its_step_and_drops_the_same_window_sentence():
    """B §3.5, P10: on a step R3 did not run, the first line ends `named at step 12.` and the
    tail opens on "Work out …"; the four lines between are the same."""
    sentence = route.SENTENCES[1].format(verb="move_right")
    bearing = pages.bearing_line([33, 31], [42, 23])
    fresh = pages.destination_block(DEST, route_sentence=sentence, bearing=bearing, fresh=True)
    held = pages.destination_block(DEST, route_sentence=sentence, bearing=bearing, fresh=False)
    assert held == fresh.replace("named this step.", "named at step 12.").replace(
        pages._SAME_WINDOW + " ", "")
    assert held.splitlines()[0] == "THE DESTINATION YOU CHOSE: [42, 23], named at step 12."
    assert held.splitlines()[-1].startswith("Work out what the first step")
    assert "same window" not in held


def test_a_kept_destination_block_names_its_step_and_says_kept_and_keeps_the_same_window():
    """B §3.5: R3 ran and named the held cell again — "named at step 12, kept this step."
    with the same-window sentence; `page_r4` derives it from the frame's step."""
    sentence = route.SENTENCES[1].format(verb="move_right")
    fresh = pages.destination_block(DEST, route_sentence=sentence, fresh=True)
    kept = pages.destination_block(DEST, route_sentence=sentence, fresh=True, kept=True)
    assert kept == fresh.replace("named this step.", "named at step 12, kept this step.")
    assert "This is the same window you just read" in kept
    # through page_r4: the frame says step 14, so the page decides step 15; DEST was named at 12
    st = dataclasses.replace(_state(), destination=DEST)
    assert "named at step 12, kept this step." in pages.page_r4(st, sentence, fresh=True)
    now = pages.Destination(DEST.cell, 15, "<need>", "<why>")
    assert "named this step." in pages.page_r4(dataclasses.replace(st, destination=now), sentence, fresh=True)
    assert "named at step 12." in pages.page_r4(st, sentence, fresh=False)


def test_the_destination_block_is_the_text_b_3_5_quotes_for_target_null():
    assert pages.destination_block(None, "<need>", "<why>") == _b_block("### 3.5 focus, R4", 1)


def test_a_destination_with_no_route_sentence_drops_the_line_and_nothing_else():
    dest = pages.Destination(tuple(axis.shown_pos([42, 23])), 3, "n", "w")
    with_route = pages.destination_block(dest, route_sentence=route.SENTENCES[1].format(verb="move_up"))
    without = pages.destination_block(dest)
    assert without == with_route.replace(
        route.SENTENCES[1].format(verb="move_up") + "\n", "")


def test_r4s_command_block_is_the_text_b_3_5_quotes():
    assert pages.command_block("R4") == _b_block("### 3.5 focus, R4", 3)
    assert '"ops"' not in pages.command_block("R4")


# -- B §3.6, flat -----------------------------------------------------------


def test_flats_command_block_is_the_text_b_3_6_quotes():
    """B §3.6's one fence is the command block. Its destination sentence is the hold's
    since 09-25 (A §3.2, A §7 D9): `null` keeps the cell the body holds."""
    assert pages.command_block("flat") == _b_block("### 3.6 flat")
    assert ('"destination": the position you are heading for, held for you from step to '
            "step and shown above; send null to keep the one you hold") in pages.command_block("flat")


# -- B §4, the list line and the focus line --------------------------------


def test_the_list_line_is_b_4s_line_and_the_dawn_entry_is_b_4s_entry():
    dawn_json = _b_paragraph_ticks("**Dawn.** Every trace arm's list starts with one entry", 2)[1]
    assert json.loads(dawn_json) == DAWN
    assert pages.list_line([DAWN]) == "current list: [" + dawn_json + "]"
    assert pages.list_line([]) == "current list: []"


def test_the_focus_line_names_the_entry_or_none():
    assert pages.focus_line(ENTRY) == "the one you are on: " + json.dumps(ENTRY)
    assert pages.focus_line(None) == _b_ticks("| focus R3, R4 |")[1]


def test_the_read_only_list_line_is_sliceds_and_says_so():
    prefix = _b_ticks("| sliced R3, R4 |")[0].split("[")[0]
    assert pages.readonly_list_line([DAWN]).startswith(prefix)
    assert pages.readonly_list_line([]).endswith("[]")


def test_an_entry_renders_its_fields_in_a_2s_order_and_drops_unset_optionals():
    full = dict(ENTRY, at=[42, 23])
    assert list(json.loads(list_store.render_entry(full))) == list(list_store.ENTRY_FIELDS)
    assert list(json.loads(list_store.render_entry(ENTRY))) == ["id", "name", "when", "until", "why"]
    assert list(json.loads(list_store.render_entry(DAWN))) == ["id", "name", "until"]
    assert '"at": [42, 23]' in list_store.render_entry(full)


def test_a_name_with_non_ascii_reads_on_the_page_as_it_reads_in_history():
    entry = {"id": "e9", "name": "找水", "until": "drink 9"}
    assert "找水" in pages.list_line([entry])


# -- B §5, the state line ---------------------------------------------------


def test_every_rounds_state_line_ends_in_b_5s_clause():
    st = _state()
    for round_id in ("R1", "R1.5", "R2", "R3", "R4", "flat"):
        want = _b_ticks(f"| {round_id} | `respond with")[0]
        assert pages.state_line(st, round_id).endswith(want), round_id


def test_the_state_line_is_state_pys_line_and_carries_b_5s_three_keys():
    line = pages.state_line(_state(), "R4")
    assert line.startswith("step current: you are at [33, 31], carrying nothing, your state {")
    body = json.loads(line[line.index("{"):line.rindex("}") + 1])
    assert {"window", "player", "standing_on"} <= set(body)
    assert body == state.render_state(_frame(), MAPPED)


# -- B §0, the order of blocks on each page kind ---------------------------


def _blocks_top(st):
    return [texts.BACKGROUND_TRACE, pages.history_block(st.history), texts.console_manual()]


def test_page_r1_is_b_0s_blocks_in_b_0s_order():
    st = _state()
    lines = [pages.EVENT_NOTE]
    assert pages.page_r1(st, lines) == "\n\n".join(
        _blocks_top(st) + [pages.list_manual(), pages.ask_r1(lines),
                           pages.list_line(st.entries), pages.axis_line(), pages.state_line(st, "R1")])


def test_page_r1_5_is_b_0s_blocks_in_b_0s_order():
    st = _state()
    assert pages.page_r1_5(st, ENTRY) == "\n\n".join(
        _blocks_top(st) + [pages.list_manual(), pages.ask_r1_5(ENTRY),
                           pages.list_line(st.entries), pages.axis_line(), pages.state_line(st, "R1.5")])


def test_page_r2_is_b_0s_blocks_in_b_0s_order():
    st = _state()
    previous = pages.previous_line("e1")
    assert pages.page_r2(st, previous) == "\n\n".join(
        _blocks_top(st) + [pages.list_manual(), pages.ask_r2(previous),
                           pages.list_line(st.entries), pages.axis_line(), pages.state_line(st, "R2")])


def test_page_r3_is_b_0s_blocks_with_the_focus_line_and_no_manual():
    st = _state()
    assert pages.page_r3(st) == "\n\n".join(
        _blocks_top(st) + [pages.ask_r3("focus"), pages.focus_line(ENTRY), pages.axis_line(),
                           pages.state_line(st, "R3")])


def test_page_r4_is_b_0s_blocks_with_the_destination_axis_and_command_blocks():
    dest = pages.Destination(tuple(axis.shown_pos([42, 23])), 9, "the pickaxe", "it is there")
    st = dataclasses.replace(_state(), destination=dest)
    sentence = route.SENTENCES[1].format(verb="move_right")
    for fresh in (True, False):
        # the frame says step 14, the page decides 15, the destination was named at 9: a fresh
        # page is the kept form (B §3.5)
        assert pages.page_r4(st, sentence, fresh=fresh) == "\n\n".join(
            _blocks_top(st) + [pages.destination_block(dest, route_sentence=sentence,
                                                       bearing=pages.bearing_line(st.pos_shown, [42, 23]),
                                                       fresh=fresh, kept=fresh),
                               pages.command_block("R4"),
                               pages.focus_line(ENTRY), pages.axis_line(), pages.state_line(st, "R4")])
    # an R3 page on the event occasion carries the held destination's line (B §3.4)
    line = pages.destination_line("event", dest)
    assert pages.page_r3(st, line) == "\n\n".join(
        _blocks_top(st) + [pages.ask_r3("focus", line=line), pages.focus_line(ENTRY), pages.axis_line(),
                           pages.state_line(st, "R3")])


def test_page_flat_is_b_0s_blocks_and_carries_no_block_with_nothing_held():
    st = _state(arm="flat", focus_id=None)
    assert pages.page_flat(st) == "\n\n".join(
        _blocks_top(st) + [pages.list_manual(),
                           pages.command_block("flat"), pages.list_line(st.entries),
                           pages.axis_line(), pages.state_line(st, "flat")])
    # with nothing held there is nothing to route to, and the sentence does not ride
    # alone: it is the destination block's line (B §3.6)
    assert pages.page_flat(st, route.SENTENCES[0]) == pages.page_flat(st)


def test_page_flat_carries_a_held_destination_block_above_the_command_block():
    """B §3.6 under the hold: §3.5's block in the shape a step that asked nothing
    renders — `named at step 12.`, the bearing line, the route sentence, no same-window
    sentence — between the list manual and the command block. flat's reply has no `need`
    and no `why`, so those two lines are absent."""
    dest = pages.Destination(tuple(axis.shown_pos([42, 23])), 12)
    st = dataclasses.replace(_state(arm="flat", focus_id=None), destination=dest)
    sentence = route.SENTENCES[1].format(verb="move_right")
    block = pages.destination_block(
        dest, route_sentence=sentence, fresh=False,
        bearing=pages.bearing_line(st.pos_shown, dest.shown,
                                   state.near_cells(st.frame["window"])))
    assert pages.page_flat(st, sentence) == "\n\n".join(
        _blocks_top(st) + [pages.list_manual(), block, pages.command_block("flat"),
                           pages.list_line(st.entries), pages.axis_line(),
                           pages.state_line(st, "flat")])
    assert block.splitlines()[0] == "THE DESTINATION YOU CHOSE: [42, 23], named at step 12."
    assert "The need you named" not in block and "What the destination is for" not in block
    assert "This is the same window you just read" not in block
    assert block.endswith(pages.DEST_TAIL_HELD)


def test_sliced_acting_pages_carry_the_read_only_list_line_and_no_manual():
    st = _state(arm="sliced", focus_id=None)
    assert pages.page_r3(st) == "\n\n".join(
        _blocks_top(st) + [pages.ask_r3("sliced"), pages.readonly_list_line(st.entries), pages.axis_line(),
                           pages.state_line(st, "R3")])
    assert pages.page_r4(st, need="water", why="none in view") == "\n\n".join(
        _blocks_top(st) + [pages.destination_block(None, "water", "none in view"),
                           pages.command_block("R4"), pages.readonly_list_line(st.entries),
                           pages.axis_line(), pages.state_line(st, "R4")])


def test_r4_s_defaulted_destination_block_is_b_3_5_s_third_shape():
    """A §3.4: R3 invalid twice defaults to `target: null`; B §3.5's third block says the
    position was refused, and keeps a parsed reply's `need`."""
    assert pages.destination_block(None, "<need>", "", defaulted=True) == _b_block("### 3.5 focus, R4", 2)
    without = pages.destination_block(None, "", "", defaulted=True)
    assert "The need you named" not in without and without.startswith("THE DESTINATION YOU CHOSE: none")
