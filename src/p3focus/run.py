"""The command that runs one cell (A §5).

    python -m p3focus run --arm {flat,focus,chat,sliced} --seed 7 --steps 400 \\
                          --server http://127.0.0.1:8080 --out runs/
    python -m p3focus run --arm focus --seed 7 --steps 40 \\
                          --policy scripted:tests/fixtures/x.jsonl --out /tmp/x

Nothing else is a flag (A §5, D8): K, the stall length, the note step, the token
caps and the timeouts are `constants.py`'s and are copied into the manifest.

Exit 0 on completion, death included; 2 on a server failure that survives the
client's retry; 3 on bad arguments — which includes a `--policy` file that runs
out of lines, because the file is an argument and a cell cannot be finished
without it.

No coordinate reaches this module: it parses flags, builds a client and hands
the cell to a controller.
"""

import argparse
import json
import sys
from pathlib import Path

from p3focus import client as client_mod, constants, trace

POLICY_PREFIX = "scripted:"


class BadArguments(Exception):
    """A §5's exit 3."""


class _Parser(argparse.ArgumentParser):
    """argparse, with A §5's exit code for a bad argument instead of its own."""

    def error(self, message):
        """A §5: a bad argument is exit 3, not argparse's own 2."""
        raise BadArguments(message)


def build_parser():
    """A §5's flags, and no others."""
    parser = _Parser(prog="python -m p3focus", add_help=True, allow_abbrev=False)
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("run", help="run one cell", allow_abbrev=False)
    run.add_argument("--arm", required=True, choices=list(constants.ARMS))
    run.add_argument("--seed", required=True, type=int, choices=list(constants.SEEDS))
    run.add_argument("--steps", required=True, type=int)
    run.add_argument("--server", default=constants.SERVER_DEFAULT)
    run.add_argument("--out", required=True)
    run.add_argument("--policy", default=None,
                     help=f"{POLICY_PREFIX}<file>: replies from a file, in call order")
    run.add_argument("--quiet", action="store_true")
    return parser


class PolicyExhausted(BadArguments):
    """A §5: a scripted file that runs out of lines, naming the call it owed."""


class ScriptedPolicy:
    """A §5's `--policy scripted:FILE`, read into a callable.

    The file is JSON lines, one object per model call **in call order**:
    `{"reply": "<text>"}`, optionally `{"round": "R1", "reply": …}`, which is
    asserted against the round the call is answering. The controller announces
    that round through `set_round` before each call; a line with no `round` is
    taken as written.
    """

    def __init__(self, rows, name):
        self.rows = list(rows)
        self.name = name
        self.i = 0
        self.round = None

    def expect(self, round_id):
        """The round the next call answers (A §5: the runner asserts a line's
        `round` against it); the controller announces it before each call."""
        self.round = round_id

    def __call__(self, messages):
        if self.i >= len(self.rows):
            raise PolicyExhausted(
                f"{self.name} ran out of replies: call {self.i + 1} answers round "
                f"{self.round!r} and the file has {len(self.rows)} lines")
        row = self.rows[self.i]
        self.i += 1
        want = row.get("round")
        if want is not None and self.round is not None and want != self.round:
            raise BadArguments(
                f"{self.name} line {self.i} says round {want!r}, but call {self.i} answers "
                f"round {self.round!r}")
        return row["reply"]


class ScriptedRunClient(client_mod.ScriptedClient):
    """`ScriptedClient` plus the two things A §5's file wants: the round hook
    the policy asserts on, and a `server` the manifest can print, so a scripted
    cell can never be read as a live one."""

    def __init__(self, policy):
        super().__init__(policy)
        self.server = f"{POLICY_PREFIX}{policy.name}"

    def set_round(self, round_id):
        """The controller's announcement of the round this call answers (A §5)."""
        self.policy.expect(round_id)


def load_policy(spec):
    """Read A §5's `--policy scripted:FILE` into a `ScriptedPolicy`."""
    if not spec.startswith(POLICY_PREFIX):
        raise BadArguments(f"--policy takes {POLICY_PREFIX}<file>, got {spec!r}")
    path = Path(spec[len(POLICY_PREFIX):])
    try:
        text = path.read_text()
    except OSError as err:
        raise BadArguments(f"--policy file {path}: {err}") from None
    rows = []
    for n, line in enumerate(text.split("\n"), 1):
        if not line.strip():
            continue
        try:
            row = json.loads(line)
        except ValueError as err:
            raise BadArguments(f"{path} line {n} is not JSON: {err}") from None
        if not isinstance(row, dict) or not isinstance(row.get("reply"), str):
            raise BadArguments(f'{path} line {n} needs a "reply" string')
        rows.append(row)
    if not rows:
        raise BadArguments(f"{path} has no replies")
    return ScriptedPolicy(rows, str(path))


def build_client(args):
    """The client one cell runs on (A §5, §6): the scripted file, or the
    server."""
    if args.policy is not None:
        return ScriptedRunClient(load_policy(args.policy))
    return client_mod.Client(server=args.server)


def run_cell(args):
    """One cell, dispatched by arm (A §5). Returns the cell's directory."""
    client = build_client(args)
    if args.arm == "chat":
        from p3focus import chat
        return chat.run_chat_cell(args.seed, args.steps, client, args.out, args.quiet).dir
    cell_dir, _ = trace.run_trace_cell(args.arm, args.seed, args.steps, client, args.out,
                                       quiet=args.quiet)
    return cell_dir


def main(argv=None):
    """A §5's exit codes: 0 done, 2 a server failure, 3 a bad argument.
    `python -m p3focus read <cell_dir>...` hands the rest to the reader."""
    argv = list(sys.argv[1:] if argv is None else argv)
    if argv[:1] == ["read"]:
        from p3focus import reader
        return reader.main(argv[1:])
    try:
        args = build_parser().parse_args(argv)
        if args.steps < 0:
            raise BadArguments("--steps is a count of world steps, so it is not negative")
        out = run_cell(args)
    except BadArguments as err:
        print(f"p3focus: {err}", file=sys.stderr)
        return 3
    except client_mod.ClientError as err:
        print(f"p3focus: the model server failed: {err}", file=sys.stderr)
        return 2
    print(out)
    return 0
