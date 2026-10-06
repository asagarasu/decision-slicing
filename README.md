# p3focus

A small cognitive-control experiment. A Crafter gridworld "body" — a model driving a
64×64 survival world through four move actions — runs a short chain of errands while a
standing map-the-surface task is pushed aside. The same body, the same world, and the
same information are given to four **arms**; the arms differ only in how a single step's
decision is produced. The question is whether structuring that decision lets a small
model finish the errand chain where a single undifferentiated pass does not.

## The four arms

All four see the same world state every step (the 9×9 window, meters, position, recent
history). They differ only in how the step's decision is formed:

- **flat** — one forward pass per step. The motivation list is on the page, and one
  reply carries any list edits, a destination, and the action. The control for layering.
- **chat** — the everyday conversational loop: the body is told the task once, in a
  system message, and the whole conversation is kept and re-sent each turn.
- **sliced** — the decision is split into single-purpose rounds, but the whole motivation
  list stays visible (read-only) while acting.
- **focus** — the same slicing as sliced, plus one extra round that chooses a single
  entry to act under, so the acting rounds see only that one entry. The treatment.

The errand task arrives mid-run as a note (at step 10): fetch two items at named cells
and return with both. "Errands completed" and "errand cells reached (0–3)" are the
primary measures. See `docs/methods.md` for the full design.

## Layout

    src/p3focus/        the package: world, gate, route hint, controllers, reader, figures
    src/vendor/crafter/ the patched Crafter substrate (vendored, MIT; see LICENSE.crafter)
    src/tests/          the test suite
    design/             the interface and page specifications the code is built to
    docs/methods.md     a concise description of the experiment
    REPRODUCE.md        how the three figures are regenerated
    generated/REBUILD.md  how to build the venv and what is pinned

## Setup

Python 3.12 (`requires-python >=3.12,<3.13`). The exact dependency pins and the vendored
Crafter provenance are in `generated/REBUILD.md`, which is authoritative. In short:

    python3.12 -m venv generated/venv
    generated/venv/bin/pip install -e ".[test,figures]"

The package uses a `src/` layout; `src/p3focus/world.py` puts `src/vendor/` on `sys.path`
at import time, so the vendored Crafter is used in place and is never pip-installed.

## Running a cell

One "cell" is one arm × one seed × N steps, against a local llama.cpp server:

    PYTHONPATH=src generated/venv/bin/python -m p3focus run \
        --arm {flat,focus,chat,sliced} --seed 7 --steps 400 \
        --server http://127.0.0.1:8080 --out runs/

A cell writes one directory under `--out` with its logs (`calls.jsonl`, `events.jsonl`,
`actions.jsonl`, `frames.jsonl`, `manifest.json`, `summary.json`). Replies can also be
scripted from a file (`--policy scripted:<file>`) to run without a server. The full flag
list is in `design/interfaces.md` §5.

## Reading results

    PYTHONPATH=src generated/venv/bin/python -m p3focus read <cell_dir>...

The reader recomputes each cell's numbers from its rows (rather than trusting
`summary.json`) and prints a per-cell summary and a seed × arm table.

## Reproducing the figures

    PYTHONPATH=src generated/venv/bin/python -m p3focus.figures \
        --runs /path/to/runs --out generated/figures

The figure code reads the pinned `src/p3focus/canonical_runs.json` — the exact run
directory for every grid cell — and recomputes every plotted number from the logs.
`--verify` recomputes and checks the pinned results without rendering. `REPRODUCE.md`
has the full procedure, the pinned aggregate results, and the cost metric.

## Tests

    PYTHONPATH=src generated/venv/bin/python -m pytest src/tests -q -n 4

## Results, briefly

This is a small-n probe (five seeds per arm), not a proof. On the 9B model, the arms that
structure the decision finish more of the errand chain and reach more errand cells than
flat or chat; `focus` finishes the most. The cost picture is the other half: a plain
kept conversation's prompt grows with the task (its per-call token count climbs as the
history accumulates), while the sliced arms pay a roughly constant per-step page size.
The exact per-model numbers are in `REPRODUCE.md`.
