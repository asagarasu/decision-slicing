"""The shared texts are the bytes B quotes; the state JSON has B §5's shape."""
import json
import re

from p3focus import axis, state, texts


def _b_block(heading_needle, fence_index=0):
    """A fenced block of design/pages.md, found after a heading needle."""
    import pathlib
    doc = pathlib.Path(__file__).resolve().parents[2].joinpath("design", "pages.md").read_text()
    start = doc.index(heading_needle)
    blocks = re.findall(r"```\n(.*?)```", doc[start:], flags=re.S)
    return blocks[fence_index].rstrip("\n")


def test_the_console_manual_is_the_text_pages_md_quotes():
    assert texts.console_manual() == _b_block("### 1.3 Console manual")


def test_the_background_is_the_text_pages_md_quotes():
    assert texts.BACKGROUND_TRACE == _b_block("### 1.1 Background")


def test_the_legend_hides_the_monsters_and_keeps_lava():
    line = texts.legend_line()
    assert "Zo=" not in line and "Sk=" not in line and "Ar=" not in line
    assert "La=lava" in line and "YOU=yourself (the centre cell)" in line


def test_the_history_grammar_drops_an_empty_intent():
    assert texts.trace_action_line(13, "move_right", "", "did not move; the cell to your right is tree") == \
        'step 13: you took action "move_right", and did not move; the cell to your right is tree.'
    assert texts.trace_action_line(12, "move_right", "heading east", "moved to [34, 31]") == \
        'step 12: you took action "move_right" on "heading east", and moved to [34, 31].'


def test_shown_y_is_an_involution_and_x_is_untouched():
    for y in (0, 1, 31, 32, 63):
        assert axis.shown_y(axis.shown_y(y)) == y
    assert axis.shown_pos([33, 32]) == [33, 31]
    assert axis.shown_pos(axis.shown_pos([5, 60])) == [5, 60]


def _frame():
    window = [["grass"] * 9 for _ in range(9)]
    window[4][4] = "player"
    window[3][4] = "tree"
    window[4][3] = "sand"
    return {"schema_version": "2", "step": 14, "daylight": 0.98123,
            "player": {"pos": [33, 32], "facing": [1, 0], "sleeping": False,
                       "health": 9, "food": 9, "drink": 7, "energy": 9},
            "inventory": {}, "window": window, "achievements": {},
            "deltas": {"inventory": {"drink": -1, "food": 0}, "achievements": {}},
            "standing_on": "grass"}


def test_render_state_has_the_keys_of_b_5_and_nothing_of_the_pickaxe_era():
    s = state.render_state(_frame(), {"here": True, "up": True, "down": True, "left": True, "right": False})
    assert set(s) == {"step", "daylight", "player", "near", "faced", "window", "mapped", "standing_on", "carrying", "deltas"}
    assert s["carrying"] == []
    assert state.render_state(_frame(), {"here": True, "up": True, "down": True, "left": True, "right": False}, ("pickaxe",))["carrying"] == ["pickaxe"]
    assert s["player"] == {"pos": [33, 31], "facing": "right", "health": 9, "drink": 7}
    assert s["near"] == {"up": "tree", "down": "grass", "left": "sand", "right": "grass"}
    assert s["faced"] == "grass" and s["standing_on"] == "grass" and s["daylight"] == 0.98
    assert s["deltas"] == {"inventory": {"drink": -1}}
    assert len(s["window"]) == 10 and s["window"][0] == "x=29 30 31 32 33 34 35 36 37"
    assert s["window"][5] == "y=31: Gr Gr Gr Sa YOU Gr Gr Gr Gr"          # the body's row (sand to its left), its shown y
    assert s["window"][4] == "y=32: Gr Gr Gr Gr Tr Gr Gr Gr Gr"           # north of it, a larger y
    assert s["window"][9].startswith("y=27: ")
    for banned in ("food", "energy", "inventory", "achievements"):
        assert banned not in s


def test_the_state_line_is_sorted_json_after_the_position():
    line = state.state_line(_frame(), {"here": True, "up": False, "down": False, "left": False, "right": False},
                            "your command: one game action (required).")
    assert line.startswith("step current: you are at [33, 31], carrying nothing, your state {")
    assert state.carrying_words(("pickaxe", "rope")) == "the pickaxe and the rope"
    assert line.endswith(". respond with your command: one game action (required).")
    body = json.loads(line[line.index("{"):line.rindex("}") + 1])
    assert list(body) == sorted(body)
