"""The new-category screen: browse the whole tree to see what exists, then
add a category deliberately, with a warning when it looks like a duplicate."""

from typing import Any, Dict, List, Optional, Tuple

import pytest

from tui_labeller.categories.category_store import CategoryStore
from tui_labeller.categories.category_yaml import CategorySaveError
from tui_labeller.tuis.urwid.category_question.CategoryTreeScreen import (
    CategoryTreeScreen,
    visible_tree_rows,
)

SIZE = (80, 24)


def _tree() -> Dict[str, Any]:
    return {
        "groceries": {"ah": {}, "ekoplaza": {}},
        "repairs": {"car": {}, "bike": {}},
        "restaurant": {},
    }


def _screen(
    *, typed_text: str = "", store: Optional[CategoryStore] = None
) -> Tuple[CategoryTreeScreen, CategoryStore, List[str], List[bool]]:
    store = store or CategoryStore(hierarchy=_tree())
    used: List[str] = []
    cancelled: List[bool] = []
    screen = CategoryTreeScreen(
        store=store,
        typed_text=typed_text,
        on_use=used.append,
        on_cancel=lambda: cancelled.append(True),
    )
    return screen, store, used, cancelled


def _press(screen: CategoryTreeScreen, *keys: str) -> None:
    for key in keys:
        # Every key is consumed: an unhandled key would reach the
        # questionnaire behind the screen ("q" quits it).
        assert screen.keypress(SIZE, key) is None


def _text(screen: CategoryTreeScreen) -> str:
    canvas = screen.render(SIZE, focus=True)
    return "\n".join(row.decode("utf-8").rstrip() for row in canvas.text)


# ------------------------------------------------------------------- rows


def test_collapsed_tree_shows_the_root_and_top_level_only() -> None:
    rows = visible_tree_rows(
        store=CategoryStore(hierarchy=_tree()), expanded=set()
    )
    assert [(row.path, row.depth) for row in rows] == [
        ("", 0),
        ("groceries", 1),
        ("repairs", 1),
        ("restaurant", 1),
    ]
    assert [row.has_children for row in rows] == [True, True, True, False]
    assert [row.expanded for row in rows] == [True, False, False, False]


def test_expanded_branch_shows_its_children_alphabetically() -> None:
    rows = visible_tree_rows(
        store=CategoryStore(hierarchy=_tree()), expanded={"repairs"}
    )
    assert [(row.path, row.depth) for row in rows] == [
        ("", 0),
        ("groceries", 1),
        ("repairs", 1),
        ("repairs:bike", 2),
        ("repairs:car", 2),
        ("restaurant", 1),
    ]


# ------------------------------------------------------------------ start


def test_empty_text_starts_browsing_on_the_root() -> None:
    screen, _, _, _ = _screen()
    assert screen.cursor_path == ""
    assert not screen.adding
    assert screen.expanded == set()


def test_existing_category_starts_browsing_on_it_expanded() -> None:
    screen, _, _, _ = _screen(typed_text="repairs")
    assert screen.cursor_path == "repairs"
    assert not screen.adding
    assert "repairs" in screen.expanded

    deep, _, _, _ = _screen(typed_text="groceries:ah")
    assert deep.cursor_path == "groceries:ah"
    assert "groceries" in deep.expanded


def test_unknown_tail_starts_adding_under_the_existing_part() -> None:
    screen, _, _, _ = _screen(typed_text="repairs:house:kitchen")
    assert screen.cursor_path == "repairs"
    assert screen.adding
    assert screen.input.edit_text == "house:kitchen"
    assert "repairs" in screen.expanded


def test_wildcard_and_case_are_cleaned_from_the_prefill() -> None:
    screen, _, _, _ = _screen(typed_text="Gro*C")
    assert screen.cursor_path == ""
    assert screen.adding
    assert screen.input.edit_text == "groc"


# --------------------------------------------------------------- browsing


def test_up_down_home_end_move_the_cursor() -> None:
    screen, _, _, _ = _screen()
    _press(screen, "down")
    assert screen.cursor_path == "groceries"
    _press(screen, "down", "down")
    assert screen.cursor_path == "restaurant"
    _press(screen, "down")
    assert screen.cursor_path == "restaurant"
    _press(screen, "up")
    assert screen.cursor_path == "repairs"
    _press(screen, "home")
    assert screen.cursor_path == ""
    _press(screen, "up")
    assert screen.cursor_path == ""
    _press(screen, "end")
    assert screen.cursor_path == "restaurant"
    _press(screen, "page up")
    assert screen.cursor_path == ""
    _press(screen, "page down")
    assert screen.cursor_path == "restaurant"


def test_right_opens_then_enters_and_left_closes_then_leaves() -> None:
    screen, _, _, _ = _screen()
    _press(screen, "down", "down")
    assert screen.cursor_path == "repairs"

    _press(screen, "right")
    assert "repairs" in screen.expanded
    assert screen.cursor_path == "repairs"
    _press(screen, "right")
    assert screen.cursor_path == "repairs:bike"
    _press(screen, "right")  # a leaf: nothing to open
    assert screen.cursor_path == "repairs:bike"

    _press(screen, "left")
    assert screen.cursor_path == "repairs"
    assert "repairs" in screen.expanded
    _press(screen, "left")
    assert "repairs" not in screen.expanded
    assert screen.cursor_path == "repairs"
    _press(screen, "left")
    assert screen.cursor_path == ""
    _press(screen, "left")
    assert screen.cursor_path == ""


def test_enter_uses_the_highlighted_category() -> None:
    screen, _, used, cancelled = _screen()
    _press(screen, "enter")  # the root row is not a category
    assert used == []
    _press(screen, "down", "enter")
    assert used == ["groceries"]
    assert cancelled == []


def test_escape_cancels() -> None:
    screen, _, used, cancelled = _screen()
    _press(screen, "esc")
    assert cancelled == [True]
    assert used == []


def test_other_keys_are_swallowed_while_browsing() -> None:
    screen, _, used, cancelled = _screen()
    _press(screen, "q", "tab", "x", "f5")
    assert used == [] and cancelled == []
    assert not screen.adding


def test_n_starts_adding_under_the_cursor_and_shows_its_children() -> None:
    screen, _, _, _ = _screen()
    _press(screen, "down", "down", "n")
    assert screen.adding
    assert screen.cursor_path == "repairs"
    assert "repairs" in screen.expanded
    assert screen.input.edit_text == ""


# ----------------------------------------------------------------- adding


def test_typing_builds_a_lower_case_name_and_ignores_other_keys() -> None:
    screen, _, _, _ = _screen()
    _press(screen, "n", *"Tra-vel 2_x:Y", "backspace")
    assert screen.input.edit_text == "travel2_x:"


def test_enter_creates_the_category_and_reports_it() -> None:
    screen, store, used, _ = _screen()
    _press(screen, "down", "down", "n", *"house:kitchen", "enter")
    assert store.exists(path="repairs:house:kitchen")
    assert used == ["repairs:house:kitchen"]


def test_top_level_category_is_added_from_the_root_row() -> None:
    screen, store, used, _ = _screen()
    _press(screen, "n", *"travel", "enter")
    assert store.exists(path="travel")
    assert used == ["travel"]


def test_existing_name_is_used_without_adding() -> None:
    screen, store, used, _ = _screen()
    before = store.paths()
    _press(screen, "down", "down", "n", *"bike", "enter")
    assert used == ["repairs:bike"]
    assert store.paths() == before


def test_look_alike_needs_a_second_enter() -> None:
    screen, store, used, _ = _screen()
    _press(screen, "n", *"grocries", "enter")
    assert screen.confirm_pending
    assert used == []
    assert not store.exists(path="grocries")
    assert "groceries" in _text(screen)

    _press(screen, "enter")
    assert used == ["grocries"]
    assert store.exists(path="grocries")


def test_editing_resets_the_look_alike_confirmation() -> None:
    screen, store, used, _ = _screen()
    _press(screen, "n", *"grocries", "enter")
    assert screen.confirm_pending
    _press(screen, "backspace")
    assert not screen.confirm_pending
    _press(screen, "s", "enter")
    assert used == []  # asks again for the edited name
    assert screen.confirm_pending


def test_enter_does_nothing_while_the_name_is_invalid() -> None:
    screen, store, used, _ = _screen()
    before = store.paths()
    _press(screen, "n", "enter")
    _press(screen, *"a::b", "enter")
    assert used == []
    assert store.paths() == before
    assert screen.adding


def test_escape_while_adding_returns_to_browsing() -> None:
    screen, _, used, cancelled = _screen()
    _press(screen, "down", "n", *"abc", "esc")
    assert not screen.adding
    assert screen.input.edit_text == ""
    assert cancelled == [] and used == []
    assert screen.cursor_path == "groceries"
    _press(screen, "esc")
    assert cancelled == [True]


def test_failed_save_is_shown_and_the_screen_stays(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    screen, store, used, _ = _screen()

    def refuse(*, path: str) -> List[str]:
        raise CategorySaveError("disk full")

    monkeypatch.setattr(store, "add", refuse)
    _press(screen, "n", *"travel", "enter")
    assert used == []
    assert "disk full" in screen.status
    assert screen.adding
    assert "disk full" in _text(screen)

    _press(screen, "x")
    assert screen.status == ""


# ----------------------------------------------------------------- render


def test_browsing_screen_shows_tree_cursor_and_legend() -> None:
    screen, _, _, _ = _screen(typed_text="repairs")
    text = _text(screen)
    assert "New category" in text
    assert "groceries" in text and "restaurant" in text
    assert "> - repairs" in text
    assert "bike" in text and "car" in text
    assert "n new child" in text and "Esc back" in text


def test_adding_screen_shows_the_preview() -> None:
    screen, _, _, _ = _screen(typed_text="repairs:house:kitchen")
    text = _text(screen)
    assert "Add under repairs: house:kitchen" in text
    assert "creates" in text
    assert "repairs:house" in text
    assert "repairs:house:kitchen" in text
    assert "Enter create" in text


def test_same_name_elsewhere_is_mentioned() -> None:
    screen, _, _, _ = _screen(typed_text="restaurant:ah")
    assert "groceries:ah" in _text(screen)


def test_cursor_row_stays_visible_in_a_long_tree() -> None:
    tree = {f"category{number:03d}": {} for number in range(100)}
    screen, _, _, _ = _screen(store=CategoryStore(hierarchy=tree))
    _press(screen, "end")
    assert screen.cursor_path == "category099"
    # Marker, then two columns where a branch shows its +/- icon.
    assert ">   category099" in _text(screen)


def test_mouse_clicks_change_nothing() -> None:
    screen, _, used, cancelled = _screen(typed_text="repairs")
    before = _text(screen)
    assert screen.mouse_event(SIZE, "mouse press", 1, 5, 20, True) is True
    assert _text(screen) == before
    assert used == [] and cancelled == []
    assert not screen.adding


def test_screen_always_takes_keys() -> None:
    screen, _, _, _ = _screen(store=CategoryStore(hierarchy={}))
    assert screen.selectable()
    _press(screen, "down", "right", "left", "enter")
    assert screen.cursor_path == ""
