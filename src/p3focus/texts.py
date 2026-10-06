"""The texts every arm shares (B §1, §7): the legend, the world's lines, the
console manual, the history grammar. One copy each; the trace and chat
controllers import them (README law 5, one live implementation). Every string
here is quoted in `design/pages.md`; `test_texts.py` pins them to it.
"""
from p3focus import constants

#: two-letter window codes, the old `LEGEND` in its order; the body's own cell is the word
PLAYER_CODE = "YOU"
LEGEND = {
    "water": "Wa", "grass": "Gr", "stone": "St", "path": "Pa", "sand": "Sa", "tree": "Tr",
    "lava": "La", "coal": "Co", "iron": "Ir", "diamond": "Di", "table": "Tb", "furnace": "Fu",
    "player": PLAYER_CODE, "cow": "Cw", "zombie": "Zo", "skeleton": "Sk", "arrow": "Ar",
    "plant": "Pl", "fence": "Fe", "none": "??", "out_of_bounds": "XX",
}
#: never in this world (removed at reset, A §1.1), so never in the legend line
HIDDEN_NAMES = ("zombie", "skeleton", "arrow")

WALKABLE_WORDS = "grass, sand, path, water"


def legend_line():
    """`WINDOW CODES: …` (B §1.3, §7), generated from LEGEND minus the hidden names."""
    parts = []
    for name, code in LEGEND.items():
        if name in HIDDEN_NAMES:
            continue
        parts.append(f"{code}=yourself (the centre cell)" if name == "player" else f"{code}={name}")
    return f"WINDOW CODES: {' '.join(parts)}. Walkable: {WALKABLE_WORDS}."


MOVE_LINE = ("- move_up / move_down / move_left / move_right: one cell that way; into a "
             "non-walkable cell it only turns you to face it")
WATER_LINE = ("- water: a water cell is walkable, like grass or sand — you step INTO it. While "
              "you stand in one your drink rises by 1 each step, up to 9. There is no verb to "
              "press: being there is drinking.")
SAFE_LINE = "- water and grass are safe to stand on"          # fixed in-world content shown to the body; kept verbatim
#: states plainly there is nothing to break or craft. Without it, a body spent many
#: steps trying to "break through the stone wall", which has no verb in this world.
NO_CRAFT_LINE = "- there is nothing to break, pick up or craft here: the four moves are everything you can do"
#: spells out that at drink 9 standing in water does nothing and costs nothing. Without
#: saying so, bodies sat in water at full drink trying to "reduce" the level.
FULL_LINE = "- at drink 9 the meter is full; standing in water then changes nothing and costs nothing"
STANDING_ON_CLAUSE = ("; standing_on (the cell you are standing ON, by name — the window draws "
                      "YOU over your own cell, so this is the one cell the window cannot tell "
                      "you about)")
AXIS_LINE = ("Remember: +y is up and -y is down. To reach a cell with a LARGER y than yours, "
             "press move_up; a SMALLER y, move_down. +x is right, -x is left.")

#: B §1.1: the trace arms' background, the task off the page
HUMAN_FRAME_TRACE = "You are a bot player in a survival world. Your human player has gone mining."
#: B §7: chat states the task once
HUMAN_FRAME_CHAT = ("You are a bot player in a survival world. Your human player has gone mining and "
                    "has left you to map the surface — every cell you can walk on. They are waiting "
                    "for the map.")
WORLD_LAW = ("The world is 64 by 64 cells. You see the 9 by 9 around you and nothing farther. The "
             "clock runs whether you act or not: your drink falls as it runs, drink at 0 drains "
             "your health, and health at 0 is death.")
BACKGROUND_TRACE = HUMAN_FRAME_TRACE + "\n\n" + WORLD_LAW

FIRST_STEP_LINE = "(nothing has happened yet — this is your first step.)"

REFUSAL_PARAGRAPH = ("The console does not flatter you and it does not hint. When an action does "
                     "nothing, the line for that step says plainly what stopped it — \"did not move; "
                     "the cell to your right is tree\". That is the world saying what is there, not a "
                     "verdict on you.")


def state_description(turn_word="step"):
    """The sentence that teaches the state JSON (B §1.3 with "step"; B §7 with "turn")."""
    return ("Your state comes back at the bottom of this page as one JSON object: step (the clock); "
            "daylight (1 noon, 0 deep night); player {pos [x, y] (x 0..63, +x is right; y 0..63, +y "
            "is up); facing up/down/left/right — the cell your actions act on; health, drink, each "
            "0..9}; near {up, down, left, right: the cell beside you, by name}; faced (the one you "
            "face)" + STANDING_ON_CLAUSE + "; carrying (the items you have picked up, by name); window "
            "(9 rows of 9 cells around you, top row to "
            "bottom row, each row left to right; the centre cell, YOU, is yourself; the first line "
            "gives each column's x and every row begins with its own y, so a cell's [x, y] can be "
            "read off directly); mapped {here, "
            "up, down, left, right: whether that cell is already mapped}; deltas (what changed "
            f"since your last {turn_word}).")


def console_manual():
    """B §1.3, the trace arms' console manual, to the byte."""
    return "\n".join([
        "HOW TO USE THIS CONSOLE",
        "",
        state_description("step"),
        "",
        legend_line(),
        "",
        "ACTIONS — exactly one per step, by name:",
        MOVE_LINE,
        WATER_LINE,
        SAFE_LINE,
        FULL_LINE,
        NO_CRAFT_LINE,
        "",
        REFUSAL_PARAGRAPH,
    ])


def trace_action_line(step, action, intent, result):
    """One line of history (B §1.2, her grammar). An empty intent gets no clause."""
    on = f' on "{intent}"' if isinstance(intent, str) and intent.strip() else ""
    return f'step {int(step)}: you took action "{action}"{on}, and {result}.'
