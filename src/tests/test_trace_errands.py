"""The rows a finished errand writes, and the event line an arrival puts on R1.

A focus cell that walks to both visits and back to the meeting place
(`fixtures/errand_run.py`), so `arrival`, `errands_completed` and the summary's
`after_errands` are read off a real run rather than asserted about in the
abstract. Arrivals are the second thing the gate opens on (A §4.2), so this is
also where B §3.1's arrival line is seen on a page.
"""
import functools
import json
import pathlib
import tempfile

from fixtures import errand_run, scripted as s
from p3focus import axis, constants, pages, trace


@functools.lru_cache(maxsize=1)
def run():
    plan = errand_run.plan()
    defaults = {"R1": s.r1_no(), "R1.5": s.r1_5(False), "R2": s.r2("e1"),
                "R3": s.r3(), "R4": s.r4("move_up")}
    script = s.Script(defaults, plan)
    out = tempfile.mkdtemp(prefix="p3focus_errands_")
    cell_dir, summary = trace.run_trace_cell(
        "focus", errand_run.SEED, errand_run.steps(), s.ScriptedClient(script), out, quiet=True)
    return cell_dir, summary


def _rows(name):
    return [json.loads(line)
            for line in (pathlib.Path(run()[0]) / name).read_text().splitlines()]


def test_each_errand_cell_writes_one_arrival_in_the_world_axis():
    arrivals = [e for e in _rows("events.jsonl") if e["kind"] == "arrival"]
    assert [a["index"] for a in arrivals] == [0, 1, 2]
    assert [tuple(a["cell"]) for a in arrivals] == list(constants.ERRANDS[errand_run.SEED])
    assert all(a["step"] > constants.NOTE_STEP for a in arrivals)
    # one row per cell, never a second on a re-crossing (A §4.2)
    assert len({a["index"] for a in arrivals}) == len(arrivals)


def test_the_return_completes_the_errands_and_says_so_once():
    events = _rows("events.jsonl")
    done = [e for e in events if e["kind"] == "errands_completed"]
    assert len(done) == 1
    arrivals = [e for e in events if e["kind"] == "arrival"]
    assert done[0]["step"] == arrivals[-1]["step"]
    assert run()[1]["errands_completed"] is True
    assert run()[1]["cells_reached"] == 3


def test_an_arrival_opens_the_next_steps_r1_with_b_3_1s_line():
    arrivals = [e for e in _rows("events.jsonl") if e["kind"] == "arrival"]
    step = arrivals[0]["step"]
    gate = [e for e in _rows("events.jsonl")
            if e["kind"] == "gate_fired" and e["step"] == step]
    assert gate and "arrival" in gate[0]["events"]
    page = [c["prompt"] for c in _rows("calls.jsonl")
            if c["round"] == "R1" and c["step"] == step + 1][0]
    assert pages.event_line_arrival(arrivals[0]["cell"]) in page
    # the line is the shown axis, the row the world's (A §1.1, §4)
    shown = axis.shown_pos(arrivals[0]["cell"])
    assert f"You are standing on [{shown[0]}, {shown[1]}]" in page


def test_the_summary_measures_what_happened_after_the_errands():
    summary = run()[1]
    after = summary["after_errands"]
    assert after["steps"] == errand_run.EXTRA_STEPS
    assert after["new_cells_seen"] >= 0
    assert len(after["focus_ids"]) == errand_run.EXTRA_STEPS
    assert summary["first_errand_step"] == min(
        e["step"] for e in _rows("events.jsonl") if e["kind"] == "arrival")
    assert summary["note_to_first_errand_steps"] == \
        summary["first_errand_step"] - constants.NOTE_STEP


def test_the_reader_can_re_derive_the_arrivals_from_the_frames():
    """A §1.1's check: positions in `frames.jsonl` reproduce the ledger."""
    frames = {f["step"]: tuple(f["player"]["pos"]) for f in _rows("frames.jsonl")}
    for arrival in [e for e in _rows("events.jsonl") if e["kind"] == "arrival"]:
        assert frames[arrival["step"]] == tuple(arrival["cell"])
