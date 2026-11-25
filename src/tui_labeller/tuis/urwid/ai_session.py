"""Keeps the questionnaire's AI suggestions current while one receipt is
labelled.

Each answer the user confirms (by moving on from its question) is passed to
the suggestion engine of hledger-ai, which then re-ranks its suggestions
for the questions that are still open; the shop addresses the engine finds
likely move to the top of the address list.  Every "reached" and "answered"
event is reported too, for hledger-ai's field timing log.

The suggester is ``hledger_ai.labeller.LabellerSuggester`` (anything with
``suggest``, ``answered`` and ``reached`` works).  A failure in it is logged
and never interrupts labelling.
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from hledger_core.AISuggestion import AISuggestion
from typeguard import typechecked

from tui_labeller.tuis.urwid.ai_suggestions import rank_choices_by_suggestions

logger = logging.getLogger(__name__)

ADDRESS_SELECTOR = "address_selector"
# Question id -> key of its suggestions (the date question's differ).
MANAGED_QUESTIONS: Dict[str, str] = {
    "date": "receipt_date",
    "category": "category",
    "bank_account": "bank_account",
    "currency": "currency",
    "amount": "amount",
    "change": "change",
    ADDRESS_SELECTOR: ADDRESS_SELECTOR,
    "subtotal": "subtotal",
    "total_tax": "total_tax",
}


@typechecked
def _question_id(*, widget: Any) -> Optional[str]:
    question_data = getattr(widget, "question_data", None)
    if question_data is None:
        return None
    return (question_data.question_id or question_data.question).strip()


@typechecked
def _answer_text(*, widget: Any) -> Optional[str]:
    """The widget's answer as text, or None while it has none."""
    try:
        if not widget.has_answer():
            return None
        answer = widget.get_answer()
    except (ValueError, IndexError):
        return None
    if answer is None or answer == "":
        return None
    if isinstance(answer, datetime):
        return answer.isoformat(sep=" ")
    return str(answer)


class AiSession:
    @typechecked
    def __init__(self, *, suggester: Any) -> None:
        self._suggester = suggester
        self._confirmed: Dict[str, str] = {}  # question id -> answer
        self._asked: Optional[Dict[str, str]] = None
        self._latest: Dict[str, List[AISuggestion]] = {}

    @typechecked
    def initial(self) -> Dict[str, List[AISuggestion]]:
        """The first guesses, before any answer; the questions are built with
        them (the date question starts at the suggested date)."""
        self._ask()
        return self._latest

    @typechecked
    def attach(self, *, tui: Any) -> None:
        """Follow *tui* (a QuestionnaireApp, possibly a rebuilt one) and bring
        its suggestions up to date."""
        tui.on_question_change = lambda left, reached: self._moved(
            tui=tui, left=left, reached=reached
        )
        self.refresh(tui=tui)

    @typechecked
    def finish(self, *, tui: Any) -> None:
        """The receipt is done: report the final answers, so suggestions
        the user did not keep are logged as corrections."""
        answers: Dict[str, str] = {}
        for input_widget in tui.inputs:
            widget = input_widget.base_widget
            question_id = _question_id(widget=widget)
            answer = _answer_text(widget=widget)
            if question_id is not None and answer is not None:
                answers[question_id] = answer
        self._safely(lambda: self._suggester.finish(answers=answers))

    @typechecked
    def confirm(self, *, tui: Any, question_id: str) -> None:
        """Count the current answer to *question_id* as confirmed."""
        for input_widget in tui.inputs:
            widget = input_widget.base_widget
            if _question_id(widget=widget) != question_id:
                continue
            answer = _answer_text(widget=widget)
            if answer is not None:
                self._confirmed[question_id] = answer
                self._safely(
                    lambda: self._suggester.answered(
                        question_id=question_id, answer=answer
                    )
                )
            return

    @typechecked
    def confirm_focused(self, *, tui: Any) -> None:
        """Count the answer to the focused question as confirmed (a
        "reconfigurer" answer ends the main loop before the focus moves)."""
        index = tui.get_focus()
        if 0 <= index < len(tui.inputs):
            question_id = _question_id(widget=tui.inputs[index].base_widget)
            if question_id is not None:
                self.confirm(tui=tui, question_id=question_id)

    @typechecked
    def refresh(self, *, tui: Any) -> None:
        """Ask for suggestions when the confirmed answers changed, and put the
        latest ones on every open question."""
        self._ask()
        self._safely(lambda: self._apply(tui=tui))

    def _ask(self) -> None:
        if self._asked == self._confirmed:
            return
        asked = dict(self._confirmed)

        def ask() -> None:
            self._latest = self._suggester.suggest(answers=asked)

        self._safely(ask)
        self._asked = asked

    def _moved(self, *, tui: Any, left: int, reached: int) -> None:
        if 0 <= left < len(tui.inputs):
            left_id = _question_id(widget=tui.inputs[left].base_widget)
            if left_id is not None:
                self.confirm(tui=tui, question_id=left_id)
        self._safely(lambda: self._report_reached(tui=tui))
        self.refresh(tui=tui)

    def _report_reached(self, *, tui: Any) -> None:
        index = tui.get_focus()
        if 0 <= index < len(tui.inputs):
            question_id = _question_id(widget=tui.inputs[index].base_widget)
            if question_id is not None:
                self._suggester.reached(question_id=question_id)

    def _apply(self, *, tui: Any) -> None:
        for input_widget in tui.inputs:
            widget = input_widget.base_widget
            question_id = _question_id(widget=widget)
            if question_id not in MANAGED_QUESTIONS:
                continue
            if question_id in self._confirmed:
                continue  # never touch what the user answered
            suggestions = self._latest.get(MANAGED_QUESTIONS[question_id], [])
            widget.question_data.ai_suggestions = suggestions
            if hasattr(widget, "ai_suggestions"):
                widget.ai_suggestions = suggestions
            if question_id == ADDRESS_SELECTOR:
                self._order_addresses(widget=widget, suggestions=suggestions)
        tui.refresh_suggestion_box()

    @staticmethod
    def _order_addresses(
        *, widget: Any, suggestions: List[AISuggestion]
    ) -> None:
        data = widget.question_data
        shop_ids = (data.extra_data or {}).get("shop_ids")
        if not shop_ids or len(shop_ids) != len(data.choices):
            return
        choices, shops = rank_choices_by_suggestions(
            choices=data.choices, shop_ids=shop_ids, suggestions=suggestions
        )
        if choices != data.choices:
            data.choices = choices
            data.extra_data["shop_ids"] = shops
            widget.refresh_choices()

    @staticmethod
    def _safely(action: Any) -> None:
        try:
            action()
        except Exception:
            logger.exception("AI suggestions failed; labelling continues")
