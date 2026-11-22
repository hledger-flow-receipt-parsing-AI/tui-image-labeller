"""CategoryStore: the category tree behind the dropdown and the new-category
screen.  Matching finds a category from any remembered fragment; additions
are previewed, checked for look-alikes and saved to the categories file."""

from pathlib import Path
from typing import Any, Dict

import pytest
import yaml

from tui_labeller.categories import category_store
from tui_labeller.categories.category_store import CategoryStore
from tui_labeller.categories.category_yaml import CategorySaveError


def _tree() -> Dict[str, Any]:
    return {
        "groceries": {"ah": {}, "ekoplaza": {}},
        "repairs": {
            "bike": {},
            "car": {},
            "house": {"kitchen": {"plumbing": {}}},
        },
        "restaurant": {},
        "transportation": {"benzine": {}},
    }


def _store() -> CategoryStore:
    return CategoryStore(hierarchy=_tree())


def test_paths_lists_every_node_including_parents() -> None:
    assert _store().paths() == [
        "groceries",
        "groceries:ah",
        "groceries:ekoplaza",
        "repairs",
        "repairs:bike",
        "repairs:car",
        "repairs:house",
        "repairs:house:kitchen",
        "repairs:house:kitchen:plumbing",
        "restaurant",
        "transportation",
        "transportation:benzine",
    ]


def test_exists_is_case_insensitive_and_false_for_empty() -> None:
    store = _store()
    assert store.exists(path="groceries:ah")
    assert store.exists(path=" Groceries:AH ")
    assert store.exists(path="repairs")
    assert not store.exists(path="")
    assert not store.exists(path="groceries:lidl")
    assert not store.exists(path="groceries:")


def test_children_are_alphabetical_and_empty_path_is_the_root() -> None:
    store = _store()
    assert store.children(path="") == [
        "groceries",
        "repairs",
        "restaurant",
        "transportation",
    ]
    assert store.children(path="repairs") == ["bike", "car", "house"]
    assert store.children(path="restaurant") == []
    assert store.children(path="nope") == []


def test_tree_with_none_leaves_is_read_like_empty_dicts() -> None:
    store = CategoryStore(hierarchy={"a": {"b": None}, "c": None})
    assert store.paths() == ["a", "a:b", "c"]
    assert store.exists(path="a:b")
    assert store.children(path="a:b") == []


def test_empty_text_matches_everything() -> None:
    store = _store()
    assert store.matches(text="") == store.paths()
    assert store.matches(text="  ") == store.paths()
    assert store.matches(text="*") == store.paths()


def test_matches_rank_exact_then_prefix_then_segment_then_contains() -> None:
    store = CategoryStore(
        hierarchy={
            "car": {},
            "carwash": {},
            "repairs": {"car": {}, "oscar": {}},
            "scarf": {},
        }
    )
    assert store.matches(text="car") == [
        "car",  # exact
        "carwash",  # path starts with the text
        "repairs:car",  # a segment starts with the text
        "repairs:oscar",  # contains
        "scarf",
    ]


def test_a_fragment_finds_a_deep_category() -> None:
    assert _store().matches(text="plumb") == ["repairs:house:kitchen:plumbing"]


def test_matching_ignores_case_and_handles_a_colon_in_the_text() -> None:
    store = _store()
    assert store.matches(text="GROC") == [
        "groceries",
        "groceries:ah",
        "groceries:ekoplaza",
    ]
    assert store.matches(text="house:kit") == [
        "repairs:house:kitchen",
        "repairs:house:kitchen:plumbing",
    ]


def test_wildcard_chunks_must_occur_in_order() -> None:
    store = _store()
    assert store.matches(text="gro*plaza") == ["groceries:ekoplaza"]
    assert store.matches(text="plaza*gro") == []
    assert store.matches(text="rep*kit*") == [
        "repairs:house:kitchen",
        "repairs:house:kitchen:plumbing",
    ]


def test_no_match_is_an_empty_list() -> None:
    assert _store().matches(text="grocries") == []


def test_deepest_existing_ancestor() -> None:
    store = _store()
    assert store.deepest_existing_ancestor(path="repairs:garden:shed") == (
        "repairs",
        "garden:shed",
    )
    assert store.deepest_existing_ancestor(path="x:y") == ("", "x:y")
    assert store.deepest_existing_ancestor(path="repairs:bike") == (
        "repairs:bike",
        "",
    )
    assert store.deepest_existing_ancestor(path="") == ("", "")
    assert store.deepest_existing_ancestor(path=":Repairs::Garden:") == (
        "repairs",
        "garden",
    )


def test_plan_lists_every_node_that_would_be_created() -> None:
    plan = _store().plan_addition(parent="repairs", text="garden:shed")
    assert plan.error is None
    assert plan.full_path == "repairs:garden:shed"
    assert plan.created == ("repairs:garden", "repairs:garden:shed")
    assert not plan.already_exists


def test_plan_under_the_root_and_through_existing_nodes() -> None:
    store = _store()
    assert store.plan_addition(parent="", text="Travel").created == ("travel",)
    plan = store.plan_addition(parent="", text="repairs:house:roof")
    assert plan.created == ("repairs:house:roof",)


@pytest.mark.parametrize(
    "parent, text",
    [
        ("repairs", ""),
        ("repairs", "   "),
        ("repairs", "a::b"),
        ("repairs", ":a"),
        ("repairs", "a:"),
        ("repairs", "a-b"),
        ("repairs", "a b"),
        ("nope", "a"),
    ],
)
def test_plan_reports_an_error(parent: str, text: str) -> None:
    plan = _store().plan_addition(parent=parent, text=text)
    assert plan.error
    assert plan.created == ()
    assert not plan.already_exists


def test_plan_for_an_existing_path() -> None:
    plan = _store().plan_addition(parent="repairs", text="bike")
    assert plan.error is None
    assert plan.already_exists
    assert plan.created == ()
    assert plan.full_path == "repairs:bike"


def test_look_alike_by_spelling_and_by_prefix() -> None:
    store = _store()
    assert store.plan_addition(parent="", text="grocries").look_alikes == (
        "groceries",
    )
    assert store.plan_addition(parent="", text="transport").look_alikes == (
        "transportation",
    )
    assert store.plan_addition(
        parent="repairs", text="bikes:chain"
    ).look_alikes == ("repairs:bike",)


def test_distinct_names_are_not_look_alikes() -> None:
    store = _store()
    assert store.plan_addition(parent="repairs", text="boat").look_alikes == ()
    assert store.plan_addition(parent="", text="travel").look_alikes == ()


def test_same_name_elsewhere_is_reported() -> None:
    store = _store()
    plan = store.plan_addition(parent="restaurant", text="ah")
    assert plan.same_name_elsewhere == ("groceries:ah",)
    assert plan.look_alikes == ()
    assert (
        store.plan_addition(parent="groceries", text="lidl").same_name_elsewhere
        == ()
    )


def test_add_in_memory_mutates_the_given_tree() -> None:
    tree = _tree()
    store = CategoryStore(hierarchy=tree)

    created = store.add(path="repairs:garden:shed")

    assert created == ["repairs:garden", "repairs:garden:shed"]
    assert tree["repairs"]["garden"] == {"shed": {}}
    assert store.exists(path="repairs:garden:shed")
    assert store.add(path="repairs:garden:shed") == []


def test_add_rejects_an_invalid_path() -> None:
    with pytest.raises(ValueError):
        _store().add(path="repairs::x")


def test_add_writes_the_file_and_updates_the_shared_tree(
    tmp_path: Path,
) -> None:
    path = tmp_path / "categories.yaml"
    path.write_text(yaml.safe_dump(_tree()), encoding="utf-8")
    tree = _tree()
    store = CategoryStore(hierarchy=tree, yaml_path=str(path))

    store.add(path="repairs:house:kitchen:tap")

    on_disk = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert on_disk["repairs"]["house"]["kitchen"] == {
        "plumbing": {},
        "tap": {},
    }
    assert tree["repairs"]["house"]["kitchen"] == {"plumbing": {}, "tap": {}}


def test_add_keeps_an_edit_made_in_an_editor_meanwhile(
    tmp_path: Path,
) -> None:
    path = tmp_path / "categories.yaml"
    path.write_text(yaml.safe_dump(_tree()), encoding="utf-8")
    tree = _tree()
    store = CategoryStore(hierarchy=tree, yaml_path=str(path))

    edited = _tree()
    edited["hobby"] = {"music": {}}
    path.write_text(yaml.safe_dump(edited), encoding="utf-8")

    store.add(path="repairs:boat")

    on_disk = yaml.safe_load(path.read_text(encoding="utf-8"))
    assert on_disk["hobby"] == {"music": {}}
    assert on_disk["repairs"]["boat"] == {}
    assert store.exists(path="hobby:music")
    assert tree["hobby"] == {"music": {}}


def test_failed_save_changes_neither_file_nor_tree(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "categories.yaml"
    original = yaml.safe_dump(_tree())
    path.write_text(original, encoding="utf-8")
    tree = _tree()
    store = CategoryStore(hierarchy=tree, yaml_path=str(path))

    def refuse(**_kwargs: object) -> None:
        raise CategorySaveError("disk full")

    monkeypatch.setattr(category_store, "save_categories", refuse)
    with pytest.raises(CategorySaveError):
        store.add(path="repairs:boat")

    assert path.read_text(encoding="utf-8") == original
    assert tree == _tree()
    assert not store.exists(path="repairs:boat")
