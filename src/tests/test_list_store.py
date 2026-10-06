"""The list (A §2): ids, the three ops, the whole-reply refusal, held deletes,
and the entry in force."""
import json

from p3focus import list_store


def test_the_list_starts_at_dawn_with_b_4s_entry_in_force():
    store = list_store.ListStore()
    assert store.entries == [{"id": "e1", "name": "map_world",
                              "until": "every walkable cell mapped"}]
    assert store.focus == "e1"
    assert list_store.ListStore(dawn=False).entries == []


def test_ids_are_given_in_order_and_never_reused():
    store = list_store.ListStore(dawn=False)
    store.add("one", "until one")
    store.add("two", "until two")
    assert store.ids == ["e1", "e2"]
    store.delete("e1")
    store.add("three", "until three")
    assert store.ids == ["e2", "e3"]


def test_an_optional_field_is_absent_and_never_null():
    store = list_store.ListStore(dawn=False)
    entry = store.add("one", "until one", why="because")
    assert entry == {"id": "e1", "name": "one", "until": "until one", "why": "because"}
    assert "when" not in entry
    assert "null" not in store.render_list()


def test_an_entry_renders_in_the_wire_order_of_a_2():
    store = list_store.ListStore(dawn=False)
    store.add("one", "until one", when="now", why="because", at=[3, 4])
    assert list(json.loads(store.render_list())[0]) == list(list_store.ENTRY_FIELDS)


def test_an_edit_changes_named_fields_and_leaves_the_rest():
    store = list_store.ListStore()
    store.edit("e1", why="the standing task")
    assert store.get("e1") == {"id": "e1", "name": "map_world",
                               "until": "every walkable cell mapped",
                               "why": "the standing task"}
    assert store.focus == "e1"          # an edit leaves the entry in force (A §2)


def test_an_edit_or_delete_naming_an_unknown_id_refuses_the_whole_reply():
    store = list_store.ListStore()
    ops = [{"op": "add", "name": "two", "until": "soon"}, {"op": "delete", "id": "e9"}]
    reason = store.validate(ops)
    assert reason and "e9" in reason
    assert store.ids == ["e1"], "nothing is applied before the reply is judged"


def test_an_edit_may_not_name_an_id_the_same_reply_added():
    store = list_store.ListStore(dawn=False)
    ops = [{"op": "add", "name": "one", "until": "soon"},
           {"op": "edit", "id": "e1", "why": "later"}]
    assert store.validate(ops) is not None       # A §2: it must have existed BEFORE


def test_an_op_that_is_not_one_of_a_2s_three_is_a_reason_not_a_crash():
    store = list_store.ListStore()
    assert "no \"op\"" in store.validate([{"op": "rerank", "id": "e1"}])
    assert store.validate([{"op": "add", "name": "one"}])           # no until
    assert store.validate([{"op": "edit", "id": "e1"}])             # changes nothing
    assert store.validate([]) is not None
    assert store.validate("no") is not None


def test_ops_apply_in_order_and_the_row_is_a_4_2s():
    store = list_store.ListStore()
    ops = [{"op": "add", "name": "two", "until": "soon"},
           {"op": "edit", "id": "e1", "name": "map"}]
    row, held = store.apply(ops, "R1")
    assert held == []
    assert set(row) == {"source", "ops", "list_after"}
    assert row["source"] == "R1"
    assert [e["id"] for e in row["list_after"]] == ["e1", "e2"]
    assert row["list_after"][0]["name"] == "map"


def test_a_delete_is_held_for_r1_5_and_applies_only_on_confirmation():
    store = list_store.ListStore()
    store.add("two", "soon")
    row, held = store.apply([{"op": "delete", "id": "e1"}], "R1", hold=True)
    assert held == ["e1"]
    assert [e["id"] for e in row["list_after"]] == ["e1", "e2"], "still there for R1.5's page"
    removed, cleared = store.confirm_delete("e1")
    assert removed and cleared                  # e1 was the entry in force
    assert store.ids == ["e2"] and store.focus is None


def test_flat_deletes_without_holding_anything():
    store = list_store.ListStore()
    store.add("two", "soon")
    row, held = store.apply([{"op": "delete", "id": "e1"}], "flat", hold=False)
    assert held == []
    assert [e["id"] for e in row["list_after"]] == ["e2"]


def test_one_reply_that_deletes_the_same_id_twice_holds_it_once():
    store = list_store.ListStore()
    _, held = store.apply([{"op": "delete", "id": "e1"}, {"op": "delete", "id": "e1"}], "R1")
    assert held == ["e1"]


def test_the_entry_in_force_is_cleared_only_when_its_own_entry_goes():
    store = list_store.ListStore()
    store.add("two", "soon")
    store.set_focus("e2")
    store.delete("e1")
    assert store.focus == "e2"
    store.delete("e2")
    assert store.focus is None


def test_r2s_id_is_checked_against_the_list():
    store = list_store.ListStore()
    assert store.validate_focus("e1") is None
    assert "e9" in store.validate_focus("e9")


def test_an_empty_list_renders_as_the_empty_list():
    store = list_store.ListStore(dawn=False)
    assert store.render_list() == "[]"
    assert store.focus_entry is None


# -- `at`, the position field (A §2) ----------------

def test_an_entry_may_carry_a_position_and_renders_it_after_its_name():
    store = list_store.ListStore(dawn=False)
    store.add("get_pickaxe", "I have the pickaxe", at=[42, 23], when="the note arrived")
    rendered = json.loads(store.render_list())[0]
    assert list(rendered) == ["id", "name", "at", "when", "until"]
    assert rendered["at"] == [42, 23]
    # an edit may set it, change it, or leave it alone
    store.edit("e1", at=[22, 39])
    assert store.get("e1")["at"] == [22, 39]
    store.edit("e1", why="still needed")
    assert store.get("e1")["at"] == [22, 39]
    # and validate refuses one that is not a position inside the world
    assert store.validate([{"op": "add", "name": "x", "until": "y", "at": [70, 2]}]).startswith(
        'operation 1 has an "at" that is not a position')
    assert store.validate([{"op": "edit", "id": "e1", "at": "there"}]).startswith(
        'operation 1 has an "at" that is not a position')
    assert store.validate([{"op": "edit", "id": "e1", "at": [1, 63]}]) is None
    assert store.validate([{"op": "add", "name": "x", "until": "y", "at": [0, 0]}]) is None
