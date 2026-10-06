"""The state JSON every page carries (A §1.3; B §5, §7): the original
`render_frame` plus `standing_on` and the `mapped` bits, keys sorted. Built from
the world's frame (A §1.2) and the world's mapped bits; pure.
"""
import json

from p3focus import axis, texts


def dumps(obj):
    """Sorted-key JSON (the original `dumps`): the model reads the same bytes every time."""
    return json.dumps(obj, sort_keys=True)


def encode_window(window, pos_shown=None):
    """The 9×9 of names -> strings of two-letter codes (B §5). With `pos_shown`
    (the body's SHOWN position), every row begins with its own shown y and a
    first line gives each column's x — a design instruction of 09-24 to label the
    window, after a body dying of thirst read the water four cells right and four
    down as "[37, 48]" and walked the wrong way; the window's rows are north-first,
    so the top row is the LARGEST shown y."""
    rows = [" ".join(texts.LEGEND.get(name, "??") for name in row) for row in window]
    if pos_shown is None:
        return rows
    half = len(window) // 2
    x0, y0 = int(pos_shown[0]), int(pos_shown[1])
    header = "x=" + " ".join(f"{x0 + dx:2d}" for dx in range(-half, half + 1))
    return [header] + [f"y={y0 + half - i:2d}: {row}" for i, row in enumerate(rows)]


def near_cells(window):
    """{up, down, left, right: the name of the cell beside the body}."""
    n = len(window)
    c = n // 2
    return {"up": window[c - 1][c], "down": window[c + 1][c],
            "left": window[c][c - 1], "right": window[c][c + 1]}


def render_state(frame, mapped_bits, carrying=()):
    """The state object (B §5 example): step, daylight to two decimals, player
    {pos in the SHOWN axis, facing word, health, drink}, near, faced, window,
    mapped, standing_on, carrying (the errand items picked up so far, A §1.3),
    deltas (inventory only, food never; empty dict when nothing changed). Food,
    energy, inventory and achievements never appear."""
    p = frame["player"]
    facing = axis.facing_word(p["facing"])
    near = near_cells(frame["window"])
    inv = {k: int(v) for k, v in (frame.get("deltas", {}).get("inventory") or {}).items()
           if k not in ("food", "energy")}
    return {
        "step": int(frame["step"]),
        "daylight": round(float(frame["daylight"]), 2),
        "player": {"pos": axis.shown_pos(p["pos"]), "facing": facing,
                   "health": int(p["health"]), "drink": int(p["drink"])},
        "near": near,
        "faced": near.get(facing),
        "window": encode_window(frame["window"], axis.shown_pos(p["pos"])),
        "mapped": {k: bool(v) for k, v in mapped_bits.items()},
        "standing_on": frame["standing_on"],
        "carrying": list(carrying),
        "deltas": ({"inventory": inv} if inv else {}),
    }


def carrying_words(carrying):
    """`nothing` / `the pickaxe` / `the pickaxe and the rope` — the words the pages use
    for what is on the body (a design note of 09-24: say it when it is empty too)."""
    items = list(carrying)
    return "nothing" if not items else " and ".join(f"the {item}" for item in items)


def state_line(frame, mapped_bits, clause, carrying=()):
    """`step current: you are at [x, y], carrying <nothing | the pickaxe …>, your state {…}.
    respond with <clause>` (B §5)."""
    body = render_state(frame, mapped_bits, carrying)
    return (f"step current: you are at {json.dumps(body['player']['pos'])}, carrying "
            f"{carrying_words(carrying)}, your state "
            f"{dumps(body)}. respond with{'' if clause.startswith(':') else ' '}{clause}")
