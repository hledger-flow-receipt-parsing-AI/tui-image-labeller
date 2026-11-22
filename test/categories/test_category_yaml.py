"""The categories file is rewritten in one canonical style, verified and
atomic: a failed save leaves the original file untouched."""

import os
from pathlib import Path

import pytest
import yaml

from tui_labeller.categories import category_yaml
from tui_labeller.categories.category_yaml import (
    CategorySaveError,
    dump_categories,
    load_categories,
    normalise_hierarchy,
    save_categories,
)


def test_dump_uses_two_space_indent_and_empty_dict_leaves() -> None:
    hierarchy = {"a": {"b": {}, "c": None}, "d": {}}
    assert (
        dump_categories(hierarchy=hierarchy) == "a:\n  b: {}\n  c: {}\nd: {}\n"
    )


def test_dump_of_empty_tree_is_an_empty_mapping() -> None:
    assert dump_categories(hierarchy={}) == "{}\n"
    assert yaml.safe_load(dump_categories(hierarchy={})) == {}


def test_normalise_turns_every_leaf_into_an_empty_dict() -> None:
    assert normalise_hierarchy(hierarchy={"a": None, "b": {"c": None}}) == {
        "a": {},
        "b": {"c": {}},
    }


def test_keys_yaml_would_misread_survive_a_round_trip() -> None:
    hierarchy = {"no": {}, "2024": {"on": {}}, "plain": {}}
    reloaded = yaml.safe_load(dump_categories(hierarchy=hierarchy))
    assert reloaded == hierarchy
    assert all(isinstance(key, str) for key in reloaded)


def test_dump_keeps_key_order() -> None:
    hierarchy = {"z": {}, "a": {"y": {}, "b": {}}}
    reloaded = yaml.safe_load(dump_categories(hierarchy=hierarchy))
    assert list(reloaded) == ["z", "a"]
    assert list(reloaded["a"]) == ["y", "b"]


def test_save_normalises_hand_formatting_without_changing_content(
    tmp_path: Path,
) -> None:
    path = tmp_path / "categories.yaml"
    path.write_text("a :  {}\n\nb:\n    c: {}\n", encoding="utf-8")
    before = load_categories(yaml_path=str(path))

    save_categories(yaml_path=str(path), hierarchy=before)

    assert load_categories(yaml_path=str(path)) == before
    assert path.read_text(encoding="utf-8") == "a: {}\nb:\n  c: {}\n"
    assert os.listdir(tmp_path) == ["categories.yaml"]


def test_failed_replace_leaves_the_original_untouched(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    path = tmp_path / "categories.yaml"
    original = "a :  {}\n"
    path.write_text(original, encoding="utf-8")

    def refuse(*_args: object, **_kwargs: object) -> None:
        raise OSError("disk full")

    monkeypatch.setattr(category_yaml.os, "replace", refuse)
    with pytest.raises(CategorySaveError):
        save_categories(yaml_path=str(path), hierarchy={"a": {}, "b": {}})

    assert path.read_text(encoding="utf-8") == original
    assert os.listdir(tmp_path) == ["categories.yaml"]


def test_save_follows_a_symlink_instead_of_replacing_it(
    tmp_path: Path,
) -> None:
    real = tmp_path / "real.yaml"
    real.write_text("a: {}\n", encoding="utf-8")
    link = tmp_path / "categories.yaml"
    link.symlink_to(real)

    save_categories(yaml_path=str(link), hierarchy={"a": {}, "b": {}})

    assert link.is_symlink()
    assert real.read_text(encoding="utf-8") == "a: {}\nb: {}\n"


def test_load_rejects_a_file_that_is_not_a_mapping(tmp_path: Path) -> None:
    path = tmp_path / "categories.yaml"
    path.write_text("- a\n- b\n", encoding="utf-8")
    with pytest.raises(CategorySaveError):
        load_categories(yaml_path=str(path))
