"""Keeping suggestions current while one receipt is labelled.

A confirmed answer goes to the suggestion engine, the remaining
questions get re-ranked suggestions (cross-inference), and every field
event is reported for the timing log.  All data here is invented.
"""

from typing import Any, Dict, List

import urwid
from hledger_core.AISuggestion import AISuggestion
from hledger_core.TransactionObjects.Address import Address
from hledger_core.TransactionObjects.ShopId import ShopId

from tui_labeller.tuis.urwid.ai_session import AiSession
from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_data_classes import (
    HorizontalMultipleChoiceQuestionData,
    InputValidationQuestionData,
    VerticalMultipleChoiceQuestionData,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp
from tui_labeller.tuis.urwid.receipts.AccountQuestions import AccountQuestions

BAKERY = "Bakker Bart: Dorpsstraat, Voorbeeldstad"
HARDWARE = "IJzerwaren Jansen: IJzerweg, Voorbeeldstad"


def _ai(text: str, probability: float = 0.9) -> AISuggestion:
    return AISuggestion(
        question=text, probability=probability, model_name="ST-x"
    )


class FakeSuggester:
    """Stands in for hledger_ai.labeller.LabellerSuggester."""

    def __init__(self) -> None:
        self.asked: List[Dict[str, Any]] = []
        self.events: List[tuple] = []

    def suggest(
        self, *, answers: Dict[str, Any]
    ) -> Dict[str, List[AISuggestion]]:
        self.asked.append(dict(answers))
        suggestions = {
            "amount": [_ai("11.54")],
            "change": [_ai("0.00")],
            "address_selector": [_ai(BAKERY, 0.7), _ai(HARDWARE, 0.3)],
        }
        if answers.get("category") == "tools":
            suggestions["address_selector"] = [
                _ai(HARDWARE, 0.8),
                _ai(BAKERY, 0.2),
            ]
        return {k: v for k, v in suggestions.items() if k not in answers}

    def answered(self, *, question_id: str, answer: Any) -> None:
        self.events.append(("answered", question_id))

    def reached(self, *, question_id: str) -> None:
        self.events.append(("reached", question_id))

    def finish(self, *, answers: Dict[str, Any]) -> int:
        self.finished = dict(answers)
        return 0


def _shop(text: str) -> ShopId:
    name, street = text.split(": ")[0], text.split(": ")[1].split(", ")[0]
    return ShopId(
        name=name, address=Address(street=street, city="Voorbeeldstad")
    )


def _app() -> QuestionnaireApp:
    questions = [
        InputValidationQuestionData(
            question="Category:",
            question_id="category",
            input_type=InputType.CATEGORY,
            ans_required=True,
            reconfigurer=False,
            terminator=False,
            ai_suggestions=[],
            history_suggestions=[],
        ),
        InputValidationQuestionData(
            question="Amount paid from account:",
            question_id="amount",
            input_type=InputType.FLOAT,
            ans_required=True,
            reconfigurer=False,
            terminator=False,
            ai_suggestions=[],
            history_suggestions=[],
        ),
        VerticalMultipleChoiceQuestionData(
            question="Select Shop Address:",
            question_id="address_selector",
            choices=["manual address", BAKERY, HARDWARE],
            nr_of_ans_per_batch=12,
            ans_required=True,
            reconfigurer=True,
            terminator=False,
            ai_suggestions=[],
            extra_data={
                "shop_ids": [
                    ShopId(name="manual address", address=Address()),
                    _shop(BAKERY),
                    _shop(HARDWARE),
                ],
                "scrollable": True,
            },
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
    app.pile.focus_position = app.nr_of_headers
    return app


def _widget(app: QuestionnaireApp, question_id: str):
    for input_widget in app.inputs:
        widget = input_widget.base_widget
        if widget.question_data.question_id == question_id:
            return widget
    raise KeyError(question_id)


def _box(app: QuestionnaireApp) -> str:
    return app.ai_suggestion_box.base_widget.text


def test_attaching_gives_every_open_question_its_first_suggestions() -> None:
    app, suggester = _app(), FakeSuggester()

    AiSession(suggester=suggester).attach(tui=app)

    assert suggester.asked == [{}]
    assert [s.question for s in _widget(app, "amount").ai_suggestions] == [
        "11.54"
    ]
    assert _widget(app, "address_selector").question_data.choices == [
        "manual address",
        BAKERY,
        HARDWARE,
    ]


def test_confirming_a_field_reranks_the_fields_after_it() -> None:
    app, suggester = _app(), FakeSuggester()
    AiSession(suggester=suggester).attach(tui=app)

    _widget(app, "category").set_edit_text("tools")
    app._handle_input("next_question")  # leave the category question

    assert suggester.asked[-1] == {"category": "tools"}
    assert _widget(app, "address_selector").question_data.choices == [
        "manual address",
        HARDWARE,
        BAKERY,
    ]
    shops = _widget(app, "address_selector").question_data.extra_data[
        "shop_ids"
    ]
    assert [s.name for s in shops] == [
        "manual address",
        "IJzerwaren Jansen",
        "Bakker Bart",
    ]


def test_a_value_the_user_did_not_confirm_is_not_treated_as_known() -> None:
    # Text typed into a field the user is still on is not an answer yet.
    app, suggester = _app(), FakeSuggester()
    AiSession(suggester=suggester).attach(tui=app)

    _widget(app, "amount").set_edit_text("99.99")  # entered, not confirmed
    _widget(app, "category").set_edit_text("tools")
    app._handle_input("next_question")

    assert suggester.asked[-1] == {"category": "tools"}


def test_confirmed_question_keeps_its_answer_and_gets_no_new_suggestions() -> (
    None
):
    app, suggester = _app(), FakeSuggester()
    AiSession(suggester=suggester).attach(tui=app)
    _widget(app, "category").set_edit_text("tools")
    app._handle_input("next_question")
    _widget(app, "amount").set_edit_text("7.25")

    app._handle_input("next_question")  # leave the amount question

    assert suggester.asked[-1] == {"category": "tools", "amount": "7.25"}
    assert _widget(app, "amount").get_edit_text() == "7.25"


def test_answered_address_keeps_its_place_in_the_list() -> None:
    app, suggester = _app(), FakeSuggester()
    session = AiSession(suggester=suggester)
    session.attach(tui=app)
    address = _widget(app, "address_selector")
    address.set_answer(BAKERY)
    session.confirm(tui=app, question_id="address_selector")

    _widget(app, "category").set_edit_text("tools")
    app._handle_input("next_question")

    assert address.get_answer() == BAKERY
    assert address.question_data.choices == ["manual address", BAKERY, HARDWARE]


def test_field_events_are_reported_for_the_timing_log() -> None:
    app, suggester = _app(), FakeSuggester()
    AiSession(suggester=suggester).attach(tui=app)
    app.announce_focus()  # what run() does when the questionnaire starts

    _widget(app, "category").set_edit_text("tools")
    app._handle_input("next_question")

    assert suggester.events == [
        ("reached", "category"),
        ("answered", "category"),
        ("reached", "amount"),
    ]


def test_moving_to_a_question_shows_that_questions_suggestions() -> None:
    app, suggester = _app(), FakeSuggester()
    AiSession(suggester=suggester).attach(tui=app)
    _widget(app, "category").set_edit_text("tools")

    app._handle_input("next_question")  # now on the amount question
    on_amount = _box(app)
    _widget(app, "amount").set_edit_text("7.25")
    app._handle_input("next_question")  # now on the address selector
    on_address = _box(app)

    assert "11.54 (90%)" in on_amount
    assert f"1: {HARDWARE} (80%)" in on_address
    assert "11.54" not in on_address


def test_a_failing_suggester_never_breaks_the_questionnaire() -> None:
    class Broken(FakeSuggester):
        def suggest(self, *, answers):
            raise RuntimeError("model file is corrupt")

    app = _app()
    AiSession(suggester=Broken()).attach(tui=app)
    _widget(app, "category").set_edit_text("tools")

    app._handle_input("next_question")

    assert app.get_focus() == 1


def test_account_questions_carry_their_suggestions() -> None:
    questions = AccountQuestions(
        account_infos_str=["alex:examplebank:checking"],
        accounts_without_csv={"alex:wallet:physical"},
        ai_suggestions={
            "bank_account": [_ai("alex:wallet:physical")],
            "currency": [_ai("EUR")],
            "amount": [_ai("11.54")],
            "change": [_ai("0.00")],
        },
    ).account_questions
    by_id = {q.question_id: q for q in questions}

    assert [s.question for s in by_id["bank_account"].ai_suggestions] == [
        "alex:wallet:physical"
    ]
    assert [s.question for s in by_id["currency"].ai_suggestions] == ["EUR"]
    assert [s.question for s in by_id["amount"].ai_suggestions] == ["11.54"]
    assert [s.question for s in by_id["change"].ai_suggestions] == ["0.00"]
    assert by_id["add_another"].ai_suggestions == []


def test_first_guesses_are_available_before_the_questions_exist() -> None:
    suggester = FakeSuggester()
    session = AiSession(suggester=suggester)

    first = session.initial()
    session.attach(tui=_app())

    assert [s.question for s in first["amount"]] == ["11.54"]
    # Asked once: attaching reuses the first answer.
    assert suggester.asked == [{}]


def test_finishing_reports_every_final_answer() -> None:
    app, suggester = _app(), FakeSuggester()
    session = AiSession(suggester=suggester)
    session.attach(tui=app)
    _widget(app, "category").set_edit_text("tools")
    _widget(app, "amount").set_edit_text("7.25")
    _widget(app, "address_selector").set_answer(HARDWARE)

    session.finish(tui=app)

    assert suggester.finished == {
        "category": "tools",
        "amount": "7.25",
        "address_selector": HARDWARE,
    }
