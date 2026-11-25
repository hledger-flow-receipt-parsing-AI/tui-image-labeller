"""The manual address questions (asked after "manual address") get AI
suggestions like every other question: read from the receipt by
hledger-ai, kept up to date by the AI session. Invented data only."""

from typing import Any, Dict, List

import urwid
from hledger_core.AISuggestion import AISuggestion

from tui_labeller.tuis.urwid.ai_session import MANAGED_QUESTIONS, AiSession
from tui_labeller.tuis.urwid.question_data_classes import (
    HorizontalMultipleChoiceQuestionData,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp
from tui_labeller.tuis.urwid.receipts.OptionalQuestions import (
    OptionalQuestions,
)

READ = {
    "shop_name": "Nieuwe Winkel",
    "shop_street": "Molenweg",
    "shop_house_nr": "21",
    "shop_zipcode": "9995VV",
    "shop_city": "Ergensveen",
    "shop_country": "Netherlands",
}


def _ai(text: str, probability: float) -> AISuggestion:
    return AISuggestion(
        question=text, probability=probability, model_name="ST-12"
    )


class AddressSuggester:
    """Stands in for hledger_ai.labeller.LabellerSuggester."""

    def __init__(self) -> None:
        self.asked: List[Dict[str, Any]] = []

    def suggest(
        self, *, answers: Dict[str, Any]
    ) -> Dict[str, List[AISuggestion]]:
        self.asked.append(dict(answers))
        return {
            question: [_ai(text, 0.8), _ai("Iets Anders", 0.1)]
            for question, text in READ.items()
            if question not in answers
        }

    def answered(self, *, question_id: str, answer: Any) -> None:
        pass

    def reached(self, *, question_id: str) -> None:
        pass

    def finish(self, *, answers: Dict[str, Any]) -> int:
        return 0


def _app() -> QuestionnaireApp:
    questions = OptionalQuestions(
        labelled_receipts=[]
    ).get_manual_address_questions()
    questions.append(
        HorizontalMultipleChoiceQuestionData(
            question="Done with this receipt?",
            question_id="done",
            choices=["yes"],
            ai_suggestions=[],
            ans_required=True,
            reconfigurer=False,
            terminator=True,
        )
    )
    app = QuestionnaireApp(
        header="h", questions=questions, labelled_receipts=[]
    )
    app.loop.screen = urwid.raw_display.Screen()
    app.pile.focus_position = app.nr_of_headers
    return app


def _widget(app: QuestionnaireApp, question_id: str) -> Any:
    for entry in app.inputs:
        if entry.base_widget.question_data.question_id == question_id:
            return entry.base_widget
    raise KeyError(question_id)


def test_every_manual_address_question_is_kept_up_to_date() -> None:
    assert set(READ) <= set(MANAGED_QUESTIONS)
    assert all(MANAGED_QUESTIONS[question] == question for question in READ)


def test_the_manual_address_questions_get_their_suggestions() -> None:
    app = _app()
    session = AiSession(suggester=AddressSuggester())
    session.attach(tui=app)
    session.wait()

    for question, text in READ.items():
        suggested = _widget(app, question).question_data.ai_suggestions
        assert [s.question for s in suggested][:1] == [text], question


def test_the_ai_panel_shows_the_street_suggestions() -> None:
    app = _app()
    session = AiSession(suggester=AddressSuggester())
    session.attach(tui=app)
    session.wait()
    app.pile.focus_position = app.nr_of_headers + 1  # the street question
    app.refresh_suggestion_box()
    panel = app.ai_suggestion_box.base_widget.text
    assert "Alt+a  Molenweg (80%)" in panel


def test_each_manual_address_question_starts_with_its_best_suggestion() -> None:
    """The values hledger-ai reads keep to each question's input rule, so the
    best one is filled in (Enter accepts it)."""
    app = _app()
    session = AiSession(suggester=AddressSuggester())
    session.attach(tui=app)
    session.wait()
    for question, text in READ.items():
        assert _widget(app, question).get_answer() == text, question
