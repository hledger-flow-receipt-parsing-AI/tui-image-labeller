"""Keeps the questionnaire's AI suggestions current while one receipt is
labelled.

Each answer the user confirms (by moving on from its question) is passed to
the suggestion engine of hledger-ai, which then re-ranks its suggestions
for the questions that are still open; the shop addresses the engine finds
likely move to the top of the address list.  Every "reached" and "answered"
event is reported too, for hledger-ai's field timing log.

Every open question is filled in with its best suggestion, so the user
corrects the guesses that are wrong (the first keystroke replaces one)
and moves on past the others with Enter.  A guess follows the re-ranking
until the user touches it; what the user typed or picked, and any answer
that was there before the session (a receipt opened again), is never
replaced.  Moving back to an earlier question confirms nothing.

The engine is asked in a background thread, so the user never waits for
it: the questionnaire goes on, and when the answer is in, the worker pokes
the urwid loop (a pipe it watches) and the open questions are updated in
the main thread.  Only the answer to the latest set of confirmed answers
is applied.

The suggester is ``hledger_ai.labeller.LabellerSuggester`` (anything with
``suggest``, ``answered`` and ``reached`` works).  A failure in it is logged
and never interrupts labelling.

With a *highlighter* (the receipt window's box drawer, ``show`` and
``toggle``), the boxes the suggester reports for the focused question
(``highlights()``, keyed by question id) are drawn on the receipt photo, so
the user can check a suggestion at a glance; Alt+h turns them off and on.
"""

import logging
import os
import threading
import time
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from hledger_core.AISuggestion import AISuggestion
from typeguard import typechecked

from tui_labeller.tuis.urwid.ai_suggestions import (
    NOTHING,
    rank_choices_by_suggestions,
)
from tui_labeller.tuis.urwid.input_validation.InputType import InputType

logger = logging.getLogger(__name__)

ADDRESS_SELECTOR = "address_selector"
# Question id -> key of its suggestions (the date question's differ).
MANAGED_QUESTIONS: Dict[str, str] = {
    "date": "receipt_date",
    "is_withdrawal": "is_withdrawal",
    "category": "category",
    "bank_account": "bank_account",
    "currency": "currency",
    "amount": "amount",
    "change": "change",
    ADDRESS_SELECTOR: ADDRESS_SELECTOR,
    # The manual address questions (asked after "manual address"): read
    # from the receipt, and the usual city and country of a shop
    # (hledger_ai.address_parts).
    "shop_name": "shop_name",
    "shop_street": "shop_street",
    "shop_house_nr": "shop_house_nr",
    "shop_zipcode": "shop_zipcode",
    "shop_city": "shop_city",
    "shop_country": "shop_country",
    "subtotal": "subtotal",
    "total_tax": "total_tax",
}
# Questions that get the best suggestion filled in but not the list: the
# withdrawal toggle would print confidence and source behind its choices,
# which belong in the AI panel only.
PREFILL_ONLY = frozenset({"is_withdrawal"})
HIGHLIGHT_HINT = "Alt+h      - receipt boxes on/off"
# Finishing a receipt waits this long at most for the first guesses.
FINISH_WAIT_SECONDS = 10.0
# The loading bar: how long the suggester usually takes, to start with,
# and how often the bar is redrawn.
EXPECTED_SECONDS = 0.6
TICK_SECONDS = 0.05
PROGRESS_CAP = 0.95  # never quite full until the work is really done

Suggestions = Dict[str, List[AISuggestion]]
Boxes = Dict[str, List[Any]]


@typechecked
def progress_fraction(*, elapsed: float, expected: float) -> float:
    """How far along the work probably is, from how long it usually takes."""
    if expected <= 0.0:
        return PROGRESS_CAP
    return min(PROGRESS_CAP, max(0.0, elapsed / expected))


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


@typechecked
def _given_answer(*, widget: Any) -> Optional[str]:
    """The answer to report for a question the user is done with: its
    text, or NOTHING for an optional question left empty on purpose."""
    answer = _answer_text(widget=widget)
    if answer is not None:
        return answer
    data = getattr(widget, "question_data", None)
    if data is None or data.ans_required or data.terminator:
        return None
    try:
        if widget.has_answer() and widget.get_answer() == "":
            return NOTHING
    except (ValueError, IndexError):
        return None
    return None


@typechecked
def fill_in(*, widget: Any, text: str) -> bool:
    """Put the suggestion *text* in *widget* as its answer, in the form the
    question takes (a choice, an existing category, a number, a date).

    False when the question cannot take it; the answer is then left
    alone. An empty *text* ("leave it empty", e.g. no subtotal on the
    receipt) only fits an optional question.
    """
    data = widget.question_data
    if text == NOTHING:
        if data.ans_required or not hasattr(widget, "set_edit_text"):
            return False
        widget.set_edit_text("")
        return True
    try:
        if hasattr(data, "choices"):
            if text not in data.choices:
                return False
            widget.set_answer(text)
        elif hasattr(widget, "store"):  # the category field
            if not widget.store.exists(path=text):
                return False
            widget.set_answer(text)
        elif getattr(widget, "input_type", None) == InputType.FLOAT:
            widget.set_answer(float(text))
        elif getattr(widget, "input_type", None) == InputType.INTEGER:
            widget.set_answer(int(text))
        else:
            widget.set_answer(text)
    except (ValueError, TypeError):
        return False
    return True


@typechecked
def _mark_untouched(*, widget: Any) -> None:
    """The answer shown is a guess: the first keystroke replaces it."""
    if hasattr(widget, "mark_default_untouched"):
        widget.mark_default_untouched()


class AiSession:
    @typechecked
    def __init__(self, *, suggester: Any, highlighter: Any = None) -> None:
        self._suggester = suggester
        self._highlighter = highlighter
        self._confirmed: Dict[str, str] = {}  # question id -> answer
        # Question id -> the answer this session filled in (as the widget
        # reports it); a question whose answer still reads so is untouched.
        self._prefilled: Dict[str, str] = {}
        self._asked: Optional[Dict[str, str]] = None
        self._latest: Suggestions = {}
        self._boxes: Boxes = {}  # question id -> highlights
        self._tui: Any = None
        # Background work: one suggester call at a time; the result of the
        # latest request waits in _pending until the main thread takes it.
        self._suggester_lock = threading.Lock()
        self._lock = threading.Lock()
        self._request = 0
        self._pending: Optional[Tuple[Suggestions, Boxes]] = None
        self._worker: Optional[threading.Thread] = None
        self._pipe: Optional[Tuple[Any, int]] = None  # (loop, write fd)
        # The loading bar: when the running request started, how long one
        # usually takes, and the loop whose alarms redraw the bar.
        self._started_at = 0.0
        self._expected = EXPECTED_SECONDS
        self._ticking: Any = None

    @typechecked
    def initial(self) -> Suggestions:
        """The first guesses, before any answer; the questions are built with
        them (the date question starts at the suggested date)."""
        self._ask()
        self.wait()
        return self._latest

    @typechecked
    def attach(self, *, tui: Any) -> None:
        """Follow *tui* (a QuestionnaireApp, possibly a rebuilt one) and bring
        its suggestions up to date."""
        self._tui = tui
        tui.on_question_change = lambda left, reached: self._moved(
            tui=tui, left=left, reached=reached
        )
        if self._highlighter is not None:
            tui.on_toggle_highlights = lambda: self._safely(
                self._highlighter.toggle
            )
            tui.add_navigation_hint(text=HIGHLIGHT_HINT)
        self._watch_loop(tui=tui)
        if self.busy():
            self._show_progress(tui=tui)
        self.refresh(tui=tui)

    @typechecked
    def wait(self, *, timeout: Optional[float] = None) -> None:
        """Let the background work finish and take its result (the running TUI
        gets it through its loop instead)."""
        worker = self._worker
        if worker is not None:
            worker.join(timeout)
        self._take_pending()

    @typechecked
    def finish(self, *, tui: Any) -> None:
        """The receipt is done: report the final answers, so suggestions
        the user did not keep are logged as corrections."""
        self.wait(timeout=FINISH_WAIT_SECONDS)
        answers: Dict[str, str] = {}
        for input_widget in tui.inputs:
            widget = input_widget.base_widget
            question_id = _question_id(widget=widget)
            answer = _given_answer(widget=widget)
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
            answer = _given_answer(widget=widget)
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
        """Ask for suggestions when the confirmed answers changed (in the
        background), and put the latest ones on every open question."""
        self._ask(tui=tui)
        self._safely(lambda: self._apply(tui=tui))
        self._safely(lambda: self._show_boxes(tui=tui))
        self._take_pending()

    # ------------------------------------------------- background work

    @typechecked
    def busy(self) -> bool:
        """Whether suggestions are being worked out right now."""
        worker = self._worker
        return self._pending is not None or (
            worker is not None and worker.is_alive()
        )

    @typechecked
    def progress_fraction(self) -> Optional[float]:
        """How far the running work probably is; None when there is none."""
        if not self.busy():
            return None
        return progress_fraction(
            elapsed=time.monotonic() - self._started_at,
            expected=self._expected,
        )

    def _ask(self, *, tui: Any = None) -> None:
        if self._asked == self._confirmed:
            return
        asked = dict(self._confirmed)
        self._asked = asked
        with self._lock:
            self._request += 1
            request = self._request
        self._started_at = time.monotonic()
        self._worker = threading.Thread(
            target=self._compute,
            args=(request, asked),
            name="ai-suggestions",
            daemon=True,
        )
        self._worker.start()
        if tui is not None:
            self._show_progress(tui=tui)

    # ------------------------------------------------------ loading bar

    def _show_progress(self, *, tui: Any) -> None:
        """Put the loading bar on *tui* and keep it moving through the alarms
        of its loop until the work is done."""
        self._set_progress(tui=tui, fraction=self.progress_fraction())
        loop = getattr(tui, "loop", None)
        if loop is None or not hasattr(loop, "set_alarm_in"):
            return
        if self._ticking is not loop:
            self._ticking = loop
            loop.set_alarm_in(TICK_SECONDS, self._tick)

    def _tick(self, loop: Any, _data: Any = None) -> None:
        if loop is not self._ticking:
            return  # a loop that was replaced: its chain ends here
        fraction = self.progress_fraction()
        self._set_progress(tui=self._tui, fraction=fraction)
        if fraction is None:
            self._ticking = None
            return
        loop.set_alarm_in(TICK_SECONDS, self._tick)

    @staticmethod
    def _set_progress(*, tui: Any, fraction: Optional[float]) -> None:
        if tui is not None and hasattr(tui, "set_progress"):
            tui.set_progress(fraction=fraction)

    def _compute(self, request: int, asked: Dict[str, str]) -> None:
        """Worker thread: the suggester's answer for *asked*."""
        try:
            with self._suggester_lock:
                latest = self._suggester.suggest(answers=asked)
                boxes: Boxes = {}
                if self._highlighter is not None and hasattr(
                    self._suggester, "highlights"
                ):
                    boxes = self._suggester.highlights()
        except Exception:
            logger.exception("AI suggestions failed; labelling continues")
            return
        with self._lock:
            if request != self._request:
                return  # the answers changed meanwhile: outdated
            self._pending = (latest, boxes)
        self._poke()

    def _poke(self) -> None:
        """Have the TUI's loop call _deliver in the main thread."""
        pipe = self._pipe
        if pipe is None:
            return
        try:
            os.write(pipe[1], b"1")
        except OSError:
            logger.debug("The TUI loop is gone; result waits", exc_info=True)

    def _deliver(self, _data: bytes) -> None:
        self._take_pending()

    def _take_pending(self) -> None:
        with self._lock:
            pending, self._pending = self._pending, None
        if pending is None:
            return
        self._latest, self._boxes = pending
        taken = time.monotonic() - self._started_at
        self._expected = 0.7 * self._expected + 0.3 * taken
        if self._tui is not None:
            tui = self._tui
            self._safely(lambda: self._apply(tui=tui))
            self._safely(lambda: self._show_boxes(tui=tui))
            self._set_progress(tui=tui, fraction=self.progress_fraction())

    def _watch_loop(self, *, tui: Any) -> None:
        loop = getattr(tui, "loop", None)
        if loop is None or not hasattr(loop, "watch_pipe"):
            return
        if self._pipe is not None:
            old_loop, old_fd = self._pipe
            if old_loop is loop:
                return
            self._safely(lambda: old_loop.remove_watch_pipe(old_fd))
            self._pipe = None
        self._pipe = (loop, loop.watch_pipe(self._deliver))

    # ------------------------------------------------- the questionnaire

    def _moved(self, *, tui: Any, left: int, reached: int) -> None:
        # Moving on confirms the answer left behind (a guess included);
        # going back to an earlier question confirms nothing.
        if 0 <= left < len(tui.inputs) and reached > left:
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

    def _show_boxes(self, *, tui: Any) -> None:
        """Draw the boxes behind the focused question's suggestion on the
        receipt photo (none: the photo is cleared)."""
        if self._highlighter is None:
            return
        boxes: List[Any] = []
        index = tui.get_focus()
        if 0 <= index < len(tui.inputs):
            question_id = _question_id(widget=tui.inputs[index].base_widget)
            boxes = self._boxes.get(question_id or "", [])
        self._highlighter.show(highlights=boxes)

    def _apply(self, *, tui: Any) -> None:
        focused = tui.get_focus()
        for index, input_widget in enumerate(tui.inputs):
            widget = input_widget.base_widget
            question_id = _question_id(widget=widget)
            if question_id not in MANAGED_QUESTIONS:
                continue
            untouched = self._untouched(widget=widget, question_id=question_id)
            if question_id in self._confirmed:
                # Never touch what the user answered; a guess they moved
                # past stays replaceable by one keystroke.
                if untouched:
                    _mark_untouched(widget=widget)
                continue
            suggestions = self._latest.get(MANAGED_QUESTIONS[question_id], [])
            if question_id not in PREFILL_ONLY:
                widget.question_data.ai_suggestions = suggestions
                if hasattr(widget, "ai_suggestions"):
                    widget.ai_suggestions = suggestions
                if question_id == ADDRESS_SELECTOR:
                    self._order_addresses(
                        widget=widget, suggestions=suggestions
                    )
            if untouched or (
                _answer_text(widget=widget) is None
                and not getattr(widget.question_data, "user_edited", False)
            ):
                self._prefill(
                    widget=widget,
                    question_id=question_id,
                    suggestions=suggestions,
                    focused=index == focused,
                )
        tui.refresh_suggestion_box()

    def _untouched(self, *, widget: Any, question_id: str) -> bool:
        """Whether the question still shows the guess this session filled in,
        with nothing typed by the user."""
        recorded = self._prefilled.get(question_id)
        if recorded is None:
            return False
        if getattr(widget.question_data, "user_edited", False):
            return False
        return _answer_text(widget=widget) == recorded

    def _prefill(
        self,
        *,
        widget: Any,
        question_id: str,
        suggestions: List[AISuggestion],
        focused: bool,
    ) -> None:
        """Fill in the best suggestion the question can take."""
        for suggestion in suggestions:
            if not fill_in(widget=widget, text=suggestion.question):
                continue
            answer = _answer_text(widget=widget)
            if answer is not None:
                self._prefilled[question_id] = answer
            _mark_untouched(widget=widget)
            if focused and hasattr(widget, "expand_choices"):
                # An answered choice shows only its answer; the user is
                # on it now and may want another.
                widget.expand_choices()
            return

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
