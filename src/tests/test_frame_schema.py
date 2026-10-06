"""The frame, and the schema that says what a frame is (A §1.2).

Ported from the old repo's `src/tests/test_telemetry.py` with its claims intact
— the acceptance line it carried was "frames validate against schema; deltas
reconcile with achievement counters over a scripted episode; zero reads of pixel
obs", and all three are still what this file checks. What changed:

  * the canonical action script came from the old `spike.action_script`, which
    is not a file this line has. It is inlined below, seed and all, so the pinned
    death step still means what it meant;
  * `schema_version` is "2" and the frame carries `standing_on` (A §7, D4), so
    the schema tests gained the material-vocabulary check and the two tests at
    the end, which are the reason the field exists at all;
  * the tests that were about the OLD line's flags and pages are not here. They
    are not this piece's.

Every test is named for the claim it carries. No LLM, no network, no pixels.

    generated/venv/bin/python -m pytest src/tests/test_frame_schema.py -q
"""
import json

import jsonschema
import numpy as np
import pytest

from p3focus import constants as K
from p3focus import world as W
from p3focus.world import (
    OUT_OF_BOUNDS,
    TelemetryExtractor,
    load_schema,
    make_env,
    semantic_window,
    standing_on,
)

SEED = 7
STEPS = 400
#: the old `spike.action_script(n, "walk")`, verbatim: movement-heavy so the
#: player walks into new chunks, with `do`, `sleep` and two `place_` verbs mixed
#: in so inventory and achievements actually move. Indices, not verbs — the
#: extractor takes the vendor's own action space, which is wider than A §1.1's
#: four; `World` is what narrows it.
ACTION_SEED = 123
SCRIPT = [int(a) for a in
          np.random.RandomState(ACTION_SEED).choice([0, 1, 2, 3, 4, 5, 5, 5, 6, 7, 8], size=STEPS)]

#: The scripted walk kills the player well before step 400. Crafter has no
#: absorbing terminal state — `Env.step` past `done` keeps returning well-formed
#: `info` — so the episode is driven for all 400 actions and this is a receipt.
DEATH_STEP = 158


def dump(frames):
    return json.dumps(frames, sort_keys=True)


def run_episode(steps=STEPS, balancer=False, poison_pixels=False):
    """Drive the fixed script through the extractor. Returns env, extractor, frames."""
    env = make_env(SEED, balancer=balancer)
    env.reset()
    tx = TelemetryExtractor(env)
    frames = [tx.frame0()]
    if poison_pixels:
        env._obs = lambda: _Poison()
        env.render = _no_render
    first_done = None
    for i, action in enumerate(SCRIPT[:steps], start=1):
        frames.append(tx.step(action))
        if tx.done and first_done is None:
            first_done = i
    return {"env": env, "tx": tx, "frames": frames, "first_done": first_done}


class PixelAccess(RuntimeError):
    """Raised if anything touches the pixel observation or calls render()."""


class _Poison:
    """Stands in for the pixel obs. Any use of it at all is a failure."""

    def __getattr__(self, name):
        raise PixelAccess(f"pixel observation touched: .{name}")

    def __getitem__(self, key):
        raise PixelAccess("pixel observation indexed")

    def __array__(self, *args, **kwargs):
        raise PixelAccess("pixel observation converted to array")

    def __len__(self):
        raise PixelAccess("pixel observation measured")

    def __iter__(self):
        raise PixelAccess("pixel observation iterated")


def _no_render(*args, **kwargs):
    raise PixelAccess("env.render called")


@pytest.fixture(scope="module")
def schema():
    return load_schema()


@pytest.fixture(scope="module")
def validator(schema):
    cls = jsonschema.validators.validator_for(schema)
    cls.check_schema(schema)  # the schema itself is valid draft 2020-12
    return cls(schema)


@pytest.fixture(scope="module")
def episode():
    return run_episode()


# -- the acceptance line -------------------------------------------------------

def test_every_frame_of_a_400_step_episode_validates_against_the_schema(validator, episode):
    frames = episode["frames"]
    assert len(frames) == STEPS + 1, "frame 0 plus one frame per action"
    assert [f["step"] for f in frames] == list(range(STEPS + 1))
    assert episode["first_done"] == DEATH_STEP, (
        "receipt: the scripted walk dies here; the run continues past it on purpose")
    for frame in frames:
        validator.validate(frame)
        json.dumps(frame)  # JSON-serializable: a numpy scalar leaking in raises here


def test_summed_deltas_reconcile_with_final_achievements_and_inventory(episode):
    frames, player = episode["frames"], episode["env"]._player
    inventory = dict(frames[0]["inventory"])
    achievements = dict(frames[0]["achievements"])
    assert set(achievements.values()) == {0}, "achievement counters start at zero"
    for frame in frames[1:]:
        for name, delta in frame["deltas"]["inventory"].items():
            inventory[name] += delta
        for name, delta in frame["deltas"]["achievements"].items():
            achievements[name] += delta
    # The oracle is the substrate itself: `Env.step` puts exactly these two dicts
    # into info by `.copy()`, so this compares the extractor against crafter
    # rather than against itself.
    assert inventory == dict(player.inventory)
    assert achievements == dict(player.achievements)
    assert inventory == frames[-1]["inventory"]
    assert achievements == frames[-1]["achievements"]
    # non-vacuous: the episode really did move both
    assert sum(achievements.values()) > 0
    assert sum(1 for f in frames[1:] if f["deltas"]["inventory"]) > 0


def test_the_extractor_reads_no_pixels_and_frames_are_render_independent(validator, episode):
    # Control first: the unconditional render belongs to the vendor, not to us.
    # `Env.step` calls `self._obs()` -> `self.render()`, so breaking render alone
    # breaks crafter's own step and proves nothing about the extractor. That is
    # why the claim below also replaces `_obs`.
    env = make_env(SEED)
    env.reset()
    env.render = _no_render
    with pytest.raises(PixelAccess):
        env.step(0)
    # and the poison itself bites — it is never touched in a passing run, so its
    # liveness has to be asserted rather than assumed
    with pytest.raises(PixelAccess):
        _Poison()[0]

    # The claim: with the obs path replaced by a value that explodes on any use
    # and render() itself fatal, the whole 400-step episode still runs.
    poisoned = run_episode(poison_pixels=True)
    assert len(poisoned["frames"]) == STEPS + 1
    for frame in poisoned["frames"]:
        validator.validate(frame)
    # And rendering changes nothing: post-PR #32 `_noise` draws from a clone of
    # the world RNG, so a run with no renders at all is byte-identical.
    assert dump(poisoned["frames"]) == dump(episode["frames"])


def test_frame0_equals_the_read_only_frame_and_the_window_is_9x9_player_centred():
    env = make_env(SEED)
    env.reset()
    tx = TelemetryExtractor(env)
    frame0 = tx.frame0()
    assert frame0 == tx.frame(info=None)
    assert tx.frame() == frame0, "frame() is read-only: it must not commit anything"

    assert frame0["step"] == 0
    assert frame0["deltas"] == {"inventory": {}, "achievements": {}}
    assert frame0["player"]["pos"] == list(K.SPAWN), "reset spawns at the area centre"
    assert len(frame0["window"]) == K.WINDOW
    assert {len(row) for row in frame0["window"]} == {K.WINDOW}
    assert frame0["window"][4][4] == "player"

    # Orientation receipt, WORLD axis: rows are +y (north->south, i.e. row 0 is
    # the row farthest ABOVE the body on screen), columns are +x (west->east).
    # Every cell, not a sample: near spawn the neighbourhood is nearly all grass,
    # so a two-cell check would pass on a transposed window by coincidence.
    semantic = tx.sem_view()
    px, py = frame0["player"]["pos"]
    assert frame0["window"] == [
        [tx.id_to_name[int(semantic[x, y])] for x in range(px - 4, px + 5)]
        for y in range(py - 4, py + 5)]
    assert frame0["window"] != [list(col) for col in zip(*frame0["window"])], (
        "this window happens to be transpose-symmetric, so the check above is "
        "vacuous — pick another seed or step")


def test_two_fresh_seed7_envs_produce_byte_identical_frame_sequences():
    first = run_episode()
    second = run_episode()
    assert dump(first["frames"]) == dump(second["frames"])
    assert first["first_done"] == second["first_done"] == DEATH_STEP


# -- the schema itself ---------------------------------------------------------

def test_the_schema_vocabulary_matches_the_pinned_vendor_constants(schema):
    """The schema is hand-written, but its enums are crafter's own vocabulary."""
    defs = schema["$defs"]
    assert defs["item_name"]["enum"] == list(W.vendor.items)
    assert defs["achievement_name"]["enum"] == list(W.vendor.achievements)
    assert defs["material"]["enum"] == list(W.vendor.materials), (
        "standing_on's vocabulary is the material map's, and only that")
    assert defs["cell"]["enum"] == (
        list(W.vendor.materials)
        + [c.__name__.lower() for c in W.SEM_OBJECT_TYPES]
        + [W.NO_MATERIAL, W.OUT_OF_BOUNDS])
    assert schema["properties"]["inventory"]["required"] == list(W.vendor.items)
    assert schema["properties"]["achievements"]["required"] == list(W.vendor.achievements)
    # $defs/level says 0..9; that is only true while every item max is 9
    assert {info["max"] for info in W.vendor.items.values()} == {defs["level"]["maximum"]}


def test_the_schema_is_version_2_and_differs_from_version_1_by_standing_on_alone(schema):
    """A §1.2: the old frame schema verbatim plus one field. The version const
    and the frames the emitter makes have to agree about which one."""
    assert schema["properties"]["schema_version"]["const"] == "2" == K.FRAME_SCHEMA_VERSION
    assert "standing_on" in schema["required"]
    old_required = ["schema_version", "step", "daylight", "player", "inventory",
                    "window", "achievements", "deltas"]
    assert [k for k in schema["required"] if k != "standing_on"] == old_required
    assert sorted(schema["properties"]) == sorted(old_required + ["standing_on"])


def test_the_schema_rejects_malformed_frames(validator, episode):
    """Positive control for the acceptance test. A schema that accepts everything
    would make the acceptance line pass while proving nothing."""
    good = episode["frames"][-1]
    validator.validate(good)  # the control's baseline really is valid
    bad = {
        "zero delta (a non-sparse emitter)":
            {**good, "deltas": {"inventory": {"wood": 0}, "achievements": {}}},
        "achievement counter going down":
            {**good, "deltas": {"inventory": {}, "achievements": {"eat_cow": -1}}},
        "unknown window cell name": {**good, "window": [["chair"]]},
        "missing inventory key":
            {**good, "inventory": {k: v for k, v in good["inventory"].items() if k != "iron"}},
        "inventory above max": {**good, "inventory": {**good["inventory"], "wood": 10}},
        "extra top-level key (e.g. someone stuffing pixels in)":
            {**good, "obs": [[0, 0, 0]]},
        "daylight not a number": {**good, "daylight": "0.5"},
        "unversioned frame": {k: v for k, v in good.items() if k != "schema_version"},
        "a version-1 frame (no standing_on)":
            {k: v for k, v in good.items() if k != "standing_on"},
        "standing_on naming an object, not a material":
            {**good, "standing_on": "cow"},
        "standing_on out of the world": {**good, "standing_on": OUT_OF_BOUNDS},
        "still claiming to be version 1": {**good, "schema_version": "1"},
    }
    for why, frame in bad.items():
        assert list(validator.iter_errors(frame)), (
            f"schema accepted a frame it should reject: {why}")


def test_our_semantic_view_adds_fence_without_shifting_the_stock_ids():
    """The stock SemanticView omits Fence (env.py:47-49). Ours appends it last,
    so ids 1-12 (materials) and 13-18 (the stock objects) are untouched."""
    env = make_env(SEED)
    env.reset()
    tx = TelemetryExtractor(env)
    stock = W.engine.SemanticView(env._world, [
        W.objects.Player, W.objects.Cow, W.objects.Zombie,
        W.objects.Skeleton, W.objects.Arrow, W.objects.Plant])
    stock_names = W.semantic_id_names(env._world, stock)
    assert "fence" not in stock_names.values()
    assert tx.id_to_name == {**stock_names, 19: "fence"}
    assert tx.id_to_name[13] == "player" and tx.id_to_name[18] == "plant"


def test_the_window_pads_out_of_bounds_at_the_world_edge():
    """The scripted episode never leaves the middle of the map, so the padding
    branch needs its own case: at a corner, 4 of 9 rows and columns are outside."""
    env = make_env(SEED)
    env.reset()
    tx = TelemetryExtractor(env)
    corner = semantic_window(tx.sem_view(), (0, 0), K.WINDOW, tx.id_to_name)
    assert len(corner) == 9 and {len(row) for row in corner} == {9}
    assert all(cell == OUT_OF_BOUNDS for row in corner[:4] for cell in row)
    assert all(row[i] == OUT_OF_BOUNDS for row in corner for i in range(4))
    assert corner[4][4] != OUT_OF_BOUNDS, "cell (0,0) itself is inside the world"


def test_make_envs_balancer_flag_changes_the_world_not_the_frame_shape(validator):
    """The balancer is off in this line, always (A §1.1: no monsters). The flag
    survives on `make_env` only so that `off` can be shown to be a real choice."""
    off = run_episode(steps=40, balancer=False)["frames"]
    on = run_episode(steps=40, balancer=True)["frames"]
    for frame in on:
        validator.validate(frame)
    assert [sorted(f) for f in on] == [sorted(f) for f in off]
    assert dump(on) != dump(off), (
        "balancer=True must actually spawn/despawn: identical frames would mean "
        "the flag is a no-op")


def test_the_guards_reject_an_unreset_env_an_even_window_and_a_bad_action():
    env = make_env(SEED)
    with pytest.raises(RuntimeError, match="has not been reset"):
        TelemetryExtractor(env)
    env.reset()
    with pytest.raises(ValueError, match="odd"):
        TelemetryExtractor(env, window=8)
    tx = TelemetryExtractor(env)
    n_actions = len(W.vendor.actions)
    with pytest.raises(ValueError):
        tx.step(n_actions)
    with pytest.raises(ValueError):
        tx.step(-1)  # would silently wrap to a real action name
    with pytest.raises(TypeError):
        tx.step("noop")
    assert tx.env._step == 0, "no rejected action advanced the world"


# -- schema "2"'s one addition (A §1.2, D4) ------------------------------------

def test_standing_on_is_the_material_map_and_the_window_cannot_answer_it():
    """Why the field exists. The window draws the player OVER their own cell, so
    `window[4][4]` is "player" and the material underfoot is not derivable from
    the window at all — unlike `faced`, which at least was. Measured on the old
    line 2026-09-18: a body IN water with its drink rising said "move closer to
    water to refill drink" and stepped out."""
    env = make_env(SEED)
    env.reset()
    tx = TelemetryExtractor(env)
    frame = tx.frame0()
    here = tuple(int(v) for v in env._player.pos)
    assert frame["window"][4][4] == "player", "the centre is YOU, not the ground"
    assert frame["standing_on"] == env._world[here][0] == standing_on(env)

    # and it follows the body: put water under it and the field says so
    env._world[here] = "water"
    assert tx.frame()["standing_on"] == "water"
    assert tx.frame()["window"][4][4] == "player", "the window still cannot say it"


def test_standing_on_is_in_every_frame_of_an_episode_and_is_always_a_material(episode):
    materials = set(W.vendor.materials)
    seen = {f["standing_on"] for f in episode["frames"]}
    assert all("standing_on" in f for f in episode["frames"])
    assert seen <= materials, f"not a material: {seen - materials}"
    assert len(seen) > 1, "a 400-step walk that never changed the ground is not a walk"
