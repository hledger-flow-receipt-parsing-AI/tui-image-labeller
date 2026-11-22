"""The category question accepts every character category names contain and
carries the category store when one is available."""

import pytest
import urwid

from tui_labeller.categories.category_store import CategoryStore
from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.input_validation.InputValidationQuestion import (
    InputValidationQuestion,
)
from tui_labeller.tuis.urwid.question_data_classes import (
    CategoryQuestionData,
    InputValidationQuestionData,
)
from tui_labeller.tuis.urwid.receipts.BaseQuestions import BaseQuestions

SIZE = (80,)
CAPTION = "\nBookkeeping expense category:"


def _plain_category_widget() -> InputValidationQuestion:
    data = InputValidationQuestionData(
        question=CAPTION,
        question_id="category",
        input_type=InputType.CATEGORY,
        ans_required=True,
        reconfigurer=True,
        terminator=False,
        ai_suggestions=[],
        history_suggestions=[],
    )
    widget = InputValidationQuestion(
        question_data=data,
        history_store={},
        ai_suggestion_box=urwid.AttrMap(urwid.Text(""), ""),
        history_suggestion_box=urwid.AttrMap(urwid.Text(""), ""),
        pile=urwid.Pile([]),
    )
    widget.owner = urwid.AttrMap(widget, "normal")
    return widget


@pytest.mark.parametrize("value", ["bicycle_parts", "a1:b_2", "groceries"])
def test_category_type_accepts_underscore_and_digits(value: str) -> None:
    widget = _plain_category_widget()
    widget.set_answer(value)
    assert widget.get_answer() == value

    typed = _plain_category_widget()
    for character in value:
        typed.keypress(SIZE, character)
    assert typed.edit_text == value


@pytest.mark.parametrize("character", ["-", " ", "/", "."])
def test_category_type_rejects_other_characters(character: str) -> None:
    widget = _plain_category_widget()
    widget.keypress(SIZE, "a")
    widget.keypress(SIZE, character)
    assert widget.edit_text == "a"
    with pytest.raises(ValueError):
        widget.set_answer(f"a{character}b")


def test_without_a_store_the_question_stays_free_text() -> None:
    question = BaseQuestions().get_category_question()
    assert not isinstance(question, CategoryQuestionData)
    assert question.question_id == "category"
    assert question.question == CAPTION
    assert question.input_type == InputType.CATEGORY


def test_with_a_store_the_question_carries_it() -> None:
    store = CategoryStore(hierarchy={"groceries": {"ekoplaza": {}}})
    base = BaseQuestions(category_store=store)
    question = base.get_category_question()
    assert isinstance(question, CategoryQuestionData)
    assert question.category_store is store
    assert question.question_id == "category"
    assert question.question == CAPTION
    assert question.input_type == InputType.CATEGORY
    assert question.ans_required and question.reconfigurer
    assert [q.question_id for q in base.base_questions] == [
        "date",
        "is_withdrawal",
        "category",
    ]
