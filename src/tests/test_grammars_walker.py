"""A small GBNF walker, and what each round's grammar admits and refuses (A §3).

Pinning a grammar's text says it did not change; it does not say what it means.
These tests say what it means: the walker parses the GBNF and decides whether a
candidate reply is in the language, so "R1 cannot produce `yes` with an empty
ops list" and "a target of 64 is not a coordinate" are checked claims and not
comments.

In one place the walker takes the strict reading rather than a generous one: a
rule ends at a newline unless the newline falls inside parentheses. Whether the
server's parser is that strict was not checked against a live llama.cpp; being
stricter here costs nothing, and it holds the grammars to one rule a line.
"""

import sys

import pytest

from p3focus import grammars


class GbnfError(ValueError):
    """The GBNF text could not be read."""


# --- the reader ---------------------------------------------------------

_LITERAL_ESCAPES = {
    "n": "\n", "r": "\r", "t": "\t", "\\": "\\", '"': '"', "'": "'", "/": "/",
    "b": "\b", "f": "\f", "]": "]", "[": "[", "-": "-", "^": "^",
}


class _Reader:
    """Index over the grammar text. `nested` is llama.cpp's `newline_ok`: true
    inside parentheses, false at the top level of a rule."""

    def __init__(self, text):
        self.s = text
        self.i = 0

    def space(self, nested):
        while self.i < len(self.s):
            char = self.s[self.i]
            if char in " \t\r":
                self.i += 1
            elif char == "\n" and nested:
                self.i += 1
            elif char == "#" and nested:
                while self.i < len(self.s) and self.s[self.i] != "\n":
                    self.i += 1
            else:
                break

    def expect(self, text):
        if not self.s.startswith(text, self.i):
            raise GbnfError(f"expected {text!r} at {self.s[self.i:self.i + 40]!r}")
        self.i += len(text)

    def name(self):
        start = self.i
        while self.i < len(self.s) and (self.s[self.i].isalnum() or self.s[self.i] in "-_"):
            self.i += 1
        if start == self.i:
            raise GbnfError(f"expected a rule name at {self.s[start:start + 40]!r}")
        return self.s[start:self.i]

    def char(self):
        """One character of a literal or a class, escapes resolved."""
        char = self.s[self.i]
        if char != "\\":
            self.i += 1
            return char
        marker = self.s[self.i + 1]
        self.i += 2
        if marker in _LITERAL_ESCAPES:
            return _LITERAL_ESCAPES[marker]
        if marker in "xu":
            width = 2 if marker == "x" else 4
            digits = self.s[self.i:self.i + width]
            self.i += width
            return chr(int(digits, 16))
        raise GbnfError(f"unknown escape \\{marker}")

    def literal(self):
        self.expect('"')
        out = []
        while self.s[self.i] != '"':
            out.append(self.char())
        self.i += 1
        return ("lit", "".join(out))

    def char_class(self):
        self.expect("[")
        negated = self.s[self.i] == "^"
        if negated:
            self.i += 1
        ranges = []
        while self.s[self.i] != "]":
            low = self.char()
            if self.s[self.i] == "-" and self.s[self.i + 1] != "]":
                self.i += 1
                ranges.append((low, self.char()))
            else:
                ranges.append((low, low))
        self.i += 1
        return ("class", negated, tuple(ranges))

    def postfix(self, node):
        if self.i >= len(self.s):
            return node
        char = self.s[self.i]
        if char in "*+?":
            self.i += 1
            return {"*": ("rep", node, 0, None), "+": ("rep", node, 1, None),
                    "?": ("rep", node, 0, 1)}[char]
        if char == "{":
            close = self.s.index("}", self.i)
            parts = self.s[self.i + 1:close].split(",")
            self.i = close + 1
            low = int(parts[0])
            if len(parts) == 1:
                return ("rep", node, low, low)
            return ("rep", node, low, None if not parts[1].strip() else int(parts[1]))
        return node

    def sequence(self, nested):
        items = []
        while True:
            self.space(nested)
            if self.i >= len(self.s):
                break
            char = self.s[self.i]
            if char == '"':
                node = self.literal()
            elif char == "[":
                node = self.char_class()
            elif char == "(":
                self.i += 1
                node = self.alternates(nested=True)
                self.space(True)
                self.expect(")")
            elif char.isalnum() or char in "-_":
                node = ("ref", self.name())
            else:
                break
            items.append(self.postfix(node))
        return items[0] if len(items) == 1 else ("seq", tuple(items))

    def alternates(self, nested):
        options = [self.sequence(nested)]
        while True:
            self.space(nested)
            if self.i < len(self.s) and self.s[self.i] == "|":
                self.i += 1
                options.append(self.sequence(nested))
            else:
                break
        return options[0] if len(options) == 1 else ("alt", tuple(options))


def parse_gbnf(text):
    """Read GBNF into `{rule name: node}`. Raises `GbnfError` on anything this
    subset does not cover, which includes a rule whose alternation runs past a
    newline outside parentheses — the mistake llama.cpp makes silently."""
    reader = _Reader(text)
    rules = {}
    while True:
        reader.space(nested=True)
        if reader.i >= len(reader.s):
            break
        name = reader.name()
        reader.space(False)
        reader.expect("::=")
        reader.space(False)
        rules[name] = reader.alternates(nested=False)
        reader.space(False)
        if reader.i < len(reader.s) and reader.s[reader.i] != "\n":
            raise GbnfError(
                f"rule {name!r} does not end at a newline: {reader.s[reader.i:reader.i + 40]!r}")
    if "root" not in rules:
        raise GbnfError("no root rule")
    return rules


def references(node):
    """Every rule name a node names, at any depth."""
    kind = node[0]
    if kind == "ref":
        return {node[1]}
    if kind in ("seq", "alt"):
        return set().union(*(references(child) for child in node[1])) if node[1] else set()
    if kind == "rep":
        return references(node[1])
    return set()


def undefined_and_unused(rules):
    """`(names referred to and never defined, names defined and never reached
    from root)` — a grammar should have neither."""
    undefined = set()
    reached = set()
    stack = ["root"]
    while stack:
        name = stack.pop()
        if name in reached:
            continue
        reached.add(name)
        if name not in rules:
            undefined.add(name)
            continue
        stack.extend(references(rules[name]))
    return sorted(undefined), sorted(set(rules) - reached)


# --- the matcher --------------------------------------------------------

def _match(node, text, at, rules, then):
    kind = node[0]
    if kind == "lit":
        return text.startswith(node[1], at) and then(at + len(node[1]))
    if kind == "class":
        if at >= len(text):
            return False
        _, negated, ranges = node
        hit = any(low <= text[at] <= high for low, high in ranges)
        return hit != negated and then(at + 1)
    if kind == "ref":
        if node[1] not in rules:
            raise GbnfError(f"undefined rule {node[1]!r}")
        return _match(rules[node[1]], text, at, rules, then)
    if kind == "seq":
        items = node[1]

        def step(index, pos):
            if index == len(items):
                return then(pos)
            return _match(items[index], text, pos, rules, lambda nxt: step(index + 1, nxt))

        return step(0, at)
    if kind == "alt":
        return any(_match(option, text, at, rules, then) for option in node[1])
    if kind == "rep":
        _, inner, low, high = node

        def repeat(pos, count):
            if count >= low and then(pos):
                return True
            if high is not None and count >= high:
                return False
            return _match(inner, text, pos, rules,
                          lambda nxt: nxt > pos and repeat(nxt, count + 1))

        return repeat(at, 0)
    raise GbnfError(f"unknown node {kind!r}")


def accepts(grammar_text, candidate):
    """Is `candidate` in the language of this GBNF, whole? The recursion limit
    is raised for the walk: a 160-character bounded field is 160 frames deep."""
    rules = grammar_text if isinstance(grammar_text, dict) else parse_gbnf(grammar_text)
    was = sys.getrecursionlimit()
    sys.setrecursionlimit(max(was, 20000))
    try:
        return _match(rules["root"], candidate, 0, rules, lambda end: end == len(candidate))
    finally:
        sys.setrecursionlimit(was)


# --- the walker's own tests ---------------------------------------------

def test_walker_reads_literals_classes_groups_and_repetition():
    text = (
        '# a comment line\n'
        'root ::= "a" (word | digit{2,3}) "z"\n'
        'word ::= [a-c]+\n'
        'digit ::= [0-9]\n'
    )
    for good in ("aaz", "abcz", "a12z", "a123z"):
        assert accepts(text, good), good
    for bad in ("az", "a1z", "a1234z", "adz", "aa", "Aaz", "aazz"):
        assert not accepts(text, bad), bad


def test_walker_resolves_the_json_escapes_the_grammars_use():
    text = 'root ::= "\\"" char* "\\""\nchar ::= [^"\\\\\\x00-\\x1F] | [\\\\] ["\\\\n]\n'
    assert accepts(text, '"plain"')
    assert accepts(text, '"a\\\\b"')       # an escaped backslash
    assert accepts(text, '"a\\"b"')        # an escaped quote
    assert not accepts(text, '"a\nb"')     # a raw control character
    assert not accepts(text, '"a\\qb"')    # not a JSON escape


def test_walker_refuses_an_alternation_split_across_lines():
    """The strict reading: a rule ends at the newline. A grammar written with
    `|` on the next line would mean one thing here and possibly another on the
    server, so it is refused rather than guessed at."""
    with pytest.raises(GbnfError):
        parse_gbnf('root ::= "a"\n  | "b"\n')
    assert accepts('root ::= (\n  "a"\n  | "b"\n)\n', "b")   # inside parens it is fine


# --- every grammar, structurally ----------------------------------------

@pytest.mark.parametrize("round_id", grammars.GRAMMAR_IDS)
def test_every_grammar_parses_with_no_undefined_and_no_unused_rule(round_id):
    rules = parse_gbnf(grammars.grammar(round_id))
    assert undefined_and_unused(rules) == ([], [])


@pytest.mark.parametrize("round_id", grammars.GRAMMAR_IDS)
def test_every_grammar_tolerates_the_whitespace_a_model_writes(round_id):
    """The same reply pretty-printed is still in the language: `ws` sits between
    every token, so indentation and newlines never make a reply invalid."""
    import json

    reply = _A_REPLY[round_id]
    text = grammars.grammar(round_id)
    assert accepts(text, json.dumps(reply))
    assert accepts(text, json.dumps(reply, indent=2))
    assert accepts(text, json.dumps(reply, separators=(",", ":")))


# one reply per round, in the shape A §3 gives it
_A_REPLY = {
    "R1": {"why": "the note names a cell I have no entry for", "maintain": "yes", "ops": [{"op": "add", "name": "reach_the_pickaxe",
                                       "until": "standing on [42, 23]"}]},
    "R1.5": {"delete": True},
    "R2": {"why": "nothing on me yet", "focus": "e3"},
    "R3": {"need": "the pickaxe", "candidates": [[42, 23], [41, 23]], "target": [42, 23],
           "why": "it is there"},
    "R4": {"action": "move_right", "intent": "getting to the pickaxe cell"},
    "flat": {"action": "move_up", "intent": "north edge is unmapped", "ops": [],
             "destination": [22, 39]},
    "chat": {"action": "move_down", "why": "the shore is south", "destination": None},
}


# --- R1: maintain -------------------------------------------------------

R1 = grammars.grammar("R1")


def test_r1_admits_no_and_yes_with_one_to_five_ops_and_nothing_else():
    assert accepts(R1, '{"why": "w", "maintain": "no"}')
    one = '{"op": "add", "name": "n", "until": "u"}'
    for count in (1, 2, 5):
        assert accepts(R1, '{"why": "w", "maintain": "yes", "ops": [%s]}' % ", ".join([one] * count))
    assert not accepts(R1, '{"why": "w", "maintain": "yes", "ops": [%s]}' % ", ".join([one] * 6))
    assert not accepts(R1, '{"why": "w", "maintain": "yes", "ops": []}')
    assert not accepts(R1, '{"why": "w", "maintain": "yes"}')
    assert not accepts(R1, '{"why": "w", "maintain": "no", "ops": [%s]}' % one)
    assert not accepts(R1, '{"why": "w", "maintain": "maybe"}')
    assert not accepts(R1, '{"maintain": "no"}')                      # the why comes first (A §3.1)
    assert not accepts(R1, '{"why": "w", "maintain": "no"} and here is why')


def test_r1_ops_are_add_edit_delete_in_the_manuals_field_order():
    def op(body):
        return '{"why": "w", "maintain": "yes", "ops": [%s]}' % body

    assert accepts(R1, op('{"op": "add", "name": "n", "until": "u"}'))
    assert accepts(R1, op('{"op": "add", "name": "n", "when": "w", "until": "u", "why": "y"}'))
    assert accepts(R1, op('{"op": "add", "name": "n", "until": "u", "why": "y"}'))
    assert accepts(R1, op('{"op": "edit", "id": "e2", "until": "u"}'))
    assert accepts(R1, op('{"op": "edit", "id": "e2", "name": "n", "why": "y"}'))
    assert accepts(R1, op('{"op": "delete", "id": "e12"}'))
    # invented ops like these are not in A §2's language
    assert not accepts(R1, op('{"op": "rerank", "id": "e2", "rank": 1}'))
    assert not accepts(R1, op('{"op": "retire", "id": "e2"}'))
    # no rank field anywhere (A §2)
    assert not accepts(R1, op('{"op": "add", "name": "n", "until": "u", "rank": 1}'))
    # add needs both of its required fields, and the order is the manual's
    assert not accepts(R1, op('{"op": "add", "name": "n"}'))
    assert not accepts(R1, op('{"op": "add", "until": "u", "name": "n"}'))
    # an id is e<digits>
    assert not accepts(R1, op('{"op": "delete", "id": "map_world"}'))
    assert not accepts(R1, op('{"op": "delete", "id": "2"}'))


def test_r1_edit_names_at_least_one_field_to_change():
    """A-QUESTION in grammars.py: A §2 does not say, and an edit that changes
    nothing would leave the list piece to invent a meaning."""
    assert not accepts(R1, '{"why": "w", "maintain": "yes", "ops": [{"op": "edit", "id": "e2"}]}')


def test_r1_bounds_a_name_at_80_characters_and_the_rest_at_160():
    def add(name="n", until="u"):
        return '{"why": "w", "maintain": "yes", "ops": [{"op": "add", "name": "%s", "until": "%s"}]}' % (
            name, until)

    assert accepts(R1, add(name="x" * 80))
    assert not accepts(R1, add(name="x" * 81))
    assert accepts(R1, add(until="x" * 160))
    assert not accepts(R1, add(until="x" * 161))


# --- R1.5, R2 -----------------------------------------------------------

def test_r1_5_admits_only_the_two_booleans():
    text = grammars.grammar("R1.5")
    assert accepts(text, '{"delete": true}')
    assert accepts(text, '{"delete": false}')
    assert not accepts(text, '{"delete": "true"}')
    assert not accepts(text, '{"delete": null}')
    assert not accepts(text, '{"delete": true, "id": "e2"}')


def test_r2_admits_an_id_and_never_none():
    """A §7 D6: the harness never picks, so `none` is its default and not an
    answer the body can give."""
    text = grammars.grammar("R2")
    assert accepts(text, '{"why": "w", "focus": "e1"}')
    assert accepts(text, '{"why": "w", "focus": "e307"}')
    assert not accepts(text, '{"why": "w", "focus": "none"}')
    assert not accepts(text, '{"why": "w", "focus": null}')
    assert not accepts(text, '{"why": "w", "focus": "map_world"}')
    assert not accepts(text, '{"focus": "e1"}')                              # the why comes first (A §3.1)
    assert not accepts(text, '{"focus": "e1", "why": "it is the errand"}')  # and not after


# --- R3, R4: the acting rounds -----------------------------------------

R3 = grammars.grammar("R3")


def test_r3_admits_need_candidates_target_why_in_that_order_and_no_other_key():
    assert accepts(R3, '{"need": "n", "candidates": [], "target": null, "why": "w"}')
    assert accepts(R3, '{"need": "n", "candidates": [[0, 0]], "target": [63, 63], "why": "w"}')
    assert not accepts(R3, '{"candidates": [], "target": null}')                      # need and why required
    assert not accepts(R3, '{"need": "n", "target": null, "candidates": [], "why": "w"}')  # order
    assert not accepts(R3, '{"need": "n", "candidates": [], "target": null, "do": "d", "why": "w"}')  # gone 09-24
    assert not accepts(R3, '{"need": "n", "candidates": [], "target": null, "why": "w", "ops": []}')


def test_r3_caps_candidates_at_three_and_keeps_coordinates_on_the_map():
    def reply(cands="[]", target="null"):
        return '{"need": "n", "candidates": %s, "target": %s, "why": "w"}' % (cands, target)

    assert accepts(R3, reply(cands="[[1, 1], [2, 2], [3, 3]]"))
    assert not accepts(R3, reply(cands="[[1, 1], [2, 2], [3, 3], [4, 4]]"))
    assert accepts(R3, reply(target="[63, 0]"))
    assert not accepts(R3, reply(target="[64, 0]"))
    assert not accepts(R3, reply(target="[0, 64]"))
    assert not accepts(R3, reply(target="[-1, 0]"))
    assert not accepts(R3, reply(target="[100, 100]"))
    assert not accepts(R3, reply(target="[7]"))
    assert not accepts(R3, reply(target="[7, 8, 9]"))


def test_r4_admits_the_four_moves_only_and_carries_no_ops_key():
    text = grammars.grammar("R4")
    for verb in grammars.VERBS:
        assert accepts(text, '{"action": "%s", "intent": "i"}' % verb)
    assert grammars.VERBS == ("move_left", "move_right", "move_up", "move_down")
    for verb in ("noop", "drink", "do", "sleep", "move_north", "MOVE_UP"):
        assert not accepts(text, '{"action": "%s", "intent": "i"}' % verb)
    assert accepts(text, '{"action": "move_up", "intent": ""}')     # A §3.1: may be ""
    assert not accepts(text, '{"action": "move_up"}')
    assert not accepts(text, '{"action": "move_up", "intent": "i", "ops": []}')
    assert not accepts(text, '{"intent": "i", "action": "move_up"}')
    assert not accepts(text, '{"action": "move_up", "intent": "%s"}' % ("x" * 161))


# --- flat, chat ---------------------------------------------------------

FLAT = grammars.grammar("flat")


def test_flat_carries_four_keys_with_ops_zero_to_five_and_a_destination_or_null():
    assert accepts(FLAT, '{"action": "move_up", "intent": "i", "ops": [], "destination": null}')
    assert accepts(
        FLAT, '{"action": "move_up", "intent": "i", "ops": [], "destination": [22, 39]}')
    one = '{"op": "delete", "id": "e1"}'
    for count in (1, 5):
        assert accepts(FLAT, '{"action": "move_up", "intent": "i", "ops": [%s], '
                             '"destination": null}' % ", ".join([one] * count))
    assert not accepts(FLAT, '{"action": "move_up", "intent": "i", "ops": [%s], '
                             '"destination": null}' % ", ".join([one] * 6))
    assert not accepts(FLAT, '{"action": "move_up", "intent": "i", "ops": []}')
    assert not accepts(FLAT, '{"action": "move_up", "intent": "i", "destination": null}')
    assert not accepts(FLAT, '{"action": "move_up", "intent": "i", "ops": [], '
                             '"destination": [64, 0]}')


def test_chat_carries_action_why_destination_and_no_intent_and_no_ops():
    text = grammars.grammar("chat")
    assert accepts(text, '{"action": "move_down", "why": "w", "destination": null}')
    assert accepts(text, '{"action": "move_down", "why": "w", "destination": [3, 4]}')
    assert not accepts(text, '{"action": "move_down", "intent": "w", "destination": null}')
    assert not accepts(text, '{"action": "move_down", "why": "w"}')
    assert not accepts(text, '{"action": "move_down", "why": "w", "destination": null, '
                             '"ops": []}')
