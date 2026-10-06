"""A §5's command, through `subprocess`: `python -m p3focus run …`.

The cell is driven by `--policy scripted:`, so nothing here contacts a server.
`run_focus_s7_12.jsonl` was produced by the same twelve-step focus cell run in
process and dumped in call order; every line names its round, which the runner
asserts against the round it is answering, so a change in the order of rounds
fails here loudly instead of quietly answering the wrong question.
"""
import json
import pathlib
import subprocess
import sys

from p3focus import cell, client as client_mod, constants, trace

ROOT = pathlib.Path(__file__).resolve().parents[1]          # src/
FIXTURE = pathlib.Path(__file__).resolve().parent / "fixtures" / "run_focus_s7_12.jsonl"
STEPS = 12
SEED = 7


def _run(args, cwd=None):
    """`python -m p3focus …` with src/ on the path, as the drivers run it."""
    env = {"PYTHONPATH": str(ROOT), "PATH": "/usr/bin:/bin"}
    return subprocess.run([sys.executable, "-m", "p3focus", *args], cwd=cwd or str(ROOT),
                          env=env, capture_output=True, text=True)


def _cell_of(out):
    found = [p for p in pathlib.Path(out).iterdir() if p.is_dir()]
    assert len(found) == 1, found
    return found[0]


def _rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def test_the_command_runs_a_cell_and_writes_a_4s_six_files(tmp_path):
    out = tmp_path / "runs"
    done = _run(["run", "--arm", "focus", "--seed", str(SEED), "--steps", str(STEPS),
                 "--policy", f"scripted:{FIXTURE}", "--out", str(out), "--quiet"])
    assert done.returncode == 0, done.stderr
    cell_dir = _cell_of(out)
    assert cell_dir.name.startswith(f"focus_s{SEED}_")
    assert done.stdout.strip().endswith(cell_dir.name)
    assert {p.name for p in cell_dir.iterdir()} == {
        "manifest.json", "calls.jsonl", "events.jsonl", "actions.jsonl",
        "frames.jsonl", "summary.json"}

    calls = _rows(cell_dir / "calls.jsonl")
    assert len(calls) == len(FIXTURE.read_text().splitlines())
    assert [c["round"] for c in calls] == [json.loads(line)["round"]
                                           for line in FIXTURE.read_text().splitlines()]
    for i, call in enumerate(calls, 1):
        assert set(call) == set(client_mod.CALL_ROW_KEYS)
        assert call["call_no"] == i and call["prefix_sha256"] is None

    actions = _rows(cell_dir / "actions.jsonl")
    assert [a["step"] for a in actions] == list(range(1, STEPS + 1))
    assert all(set(a) == set(cell.ACTION_KEYS) for a in actions)

    frames = _rows(cell_dir / "frames.jsonl")
    assert [f["step"] for f in frames] == list(range(0, STEPS + 1))

    events = _rows(cell_dir / "events.jsonl")
    assert all({"step", "kind"} <= set(e) for e in events)
    assert "note_landed" in {e["kind"] for e in events}

    manifest = json.loads((cell_dir / "manifest.json").read_text())
    assert manifest["arm"] == "focus" and manifest["steps"] == STEPS
    assert manifest["grammar_ids"] == list(trace.ARM_ROUNDS["focus"])
    assert manifest["server"] == f"scripted:{FIXTURE}"

    summary = json.loads((cell_dir / "summary.json").read_text())
    assert summary["steps_survived"] == STEPS and summary["n_calls"] == len(calls)


def test_the_console_line_is_one_a_step_unless_quiet(tmp_path):
    loud = _run(["run", "--arm", "focus", "--seed", str(SEED), "--steps", str(STEPS),
                 "--policy", f"scripted:{FIXTURE}", "--out", str(tmp_path / "loud")])
    assert loud.returncode == 0, loud.stderr
    step_lines = [ln for ln in loud.stdout.splitlines() if ln.startswith("step ")]
    assert len(step_lines) == STEPS


def test_a_bad_argument_is_exit_3(tmp_path):
    for args in (["run", "--arm", "nope", "--seed", "7", "--steps", "2",
                  "--out", str(tmp_path / "a")],
                 ["run", "--arm", "focus", "--seed", "99", "--steps", "2",
                  "--out", str(tmp_path / "b")],
                 ["run", "--arm", "focus", "--seed", "7", "--out", str(tmp_path / "c")],
                 ["run", "--arm", "focus", "--seed", "7", "--steps", "2",
                  "--out", str(tmp_path / "d"), "--far-target"],
                 ["fly", "--arm", "focus"]):
        done = _run(args)
        assert done.returncode == 3, (args, done.returncode, done.stderr)


def test_a_policy_file_that_runs_out_names_the_call_it_owed(tmp_path):
    short = tmp_path / "short.jsonl"
    short.write_text(FIXTURE.read_text().splitlines()[0] + "\n")
    done = _run(["run", "--arm", "focus", "--seed", str(SEED), "--steps", "3",
                 "--policy", f"scripted:{short}", "--out", str(tmp_path / "out"), "--quiet"])
    assert done.returncode == 3
    assert "ran out of replies" in done.stderr and "R4" in done.stderr


def test_a_policy_line_that_names_the_wrong_round_is_refused(tmp_path):
    wrong = tmp_path / "wrong.jsonl"
    wrong.write_text(json.dumps({"round": "R1", "reply": '{"maintain": "no"}'}) + "\n")
    done = _run(["run", "--arm", "focus", "--seed", str(SEED), "--steps", "1",
                 "--policy", f"scripted:{wrong}", "--out", str(tmp_path / "out"), "--quiet"])
    assert done.returncode == 3
    assert "round 'R3'" in done.stderr or 'round "R3"' in done.stderr


def test_a_reply_with_a_line_separator_in_it_is_one_line_of_the_file(tmp_path):
    """JSON takes U+2028 raw inside a string, and a reply copied out of a real
    transcript can carry one; `str.splitlines` ends a line there, which would
    make one reply two lines, neither of them JSON. Written raw
    (`ensure_ascii=False`), it loads as the one reply it is."""
    from p3focus import run as run_mod
    row = {"round": "R3", "reply": '{"why": "east of the lake\u2028then south"}'}
    policy = tmp_path / "separator.jsonl"
    policy.write_text(json.dumps(row, ensure_ascii=False) + "\n")
    assert "\u2028" in policy.read_text()        # the character itself, not its escape
    assert run_mod.load_policy(f"scripted:{policy}").rows == [row]


def test_a_server_failure_that_survives_the_retry_is_exit_2(tmp_path):
    # no server listens on this port, so the client's one retry fails too (A §6)
    done = _run(["run", "--arm", "focus", "--seed", str(SEED), "--steps", "1",
                 "--server", "http://127.0.0.1:9", "--out", str(tmp_path / "out"), "--quiet"])
    assert done.returncode == 2, done.stderr
    assert "model server failed" in done.stderr


def test_the_only_flags_are_a_5s():
    """A §5: "Nothing else is a flag." """
    import argparse

    from p3focus import run as run_mod
    parser = run_mod.build_parser()
    sub = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)][0]
    assert set(sub.choices) == {"run"}
    flags = {option for action in sub.choices["run"]._actions
             for option in action.option_strings if option.startswith("--")}
    assert flags == {"--help", "--arm", "--seed", "--steps", "--server", "--out",
                     "--policy", "--quiet"}


def test_every_arm_the_command_offers_is_a_5s():
    assert set(constants.ARMS) == {"flat", "focus", "chat", "sliced"}
    assert set(trace.ARMS) | {"chat"} == set(constants.ARMS)
