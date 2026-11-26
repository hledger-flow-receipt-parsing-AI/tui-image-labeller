"""Tab moves through the parts of the receipt date, also when the AI suggested
a date (it used to take that date over and leave the question from the year
field).

All data here is invented.
"""

import urwid
from hledger_core.AISuggestion import AISuggestion

from tui_labeller.tuis.urwid.date_question.DateTimeQuestion import (
    DateTimeQuestion,
)
from tui_labeller.tuis.urwid.question_data_classes import DateQuestionData

SIZE = (60,)


def _date_question(*, suggestions: list) -> DateTimeQuestion:
    return DateTimeQuestion(
        question_data=DateQuestionData(
            question="Receipt date and time:\n",
            question_id="date",
            date_only=False,
            ai_suggestions=suggestions,
            ans_required=True,
            reconfigurer=False,
            terminator=False,
        ),
        ai_suggestion_box=urwid.AttrMap(urwid.Text(""), "ai_suggestions"),
        pile=urwid.Pile([]),
    )


def _one_suggestion() -> list:
    return [
        AISuggestion(
            question="2024-03-07 11:42", probability=0.8, model_name="ST-x"
        )
    ]


def test_tab_from_the_year_goes_to_the_month_with_one_suggested_date():
    question = _date_question(suggestions=_one_suggestion())
    question.set_edit_pos(0)

    assert question.keypress(SIZE, "tab") is None
    assert question.edit_pos == 5  # yyyy-[m]m-dd hh:mm


def test_tab_walks_every_part_then_leaves_the_question():
    question = _date_question(suggestions=_one_suggestion())
    question.set_edit_pos(0)

    positions = []
    results = []
    for _ in range(5):
        results.append(question.keypress(SIZE, "tab"))
        positions.append(question.edit_pos)

    assert results == [None, None, None, None, "next_question"]
    assert positions[:4] == [5, 8, 11, 14]


def test_tab_keeps_the_typed_date_instead_of_the_suggestion():
    question = _date_question(suggestions=_one_suggestion())
    question.set_answer("2023-12-30 09:05")
    question.set_edit_pos(0)

    question.keypress(SIZE, "tab")

    assert question.get_edit_text() == "2023-12-30 09:05"


def test_alt_a_still_takes_the_suggested_date():
    question = _date_question(suggestions=_one_suggestion())
    question.set_answer("2023-12-30 09:05")

    assert question.keypress(SIZE, "meta a") == "next_question"
    assert question.get_edit_text() == "2024-03-07 11:42"
