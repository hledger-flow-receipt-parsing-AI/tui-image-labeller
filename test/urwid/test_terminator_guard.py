"""The questionnaire refuses to finish while a required question is unanswered.

Before: pressing Enter on "Done with this receipt?" exited the loop and
``get_answers`` crashed with ``int('')`` on the unanswered "Select Shop
Address:" (the US-2b.10 demo recording ends in that traceback).
"""

import pytest
import urwid

from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_app.get_answers import get_answers
from tui_labeller.tuis.urwid.question_data_classes import (
    HorizontalMultipleChoiceQuestionData,
    InputValidationQuestionData,
    VerticalMultipleChoiceQuestionData,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp


def _app() -> QuestionnaireApp:
    questions = [
        InputValidationQuestionData(
            question="Shop name:",
            question_id="shop_name",
            input_type=InputType.NAME,
            ans_required=False,
            reconfigurer=False,
            terminator=False,
            ai_suggestions=[],
            history_suggestions=[],
        ),
        VerticalMultipleChoiceQuestionData(
            question="Select Shop Address:",
            question_id="address_selector",
            choices=["manual address"],
            nr_of_ans_per_batch=8,
            ans_required=True,
            reconfigurer=True,
            terminator=False,
            ai_suggestions=[],
        ),
        HorizontalMultipleChoiceQuestionData(
            question="Done with this receipt?",
            question_id="done",
            choices=["yes"],
            ai_suggestions=[],
            ans_required=True,
            reconfigurer=False,
            terminator=True,
        ),
    ]
    app = QuestionnaireApp(
        header="h", questions=questions, labelled_receipts=[]
    )
    app.loop.screen = urwid.raw_display.Screen()
    return app


def test_first_unanswered_required_finds_the_vertical_question() -> None:
    app = _app()
    assert app.first_unanswered_required() == 1
    app.inputs[1].base_widget.set_answer("manual address")
    assert app.first_unanswered_required() is None
    assert app.first_unanswered_required(default=7) == 7


def test_terminator_is_refused_while_required_unanswered() -> None:
    app = _app()
    done = app.inputs[2].base_widget
    done.set_answer("yes")
    app.set_focus(2)
    app._handle_input("terminator")  # must NOT raise ExitMainLoop
    assert app.get_focus() == 1
    assert not done.has_answer(), "the Done answer is cleared so the loop "
    "does not treat the receipt as terminated"
    error_text = app.error_display.base_widget.contents[1][0].text
    assert "Select Shop Address" in error_text


def test_terminator_exits_when_everything_is_answered() -> None:
    app = _app()
    app.inputs[1].base_widget.set_answer("manual address")
    app.inputs[2].base_widget.set_answer("yes")
    with pytest.raises(urwid.ExitMainLoop):
        app._handle_input("terminator")


def test_get_answers_reports_the_unanswered_question() -> None:
    app = _app()
    with pytest.raises(ValueError, match="Select Shop Address"):
        get_answers(inputs=app.inputs)
