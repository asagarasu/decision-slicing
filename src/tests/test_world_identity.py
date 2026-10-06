"""Identity: this world reproduces the recorded world, step for step (A §1.1).

    Same seed, same action sequence -> same positions, meters and window as the
    recorded run, step for step. That recorded run is the answer key.

How this is checked here, and why it is self-contained. The answer key was
produced by the original (private) harness and is not shipped with this public
repository. Two things stand in for it, both committed here:

  * `src/tests/fixtures/world_identity_seed7.jsonl` — the answer key itself:
    position, drink, health and a digest of the window, one row per step, for the
    seed-7 script below. It was generated from the original harness (see
    `generated/REBUILD.md`, "the identity fixture") and committed so the identity
    claim survives without that harness.
  * the vendored-crafter digest recorded in `generated/REBUILD.md` — so the
    substrate this world runs on is provably the one the fixture was made against.
    A frame match against a different Crafter would prove nothing.

The three tests below need nothing outside this repository:

  * `test_the_vendored_tree_matches_the_recorded_digest` — the substrate is the
    one `REBUILD.md` records;
  * `test_the_world_reproduces_the_committed_fixture` — position, drink, health
    and the window's digest, step for step, against the committed answer key;
  * `test_the_fixture_is_not_a_run_of_one_cell` — a positive control: an answer
    key the body could match by standing still would prove nothing about the world.

The original test also compared this world against the private harness directly and
could regenerate the fixture from it. Both reached a path outside this repository
and have been removed; the committed fixture and the recorded digest replace them.
"""
import hashlib
import json
import sys
from pathlib import Path

import numpy as np

# the same line `conftest.py` runs, repeated so the module imports cleanly even
# when it is imported outside a pytest run that has loaded the conftest.
_SRC = str(Path(__file__).resolve().parents[1])
if _SRC not in sys.path:
    sys.path.insert(0, _SRC)

from p3focus.world import VERBS, World, vendor_digest_of  # noqa: E402

FIXTURE = Path(__file__).resolve().parent / "fixtures" / "world_identity_seed7.jsonl"

#: the vendored crafter tree's digest, as recorded in generated/REBUILD.md. The
#: fixture below was produced against exactly this substrate.
VENDOR_DIGEST = "b88545aa1bed8ee8e38fe50d44d48c3e4077941b12bf81ded337b0ac1db4d746"

SEED = 7
#: the original `test_hot_ground.py`'s own walk: from the spawn at [32, 32] to the
#: grass cell west of the south-east beach, then ten steps that each END on sand.
#: It crosses a cow (two blocked moves), so it exercises the refusal branch too.
APPROACH = (["move_right"] * 5 + ["move_down"] * 6 + ["move_right"] + ["move_down"]
            + ["move_right"] * 7)
SAND_WALK = (["move_right"] * 4 + ["move_down"] + ["move_left"] * 3 + ["move_right"]
             + ["move_down"])
#: and then a fixed pseudo-random wander, so the comparison is not confined to
#: the cells a hand-written walk happens to touch. 170 steps takes the body
#: through water, through the drink meter emptying, and past death.
WANDER_SEED = 42
WANDER_STEPS = 170


def _wander(n, seed=WANDER_SEED):
    rng = np.random.RandomState(seed)
    return [VERBS[int(i)] for i in rng.randint(0, len(VERBS), size=n)]


SCRIPT = APPROACH + SAND_WALK + _wander(WANDER_STEPS)


def window_sha(window):
    """A stable digest of one frame's 9x9, for the compact fixture."""
    return hashlib.sha256("|".join(",".join(row) for row in window).encode()).hexdigest()[:16]


def fixture_row(frame):
    """The four things A §1.1 names, plus the step they belong to. WORLD axis."""
    return {"step": int(frame["step"]),
            "pos": list(frame["player"]["pos"]),
            "drink": int(frame["player"]["drink"]),
            "health": int(frame["player"]["health"]),
            "window_sha": window_sha(frame["window"])}


def our_frames():
    """Frame 0 and one frame per verb of `SCRIPT`, from this world."""
    world = World(SEED)
    frames = [world.reset()]
    for verb in SCRIPT:
        frames.append(world.step(verb)[0])
    return frames


def read_fixture():
    return [json.loads(line) for line in FIXTURE.read_text().splitlines() if line.strip()]


# -- the claim ----------------------------------------------------------------

def test_the_vendored_tree_matches_the_recorded_digest():
    """The identity claim is about the harness, not about the substrate. If the
    vendored tree were not the one the fixture was made against, a frame match
    would mean nothing. The recorded digest is in generated/REBUILD.md."""
    tree = Path(__file__).resolve().parents[1] / "vendor" / "crafter"
    assert vendor_digest_of(tree) == VENDOR_DIGEST, (
        "the vendored crafter tree does not digest to the value recorded in "
        "generated/REBUILD.md; the identity fixture was made against that tree")


def test_the_world_reproduces_the_committed_fixture():
    """A §1.1's identity against the committed answer key: position, drink, health
    and the window's digest, step for step."""
    rows = [fixture_row(f) for f in our_frames()]
    golden = read_fixture()
    assert len(rows) == len(golden) == len(SCRIPT) + 1
    for mine, want in zip(rows, golden):
        assert mine == want, f"step {mine['step']} parts from the answer key"


def test_the_fixture_is_not_a_run_of_one_cell():
    """A positive control for the test above: an answer key the body could match
    by standing still would prove nothing about the world."""
    golden = read_fixture()
    assert len({tuple(r["pos"]) for r in golden}) > 20, "the scripted walk went somewhere"
    assert len({r["window_sha"] for r in golden}) > 20, "and the window moved with it"
    assert {r["drink"] for r in golden} >= {0, 3}, "and the meter emptied"
