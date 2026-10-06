"""The GBNF grammars, one per round (A §3; A §7 D1: every arm's reply is
grammar-constrained, so a reply is always the right *shape* and "invalid" can
only ever mean semantically wrong — A §3.4, which is the controllers' work).

Each grammar pins the top-level keys in the order its page prints them (B §3),
pins their value types, and bounds free text to the lengths A §2 gives. Bounds
are the grammar's, never truncation's (A §2, "Limits").

Coordinates here are in the **shown** axis (+y up, A §1.1): every coordinate a
grammar admits is one the model wrote after reading a page in that axis, and it
is the controller that maps it back to the world axis (+y down) before anything
is logged. The grammar only says "two integers 0..63".

Public: `GRAMMAR_IDS`, `grammar(round_id)`, `all_grammars()`.
"""

from p3focus import constants

# Field limits, A §2. Not in constants.py (four branches merge into it); named
# here because only the grammars enforce them.
NAME_MAX = 80             # an entry's `name`
TEXT_MAX = 160            # `when`, `until`, `why`, and the free text of a round:
                          # R3's `need` and `why`, R4's and flat's `intent`, chat's `why`

# The verbs, A §1.1: the four moves and nothing else, from constants since the
# merge (the world piece reads the same tuple). `noop` is the harness's word for
# a defaulted reply and is not in any grammar.
VERBS = constants.VERBS

GRAMMAR_IDS = ("R1", "R1.5", "R2", "R3", "R4", "flat", "chat")


# --- the shared rules ---------------------------------------------------
# String, char, hex and ws follow llama.cpp's shipped json.gbnf idioms. One rule
# to a line, and no alternation split across lines: whether a rule may continue
# past a newline outside parentheses is the grammar server's parser's business,
# and these grammars never rely on it.

#: Bounded, not `*`: a show cell's six invalid replies were all
#: R1, all the same shape — the body's `why` ran past TEXT_MAX, the grammar forced the closing
#: quote, and the model then emitted newlines, tabs or spaces to the 600-token cap, because
#: unbounded `ws` was the only continuation that read like more prose. Sixteen is more than any
#: reply needs between two tokens — a pretty-printed reply indents nine deep at most — and too few to run away in.
_WS = r'ws ::= [ \t\n]{0,16}'
_CHAR = r'char ::= [^"\\\x7F\x00-\x1F] | [\\] (["\\/bfnrt] | "u" hex hex hex hex)'
_HEX = r'hex ::= [0-9a-fA-F]'
_ENTRY_ID = r'entry-id ::= "\"e" [0-9]+ "\""'   # ids are e1, e2, … (A §2)


def _text_rule(limit):
    """`text-<limit>`: a JSON string of at most `limit` characters (A §2)."""
    return r'text-%d ::= "\"" char{0,%d} "\""' % (limit, limit)


def _kv(key, value_rule):
    """One `"key": <rule>` member, with the key spelled as a literal. The value
    may not carry a bare `|`: llama.cpp reads alternation at the top of the rule
    it appears in, so `"a" | "b"` here would split the whole object in two. A
    choice of values gets its own rule (`boolean`, `coord-or-null`)."""
    if "|" in value_rule:
        raise ValueError(
            f"value of {key!r} carries a bare '|' ({value_rule!r}); give it a rule name")
    return r'"\"%s\"" ws ":" ws %s' % (key, value_rule)


def _named_kv(name, key, value_rule):
    """A rule named `name` for one `"key": <rule>` member."""
    return "%s ::= %s" % (name, _kv(key, value_rule))


def _obj(*members):
    """A JSON object whose members are fixed, in this order, all present."""
    return '"{" ws ' + ' ws "," ws '.join(members) + ' ws "}"'


def _coord_int_rule(size=constants.WORLD_SIZE):
    """`coord-int`: the integers 0..size-1, as digit alternatives. World is
    64 cells a side (A §1.1), so this is 0..63."""
    hi = size - 1
    if not 10 <= hi <= 99:
        raise ValueError(f"world size {size} is outside this rule's two-digit range")
    tens, ones = divmod(hi, 10)
    alts = ["[0-9]"]
    if tens >= 2:
        alts.append(f"[1-{tens - 1}] [0-9]")
    alts.append(f'"{tens}" [0-{ones}]')
    return "coord-int ::= " + " | ".join(alts)


_COORD = 'coord ::= "[" ws coord-int ws "," ws coord-int ws "]"'
_COORD_OR_NULL = 'coord-or-null ::= coord | "null"'
_BOOLEAN = 'boolean ::= "true" | "false"'
_VERB = "verb ::= " + " | ".join(r'"\"%s\""' % v for v in VERBS)

_STRING_RULES = [_CHAR, _HEX]
_COORD_RULES = [_COORD_OR_NULL, _COORD, _coord_int_rule()]


def _opt(member):
    """`member`, optional, with the comma that would precede it."""
    return ' (ws "," ws %s)?' % member


def _op_rules():
    """The whole language of change (A §2): add, edit, delete, in the field
    order the list manual prints (B §2). `edit` carries at least one field to
    change; see the A-QUESTION below."""
    return [
        "op ::= op-add | op-edit | op-delete",
        "op-add ::= " + _obj(
            _kv("op", r'"\"add\""'), "name-kv" + _opt("at-kv") + _opt("when-kv"),
            "until-kv" + _opt("why-kv")),
        "op-edit ::= " + _obj(_kv("op", r'"\"edit\""'), "id-kv", "edit-fields"),
        # A-QUESTION: A §2 spells edit as `{"op":"edit","id":…}` plus "any of"
        # the four fields and does not say whether none of them is an edit. An
        # edit that names no field changes nothing and the list piece would have
        # to invent a meaning for it, so the grammar requires one; the four
        # alternatives keep the manual's field order.
        "edit-fields ::= " + " | ".join([
            "name-kv" + _opt("at-kv") + _opt("when-kv") + _opt("until-kv") + _opt("why-kv"),
            "at-kv" + _opt("when-kv") + _opt("until-kv") + _opt("why-kv"),
            "when-kv" + _opt("until-kv") + _opt("why-kv"),
            "until-kv" + _opt("why-kv"),
            "why-kv",
        ]),
        "op-delete ::= " + _obj(_kv("op", r'"\"delete\""'), "id-kv"),
        _named_kv("id-kv", "id", "entry-id"),
        _named_kv("name-kv", "name", "text-%d" % NAME_MAX),
        # A §2: the position an entry is about, shown-axis, inside the world
        _named_kv("at-kv", "at", "coord"),
        _named_kv("when-kv", "when", "text-%d" % TEXT_MAX),
        _named_kv("until-kv", "until", "text-%d" % TEXT_MAX),
        _named_kv("why-kv", "why", "text-%d" % TEXT_MAX),
        _ENTRY_ID,
    ]


def _op_list_rule(low, high=constants.MAX_OPS_PER_REPLY):
    """`op-list`: an array of `low`..`high` ops (A §2: at most five a reply)."""
    filled = 'ws op (ws "," ws op){0,%d} ws' % (high - 1)
    if low == 0:
        return 'op-list ::= "[" ws "]" | "[" %s "]"' % filled
    return 'op-list ::= "[" %s "]"' % filled


# --- one builder per round ----------------------------------------------

def _r1():
    return [
        "# R1 — maintain (A §3.1). The reply is {\"why\":…,\"maintain\":\"no\"} or",
        "# {\"why\":…,\"maintain\":\"yes\",\"ops\":[…]} with one to five ops, and nothing else;",
        "# the why comes first (think, then decide):",
        '# "yes" with [] and a sixth op are both outside the language.',
        "root ::= maintain-no | maintain-yes",
        "maintain-no ::= " + _obj(_kv("why", "text-%d" % TEXT_MAX), _kv("maintain", r'"\"no\""')),
        "maintain-yes ::= " + _obj(_kv("why", "text-%d" % TEXT_MAX), _kv("maintain", r'"\"yes\""'),
                                   _kv("ops", "op-list")),
        _op_list_rule(low=1),
        *_op_rules(),
        _COORD, _coord_int_rule(),      # for an entry's `at` (A §2)
        _text_rule(NAME_MAX),
        _text_rule(TEXT_MAX),
        *_STRING_RULES,
        _WS,
    ]


def _r1_5():
    return [
        "# R1.5 — confirm a deletion (A §3.1). One key, one boolean.",
        "root ::= " + _obj(_kv("delete", "boolean")),
        _BOOLEAN,
        _WS,
    ]


def _r2():
    return [
        "# R2 — the entry in force (A §3.1). One id and nothing else: the",
        "# harness never picks, so `none` is not an answer here (A §7 D6).",
        "# The body says why first, then picks; the harness reads",
        "# only `focus`. Text before the decision, as R3's `need` is.",
        "root ::= " + _obj(_kv("why", "text-%d" % TEXT_MAX), _kv("focus", "entry-id")),
        _text_rule(TEXT_MAX),
        *_STRING_RULES,
        _ENTRY_ID,
        _WS,
    ]


def _r3():
    return [
        "# R3 — the old round one (A §3.1, B §3.4): need, candidates, target, why,",
        "# in the page's order; no ops key (A §3.1: the acting rounds cannot reach",
        "# the list). The text before the target is where the body works out",
        "# which cell; the text after says what it is for. Coordinates are",
        "# shown-axis, +y up.",
        "root ::= " + _obj(
            _kv("need", "text-%d" % TEXT_MAX),
            _kv("candidates", "candidate-list"),
            _kv("target", "coord-or-null"),
            _kv("why", "text-%d" % TEXT_MAX)),
        'candidate-list ::= "[" ws "]" | "[" ws coord (ws "," ws coord){0,%d} ws "]"'
        % (constants.R3_CANDIDATES - 1),
        *_COORD_RULES,
        _text_rule(TEXT_MAX),
        *_STRING_RULES,
        _WS,
    ]


def _r4():
    return [
        "# R4 — the action (A §3.1, B §3.5). Two keys, no ops key; `intent` is",
        '# required and may be "".',
        "root ::= " + _obj(_kv("action", "verb"), _kv("intent", "text-%d" % TEXT_MAX)),
        _VERB,
        _text_rule(TEXT_MAX),
        *_STRING_RULES,
        _WS,
    ]


def _flat():
    return [
        "# flat — the whole step in one reply (A §3.2, B §3.6). Four keys in",
        "# the page's order; ops is zero to five, [] when nothing changed.",
        "# `destination` is shown-axis, +y up, and null is an answer.",
        "root ::= " + _obj(
            _kv("action", "verb"),
            _kv("intent", "text-%d" % TEXT_MAX),
            _kv("ops", "op-list"),
            _kv("destination", "coord-or-null")),
        _VERB,
        _op_list_rule(low=0),
        *_op_rules(),
        *_COORD_RULES,
        _text_rule(NAME_MAX),
        _text_rule(TEXT_MAX),
        *_STRING_RULES,
        _WS,
    ]


def _chat():
    return [
        "# chat — one reply a turn (A §3.3, B §7). Three keys in the system",
        "# message's order; chat has no list. `destination` is shown-axis, +y up.",
        "root ::= " + _obj(
            _kv("action", "verb"),
            _kv("why", "text-%d" % TEXT_MAX),
            _kv("destination", "coord-or-null")),
        _VERB,
        *_COORD_RULES,
        _text_rule(TEXT_MAX),
        *_STRING_RULES,
        _WS,
    ]


_BUILDERS = {
    "R1": _r1,
    "R1.5": _r1_5,
    "R2": _r2,
    "R3": _r3,
    "R4": _r4,
    "flat": _flat,
    "chat": _chat,
}


def grammar(round_id):
    """The GBNF text for one round (A §3), ending in a newline. `round_id` is
    one of `GRAMMAR_IDS` and is also the `grammar_id` of that call's row
    (A §4.1) and one of the manifest's `grammar_ids` (A §4.4)."""
    try:
        build = _BUILDERS[round_id]
    except KeyError:
        raise ValueError(
            f"no grammar for {round_id!r}; the rounds are {list(GRAMMAR_IDS)}") from None
    return "\n".join(build()) + "\n"


def all_grammars():
    """Every round's grammar, `{grammar_id: text}`, in `GRAMMAR_IDS` order —
    what the manifest's `grammar_ids` names (A §4.4)."""
    return {round_id: grammar(round_id) for round_id in GRAMMAR_IDS}
