# Reproducing the three figures

`src/p3focus/figures.py` reads the canonical run logs and regenerates the demo's
three figures. Every number is recomputed from the logs; nothing is hard-coded
except the identifiers of the cells the cost figures sample (verified, below).

## The figures

| file | what it shows |
|---|---|
| `A_grid.png` | the 9B result as a 4-arm x 5-seed grid of errand cells reached — the clean single-model picture |
| `T1_ladder.png` | the full 2B -> 35B ladder across the four arms (chains and cells), plus a token-cost sidebar |
| `T2_cost.png` | cost against task length for one 9B run per arm (chat vs focus): O(1) vs O(n) per step |

## Dependency and environment

The figures need **matplotlib** (nothing else in this repo does), declared as a
`figures` extra. numpy is already a core dependency. Rendering is headless
(`matplotlib.use("Agg")`).

    python3.12 -m venv generated/venv
    generated/venv/bin/pip install "matplotlib==3.11.2" "numpy==2.5.3"
    # or, with the repo installed:  pip install -e ".[figures]"

## Running

    PYTHONPATH=src generated/venv/bin/python -m p3focus.figures \
        --runs /path/to/runs --out generated/figures

- `--runs` points at the directory of run cells (`{arm}_s{seed}_{timestamp}/`);
  the specific cells used are named in `src/p3focus/canonical_runs.json`.
- `--out` is where the three PNGs are written (default `generated/figures`).
- `--canonical` overrides the pinned `canonical_runs.json` (default: the packaged
  one).
- `--verify` recomputes the grid, prints it, asserts the pinned results, and
  exits **without** rendering. If any pin fails the command exits non-zero and
  renders nothing — the figures are never drawn from numbers that do not
  reproduce the pins. A pinned run missing under `--runs` also fails loudly.

## Canonical-run selection

The grid is sizes x arms x seeds, one run per cell. The exact run directory for
every cell is **pinned** in `src/p3focus/canonical_runs.json` (package data):
`size -> arm -> seed -> {run, chains, cells}`. The figures read it verbatim and
do not infer a run from a manifest or a timestamp.

- **Sizes** 2B, 4B, 9B, 27B, 35B-A3B. **Seeds** 7, 10, 11, 12, 13.
  **Arms** flat, chat, sliced, focus.
- Per cell: chains = 1 if the errands completed else 0; cells = errand cells
  reached (0-3). Aggregated over the 5 seeds as chains/5 and cells/15. The grid
  values go through the ported reader (`reader.read_cell`), which recomputes a
  cell's numbers from its rows rather than trusting its `summary.json`; `--verify`
  then checks each recomputed cell against the number the pin records for it, and
  each aggregate against the targets below.

### Why a pinned list, not a sizing rule

flat / sliced / focus runs name their model in `manifest.json["model"]` (e.g.
`.../Qwen3.5-9B-...gguf -> 9B`) and could be selected by that. **chat runs
cannot** — their `manifest["model"]` is `"local"`. An earlier version sized chat
by wall time (a bigger model is slower), which is **wrong**: the 09-27
Qwen3.5-4B backfill chat runs take ~25 min, the same band as the 09-24 9B panel,
so wall time cannot separate a 4B chat run from a 9B one — the 4B runs leaked
into the 9B bucket and inflated 9B chat's errand-cells count above the correct
2|6. Each chat run's size is authoritative from the **launch log** — which loop launched
it, hence which model — and `canonical_runs.json` records that result for every
cell, chat and trace arm alike. With the pin, every cell (chat included)
reproduces the first-pass figures exactly.

## Recompute vs. pinned results

`--verify` recomputes every cell from its rows and checks it twice: against the
per-cell numbers in `canonical_runs.json` (all 100 cells match) and against the
aggregate targets below. `chains|cells`, over 5 seeds:

| model | flat | chat | sliced | focus |
|---|---|---|---|---|
| Qwen3.5-2B | 0\|0 | 0\|1 | 0\|0 | 0\|0 |
| Qwen3.5-4B | 0\|1 | 1\|8 | 1\|7 | 0\|3 |
| **Qwen3.5-9B** | **0\|1** | **2\|6** | **2\|10** | **4\|13** |
| Qwen3.5-27B | 4\|13 | 5\|15 | 5\|15 | 5\|15 |
| Qwen3.5-35B-A3B | 3\|12 | 4\|13 | 5\|15 | 4\|14 |

All 20 aggregate pins match (ALL PINS MATCH): 2B 0\|0 / 0\|1 / 0\|0 / 0\|0;
4B 0\|1 / 1\|8 / 1\|7 / 0\|3; 9B 0\|1 / 2\|6 / 2\|10 / 4\|13;
27B 4\|13 / 5\|15 / 5\|15 / 5\|15; 35B-A3B 3\|12 / 4\|13 / 5\|15 / 4\|14.

## The cost metric (T2 and the T1 sidebar)

Per model call the server reports `tokens.prompt` (the whole prompt it saw) and
`elapsed_s`. The cost figures plot, within each 100-step task-length bucket, the
mean **per call**: total prompt tokens over the calls in the bucket divided by the
number of calls, and likewise for seconds. For chat there is one call per step,
so "per call" is "per step"; a trace arm issues several round-pages (calls) per
step, so its plotted value is the size of one decision page (this is the
"~1.7k tokens/step" of the write-up).

The cost figures sample one 9B run per arm (n = 1), fixed by identifier because
they reproduce the first-pass cost figure's labels exactly:

    T2 chat   = chat_s11_20260924T181638     (23,295 -> 89,857 tokens/call)
    T2 focus  = focus_s7_20260924T170858     (~1.7k tokens/call, flat)
    T1 sidebar trace arm = sliced_s7_20260924T172418   (~1.8k, flat)

`figures.novel_prompt_tokens` additionally ports the cache-aware "novel tokens"
estimate from the research tool `tools/token_metrics_99.py` (what each request
adds past the server's reused prefix). It is available for cross-checks; the
headline figures plot the per-call prompt size, because that is the O(1)-vs-O(n)
signal the figure makes.

## Colours

Colours are the data-viz reference palette, used verbatim: a single-hue blue
sequential ramp for the heatmap fills (magnitude = cells, or chains), and for the
two cost series the reference categorical slots 1 (blue, focus) and 2 (orange,
chat). The sequential ramp is lightness-ordered and so colour-vision-deficiency
safe by construction; the blue/orange pair is one the reference certifies.

## Output

`generated/figures/A_grid.png`, `T1_ladder.png`, `T2_cost.png`. `generated/` is
regenerable and git-ignored; the PNGs are not committed.

## Release bundle: the run data

The run data is **not** in this repository; the 100 canonical run directories (named in
`src/p3focus/canonical_runs.json`) are bundled with the GitHub *release*. Download that
archive, unpack it, and point `--runs` at the unpacked `runs/` directory to reproduce the
figures. The bundle carries the `.jsonl`/`.json` run files the figures consume.
