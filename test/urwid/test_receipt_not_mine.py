"""Option 6 of the matching menu, "This receipt is not mine": after an explicit
yes the questionnaire is abandoned and the answers typed so far go with the
receipt; a no returns to the menu."""

# The application enters through hledger_preprocessor, which resolves a
# circular import between the packages.
import hledger_preprocessor  # noqa: F401  isort: skip

from datetime import datetime
from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
import urwid
from hledger_receipt_processing.matching import ask_user_action
from hledger_receipt_processing.matching.ask_user_action import (
    ReceiptMatchingAction,
)
from hledger_receipt_processing.receipts_to_objects import receipt_not_mine

from tui_labeller.tuis.urwid import ask_urwid_receipt
from tui_labeller.tuis.urwid.ask_urwid_receipt import (
    _ReceiptAbandoned,
    _run_matching_cli_loop,
)
from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_app.get_answers import (
    get_answers_so_far,
)
from tui_labeller.tuis.urwid.question_app.reconfiguration.reconfiguration import (  # noqa: E501
    make_match_choice_question,
)
from tui_labeller.tuis.urwid.question_data_classes import (
    DateQuestionData,
    HorizontalMultipleChoiceQuestionData,
    InputValidationQuestionData,
    VerticalMultipleChoiceQuestionData,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp

IMAGES = ["/finance/receipt_images_input/photo_a.jpg"]


# ----------------------------------------------------------- answers so far


def _text_question(*, question_id: str) -> InputValidationQuestionData:
    return InputValidationQuestionData(
        question=f"{question_id}:",
        question_id=question_id,
        input_type=InputType.NAME,
        ans_required=False,
        reconfigurer=False,
        terminator=False,
        ai_suggestions=[],
        history_suggestions=[],
    )


def _app() -> QuestionnaireApp:
    questions = [
        DateQuestionData(
            question="Receipt date and time:\n",
            question_id="date",
            date_only=False,
            ai_suggestions=[],
            ans_required=True,
            reconfigurer=False,
            terminator=False,
        ),
        _text_question(question_id="shop_name"),
        _text_question(question_id="shop_city"),
        VerticalMultipleChoiceQuestionData(
            question="Currency:",
            question_id="currency",
            choices=["EUR", "GBP"],
            nr_of_ans_per_batch=8,
            ans_required=True,
            reconfigurer=False,
            terminator=False,
            ai_suggestions=[],
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
        make_match_choice_question(),
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


def _widget(app: QuestionnaireApp, question_id: str) -> Any:
    return next(
        entry.base_widget
        for entry in app.inputs
        if entry.base_widget.question_data.question_id == question_id
    )


def test_answers_so_far_are_keyed_by_question_id() -> None:
    app = _app()
    _widget(app, "date").set_answer(datetime(2025, 1, 15, 10, 30))
    _widget(app, "shop_name").set_answer("Ekoplaza")
    _widget(app, "currency").set_answer("GBP")

    answers = get_answers_so_far(inputs=app.inputs)

    assert answers == {
        "date": "2025-01-15 10:30:00",
        "shop_name": "Ekoplaza",
        "currency": "GBP",
    }
    assert all(isinstance(value, str) for value in answers.values())


def test_unanswered_flow_and_finishing_questions_are_left_out() -> None:
    app = _app()
    _widget(app, "shop_name").set_answer("Ekoplaza")
    # How the menu was reached and the "done" button are not label data.
    _widget(app, "match_choice").set_answer("Enter matching CLI")
    _widget(app, "done").set_answer("yes")

    answers = get_answers_so_far(inputs=app.inputs)

    assert "shop_city" not in answers  # never answered
    assert "address_selector" not in answers  # required but unanswered
    assert "match_choice" not in answers
    assert "done" not in answers
    assert answers["shop_name"] == "Ekoplaza"


# ----------------------------------------------------------------- the menu


def _dataset() -> SimpleNamespace:
    return SimpleNamespace(
        account="account",
        search_receipt_account_transaction="transaction",
        receipt="receipt",
        config="config",
    )


def _script_menu(
    monkeypatch: pytest.MonkeyPatch,
    *,
    actions: List[ReceiptMatchingAction],
    confirmations: List[bool],
) -> Dict[str, List[Any]]:
    """Replace the menu and the confirmation prompt by scripted answers."""
    seen: Dict[str, List[Any]] = {"menu": [], "confirm": []}
    pending_actions = list(actions)
    pending_confirmations = list(confirmations)

    def fake_menu(**kwargs: Any) -> ReceiptMatchingAction:
        seen["menu"].append(kwargs)
        return pending_actions.pop(0)

    def fake_confirm(**kwargs: Any) -> bool:
        seen["confirm"].append(kwargs)
        return pending_confirmations.pop(0)

    monkeypatch.setattr(ask_user_action, "get_receipt_action", fake_menu)
    monkeypatch.setattr(
        receipt_not_mine, "confirm_receipt_not_mine", fake_confirm
    )
    return seen


def test_confirmed_not_mine_abandons_the_receipt(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _script_menu(
        monkeypatch,
        actions=[ReceiptMatchingAction.NOT_MINE],
        confirmations=[True],
    )
    with pytest.raises(_ReceiptAbandoned):
        _run_matching_cli_loop(_dataset(), raw_receipt_img_filepaths=IMAGES)

    assert seen["menu"][0]["allow_not_mine"] is True
    assert seen["confirm"] == [
        {"config": "config", "raw_receipt_img_filepaths": IMAGES}
    ]


def test_declined_not_mine_returns_to_the_menu(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture
) -> None:
    seen = _script_menu(
        monkeypatch,
        actions=[
            ReceiptMatchingAction.NOT_MINE,
            ReceiptMatchingAction.CHECK_RECEIPT,
        ],
        confirmations=[False],
    )
    result = _run_matching_cli_loop(
        _dataset(), raw_receipt_img_filepaths=IMAGES
    )
    assert result is None  # CHECK_RECEIPT: back to the questionnaire
    assert len(seen["menu"]) == 2
    assert "Nothing was moved" in capsys.readouterr().out


def test_option_is_not_offered_without_the_receipt_images(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen = _script_menu(
        monkeypatch,
        actions=[ReceiptMatchingAction.CHECK_RECEIPT],
        confirmations=[],
    )
    assert _run_matching_cli_loop(_dataset()) is None
    assert "allow_not_mine" not in seen["menu"][0]


def test_option_is_not_offered_with_an_older_receipt_processing(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Without the receipt_not_mine module the menu stays as it was."""
    seen = _script_menu(
        monkeypatch,
        actions=[ReceiptMatchingAction.CHECK_RECEIPT],
        confirmations=[],
    )
    monkeypatch.setattr(ask_urwid_receipt, "_not_mine_support", lambda: None)
    assert (
        _run_matching_cli_loop(_dataset(), raw_receipt_img_filepaths=IMAGES)
        is None
    )
    assert "allow_not_mine" not in seen["menu"][0]
