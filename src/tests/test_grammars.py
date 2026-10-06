"""Each round's grammar text, pinned (A §3), and A's example replies read back.

A grammar is generated code that reaches the server as text, so the text is what
is pinned here: a change to `grammars.py` that moves a single token has to move
these strings too, and the chair sees the change as a diff. What the grammars
*mean* — what each admits and refuses — is `test_grammars_walker.py`.
"""

import json

import pytest

from p3focus import grammars

# The seven grammars, verbatim. Regenerate with:
#   python -c "from p3focus import grammars; print(grammars.grammar('R1'), end='')"
PINNED = {
    'R1': r"""# R1 — maintain (A §3.1). The reply is {"why":…,"maintain":"no"} or
# {"why":…,"maintain":"yes","ops":[…]} with one to five ops, and nothing else;
# the why comes first (think, then decide):
# "yes" with [] and a sixth op are both outside the language.
root ::= maintain-no | maintain-yes
maintain-no ::= "{" ws "\"why\"" ws ":" ws text-160 ws "," ws "\"maintain\"" ws ":" ws "\"no\"" ws "}"
maintain-yes ::= "{" ws "\"why\"" ws ":" ws text-160 ws "," ws "\"maintain\"" ws ":" ws "\"yes\"" ws "," ws "\"ops\"" ws ":" ws op-list ws "}"
op-list ::= "[" ws op (ws "," ws op){0,4} ws "]"
op ::= op-add | op-edit | op-delete
op-add ::= "{" ws "\"op\"" ws ":" ws "\"add\"" ws "," ws name-kv (ws "," ws at-kv)? (ws "," ws when-kv)? ws "," ws until-kv (ws "," ws why-kv)? ws "}"
op-edit ::= "{" ws "\"op\"" ws ":" ws "\"edit\"" ws "," ws id-kv ws "," ws edit-fields ws "}"
edit-fields ::= name-kv (ws "," ws at-kv)? (ws "," ws when-kv)? (ws "," ws until-kv)? (ws "," ws why-kv)? | at-kv (ws "," ws when-kv)? (ws "," ws until-kv)? (ws "," ws why-kv)? | when-kv (ws "," ws until-kv)? (ws "," ws why-kv)? | until-kv (ws "," ws why-kv)? | why-kv
op-delete ::= "{" ws "\"op\"" ws ":" ws "\"delete\"" ws "," ws id-kv ws "}"
id-kv ::= "\"id\"" ws ":" ws entry-id
name-kv ::= "\"name\"" ws ":" ws text-80
at-kv ::= "\"at\"" ws ":" ws coord
when-kv ::= "\"when\"" ws ":" ws text-160
until-kv ::= "\"until\"" ws ":" ws text-160
why-kv ::= "\"why\"" ws ":" ws text-160
entry-id ::= "\"e" [0-9]+ "\""
coord ::= "[" ws coord-int ws "," ws coord-int ws "]"
coord-int ::= [0-9] | [1-5] [0-9] | "6" [0-3]
text-80 ::= "\"" char{0,80} "\""
text-160 ::= "\"" char{0,160} "\""
char ::= [^"\\\x7F\x00-\x1F] | [\\] (["\\/bfnrt] | "u" hex hex hex hex)
hex ::= [0-9a-fA-F]
ws ::= [ \t\n]{0,16}
""",
    'R1.5': r"""# R1.5 — confirm a deletion (A §3.1). One key, one boolean.
root ::= "{" ws "\"delete\"" ws ":" ws boolean ws "}"
boolean ::= "true" | "false"
ws ::= [ \t\n]{0,16}
""",
    'R2': r"""# R2 — the entry in force (A §3.1). One id and nothing else: the
# harness never picks, so `none` is not an answer here (A §7 D6).
# The body says why first, then picks; the harness reads
# only `focus`. Text before the decision, as R3's `need` is.
root ::= "{" ws "\"why\"" ws ":" ws text-160 ws "," ws "\"focus\"" ws ":" ws entry-id ws "}"
text-160 ::= "\"" char{0,160} "\""
char ::= [^"\\\x7F\x00-\x1F] | [\\] (["\\/bfnrt] | "u" hex hex hex hex)
hex ::= [0-9a-fA-F]
entry-id ::= "\"e" [0-9]+ "\""
ws ::= [ \t\n]{0,16}
""",
    'R3': r"""# R3 — the old round one (A §3.1, B §3.4): need, candidates, target, why,
# in the page's order; no ops key (A §3.1: the acting rounds cannot reach
# the list). The text before the target is where the body works out
# which cell; the text after says what it is for. Coordinates are
# shown-axis, +y up.
root ::= "{" ws "\"need\"" ws ":" ws text-160 ws "," ws "\"candidates\"" ws ":" ws candidate-list ws "," ws "\"target\"" ws ":" ws coord-or-null ws "," ws "\"why\"" ws ":" ws text-160 ws "}"
candidate-list ::= "[" ws "]" | "[" ws coord (ws "," ws coord){0,2} ws "]"
coord-or-null ::= coord | "null"
coord ::= "[" ws coord-int ws "," ws coord-int ws "]"
coord-int ::= [0-9] | [1-5] [0-9] | "6" [0-3]
text-160 ::= "\"" char{0,160} "\""
char ::= [^"\\\x7F\x00-\x1F] | [\\] (["\\/bfnrt] | "u" hex hex hex hex)
hex ::= [0-9a-fA-F]
ws ::= [ \t\n]{0,16}
""",
    'R4': r"""# R4 — the action (A §3.1, B §3.5). Two keys, no ops key; `intent` is
# required and may be "".
root ::= "{" ws "\"action\"" ws ":" ws verb ws "," ws "\"intent\"" ws ":" ws text-160 ws "}"
verb ::= "\"move_left\"" | "\"move_right\"" | "\"move_up\"" | "\"move_down\""
text-160 ::= "\"" char{0,160} "\""
char ::= [^"\\\x7F\x00-\x1F] | [\\] (["\\/bfnrt] | "u" hex hex hex hex)
hex ::= [0-9a-fA-F]
ws ::= [ \t\n]{0,16}
""",
    'flat': r"""# flat — the whole step in one reply (A §3.2, B §3.6). Four keys in
# the page's order; ops is zero to five, [] when nothing changed.
# `destination` is shown-axis, +y up, and null is an answer.
root ::= "{" ws "\"action\"" ws ":" ws verb ws "," ws "\"intent\"" ws ":" ws text-160 ws "," ws "\"ops\"" ws ":" ws op-list ws "," ws "\"destination\"" ws ":" ws coord-or-null ws "}"
verb ::= "\"move_left\"" | "\"move_right\"" | "\"move_up\"" | "\"move_down\""
op-list ::= "[" ws "]" | "[" ws op (ws "," ws op){0,4} ws "]"
op ::= op-add | op-edit | op-delete
op-add ::= "{" ws "\"op\"" ws ":" ws "\"add\"" ws "," ws name-kv (ws "," ws at-kv)? (ws "," ws when-kv)? ws "," ws until-kv (ws "," ws why-kv)? ws "}"
op-edit ::= "{" ws "\"op\"" ws ":" ws "\"edit\"" ws "," ws id-kv ws "," ws edit-fields ws "}"
edit-fields ::= name-kv (ws "," ws at-kv)? (ws "," ws when-kv)? (ws "," ws until-kv)? (ws "," ws why-kv)? | at-kv (ws "," ws when-kv)? (ws "," ws until-kv)? (ws "," ws why-kv)? | when-kv (ws "," ws until-kv)? (ws "," ws why-kv)? | until-kv (ws "," ws why-kv)? | why-kv
op-delete ::= "{" ws "\"op\"" ws ":" ws "\"delete\"" ws "," ws id-kv ws "}"
id-kv ::= "\"id\"" ws ":" ws entry-id
name-kv ::= "\"name\"" ws ":" ws text-80
at-kv ::= "\"at\"" ws ":" ws coord
when-kv ::= "\"when\"" ws ":" ws text-160
until-kv ::= "\"until\"" ws ":" ws text-160
why-kv ::= "\"why\"" ws ":" ws text-160
entry-id ::= "\"e" [0-9]+ "\""
coord-or-null ::= coord | "null"
coord ::= "[" ws coord-int ws "," ws coord-int ws "]"
coord-int ::= [0-9] | [1-5] [0-9] | "6" [0-3]
text-80 ::= "\"" char{0,80} "\""
text-160 ::= "\"" char{0,160} "\""
char ::= [^"\\\x7F\x00-\x1F] | [\\] (["\\/bfnrt] | "u" hex hex hex hex)
hex ::= [0-9a-fA-F]
ws ::= [ \t\n]{0,16}
""",
    'chat': r"""# chat — one reply a turn (A §3.3, B §7). Three keys in the system
# message's order; chat has no list. `destination` is shown-axis, +y up.
root ::= "{" ws "\"action\"" ws ":" ws verb ws "," ws "\"why\"" ws ":" ws text-160 ws "," ws "\"destination\"" ws ":" ws coord-or-null ws "}"
verb ::= "\"move_left\"" | "\"move_right\"" | "\"move_up\"" | "\"move_down\""
coord-or-null ::= coord | "null"
coord ::= "[" ws coord-int ws "," ws coord-int ws "]"
coord-int ::= [0-9] | [1-5] [0-9] | "6" [0-3]
text-160 ::= "\"" char{0,160} "\""
char ::= [^"\\\x7F\x00-\x1F] | [\\] (["\\/bfnrt] | "u" hex hex hex hex)
hex ::= [0-9a-fA-F]
ws ::= [ \t\n]{0,16}
""",
}


def test_the_rounds_are_As_and_the_ids_are_the_manifests():
    """A §3: R1, R1.5, R2, R3, R4 for the trace arms, flat and chat for the
    one-round arms. The same ids are a call row's `grammar_id` (A §4.1) and the
    manifest's `grammar_ids` (A §4.4)."""
    assert grammars.GRAMMAR_IDS == ("R1", "R1.5", "R2", "R3", "R4", "flat", "chat")
    assert list(grammars.all_grammars()) == list(grammars.GRAMMAR_IDS)


@pytest.mark.parametrize("round_id", grammars.GRAMMAR_IDS)
def test_the_grammar_text_is_what_was_pinned(round_id):
    assert grammars.grammar(round_id) == PINNED[round_id]
    assert grammars.all_grammars()[round_id] == PINNED[round_id]


def test_a_round_with_no_grammar_is_refused_by_name():
    with pytest.raises(ValueError) as caught:
        grammars.grammar("R5")
    assert "R5" in str(caught.value)


def test_the_field_limits_are_As_and_reach_the_text():
    """A §2: name 80 characters, the rest 160. The grammars carry the numbers,
    so a change to either is visible in the pinned text above."""
    assert (grammars.NAME_MAX, grammars.TEXT_MAX) == (80, 160)
    assert r'text-80 ::= "\"" char{0,80} "\""' in PINNED["R1"]
    assert r'text-160 ::= "\"" char{0,160} "\""' in PINNED["R1"]


def test_no_acting_round_pins_an_ops_key():
    """A §3.1: neither R3's nor R4's grammar has an `ops` field, so the parser
    has no path from the acting rounds to the list (A §4.2, `ops_in_acting_reply`
    must never fire)."""
    for round_id in ("R3", "R4", "chat"):
        assert '"ops"' not in PINNED[round_id].replace(r'\"', '"')
    for round_id in ("R1", "flat"):
        assert r'"\"ops\""' in PINNED[round_id]


# A's reply shapes (§3.1-§3.3) with their placeholders filled: the keys, and the
# order the page prints them in (B §3).
A_EXAMPLES = [
    ("R1", '{"why": "as it stands", "maintain": "no"}', ["why", "maintain"]),
    ("R1", '{"why": "the note names a cell I have no entry for", "maintain": "yes", "ops": [{"op": "add",'
           ' "name": "reach_the_pickaxe", "until": "standing on [42, 23]"}]}', ["why", "maintain", "ops"]),
    ("R1.5", '{"delete": true}', ["delete"]),
    ("R2", '{"why": "I carry nothing, so the pickaxe first", "focus": "e3"}', ["why", "focus"]),
    ("R3", '{"need": "the pickaxe", "candidates": [[42, 23], [41, 23]], "target": [42, 23],'
           ' "why": "it is there"}', ["need", "candidates", "target", "why"]),
    ("R3", '{"need": "water", "candidates": [], "target": null, "why": "none in view"}',
     ["need", "candidates", "target", "why"]),
    ("R4", '{"action": "move_right", "intent": "getting to the pickaxe"}',
     ["action", "intent"]),
    ("flat", '{"action": "move_up", "intent": "the north edge is unmapped",'
             ' "ops": [], "destination": [22, 39]}',
     ["action", "intent", "ops", "destination"]),
    ("chat", '{"action": "move_down", "why": "the shore is south",'
             ' "destination": null}', ["action", "why", "destination"]),
]


@pytest.mark.parametrize("round_id,reply,keys", A_EXAMPLES,
                         ids=[f"{row[0]}-{i}" for i, row in enumerate(A_EXAMPLES)])
def test_As_example_replies_read_back_with_exactly_the_keys_the_page_prints(
        round_id, reply, keys):
    parsed = json.loads(reply)
    assert list(parsed) == keys      # dict order is the JSON's order: A's order
    assert round_id in grammars.GRAMMAR_IDS


def test_the_op_shapes_of_A_2_read_back_with_their_own_keys():
    """A §2: the whole language of change. `add` carries name and until and may
    carry when and why; `edit` names an id and what changes; `delete` names an
    id. No `rank` anywhere (A §2)."""
    add = json.loads('{"op": "add", "name": "n", "when": "w", "until": "u", "why": "y"}')
    assert list(add) == ["op", "name", "when", "until", "why"]
    assert list(json.loads('{"op": "edit", "id": "e3", "until": "u"}')) == ["op", "id", "until"]
    assert list(json.loads('{"op": "delete", "id": "e3"}')) == ["op", "id"]
    assert "rank" not in PINNED["R1"]
