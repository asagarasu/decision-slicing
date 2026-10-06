"""What the reader prints: the seed × arm table (the plan, "Reading"), the
trajectory map, and the command the chair wires into `python -m p3focus read`.

The fixture is the same five cells as `test_reader.py`; what is checked here is
the shape of the text, not the numbers in it.
"""
import json
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).parent / "fixtures" / "reader"))
import cells  # noqa: E402

from p3focus import constants, reader  # noqa: E402

MAP_LINE = re.compile(r"^ *(\d+) ([.:#SX123]{64})$")


@pytest.fixture(scope="session")
def made(tmp_path_factory):
    return cells.write_all(tmp_path_factory.mktemp("out_cells"))


@pytest.fixture(scope="session")
def read(made):
    return {name: reader.read_cell(path) for name, path in made.items()}


def map_rows(text):
    """The map out of a trajectory, as `{y: row}` — 64 rows of 64 characters."""
    rows = {}
    for line in text.splitlines():
        m = MAP_LINE.match(line)
        if m:
            rows[int(m.group(1))] = m.group(2)
    return rows


def columns(line):
    """One Markdown row's cells, trimmed."""
    return [c.strip() for c in line.strip().strip("|").split("|")]


def row_of(table, arm, seed):
    """One cell's table row as `{column: text}`."""
    header = columns(table.splitlines()[0])
    for line in table.splitlines():
        cells_ = columns(line)
        if cells_[:2] == [arm, str(seed)]:
            return dict(zip(header, cells_))
    raise AssertionError(f"no row for {arm} {seed} in\n{table}")


# --- the table ------------------------------------------------------------------

def test_the_table_has_a_row_for_every_cell_in_arm_then_seed_order(read):
    lines = reader.table(list(read.values())).splitlines()
    assert lines[0].startswith("| arm | seed | errands completed | cells reached |")
    assert lines[1].startswith("|:---|")
    body = [l for l in lines if l.startswith("| ") and not l.startswith("| arm")]
    assert [l.split(" | ")[0:2] for l in body] == [
        ["| flat", "7"], ["| flat", "10"], ["| focus", "7"], ["| focus", "10"],
        ["| sliced", "11"]]


def test_the_table_keeps_its_columns_and_adds_the_hold_s_three_after_them(read):
    """A §3.1's three, and every older column where it was: the table is read
    beside older ones, so a column that moved would be a column misread."""
    lines = reader.table(list(read.values())).splitlines()
    assert columns(lines[0]) == [
        "arm", "seed", "errands completed", "cells reached", "steps survived",
        "died", "first errand step", "invalid replies", "focus is errand",
        "destinations", "R3 asks", "steps / dest"]
    assert len(columns(lines[1])) == len(columns(lines[0]))
    assert all(len(columns(l)) == len(columns(lines[0]))
               for l in lines if l.startswith("| "))


def test_the_table_says_which_cell_finished_the_errands_and_which_died(read):
    rows = {(c["arm"], c["seed"]): r for c, r in
            zip(sorted(read.values(), key=lambda c: (c["arm"], c["seed"])), [None] * 4)}
    table = reader.table(list(read.values()))
    done = [l for l in table.splitlines() if l.startswith("| focus | 7 ")][0]
    assert "✓" in done and "| 3 |" in done and "| 102 |" in done and "| no |" in done
    died = [l for l in table.splitlines() if l.startswith("| flat | 10 ")][0]
    assert "✗" in died and "| yes |" in died
    assert rows is not None            # the zip above is only a shape check


def test_the_table_s_focus_column_is_empty_for_an_arm_without_a_focus(read):
    table = reader.table(list(read.values()))
    assert row_of(table, "focus", 7)["focus is errand"] == f"{73 / 102:.2f}"
    for arm, seed in (("flat", 7), ("flat", 10), ("sliced", 11)):
        assert row_of(table, arm, seed)["focus is errand"] == "—"


def test_the_hold_s_three_columns_are_the_arms_that_hold_a_destination(read):
    """`destinations` is one heading over two quantities (A §4.3, A §3.1): the
    cells chat names a turn, and the cells flat, focus and sliced choose when
    they are asked. `steps / dest` is every holding arm's; `R3 asks` is the arms
    that ask R3, which flat is not — it holds one without that round (A §7 D9).

    The fixture's flat cells are records from before the hold and chose nothing,
    so their count reads 0 and their mean is empty; a flat cell that holds one
    fills both, which `test_trace_flat_hold.py` checks on a cell really run."""
    table = reader.table(list(read.values()))
    focus = row_of(table, "focus", 7)
    assert [focus[c] for c in ("destinations", "R3 asks", "steps / dest")] == \
        ["8", "11", "12.5"]
    sliced = row_of(table, "sliced", 11)
    assert [sliced[c] for c in ("destinations", "R3 asks", "steps / dest")] == \
        ["4", "4", "5.5"]
    flat = row_of(table, "flat", 10)
    assert [flat[c] for c in ("destinations", "R3 asks", "steps / dest")] == \
        ["0", "—", "—"]


def test_a_holding_arm_that_never_chose_one_shows_no_mean_and_still_counts(tmp_path):
    """The mean is empty where there is nothing to average, and the count is 0
    rather than empty: 0 destinations is a reading, not a missing one."""
    from p3focus import cell as cellmod
    empty = tmp_path / "sliced_s7_killed"
    empty.mkdir()
    cellmod.write_manifest(empty / "manifest.json", arm="sliced", seed=7, steps=400,
                           server="s", model="m", grammar_ids=[])
    row = row_of(reader.table([reader.read_cell(empty)]), "sliced", 7)
    assert [row[c] for c in ("destinations", "R3 asks", "steps / dest")] == ["0", "0", "—"]


def test_a_cell_that_reached_nothing_shows_a_dash_for_its_first_errand_step(read):
    line = [l for l in reader.table(list(read.values())).splitlines()
            if l.startswith("| focus | 10 ")][0]
    assert line.split(" | ")[6] == "—"


def test_one_line_per_arm_counts_the_completed_cells_over_the_cells_run(read):
    tail = reader.table(list(read.values())).splitlines()[-3:]
    assert tail == ["- flat: 0/2 cells completed the errands",
                    "- focus: 1/2 cells completed the errands",
                    "- sliced: 0/1 cells completed the errands"]


def test_the_table_of_one_cell_is_a_table_of_one_cell(read):
    table = reader.table([read["focus_s7_completed"]])
    assert len([l for l in table.splitlines() if l.startswith("| focus")]) == 1
    assert table.splitlines()[-1] == "- focus: 1/1 cells completed the errands"


# --- the trajectory -------------------------------------------------------------

def test_the_map_marks_the_errand_cells_the_walk_and_the_spawn(made):
    grid = map_rows(reader.trajectory(made["focus_s7_completed"]))
    assert len(grid) == constants.WORLD_SIZE
    for index, (x, y) in enumerate(constants.ERRANDS[7]):
        assert grid[y][x] == str(index + 1)
    assert grid[32][37] == "#"                      # the walk east, step 15
    assert grid[40][30] == "#"                      # the walk west along y = 40
    assert grid[32][32] == "3"                      # seed 7's return cell IS the spawn
    assert grid[36][40] == "."                      # the cow's cell: never seen (R3)
    assert grid[31][45] == "."                      # stone is not walkable, so never seen
    assert grid[31][43] == ":"                      # seen from the walk, never stood on


def test_the_map_marks_where_the_body_died(made):
    grid = map_rows(reader.trajectory(made["flat_s10_died"]))
    assert grid[37][37] == "X"
    assert grid[32][32] == "3"     # the spawn is seed 10's return cell too
    assert grid[30][14] == "2"     # an errand cell the body never came near


def test_the_map_says_which_axis_it_is_in_and_what_the_marks_mean(made):
    head = reader.trajectory(made["focus_s7_completed"]).splitlines()[:5]
    text = "\n".join(head)
    assert "WORLD axis (+y down)" in text and "row 0 at the top" in text
    assert "[42, 23], [22, 39], [32, 31]" in text      # the note's cells, shown axis
    assert ". unseen" in text and "# walked" in text and "X died" in text
    assert "arm: focus" in text and "seed: 7" in text


def test_the_action_lines_are_the_first_and_the_last_twenty(made):
    lines = reader.trajectory(made["focus_s7_completed"]).splitlines()
    head = lines.index("actions (world axis; pos is pos_after): "
                       "step, action, pos, drink, health, focus_id")
    body = [l.strip() for l in lines[head + 1:]]
    assert len(body) == 41                     # twenty, a line saying what was dropped, twenty
    assert body[0] == "1, move_right, [33, 32], 3, 9, e1"
    assert body[19].startswith("20, move_right, [42, 32],")
    assert body[20] == "… 62 steps not shown …"
    assert body[-1] == "102, move_up, [32, 12], 0, 6, e4"
    # the meters the body actually read: on the sand the drink falls a step at a
    # time and reaches 0 at step 99, and health starts falling the step after
    assert body[-4] == "99, move_up, [32, 15], 0, 9, e3"
    assert body[-3] == "100, move_up, [32, 14], 0, 8, e1"


def test_a_short_cell_shows_every_step_and_says_nothing_was_dropped(made):
    lines = reader.trajectory(made["focus_s10_disagrees"]).splitlines()
    body = [l.strip() for l in lines if re.match(r"^\s*\d+, move_", l)]
    assert len(body) == 25
    assert not any("not shown" in l for l in lines)


def test_a_bare_arm_s_action_lines_say_none_where_a_focus_would_be(made):
    lines = reader.trajectory(made["flat_s10_died"]).splitlines()
    last = [l.strip() for l in lines if re.match(r"^\s*\d+, move_", l)][-1]
    assert last == "30, move_down, [37, 37], 3, 0, none"


# --- the command ----------------------------------------------------------------

def read_json_blocks(text):
    """Every JSON object printed one after another, in order."""
    decoder, out, i = json.JSONDecoder(), [], 0
    while i < len(text):
        if text[i] != "{":
            i += 1
            continue
        obj, end = decoder.raw_decode(text, i)
        out.append(obj)
        i = end
    return out


def test_main_prints_each_cell_s_summary_as_json_and_then_the_table(made, capsys):
    argv = [str(made["focus_s7_completed"]), str(made["flat_s10_died"])]
    assert reader.main(argv) == 0
    out = capsys.readouterr().out
    blocks = read_json_blocks(out.split("| arm |")[0])
    assert [b["cell_dir"] for b in blocks] == argv
    assert blocks[0]["errands_completed"] is True and blocks[1]["died"] is True
    assert "| arm | seed | errands completed |" in out
    assert "- focus: 1/1 cells completed the errands" in out


def test_main_trajectory_prints_the_map_and_not_the_table(made, capsys):
    assert reader.main(["--trajectory", str(made["focus_s7_completed"])]) == 0
    out = capsys.readouterr().out
    assert len(map_rows(out)) == constants.WORLD_SIZE
    assert "| arm | seed |" not in out


def test_main_trajectory_prints_one_map_per_cell(made, capsys):
    assert reader.main(["--trajectory", str(made["focus_s7_completed"]),
                        str(made["flat_s10_died"])]) == 0
    out = capsys.readouterr().out
    assert out.count("cell: ") == 2


def test_main_without_arguments_says_how_to_use_it(capsys):
    assert reader.main([]) == 3
    assert "usage: reader" in capsys.readouterr().err


def test_main_on_a_directory_that_is_not_a_cell_is_an_error(tmp_path, capsys):
    (tmp_path / "nothing_here").mkdir()
    assert reader.main([str(tmp_path / "nothing_here")]) == 3
    assert "manifest.json" in capsys.readouterr().err


def test_main_rejects_a_flag_it_does_not_know(made, capsys):
    assert reader.main(["--summary", str(made["flat_s10_died"])]) == 3
    assert "usage: reader" in capsys.readouterr().err
