#!/usr/bin/env python3.12
"""Regenerate the demo's three figures from the canonical runs.

    python -m p3focus.figures --runs /path/to/runs --out generated/figures

Three figures are written as PNGs (see the demo write-up, demo_description §2/§4):

  A_grid.png   The 9B result as a 4-arm x 5-seed grid of errand cells reached.
               The clean, self-contained single-model picture.
  T1_ladder.png  The full 2B -> 35B ladder across the four arms (chains and
               errand cells), plus a token-cost sidebar: small models rescued by
               structure, large models passing the easy task cold at exploding
               cost.
  T2_cost.png  Cost against task length for one 9B run per arm: the trace arms
               stay ~constant per step while a plain conversation climbs
               (O(1) vs O(n)).

EVERY number is recomputed from the run logs; nothing is hard-coded except the
identifiers of the cells the cost figures sample (which are verified, below).
The grid numbers go through the ported `reader` (reader.read_cell), so a cell's
own summary.json is recomputed from its rows rather than believed.

CANONICAL-RUN SELECTION (A §5's grid: sizes x arms x seeds, one run per cell).

  Sizes   2B, 4B, 9B, 27B, 35B-A3B        Seeds   7, 10, 11, 12, 13
  Arms    flat, chat, sliced, focus       Run dir {arm}_s{seed}_{YYYYMMDDTHHMMSS}

  The exact run directory for every cell is PINNED in `canonical_runs.json`
  (package data, beside this module): size -> arm -> seed -> {run, chains,
  cells}. The figures read it verbatim and do not infer a run from a manifest or
  a timestamp. The grid's numbers are still recomputed from the chosen cell's
  rows by `reader.read_cell` and then checked against the pin.

  Why a pinned list rather than a rule. flat / sliced / focus runs carry their
  model in manifest.json["model"] and could be selected by that; chat runs cannot
  -- manifest["model"] is "local". An earlier version sized chat by wall time,
  which is WRONG: the 09-27 Qwen3.5-4B backfill chat runs (~25 min) fall in the
  same band as the 09-24 9B panel, so wall time cannot separate a 4B chat run
  from a 9B one and the 4B runs leaked into the 9B bucket (inflating 9B chat).
  Each chat run's size is fixed instead by the LAUNCH LOG -- which loop launched
  it, hence which model -- and `canonical_runs.json` records that authoritative
  result for every cell, chat and trace arm alike.

  Per cell: chains = 1 if the errands were completed else 0; cells = errand
  cells reached (0-3). A cell is aggregated over its 5 seeds as chains/5 and
  cells/15.

COST METRIC (T2 and the T1 sidebar). Per model call the server reports
tokens.prompt (the whole prompt it saw) and elapsed_s. The figures plot, within
each 100-step task-length bucket, the mean PER CALL: total prompt tokens over the
calls in the bucket divided by the number of calls, and likewise for seconds.
For chat there is one call per step, so "per call" is "per step"; a trace arm
issues several round-pages (calls) per step, so the plotted quantity is the size
of one decision page. This is the quantity the demo write-up calls "~1.7k
tokens/step". `novel_prompt_tokens` additionally ports the cache-aware "novel
tokens" estimate from the research tool `tools/token_metrics_99.py`: it is the
more careful cost measure (what each request adds past the server's reused
prefix) and is available for cross-checks, but the headline per-call prompt size
is what the figures draw, because that is the O(1)-vs-O(n) signal.

PALETTE. Colours are the data-viz reference instance (the `dataviz` skill's
`references/palette.md`), used verbatim: a single-hue blue sequential ramp for
the heatmap fills (magnitude = cells, or chains), and for the two cost series the
reference categorical slots 1 (blue) and 2 (orange). The sequential ramp is
lightness-ordered and so colour-vision-deficiency-safe by construction; the
blue/orange categorical pair is one the reference file certifies (its first three
slots clear the all-pairs CVD separation floor in both light and dark).
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # headless: render to file, never to a display
import matplotlib.pyplot as plt  # noqa: E402
from matplotlib.patches import FancyBboxPatch, Rectangle  # noqa: E402

from p3focus import reader  # noqa: E402

# -- the experiment grid -------------------------------------------------------

SIZES = ["2B", "4B", "9B", "27B", "35B-A3B"]
SEEDS = [7, 10, 11, 12, 13]
#: Display names for the size rows (the ladder labels the model, not the bare size).
SIZE_LABEL = {s: f"Qwen3.5-{s}" for s in SIZES}

#: The cells the cost figures sample -- one 9B run per arm (n = 1), chosen because
#: they reproduce the first-pass cost figure's labels exactly. Verified, not
#: fitted: see the module docstring and REPRODUCE.md.
T2_CHAT_CELL = "chat_s11_20260924T181638"
T2_FOCUS_CELL = "focus_s7_20260924T170858"
COST_SLICED_CELL = "sliced_s7_20260924T172418"  # the T1 sidebar's trace-arm bars
STEP_BUCKETS = [(1, 100), (101, 200), (201, 300), (301, 400)]

#: The pinned aggregate results (chains, cells) the recomputation must reproduce;
#: `--verify` asserts these. With chat now sized authoritatively (not by wall
#: time), chat is pinned at every size too. Per-cell numbers are additionally
#: checked against `canonical_runs.json` itself (see `verify`).
PINS = {
    ("2B", "flat"): (0, 0), ("2B", "chat"): (0, 1),
    ("2B", "sliced"): (0, 0), ("2B", "focus"): (0, 0),
    ("4B", "flat"): (0, 1), ("4B", "chat"): (1, 8),
    ("4B", "sliced"): (1, 7), ("4B", "focus"): (0, 3),
    ("9B", "flat"): (0, 1), ("9B", "chat"): (2, 6),
    ("9B", "sliced"): (2, 10), ("9B", "focus"): (4, 13),
    ("27B", "flat"): (4, 13), ("27B", "chat"): (5, 15),
    ("27B", "sliced"): (5, 15), ("27B", "focus"): (5, 15),
    ("35B-A3B", "flat"): (3, 12), ("35B-A3B", "chat"): (4, 13),
    ("35B-A3B", "sliced"): (5, 15), ("35B-A3B", "focus"): (4, 14),
}

# -- palette (dataviz reference instance, verbatim) ----------------------------

#: Single-hue blue sequential ramp, lightest -> darkest (CVD-safe by lightness).
SEQ_BLUE = {
    100: "#cde2fb", 150: "#b7d3f6", 200: "#9ec5f4", 250: "#86b6ef", 300: "#6da7ec",
    350: "#5598e7", 400: "#3987e5", 450: "#2a78d6", 500: "#256abf", 550: "#1c5cab",
    600: "#184f95", 650: "#104281", 700: "#0d366b",
}
#: errand cells reached (0-3) -> fill, drawn from the ramp above.
CELLS_FILL = {0: SEQ_BLUE[100], 1: SEQ_BLUE[200], 2: SEQ_BLUE[400], 3: SEQ_BLUE[650]}
CELLS_WHITE_TEXT = {2, 3}
#: chains completed (0-5) -> fill, from the same ramp.
CHAINS_FILL = {0: SEQ_BLUE[100], 1: SEQ_BLUE[200], 2: SEQ_BLUE[300],
               3: SEQ_BLUE[400], 4: SEQ_BLUE[500], 5: SEQ_BLUE[650]}
CHAINS_WHITE_TEXT = {3, 4, 5}

CHAT_COLOR = "#eb6834"   # categorical slot 2 (orange)
FOCUS_COLOR = "#2a78d6"  # categorical slot 1 (blue)
HILITE = "#eb6834"       # the 9B-row emphasis ring in the ladder (orange)

BG = "#f9f9f7"           # page plane: the warm off-white the figures sit on
INK = "#0b0b0b"          # primary text
INK2 = "#52514e"         # secondary text (subtitles)
MUTED = "#898781"        # axis / tick / de-emphasised labels
GRID = "#e1e0d9"         # hairline gridlines
BASELINE = "#c3c2b7"     # axis / baseline rule
COST_BAR = "#a9a7a0"     # the cost sidebar's neutral bars (deliberately not a hue)

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["DejaVu Sans"],  # the system sans available headless
    "svg.fonttype": "none",
    "axes.edgecolor": BASELINE,
    "text.color": INK,
})


# -- canonical-run selection (the pinned grid) ---------------------------------

#: The authoritative per-cell run table, pinned as package data beside this
#: module: size -> arm -> seed -> {"run", "chains", "cells"}.
CANONICAL_RUNS_PATH = Path(__file__).with_name("canonical_runs.json")


def load_canonical_runs(path=None):
    """The pinned size -> arm -> seed -> {run, chains, cells} table."""
    path = Path(path) if path is not None else CANONICAL_RUNS_PATH
    return json.loads(path.read_text())


def select_canonical_runs(runs_dir, canonical=None):
    """Map each (size, arm, seed) to its pinned run DIRECTORY under `runs_dir`.

    The run for every cell is read verbatim from `canonical_runs.json`; nothing
    is inferred from a manifest or a timestamp. Raises if a pinned run dir is not
    present under `runs_dir`, so a stale pin fails loudly rather than silently.
    """
    runs_dir = Path(runs_dir)
    table = canonical if canonical is not None else load_canonical_runs()
    chosen = {}
    for size, by_arm in table.items():
        for arm, by_seed in by_arm.items():
            for seed, cell in by_seed.items():
                path = runs_dir / cell["run"]
                if not (path / "manifest.json").exists():
                    raise FileNotFoundError(
                        f"pinned run for ({size}, {arm}, s{seed}) is not under "
                        f"{runs_dir}: {cell['run']}")
                chosen[(size, arm, int(seed))] = path
    return chosen


def load_grid(runs_dir, canonical=None):
    """`{(size, arm, seed): (chains, cells)}` over the pinned runs, each value
    recomputed from the cell's rows by `reader.read_cell`. The pin names the run;
    the numbers still come from the rows."""
    grid = {}
    for key, path in select_canonical_runs(runs_dir, canonical).items():
        cell = reader.read_cell(str(path))
        grid[key] = (int(cell["errands_completed"]), int(cell["cells_reached"]))
    return grid


def aggregate(grid, size, arm):
    """(chains over 5 seeds, cells over 5 seeds, seeds present) for one cell of
    the ladder."""
    chains = cells = present = 0
    for seed in SEEDS:
        value = grid.get((size, arm, seed))
        if value is not None:
            chains += value[0]
            cells += value[1]
            present += 1
    return chains, cells, present


# -- cost (ported from tools/token_metrics_99.py, cleaned) ---------------------

def _longest_common_prefix_len(a, b):
    """Length of the longest common prefix of two strings (binary search; the
    prompt strings are ~10 KB, so this is cheap)."""
    hi = min(len(a), len(b))
    lo = 0
    while lo < hi:
        mid = (lo + hi + 1) // 2
        if a[:mid] == b[:mid]:
            lo = mid
        else:
            hi = mid - 1
    return lo


def _read_calls(cell_dir):
    return reader._read_jsonl(Path(cell_dir) / "calls.jsonl")


def _trimmed_steps(cell_dir):
    events = reader._read_jsonl(Path(cell_dir) / "events.jsonl")
    return {e["step"] for e in events if e.get("kind") == "conversation_trimmed"}


def novel_prompt_tokens(cell_dir):
    """The cache-aware "novel prompt tokens" per call, in call order -- what each
    request adds past the prefix the server reused from the previous one.

    Ported from `tools/token_metrics_99.py`. llama.cpp with one slot reuses the
    longest common prefix of the previous request, so the raw prompt count
    overstates the work. For a trace arm the whole prompt text is logged, so the
    novel part is the tokens after the longest common prefix with the previous
    call's prompt (characters converted to tokens by this call's own ratio). For
    chat the logged prompt is only the new turn; the conversation grew by that
    turn plus the previous reply (already cached), so the novel part is
    prompt[i] - prompt[i-1] - eval[i-1], except where the conversation was
    trimmed (the prefix breaks) and the whole prompt is novel. The first call of
    a cell is all novel.
    """
    arm = json.loads((Path(cell_dir) / "manifest.json").read_text())["arm"]
    trimmed = _trimmed_steps(cell_dir) if arm == "chat" else set()
    out = []
    prev = None
    for call in _read_calls(cell_dir):
        tokens = call.get("tokens")
        if not tokens:
            continue
        prompt = tokens["prompt"]
        if arm == "chat":
            if prev is None or call["step"] in trimmed:
                novel = float(prompt)
            else:
                novel = float(max(0, prompt - prev["tokens"]["prompt"] - prev["tokens"]["eval"]))
        else:
            text = call.get("prompt", "") or ""
            ratio = prompt / max(1, len(text))
            if prev is None:
                novel = float(prompt)
            else:
                shared = _longest_common_prefix_len(prev.get("prompt", "") or "", text)
                novel = (len(text) - shared) * ratio
        out.append(novel)
        prev = call
    return out


def per_call_cost(cell_dir, buckets=STEP_BUCKETS):
    """Per task-length bucket, the mean prompt tokens and seconds PER CALL.

    `{(lo, hi): {"prompt_per_call", "sec_per_call", "n_calls", "n_steps"}}`.
    This is the quantity the cost figures plot (see the module docstring). A
    bucket with no calls is omitted.
    """
    def bucket_of(step):
        for lo, hi in buckets:
            if lo <= step <= hi:
                return (lo, hi)
        return None

    acc = {b: {"prompt": 0, "seconds": 0.0, "n_calls": 0, "steps": set()} for b in buckets}
    for call in _read_calls(cell_dir):
        tokens = call.get("tokens")
        if not tokens:
            continue
        bucket = bucket_of(call["step"])
        if bucket is None:
            continue
        a = acc[bucket]
        a["prompt"] += tokens["prompt"]
        a["seconds"] += call.get("elapsed_s", 0) or 0
        a["n_calls"] += 1
        a["steps"].add(call["step"])
    out = {}
    for bucket, a in acc.items():
        if a["n_calls"]:
            out[bucket] = {
                "prompt_per_call": a["prompt"] / a["n_calls"],
                "sec_per_call": a["seconds"] / a["n_calls"],
                "n_calls": a["n_calls"],
                "n_steps": len(a["steps"]),
            }
    return out


# -- small drawing helpers -----------------------------------------------------

def _cell_box(ax, x, y, w, h, facecolor, *, ring=None, ring_width=0.0, gap=0.006):
    """A single heatmap cell: a filled rounded rectangle with a thin surface gap
    to its neighbours, optionally with an inset ring (the completed-chain mark).

    The corner radius is proportional to the box, so a small swatch rounds gently
    rather than collapsing into a pill the way a fixed radius would.
    """
    inner_w, inner_h = w - 2 * gap, h - 2 * gap
    ax.add_patch(FancyBboxPatch(
        (x + gap, y + gap), inner_w, inner_h,
        boxstyle=f"round,pad=0,rounding_size={min(inner_w, inner_h) * 0.14:.5f}",
        linewidth=0, facecolor=facecolor, edgecolor="none",
        mutation_aspect=h / w if w else 1.0, zorder=2))
    if ring is not None:
        inset = gap + 0.012
        ring_w, ring_h = w - 2 * inset, h - 2 * inset
        ax.add_patch(FancyBboxPatch(
            (x + inset, y + inset), ring_w, ring_h,
            boxstyle=f"round,pad=0,rounding_size={min(ring_w, ring_h) * 0.16:.5f}",
            linewidth=ring_width, facecolor="none", edgecolor=ring,
            mutation_aspect=h / w if w else 1.0, zorder=4))


def _blank_ax(fig):
    ax = fig.add_axes([0, 0, 1, 1])
    ax.set_xlim(0, 1)
    ax.set_ylim(0, 1)
    ax.axis("off")
    return ax


def _save(fig, out_path):
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=150, facecolor=BG)
    plt.close(fig)
    return out_path


# -- figure A: the 9B grid -----------------------------------------------------

#: The 9B arms, top to bottom, with their one-line descriptions.
A_ROWS = [
    ("flat", "the list on the page, every step", False),
    ("chat", "a running conversation, no list", False),
    ("sliced", "the list served in slices", False),
    ("focus", "one entry in force when acting", True),
]


def figure_a_grid(grid, out_path):
    """A_grid: the 9B result as a 4-arm x 5-seed grid of errand cells reached.

    Each cell shows the cells reached (0-3); a completed chain (chains = 1, i.e.
    all three reached) is boxed and ticked. Fill is the blue ramp by cells
    reached. The right column gives chains completed / 5.
    """
    fig = plt.figure(figsize=(12.8, 5.4))
    ax = _blank_ax(fig)

    x0, col_w = 0.300, 0.088          # grid left edge, column width
    y_top, row_h = 0.730, 0.122       # top row's BOTTOM edge, row height
    header_y = 0.905                  # seed headers, clear above the top row

    def col_x(j):
        return x0 + j * col_w

    def row_y(i):                     # i = 0 is the top row (flat)
        return y_top - i * row_h

    # headers (above the grid, so they never sit on the top row)
    ax.text(x0 - 0.016, header_y, "world seed", ha="right", va="center",
            fontsize=13, color=MUTED)
    for j, seed in enumerate(SEEDS):
        ax.text(col_x(j) + col_w / 2, header_y, str(seed),
                ha="center", va="center", fontsize=17, color=INK2)
    ax.text(col_x(len(SEEDS)) + 0.028, header_y, "chains completed",
            ha="left", va="center", fontsize=13, color=MUTED)

    # rows
    for i, (arm, subtitle, emph) in enumerate(A_ROWS):
        y = row_y(i)
        ax.text(x0 - 0.016, y + row_h * 0.60, arm, ha="right", va="center",
                fontsize=22, color=INK, fontweight="bold" if emph else "normal")
        ax.text(x0 - 0.016, y + row_h * 0.22, subtitle, ha="right", va="center",
                fontsize=12.5, color=MUTED)
        chains = 0
        for j, seed in enumerate(SEEDS):
            ch, ce = grid.get(("9B", arm, seed), (0, 0))
            chains += ch
            done = ch == 1
            _cell_box(ax, col_x(j), y, col_w, row_h, CELLS_FILL[ce],
                      ring="#ffffff" if done else None, ring_width=3.0)
            txt_color = "#ffffff" if ce in CELLS_WHITE_TEXT else INK
            label = f"{ce} ✓" if done else str(ce)
            ax.text(col_x(j) + col_w / 2, y + row_h / 2, label, ha="center",
                    va="center", fontsize=23 if not done else 20,
                    fontweight="bold" if done else "normal", color=txt_color, zorder=5)
        ax.text(col_x(len(SEEDS)) + 0.028, y + row_h / 2, f"{chains} / 5",
                ha="left", va="center", fontsize=18, color=INK,
                fontweight="bold" if emph else "normal")

    # legend: the cells ramp, then the completed-box key
    ly = 0.115
    ax.text(0.020, ly, "errand cells reached", ha="left", va="center",
            fontsize=13.5, color=INK2)
    sw_x, sw = 0.205, 0.040
    for k in range(4):
        _cell_box(ax, sw_x + k * (sw + 0.004), ly - sw / 2, sw, sw, CELLS_FILL[k], gap=0.003)
        ax.text(sw_x + k * (sw + 0.004) + sw / 2, ly, str(k), ha="center", va="center",
                fontsize=14, color="#ffffff" if k in CELLS_WHITE_TEXT else INK, zorder=5)
    # the key box takes a grid cell's taller proportions, so its inset ring does
    # not collapse into a sliver the way a short, wide box would
    kx, kw, kh = 0.398, 0.070, 0.092
    ky = ly - kh / 2
    _cell_box(ax, kx, ky, kw, kh, CELLS_FILL[3], gap=0.004)   # filled cell, no ring
    # a crisp rectangular ring: sharp corners render reliably at swatch scale,
    # where the cells' rounded inset ring would collapse
    rin = 0.014
    ax.add_patch(Rectangle((kx + rin, ky + rin), kw - 2 * rin, kh - 2 * rin,
                           fill=False, edgecolor="#ffffff", linewidth=2.5, zorder=4))
    ax.text(kx + kw / 2, ly, "3 ✓", ha="center", va="center",
            fontsize=16, fontweight="bold", color="#ffffff", zorder=5)
    ax.text(kx + kw + 0.018, ly + 0.018,
            "the chain completed — pickaxe, then rope, then back to the human.",
            ha="left", va="center", fontsize=12.5, color=INK2)
    ax.text(kx + kw + 0.018, ly - 0.018,
            "Every 3 in this panel is a completed chain; nothing below 3 is.",
            ha="left", va="center", fontsize=12.5, color=INK2)
    return _save(fig, out_path)


# -- figure T1: the ladder -----------------------------------------------------

#: The ladder's arm columns, left to right, with headers and descriptions. chat
#: is set apart on the left (it is not a clean baseline); the trace arms group on
#: the right.
T1_COLS_LEFT = [("chat", "chat*", "a running\nconversation, no list")]
T1_COLS_RIGHT = [
    ("flat", "flat", "the whole list on\nthe page, every step"),
    ("sliced", "sliced", "the list served\nin slices"),
    ("focus", "focus", "one entry in force\nwhen acting"),
]


def _chain_cell(ax, x, y, w, h, chains, cells):
    """One ladder cell: 'chains | cells', chains large, cells smaller, filled by
    chains."""
    _cell_box(ax, x, y, w, h, CHAINS_FILL[chains])
    white = chains in CHAINS_WHITE_TEXT
    main = "#ffffff" if white else INK
    sub = "#ffffff" if white else INK2
    cx = x + w / 2
    cy = y + h / 2
    ax.text(cx - 0.018, cy, str(chains), ha="right", va="center", fontsize=25,
            color=main, zorder=5)
    ax.text(cx, cy, "|", ha="center", va="center", fontsize=20, color=sub, zorder=5)
    ax.text(cx + 0.020, cy, str(cells), ha="left", va="center", fontsize=16,
            color=sub, zorder=5)


def _cost_sidebar(ax, x0, x1, y0, y1, chat_cost, sliced_cost):
    """The ladder's token-cost strip: four neutral vertical bars -- chat early
    and late, a trace arm early and late -- showing the per-call prompt size
    staying flat for the trace arm while the conversation's climbs. Labelled in k
    tokens; a free-standing annotation, not aligned to the size rows."""
    chat_early = chat_cost[STEP_BUCKETS[0]]["prompt_per_call"]
    chat_late = chat_cost[STEP_BUCKETS[-1]]["prompt_per_call"]
    tr_early = sliced_cost[STEP_BUCKETS[0]]["prompt_per_call"]
    tr_late = sliced_cost[STEP_BUCKETS[-1]]["prompt_per_call"]
    vmax = max(chat_early, chat_late) * 1.06
    bar_w = (x1 - x0) / 7.0

    def bar(slot, value, label, sublabel):
        bx = x0 + (0.6 + slot * 1.5) * bar_w
        bh = (y1 - y0) * (value / vmax)
        ax.add_patch(Rectangle((bx, y0), bar_w, bh, facecolor=COST_BAR,
                               edgecolor="none", zorder=2))
        ax.text(bx + bar_w / 2, y0 + bh + 0.012, label, ha="center", va="bottom",
                fontsize=12.5, color=INK2)
        ax.text(bx + bar_w / 2, y0 - 0.010, sublabel, ha="center", va="top",
                fontsize=9, color=MUTED, rotation=90)

    def k(value):
        return f"{value / 1000:.0f}k" if value >= 9500 else f"{value / 1000:.1f}k"

    bar(0, chat_early, k(chat_early), "chat-early")
    bar(1, chat_late, k(chat_late), "chat-late")
    bar(2, tr_early, k(tr_early), "sliced-early")
    bar(3, tr_late, "", "sliced-late")
    ax.text((x0 + x1) / 2, y1 + 0.135, "tokens / step", ha="center", va="center",
            fontsize=14.5, color=INK2)


def figure_t1_ladder(grid, chat_cost, sliced_cost, out_path):
    """T1_ladder: the full 2B -> 35B ladder across the four arms (chains and
    cells), with the token-cost sidebar. The 9B row is ringed."""
    fig = plt.figure(figsize=(13.3, 7.6))
    ax = _blank_ax(fig)

    # geometry: chat column (left), cost strip (middle), trace columns (right)
    col_w = 0.118
    chat_x = 0.250
    cost_x0, cost_x1 = chat_x + col_w + 0.020, chat_x + col_w + 0.175
    right_x0 = cost_x1 + 0.035
    row_h = 0.106
    y_top = 0.640                     # top (2B) row's BOTTOM edge
    title_y, sub_y, model_y = 0.880, 0.800, 0.792   # header band, above the cells

    def row_y(i):
        return y_top - i * row_h

    def right_col_x(j):
        return right_x0 + j * col_w

    # column headers (a band above the grid; subtitles never sit on the 2B row)
    ax.text(0.020, model_y, "model", ha="left", va="center", fontsize=13.5, color=MUTED)
    ax.text(chat_x + col_w / 2, title_y, "chat*", ha="center", va="center",
            fontsize=20, color=INK)
    ax.text(chat_x + col_w / 2, sub_y, "a running\nconversation, no list",
            ha="center", va="center", fontsize=11.5, color=MUTED, linespacing=1.3)
    for j, (_, head, sub) in enumerate(T1_COLS_RIGHT):
        ax.text(right_col_x(j) + col_w / 2, title_y, head, ha="center",
                va="center", fontsize=20, color=INK)
        ax.text(right_col_x(j) + col_w / 2, sub_y, sub, ha="center",
                va="center", fontsize=11.5, color=MUTED, linespacing=1.3)

    # rows
    for i, size in enumerate(SIZES):
        y = row_y(i)
        emph = size == "9B"
        ax.text(0.020, y + row_h * 0.58, SIZE_LABEL[size], ha="left", va="center",
                fontsize=19, color=INK, fontweight="bold" if emph else "normal")
        if size == "35B-A3B":
            ax.text(0.020, y + row_h * 0.20, "MoE, ~3B active", ha="left", va="center",
                    fontsize=11.5, color=MUTED)
        ch, ce, _ = aggregate(grid, size, "chat")
        _chain_cell(ax, chat_x, y, col_w, row_h, ch, ce)
        for j, (arm, _, _) in enumerate(T1_COLS_RIGHT):
            ch, ce, _ = aggregate(grid, size, arm)
            _chain_cell(ax, right_col_x(j), y, col_w, row_h, ch, ce)

    # the 9B emphasis rings (around the chat cell, and around the trace trio)
    y9 = row_y(SIZES.index("9B"))
    for (rx, rw) in [(chat_x, col_w), (right_x0, col_w * 3)]:
        ax.add_patch(FancyBboxPatch(
            (rx - 0.004, y9 - 0.004), rw + 0.008, row_h + 0.008,
            boxstyle="round,pad=0,rounding_size=0.012", linewidth=3.0,
            facecolor="none", edgecolor=HILITE, zorder=6))

    # the cost strip sits in the gutter between the chat and trace columns
    _cost_sidebar(ax, cost_x0, cost_x1, row_y(len(SIZES) - 1) + 0.032,
                  y_top + row_h * 0.55, chat_cost, sliced_cost)

    # legend and footnotes (below where the cost strip's rotated labels end)
    ly = 0.098
    ax.text(0.020, ly, "chains completed / 5 seeds (left):", ha="left", va="center",
            fontsize=13.5, color=INK2)
    sw_x, sw = 0.360, 0.034
    for k in range(6):
        _cell_box(ax, sw_x + k * (sw + 0.004), ly - sw / 2, sw, sw, CHAINS_FILL[k], gap=0.003)
        ax.text(sw_x + k * (sw + 0.004) + sw / 2, ly, str(k), ha="center", va="center",
                fontsize=13, color="#ffffff" if k in CHAINS_WHITE_TEXT else INK, zorder=5)
    ax.text(sw_x + 6 * (sw + 0.004) + 0.012, ly, "·  errand cells reached / 15 (right)",
            ha="left", va="center", fontsize=13.5, color=INK2)
    ax.text(0.020, 0.050,
            "* chat isn't a true baseline; its naming aid is already a mild slicing.",
            ha="left", va="center", fontsize=12, color=MUTED)
    ax.text(0.020, 0.022,
            "Qwen3.5, bf16, deterministic (temperature 0, sampling seed 42).",
            ha="left", va="center", fontsize=12, color=MUTED)
    return _save(fig, out_path)


# -- figure T2: cost vs task length --------------------------------------------

def _barh_panel(ax, title, chat_vals, focus_vals, labels, *, fmt, xmax, budget=None):
    """One T2 panel: grouped horizontal bars, chat over focus, newest bucket at
    top, direct value labels, recessive grid."""
    n = len(labels)
    group_h = 1.0
    bar_h = 0.34
    gap = 0.06
    ax.set_xlim(0, xmax)
    ax.set_ylim(-0.5, n - 0.5)
    ax.invert_yaxis()                 # 1-100 at the top
    ax.set_yticks(range(n))
    ax.set_yticklabels(labels, fontsize=13, color=INK2)
    ax.set_title(title, fontsize=16, color=INK, loc="left", pad=14)
    ax.tick_params(axis="x", labelsize=11, colors=MUTED, length=0)
    ax.grid(axis="x", color=GRID, linewidth=1.0, zorder=0)
    ax.set_axisbelow(True)
    for spine in ("top", "right", "left"):
        ax.spines[spine].set_visible(False)
    ax.spines["bottom"].set_color(BASELINE)

    def row(i, value, color, up):
        # chat sits above focus within each task-length group (y is inverted, so
        # "above" is the smaller coordinate)
        cy = i - (bar_h / 2 + gap / 2) if up else i + (bar_h / 2 + gap / 2)
        ax.barh(cy, value, height=bar_h, color=color, zorder=3, align="center")
        ax.text(value + xmax * 0.012, cy, fmt(value), ha="left", va="center",
                fontsize=12.5, color=INK2, zorder=4)

    for i in range(n):
        row(i, chat_vals[i], CHAT_COLOR, up=True)
        row(i, focus_vals[i], FOCUS_COLOR, up=False)
    if budget is not None:
        ax.axvline(budget, color=BASELINE, linewidth=1.4, linestyle=(0, (4, 3)), zorder=2)
        ax.text(budget, -0.48, "chat budget cap ≈ 90k", ha="right", va="bottom",
                fontsize=11.5, color=MUTED)


def figure_t2_cost(chat_cost, focus_cost, out_path):
    """T2_cost: seconds per step and prompt tokens per step against task length,
    one 9B run per arm (chat vs focus)."""
    labels = [f"{lo}–{hi}" for lo, hi in STEP_BUCKETS]
    chat_sec = [chat_cost[b]["sec_per_call"] for b in STEP_BUCKETS]
    focus_sec = [focus_cost[b]["sec_per_call"] for b in STEP_BUCKETS]
    chat_tok = [chat_cost[b]["prompt_per_call"] for b in STEP_BUCKETS]
    focus_tok = [focus_cost[b]["prompt_per_call"] for b in STEP_BUCKETS]

    fig, (ax_l, ax_r) = plt.subplots(1, 2, figsize=(13.3, 5.7))
    fig.subplots_adjust(left=0.085, right=0.975, top=0.80, bottom=0.17, wspace=0.28)

    _barh_panel(ax_l, "seconds per step", chat_sec, focus_sec, labels,
                fmt=lambda v: f"{v:.2f}", xmax=max(chat_sec) * 1.22)
    _barh_panel(ax_r, "prompt tokens per step", chat_tok, focus_tok, labels,
                fmt=lambda v: f"{v:,.0f}", xmax=100_000, budget=90_000)

    # one legend for both panels (two series -> a legend is required)
    fig.text(0.085, 0.935, "■", color=CHAT_COLOR, fontsize=15, va="center")
    fig.text(0.108, 0.935, "chat", color=INK, fontsize=14, va="center")
    fig.text(0.165, 0.935, "■", color=FOCUS_COLOR, fontsize=15, va="center")
    fig.text(0.188, 0.935, "focus", color=INK, fontsize=14, va="center")
    fig.text(0.085, 0.085,
             "One 9B run per arm (n = 1 each): the per-step shape, not a mean over seeds.\n"
             "A trace arm issues several pages per step, so its value is per decision "
             "page (= per step for chat).",
             color=MUTED, fontsize=11, va="top", linespacing=1.4)
    return _save(fig, out_path)


# -- verification --------------------------------------------------------------

def verify(grid, canonical=None):
    """Assert the recomputed grid against the pins; return (ok, lines).

    Two independent checks. Per cell: the numbers recomputed from a run's rows
    must equal the (chains, cells) `canonical_runs.json` records for that cell --
    this catches a pin that names a run whose rows disagree with its recorded
    numbers. Per aggregate: every (size, arm) total must equal `PINS` -- this
    catches a drift in the aggregate targets.
    """
    table = canonical if canonical is not None else load_canonical_runs()
    arms = ["flat", "chat", "sliced", "focus"]
    lines = ["computed grid  (chains|cells, over 5 seeds):"]
    header = "    " + "".join(f"{a:>12}" for a in arms)
    lines.append(f"{'size':>9}{header}")
    for size in SIZES:
        cells = "".join(f"{f'{aggregate(grid, size, a)[0]}|{aggregate(grid, size, a)[1]}':>12}"
                        for a in arms)
        lines.append(f"{size:>9}    {cells}")
    ok = True

    # per-cell: recomputed rows vs the pin file's own numbers
    mismatches = []
    n_cells = 0
    for size, by_arm in table.items():
        for arm, by_seed in by_arm.items():
            for seed, pinned in by_seed.items():
                n_cells += 1
                got = grid.get((size, arm, int(seed)))
                want = (int(pinned["chains"]), int(pinned["cells"]))
                if got != want:
                    mismatches.append((size, arm, seed, got, want, pinned["run"]))
    lines.append("")
    if mismatches:
        ok = False
        lines.append(f"per-cell vs canonical_runs.json: {len(mismatches)} MISMATCH")
        for size, arm, seed, got, want, run in mismatches:
            shown = "missing" if got is None else f"{got[0]}|{got[1]}"
            lines.append(f"  [BAD] {size:>8} {arm:<7} s{seed:<3} rows {shown} "
                         f"!= pinned {want[0]}|{want[1]}  ({run})")
    else:
        lines.append(f"per-cell vs canonical_runs.json: all {n_cells} cells OK")

    # aggregates vs the target pins
    lines.append("")
    lines.append("aggregate pin check:")
    for (size, arm), (pch, pce) in sorted(PINS.items()):
        ch, ce, _ = aggregate(grid, size, arm)
        good = (ch, ce) == (pch, pce)
        ok &= good
        lines.append(f"  [{'OK' if good else 'BAD'}] {size:>8} {arm:<7} got {ch}|{ce}  pin {pch}|{pce}")
    lines.append("")
    lines.append("ALL PINS MATCH" if ok else "*** PIN MISMATCH -- figures NOT trustworthy ***")
    return ok, lines


# -- command -------------------------------------------------------------------

def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="p3focus.figures",
        description="Regenerate the demo's three figures from the canonical runs.")
    parser.add_argument("--runs", default="runs", type=Path,
                        help="the runs/ directory (default: ./runs)")
    parser.add_argument("--out", default=Path("generated/figures"), type=Path,
                        help="output directory for the PNGs (default: generated/figures)")
    parser.add_argument("--canonical", default=None, type=Path,
                        help="override the pinned canonical_runs.json (default: the packaged one)")
    parser.add_argument("--verify", action="store_true",
                        help="recompute the grid, print it, assert the pins, and exit")
    args = parser.parse_args(argv)

    if not args.runs.is_dir():
        parser.error(f"--runs {args.runs} is not a directory; point it at the runs/ data")

    canonical = load_canonical_runs(args.canonical)
    try:
        grid = load_grid(args.runs, canonical)
    except FileNotFoundError as exc:
        print(f"figures: {exc}", file=sys.stderr)
        return 1
    ok, lines = verify(grid, canonical)
    print("\n".join(lines))
    if not ok:
        print("\nRefusing to render from numbers that do not reproduce the pins.", file=sys.stderr)
        return 1
    if args.verify:
        return 0

    chat_cost = per_call_cost(args.runs / T2_CHAT_CELL)
    focus_cost = per_call_cost(args.runs / T2_FOCUS_CELL)
    sliced_cost = per_call_cost(args.runs / COST_SLICED_CELL)

    paths = [
        figure_a_grid(grid, args.out / "A_grid.png"),
        figure_t1_ladder(grid, chat_cost, sliced_cost, args.out / "T1_ladder.png"),
        figure_t2_cost(chat_cost, focus_cost, args.out / "T2_cost.png"),
    ]
    print("\nwrote:")
    for path in paths:
        print(f"  {path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
