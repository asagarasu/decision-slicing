"""One cell's directory and its files (A §4): `manifest.json`, `events.jsonl`,
`actions.jsonl`, `frames.jsonl`, `summary.json`; `calls.jsonl` is the client's
`CallLog`. Rows are sorted-key JSON, one a line, serialized before the file is
touched so a bad value never half-writes a line. Coordinates in every row are the
WORLD axis (+y down), A §4.
"""
import json
import subprocess
import time
from pathlib import Path

from p3focus import constants

#: A §4.2's event kinds and the fields each carries beside `step` and `kind`
EVENT_FIELDS = {
    "note_landed": (), "arrival": ("cell", "index"), "errands_completed": (),
    "drink_crossing": ("drink_from", "drink_to", "health_from", "health_to"),
    "stall_start": ("since_step", "length"), "stall_end": ("since_step", "length"),
    "death": (), "gate_fired": ("events",),
    "ops_applied": ("source", "ops", "list_after"), "ops_rejected": ("source", "ops", "reason"),
    "delete_confirmed": ("id",), "delete_declined": ("id",),
    "focus_chosen": ("id",), "focus_missing": ("reason",), "focus_none": ("reason",),
    "route": ("target", "first_step", "sentence_id"),
    "destination_chosen": ("cell",), "destination_reached": ("cell", "held_steps"),
    "destination_cleared": ("cell", "held_steps", "reason"),
    "reply_invalid": ("round", "attempt", "reason"), "reply_defaulted": ("round", "default"),
    "ops_in_acting_reply": ("round", "ops"), "conversation_trimmed": ("dropped_turns", "windows_omitted"),
}

#: A §4.3's action row keys
ACTION_KEYS = (
    "step", "arm", "action", "intent", "focus_id", "target", "destination", "route_first_step",
    "pos_before", "pos_after", "moved", "standing_on_after", "drink_after", "health_after",
    "list_size", "n_calls",
)


def cell_dir(out_parent, arm, seed):
    """`<out>/<arm>_s<seed>_<yyyymmddThhmmss>/`, created (A §4)."""
    stamp = time.strftime("%Y%m%dT%H%M%S", time.gmtime())
    path = Path(out_parent) / f"{arm}_s{seed}_{stamp}"
    path.mkdir(parents=True, exist_ok=False)
    return path


class JsonlLog:
    """Append-only JSON lines. `append` serializes first (sorted keys) and returns the row."""

    def __init__(self, path):
        self.path = Path(path)
        self.n_rows = 0
        # the file exists from the cell's first moment, so a cell with no rows of
        # a kind still has all six files (A §4) and a reader never guesses
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.touch()

    def append(self, row):
        line = json.dumps(row, sort_keys=True) + "\n"
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.path.open("a") as fh:
            fh.write(line)
        self.n_rows += 1
        return row


class EventLog(JsonlLog):
    """`events.jsonl` (A §4.2). A row must be a known kind with exactly its fields."""

    def event(self, step, kind, **fields):
        want = EVENT_FIELDS.get(kind)
        if want is None:
            raise ValueError(f"unknown event kind {kind!r}; A §4.2 lists {sorted(EVENT_FIELDS)}")
        if set(fields) != set(want):
            raise ValueError(f"{kind} carries {sorted(want)}, got {sorted(fields)}")
        return self.append({"step": int(step), "kind": kind, **fields})


class ActionLog(JsonlLog):
    """`actions.jsonl` (A §4.3): one row per world step, exactly `ACTION_KEYS`."""

    def action(self, **row):
        if set(row) != set(ACTION_KEYS):
            missing = [k for k in ACTION_KEYS if k not in row]
            spare = sorted(set(row) - set(ACTION_KEYS))
            raise ValueError(f"an actions.jsonl row carries A §4.3's keys; missing {missing}, spare {spare}")
        return self.append(row)


class FrameLog(JsonlLog):
    """`frames.jsonl` (A §4.4): one frame per step, frame 0 first, no gaps."""

    def frame(self, frame):
        if int(frame["step"]) != self.n_rows:
            raise RuntimeError(f"frames.jsonl expects step {self.n_rows}, got {frame['step']}")
        return self.append(frame)


def code_sha():
    """The repo's HEAD, for the manifest; 'unknown' outside a checkout."""
    try:
        return subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=Path(__file__).parent,
                                       stderr=subprocess.DEVNULL, text=True).strip()
    except Exception:
        return "unknown"


def write_manifest(path, arm, seed, steps, server, model, grammar_ids):
    """`manifest.json` (A §4.4): every constant a reader might otherwise guess."""
    body = {
        "arm": arm, "seed": int(seed), "steps": int(steps), "model": model, "server": server,
        "code_sha": code_sha(), "started_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "errand_cells": [list(c) for c in constants.ERRANDS[int(seed)]],
        "note_step": constants.NOTE_STEP, "k_history": constants.K_HISTORY,
        "stall_length": constants.STALL_LENGTH, "drink_crossing_at": constants.DRINK_CROSSING_AT,
        "chat_budget_tokens": constants.CHAT_BUDGET_TOKENS, "chat_keep_turns": constants.CHAT_KEEP_TURNS,
        "max_tokens": constants.MAX_TOKENS, "timeout_s": constants.TIMEOUT_S,
        "max_ops_per_reply": constants.MAX_OPS_PER_REPLY, "r3_candidates": constants.R3_CANDIDATES,
        "grammar_ids": list(grammar_ids), "frame_schema_version": constants.FRAME_SCHEMA_VERSION,
    }
    Path(path).write_text(json.dumps(body, sort_keys=True, indent=1) + "\n")
    return body


def write_summary(path, body):
    """`summary.json` (A §4.4); the caller builds the body, this writes it sorted."""
    Path(path).write_text(json.dumps(body, sort_keys=True, indent=1) + "\n")
    return body
