"""The cell's files carry A §4's rows and refuse others."""
import json

import pytest

from p3focus import cell


def test_events_take_known_kinds_with_exactly_their_fields(tmp_path):
    log = cell.EventLog(tmp_path / "events.jsonl")
    log.event(11, "gate_fired", events=["note_landed"])
    log.event(12, "route", target=[42, 40], first_step="move_right", sentence_id=3)
    with pytest.raises(ValueError):
        log.event(1, "gate_fired")                       # missing a field
    with pytest.raises(ValueError):
        log.event(1, "route", target=[1, 1], first_step=None, sentence_id=1, extra=1)
    with pytest.raises(ValueError):
        log.event(1, "steered")                          # not a kind
    rows = [json.loads(l) for l in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert [r["kind"] for r in rows] == ["gate_fired", "route"] and rows[0]["step"] == 11


def test_actions_carry_exactly_a_4_3s_keys(tmp_path):
    log = cell.ActionLog(tmp_path / "actions.jsonl")
    row = {k: None for k in cell.ACTION_KEYS}
    row.update(step=0, arm="focus", action="move_right", moved=True, list_size=1, n_calls=2)
    log.action(**row)
    with pytest.raises(ValueError):
        log.action(**{k: v for k, v in row.items() if k != "n_calls"})


def test_frames_refuse_a_gap(tmp_path):
    log = cell.FrameLog(tmp_path / "frames.jsonl")
    log.frame({"step": 0}); log.frame({"step": 1})
    with pytest.raises(RuntimeError):
        log.frame({"step": 3})


def test_the_manifest_copies_every_constant(tmp_path):
    body = cell.write_manifest(tmp_path / "manifest.json", "focus", 7, 400, "http://x", "m", ["R1"])
    on_disk = json.loads((tmp_path / "manifest.json").read_text())
    assert on_disk == body
    assert body["errand_cells"] == [[42, 40], [22, 24], [32, 32]]
    for key in ("k_history", "stall_length", "note_step", "max_tokens", "timeout_s",
                "chat_budget_tokens", "chat_keep_turns", "grammar_ids", "code_sha"):
        assert key in body


def test_cell_dir_names_arm_and_seed(tmp_path):
    path = cell.cell_dir(tmp_path, "flat", 10)
    assert path.is_dir() and path.name.startswith("flat_s10_")
