"""The category question only accepts categories that exist: the user picks
from the filtered list, and unknown text leads to the new-category screen
instead of silently becoming a category."""

from typing import Any, Dict, Optional

import urwid

from tui_labeller.categories.category_store import CategoryStore
from tui_labeller.tuis.urwid.category_question.CategoryQuestion import (
    NEW_CATEGORY_KEY,
    NO_ROW,
    CategoryQuestion,
)
from tui_labeller.tuis.urwid.question_app.create_widgets import (
    create_question_widget,
)
from tui_labeller.tuis.urwid.receipts.BaseQuestions import BaseQuestions

SIZE = (80,)


def _tree() -> Dict[str, Any]:
    return {
        "groceries": {"ah": {}, "ekoplaza": {}},
        "repairs": {"bike_shed": {}, "car2": {}},
        "restaurant": {},
    }


def _question(*, store: Optional[CategoryStore] = None) -> CategoryQuestion:
    store = store or CategoryStore(hierarchy=_tree())
    data = BaseQuestions(category_store=store).get_category_question()
    pile = urwid.Pile([])
    attr = create_question_widget(
        pile=pile,
        ai_suggestion_box=urwid.AttrMap(urwid.Text(""), ""),
        history_suggestion_box=urwid.AttrMap(urwid.Text(""), ""),
        error_display=urwid.AttrMap(urwid.Pile([urwid.Text("")]), ""),
        question_data=data,
        history_store={},
        descriptor_col_width=20,
    )
    # Header, one earlier question, then the category question in focus.
    pile.contents = [
        (urwid.Text("header"), ("pack", None)),
        (urwid.Edit("first: "), ("pack", None)),
        (attr, ("pack", None)),
    ]
    pile.focus_position = 2
    return attr.base_widget


def _type(question: CategoryQuestion, text: str) -> None:
    for character in text:
        assert question.keypress(SIZE, character) is None


def _attr(question: CategoryQuestion) -> Any:
    return question.owner.attr_map[None]


def test_widget_is_a_category_question_directly_under_its_attr_map() -> None:
    question = _question()
    assert isinstance(question, CategoryQuestion)
    assert question.owner._original_widget is question


def test_starts_open_with_every_category_and_nothing_highlighted() -> None:
    question = _question()
    assert question.dropdown_open
    assert question.matches == question.store.paths()
    assert question.highlighted_row == NO_ROW


def test_enter_on_an_empty_field_picks_nothing() -> None:
    """A stray Enter must not take whichever category comes first."""
    question = _question()
    assert question.keypress(SIZE, "enter") is None
    assert question.edit_text == ""
    assert _attr(question) == "error"
    assert question.dropdown_open


def test_empty_field_can_still_be_browsed_with_down() -> None:
    question = _question()
    assert question.keypress(SIZE, "down") is None
    assert question.highlighted_row == 0
    assert question.keypress(SIZE, "down") is None
    assert question.highlighted_row == 1
    assert question.keypress(SIZE, "enter") == "reconfigurer"
    assert question.edit_text == "groceries"


def test_up_on_an_empty_field_goes_to_the_previous_question() -> None:
    question = _question()
    assert question.keypress(SIZE, "up") == "previous_question"


def test_clearing_the_text_removes_the_highlight() -> None:
    question = _question()
    _type(question, "g")
    assert question.highlighted_row == 1
    question.keypress(SIZE, "backspace")
    assert question.highlighted_row == NO_ROW


def test_typing_filters_and_enter_takes_the_highlighted_match() -> None:
    question = _question()
    _type(question, "groc")
    assert question.matches == [
        "groceries",
        "groceries:ah",
        "groceries:ekoplaza",
    ]
    assert question.highlighted_row == 1

    assert question.keypress(SIZE, "enter") == "reconfigurer"
    assert question.edit_text == "groceries"
    assert question.get_answer() == "groceries"
    assert _attr(question) == "normal"


def test_down_and_up_move_the_highlight_within_the_list() -> None:
    question = _question()
    _type(question, "groc")
    assert question.keypress(SIZE, "down") is None
    assert question.keypress(SIZE, "down") is None
    assert question.highlighted_row == 3
    assert question.keypress(SIZE, "down") is None  # already the last row
    assert question.highlighted_row == 3

    assert question.keypress(SIZE, "enter") == "reconfigurer"
    assert question.edit_text == "groceries:ekoplaza"


def test_up_reaches_the_new_row_and_then_the_previous_question() -> None:
    question = _question()
    _type(question, "groc")
    assert question.keypress(SIZE, "up") is None
    assert question.highlighted_row == 0
    assert question.keypress(SIZE, "enter") == NEW_CATEGORY_KEY
    assert question.edit_text == "groc"

    assert question.keypress(SIZE, "up") == "previous_question"


def test_unknown_text_leaves_only_the_new_row() -> None:
    question = _question()
    _type(question, "grocries")
    assert question.matches == []
    assert question.highlighted_row == 0
    assert question.keypress(SIZE, "enter") == NEW_CATEGORY_KEY
    assert question.edit_text == "grocries"


def test_tab_copies_the_highlighted_category_and_keeps_the_list() -> None:
    question = _question()
    _type(question, "rep")
    assert question.keypress(SIZE, "tab") is None
    assert question.edit_text == "repairs"
    assert question.edit_pos == len("repairs")
    assert question.dropdown_open
    assert question.matches == [
        "repairs",
        "repairs:bike_shed",
        "repairs:car2",
    ]


def test_tab_on_the_new_row_does_nothing() -> None:
    question = _question()
    _type(question, "zzz")
    assert question.keypress(SIZE, "tab") is None
    assert question.edit_text == "zzz"


def test_escape_closes_and_typing_reopens() -> None:
    question = _question()
    _type(question, "gro")
    assert question.keypress(SIZE, "esc") is None
    assert not question.dropdown_open
    _type(question, "c")
    assert question.dropdown_open
    assert question.edit_text == "groc"


def test_closed_list_refuses_unknown_text_and_reopens() -> None:
    question = _question()
    _type(question, "groc")
    question.keypress(SIZE, "esc")

    assert question.keypress(SIZE, "enter") is None
    assert _attr(question) == "error"
    assert question.dropdown_open
    assert question.edit_text == "groc"


def test_closed_list_accepts_an_exact_category_on_enter_and_down() -> None:
    for key in ("enter", "down"):
        question = _question()
        _type(question, "groceries:ah")
        question.keypress(SIZE, "esc")
        assert question.keypress(SIZE, key) == "reconfigurer"
        assert question.edit_text == "groceries:ah"


def test_typing_clears_the_error_colour() -> None:
    question = _question()
    _type(question, "zzz")
    question.keypress(SIZE, "esc")
    question.keypress(SIZE, "enter")
    assert _attr(question) == "error"
    question.keypress(SIZE, "backspace")
    assert _attr(question) == "normal"


def test_underscore_and_digits_can_be_typed() -> None:
    question = _question()
    _type(question, "bike_s")
    assert question.matches == ["repairs:bike_shed"]
    assert question.keypress(SIZE, "enter") == "reconfigurer"
    assert question.edit_text == "repairs:bike_shed"

    other = _question()
    _type(other, "car2")
    assert other.matches == ["repairs:car2"]


def test_wildcard_filters_without_replacing_the_text() -> None:
    question = _question()
    _type(question, "gro*plaza")
    assert question.edit_text == "gro*plaza"
    assert question.matches == ["groceries:ekoplaza"]
    assert question.keypress(SIZE, "enter") == "reconfigurer"
    assert question.edit_text == "groceries:ekoplaza"


def test_upper_case_exact_match_is_stored_lower_case() -> None:
    question = _question()
    _type(question, "Groceries:AH")
    assert question.keypress(SIZE, "enter") == "reconfigurer"
    assert question.edit_text == "groceries:ah"


def test_restored_unknown_category_is_kept_but_not_known() -> None:
    question = _question()
    question.set_answer("groceries:ah:zz")
    assert question.edit_text == "groceries:ah:zz"
    assert question.has_answer()
    assert question.get_answer() == "groceries:ah:zz"
    assert not question.is_known_category()

    question.set_answer("groceries:ah")
    assert question.is_known_category()


def test_empty_field_is_not_a_known_category() -> None:
    question = _question()
    assert not question.is_known_category()
    question.keypress(SIZE, "esc")
    assert question.keypress(SIZE, "enter") is None
    assert _attr(question) == "error"


def test_accept_category_fills_the_field_and_continues() -> None:
    question = _question()
    _type(question, "zzz")
    assert question.accept_category(path="repairs:car2") == "reconfigurer"
    assert question.edit_text == "repairs:car2"
    assert question.question_data.user_edited


def test_list_is_open_again_after_leaving_the_field() -> None:
    question = _question()
    _type(question, "groceries")
    question.keypress(SIZE, "esc")
    assert question.keypress(SIZE, "shift tab") == "previous_question"
    assert question.dropdown_open


def test_a_category_added_to_the_store_shows_up_at_once() -> None:
    store = CategoryStore(hierarchy=_tree())
    question = _question(store=store)
    _type(question, "boat")
    assert question.matches == []
    store.add(path="repairs:boat")
    assert question.accept_category(path="repairs:boat") == "reconfigurer"
    assert question.matches[0] == "repairs:boat"
