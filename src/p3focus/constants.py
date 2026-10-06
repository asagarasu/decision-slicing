"""Experiment constants, fixed in code rather than exposed as flags (A §5, D8).

Only three things vary between cells: arm, seed, steps. Everything here is copied
verbatim into every cell's manifest.json by the run command, so a reader never has
to guess what a run was configured with.
"""

ARMS = ("flat", "focus", "chat", "sliced")
SEEDS = (7, 10, 11, 12, 13)

WORLD_SIZE = 64            # cells per side; coordinates 0..63
WINDOW = 9                 # the body's view, odd, centred on the body
SPAWN = (32, 32)           # world axis

# per seed: two visits and the return, WORLD axis (+y down); A §1.1
ERRANDS = {
    7:  ((42, 40), (22, 24), (32, 32)),
    10: ((42, 44), (14, 30), (32, 32)),
    11: ((47, 40), (16, 25), (32, 32)),
    12: ((36, 51), (19, 22), (32, 32)),
    13: ((48, 38), (18, 28), (32, 32)),
}
NOTE_STEP = 10             # the note lands after this world step; A §1.1
ERRAND_ITEMS = ("pickaxe", "rope")   # the note's item words, one per visit, in order

VERBS = ("move_left", "move_right", "move_up", "move_down")   # A §1.1: the four moves and nothing else
NOOP = "noop"              # the harness's word for a defaulted reply; never offered to the model

K_HISTORY = 5              # trace lines shown; A §1.3
STALL_LENGTH = 8           # steps with no new seen cell; A §4.2
STALL_WINDOW = STALL_LENGTH + 1   # the gate's history window, one longer than the stall
DRINK_CROSSING_AT = 0      # drink reaching this from above fires the crossing; A §4.2
MAX_OPS_PER_REPLY = 5      # A §2
R3_CANDIDATES = 3          # A §3.1: at most three candidate cells in R3's reply

# model client; A §6
SERVER_DEFAULT = "http://127.0.0.1:8080"
MAX_TOKENS = 600
TIMEOUT_S = 600
TEMPERATURE = 0
SAMPLING_SEED = 42
GRAMMAR_PROBE_MARKER = "GRAMMAR-HELD"

# chat; A §3.3, B §7
CHAT_BUDGET_TOKENS = 90000
CHAT_KEEP_TURNS = 20

FRAME_SCHEMA_VERSION = "2"  # A §1.2: the old frame plus standing_on
