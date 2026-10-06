# REBUILD manifest — one line per artifact BEFORE it enters generated/

Everything under `generated/` is regenerable. `src/vendor/crafter/` is NOT here: it is the
patched substrate we own, git-tracked; the world layer records its provenance below.

## venv

    python3.12 -m venv generated/venv
    generated/venv/bin/pip install pytest pytest-xdist numpy jsonschema
    # crafter's own deps, which the world layer needs to import the vendored substrate:
    generated/venv/bin/pip install imageio pillow opensimplex ruamel.yaml

The world layer added **no** dependency: every one of those was already installed when the
work began. Versions measured 2026-09-24 —

    python 3.12.14 · numpy 2.5.3 · imageio 2.37.4 · pillow 12.3.0 · opensimplex 0.4.5.1
    ruamel.yaml 0.19.1 · jsonschema 4.26.0 · pytest 9.1.1 · pytest-xdist 3.8.0

(The original repo pinned numpy 2.5.2; this line pins 2.5.3, the version the measurement
above was taken under, and `pyproject.toml` records every pin exactly.)

## tests

    generated/venv/bin/python -m pytest src/tests -q -n 4

Run it with `-n`. Drop to `-n 0` when a failure looks order- or worker-dependent: a
serial run is the tiebreaker, and a test that only fails under `-n` is an isolation
bug, not a drifted pin. `src/tests/conftest.py` puts `src/` on `sys.path`;
`src/p3focus/world.py` puts `src/vendor/` there, so crafter is never pip-installed.

## figures (generated/figures/)

`src/p3focus/figures.py` regenerates the three demo figures from the run logs.
Unlike the world layer, the figures layer adds **one** dependency — matplotlib —
which the harness, the reader and the tests do not use, so it lives in a
`figures` extra in `pyproject.toml` rather than in the core pins. numpy is
already a core dependency. Rendering is headless (`matplotlib.use("Agg")`); no
display is needed.

    python3.12 -m venv generated/venv
    generated/venv/bin/pip install "matplotlib==3.11.2" "numpy==2.5.3"
    PYTHONPATH=src generated/venv/bin/python -m p3focus.figures \
        --runs /path/to/runs --out generated/figures

Versions measured 2026-10-05 — matplotlib 3.11.2 · numpy 2.5.3 (python 3.12).
`generated/figures/` is regenerable output; the three PNGs are not committed.
`--verify` recomputes the grid and asserts the pinned results without rendering.
See `REPRODUCE.md` (repo root) for the canonical-run selection and the full
recompute-vs-pin table.

## the vendored substrate (already in src/vendor; rebuild only if lost)

`danijar/crafter` at the pin this line ran, plus unmerged PR #32:

    SHA=e04542a2159f1aad3d4c5ad52e8185717380ee3a
    curl -sSL -o generated/vendor_dl/crafter_${SHA:0:8}.tar.gz \
      https://github.com/danijar/crafter/archive/${SHA}.tar.gz
    # sha256 cd9f7d358ade4e1efa79e16d29f66fa8eba580350eb8036b5da62eadbc718038
    tar -xzf generated/vendor_dl/crafter_${SHA:0:8}.tar.gz -C generated/vendor_dl
    cp -R generated/vendor_dl/crafter-${SHA}/crafter src/vendor/crafter
    curl -sSL -o generated/vendor_dl/pr32.diff https://github.com/danijar/crafter/pull/32.diff
    (cd src/vendor && patch -p1 < ../../generated/vendor_dl/pr32.diff)

and then two further patches on top of it, which that recipe does NOT reproduce. The tree
here was copied whole from the original private repo's `src/vendor/crafter` (git-tracked
there) rather than rebuilt, and these two commits are why:

| commit (origin) | what it changes | why this line needs it |
|---|---|---|
| `8b9a9b2` | `objects.Player.walkable` and `_update_life_stats` read a `water_walkable` INSTANCE attribute through `getattr`: water joins the walkable set, standing in it adds 1 drink a step clamped at 9 with thirst held at 0, and `collect_drink` fires only when the swallow moves the meter | A §1.1's first rule. `world.pin_water_walkable` sets that attribute before every step |
| `989892f` | `worldgen.generate_world` / `_set_material` take `water_offset`, default `WATER_OFFSET = 0.1`, read off the env by `getattr`; `Env.reset` passes it | nothing here sets it, so the default path is the vendor's own. It rides along because the tree was copied whole |

Digest of the tree as vendored, by `p3focus.world.vendor_digest_of` (relative path +
bytes, sorted, every `.py` and `data.yaml`, not the assets):

    b88545aa1bed8ee8e38fe50d44d48c3e4077941b12bf81ded337b0ac1db4d746

**Not** the `7b2c1203562e0296a9eec66e7750f08f0d623fa34ea3cb73dff657bd3fb36505` that the
original repo's finished batteries carry: those were shot before the two patches above.
`src/tests/test_world_identity.py` asserts the vendored tree digests to the value above
before it compares frames against the committed fixture.

`src/vendor/LICENSE.crafter` is the upstream MIT licence, copied with the tree.

## the identity fixture

`src/tests/fixtures/world_identity_seed7.jsonl` is not under `generated/` — it is the
answer key, committed so the identity claim survives without the original repo. It was
generated from that private repo (and from nothing else), by running this world's seed-7
script through the original harness and recording pos, drink, health and a window digest
per step.

It is therefore **not** regenerable from within this public repo: the original repo is not
part of it, which is the whole reason the fixture is committed. `test_world_identity.py`
here checks this world's frames against the committed fixture, and checks the vendored tree
against the digest recorded above; the cross-repo comparison and the fixture-regeneration
entry point that lived in the original test are gone, because both reached a path outside
this repository.

## artifacts under generated/

| artifact | source URL | version/tag | pin (sha256) | rebuild command |
|---|---|---|---|---|

The world layer writes nothing here.
