"""Skipping a receipt for now: Alt+s or the button at the top right, then a
red "Are you sure?" dialog.  All data here is invented."""

import pytest
import urwid

from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_data_classes import (
    InputValidationQuestionData,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp
from tui_labeller.tuis.urwid.skip_receipt import (
    BUTTON_LABEL,
    SkipConfirmation,
    receipt_skipping,
    skipping_allowed,
)

SIZE = (110, 30)


def _app(*, skipping: bool) -> QuestionnaireApp:
    questions = [
        InputValidationQuestionData(
            question="Shop note:",
            question_id="note",
            input_type=InputType.NAME,
            ans_required=False,
            reconfigurer=False,
            terminator=False,
            ai_suggestions=[],
            history_suggestions=[],
        )
    ]
    if not skipping:
        return QuestionnaireApp(
            header="Answer the receipt questions.",
            questions=questions,
            labelled_receipts=[],
        )
    with receipt_skipping():
        return QuestionnaireApp(
            header="Answer the receipt questions.",
            questions=questions,
            labelled_receipts=[],
        )


def _screen(app: QuestionnaireApp) -> str:
    canvas = app.loop.widget.render(SIZE, focus=True)
    return "\n".join(row.decode("utf-8") for row in canvas.text)


def _dialog_open(app: QuestionnaireApp) -> bool:
    widget = app.loop.widget
    return isinstance(widget, urwid.Overlay) and isinstance(
        widget.top_w, SkipConfirmation
    )


def test_skipping_is_only_offered_inside_the_context() -> None:
    assert not skipping_allowed()
    with receipt_skipping():
        assert skipping_allowed()
    assert not skipping_allowed()


def test_the_button_is_in_the_top_row_while_skipping_is_offered() -> None:
    assert BUTTON_LABEL in _screen(_app(skipping=True)).splitlines()[0]


def test_no_button_and_alt_s_passes_on_without_the_offer() -> None:
    app = _app(skipping=False)

    assert BUTTON_LABEL not in _screen(app)
    assert app._filter_input(["meta s"], []) == ["meta s"]
    assert not _dialog_open(app)


def test_alt_s_asks_are_you_sure() -> None:
    app = _app(skipping=True)

    assert app._filter_input(["meta s"], []) == []

    assert _dialog_open(app)
    assert "Are you sure?" in _screen(app)
    assert not app.skip_requested


@pytest.mark.parametrize("key", ["n", "esc"])
def test_no_goes_back_to_the_questions(key: str) -> None:
    app = _app(skipping=True)
    questions = app.loop.widget
    app._filter_input(["meta s"], [])

    app.loop.widget.keypress(SIZE, key)

    assert app.loop.widget is questions
    assert not app.skip_requested


def test_enter_presses_no_unless_the_user_moved_to_yes() -> None:
    app = _app(skipping=True)
    app._filter_input(["meta s"], [])

    app.loop.widget.keypress(SIZE, "enter")

    assert not _dialog_open(app)
    assert not app.skip_requested


def test_yes_ends_the_questionnaire_with_the_skip() -> None:
    app = _app(skipping=True)
    app._filter_input(["meta s"], [])

    with pytest.raises(urwid.ExitMainLoop):
        app.loop.widget.keypress(SIZE, "y")

    assert app.skip_requested


def test_moving_to_yes_and_enter_skips_too() -> None:
    app = _app(skipping=True)
    app._filter_input(["meta s"], [])

    app.loop.widget.keypress(SIZE, "left")
    with pytest.raises(urwid.ExitMainLoop):
        app.loop.widget.keypress(SIZE, "enter")

    assert app.skip_requested


def test_other_keys_stay_in_the_dialog() -> None:
    app = _app(skipping=True)
    app._filter_input(["meta s"], [])

    app.loop.widget.keypress(SIZE, "x")

    assert _dialog_open(app)
    assert not app.skip_requested


def test_a_second_alt_s_opens_no_second_dialog() -> None:
    app = _app(skipping=True)
    app._filter_input(["meta s"], [])
    first = app.loop.widget

    app._filter_input(["meta s"], [])

    assert app.loop.widget is first


def test_clicking_the_button_asks_are_you_sure() -> None:
    app = _app(skipping=True)
    top_row = _screen(app).splitlines()[0]
    column = top_row.index(BUTTON_LABEL) + 2

    app.loop.widget.mouse_event(SIZE, "mouse press", 1, column, 0, True)

    assert _dialog_open(app)
