"""Keeping suggestions current while one receipt is labelled.

A confirmed answer goes to the suggestion engine, the remaining
questions get re-ranked suggestions (cross-inference), and every field
event is reported for the timing log.  All data here is invented.
"""

import os
import select
import threading
import time
from types import SimpleNamespace
from typing import Any, Dict, List

import urwid
from hledger_core.AISuggestion import AISuggestion
from hledger_core.TransactionObjects.Address import Address
from hledger_core.TransactionObjects.ShopId import ShopId

from tui_labeller.tuis.urwid.ai_session import AiSession, progress_fraction
from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_data_classes import (
    HorizontalMultipleChoiceQuestionData,
    InputValidationQuestionData,
    VerticalMultipleChoiceQuestionData,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import (
    QuestionnaireApp,
    render_progress,
)
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


def _attached(
    app: QuestionnaireApp, suggester: Any, highlighter: Any = None
) -> AiSession:
    """A session attached to *app* with its background work finished."""
    session = AiSession(suggester=suggester, highlighter=highlighter)
    session.attach(tui=app)
    session.wait()
    return session


def _next(app: QuestionnaireApp, session: AiSession) -> None:
    """Leave the focused question and let the session catch up."""
    app._handle_input("next_question")
    session.wait()


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

    _attached(app, suggester)

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
    session = _attached(app, suggester)

    _widget(app, "category").set_edit_text("tools")
    _next(app, session)  # leave the category question

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
    session = _attached(app, suggester)

    _widget(app, "amount").set_edit_text("99.99")  # entered, not confirmed
    _widget(app, "category").set_edit_text("tools")
    _next(app, session)

    assert suggester.asked[-1] == {"category": "tools"}


def test_confirmed_question_keeps_its_answer_and_gets_no_new_suggestions() -> (
    None
):
    app, suggester = _app(), FakeSuggester()
    session = _attached(app, suggester)
    _widget(app, "category").set_edit_text("tools")
    _next(app, session)
    _widget(app, "amount").set_edit_text("7.25")

    _next(app, session)  # leave the amount question

    assert suggester.asked[-1] == {"category": "tools", "amount": "7.25"}
    assert _widget(app, "amount").get_edit_text() == "7.25"


def test_answered_address_keeps_its_place_in_the_list() -> None:
    app, suggester = _app(), FakeSuggester()
    session = _attached(app, suggester)
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
    session = _attached(app, suggester)
    _widget(app, "category").set_edit_text("tools")

    _next(app, session)  # now on the amount question
    on_amount = _box(app)
    _widget(app, "amount").set_edit_text("7.25")
    _next(app, session)  # now on the address selector
    on_address = _box(app)

    assert "11.54 (90%)" in on_amount
    assert f"1: {HARDWARE} (80%)" in on_address
    assert "11.54" not in on_address


def test_a_failing_suggester_never_breaks_the_questionnaire() -> None:
    class Broken(FakeSuggester):
        def suggest(self, *, answers):
            raise RuntimeError("model file is corrupt")

    app = _app()
    session = _attached(app, Broken())
    _widget(app, "category").set_edit_text("tools")

    _next(app, session)

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


# ------------------------------------------------------------ highlights


def _highlight(text: str) -> SimpleNamespace:
    """What hledger-ai's Highlight looks like to the labeller."""
    return SimpleNamespace(
        image_path="/finance/proc/a_cropped.jpg",
        box=((1.0, 2.0), (3.0, 2.0), (3.0, 4.0), (1.0, 4.0)),
        text=text,
    )


AMOUNT_BOX, CATEGORY_BOX, TOOLS_BOX = (
    _highlight("11.54"),
    _highlight("Bakker Bart"),
    _highlight("IJzerwaren"),
)


class HighlightingSuggester(FakeSuggester):
    """Also says where on the photo its suggestions come from."""

    def __init__(self) -> None:
        super().__init__()
        self.highlight_calls = 0

    def highlights(self) -> Dict[str, List[Any]]:
        self.highlight_calls += 1
        if self.asked and self.asked[-1].get("category") == "tools":
            return {"amount": [TOOLS_BOX]}
        return {"category": [CATEGORY_BOX], "amount": [AMOUNT_BOX]}


class FakeHighlighter:
    """Stands in for the receipt window's box drawer."""

    def __init__(self) -> None:
        self.shown: List[List[Any]] = []
        self.toggles = 0

    def show(self, *, highlights: List[Any]) -> None:
        self.shown.append(list(highlights))

    def toggle(self) -> bool:
        self.toggles += 1
        return self.toggles % 2 == 0


def test_attaching_shows_the_boxes_of_the_focused_question() -> None:
    app, highlighter = _app(), FakeHighlighter()

    _attached(app, HighlightingSuggester(), highlighter)

    assert highlighter.shown[-1] == [CATEGORY_BOX]


def test_moving_to_the_next_question_shows_its_boxes() -> None:
    app, highlighter = _app(), FakeHighlighter()
    session = _attached(app, HighlightingSuggester(), highlighter)

    _next(app, session)  # category -> amount

    assert highlighter.shown[-1] == [AMOUNT_BOX]


def test_a_question_without_boxes_clears_the_photo() -> None:
    app, highlighter = _app(), FakeHighlighter()
    session = _attached(app, HighlightingSuggester(), highlighter)

    _next(app, session)
    _next(app, session)  # -> address_selector

    assert highlighter.shown[-1] == []


def test_boxes_follow_the_suggestions_after_an_answer() -> None:
    app, highlighter = _app(), FakeHighlighter()
    session = _attached(app, HighlightingSuggester(), highlighter)

    _widget(app, "category").set_edit_text("tools")
    _next(app, session)  # confirms the category

    assert highlighter.shown[-1] == [TOOLS_BOX]


def test_alt_h_toggles_the_boxes_and_never_reaches_the_questions() -> None:
    app, highlighter = _app(), FakeHighlighter()
    _attached(app, HighlightingSuggester(), highlighter)

    passed_on = app._filter_input(["meta h", "x"], [])

    assert passed_on == ["x"]
    assert highlighter.toggles == 1
    hints = [
        widget.text for widget, _ in app.navigation_display.base_widget.contents
    ]
    assert any("Alt+h" in hint for hint in hints)


def test_without_a_highlighter_no_boxes_are_worked_out() -> None:
    app, suggester = _app(), HighlightingSuggester()
    session = _attached(app, suggester)

    _next(app, session)

    assert suggester.highlight_calls == 0
    assert app._filter_input(["meta h"], []) == ["meta h"]


def test_a_suggester_without_highlights_leaves_the_photo_clear() -> None:
    app, highlighter = _app(), FakeHighlighter()

    _attached(app, FakeSuggester(), highlighter)

    assert highlighter.shown and all(shown == [] for shown in highlighter.shown)


# ------------------------------------------------------ background work


class SlowSuggester(FakeSuggester):
    """Answers only once released, like a model that takes its time; the first
    *quick* calls answer at once."""

    def __init__(self, quick: int = 0) -> None:
        super().__init__()
        self.quick = quick
        self.calls = 0
        self.started = threading.Event()
        self.release = threading.Event()
        self.order: List[str] = []

    def suggest(self, *, answers: Dict[str, Any]) -> Dict[str, List[Any]]:
        self.calls += 1
        if self.calls > self.quick:
            self.started.set()
            self.release.wait(timeout=5)
        self.order.append("suggest")
        return super().suggest(answers=answers)

    def finish(self, *, answers: Dict[str, Any]) -> int:
        self.order.append("finish")
        return super().finish(answers=answers)


class FakeLoop:
    """The part of urwid's MainLoop the session uses to be told, in the main
    thread, that the background work is done."""

    def __init__(self) -> None:
        self.read_fd = -1
        self.callback: Any = None
        self.removed: List[int] = []

    def watch_pipe(self, callback: Any) -> int:
        self.read_fd, write_fd = os.pipe()
        self.callback = callback
        return write_fd

    def remove_watch_pipe(self, write_fd: int) -> None:
        self.removed.append(write_fd)

    def set_alarm_in(self, seconds: float, callback: Any) -> Any:
        return ("alarm", seconds, callback)

    def pump(self) -> None:
        """One pass of the loop: deliver what the worker wrote."""
        ready, _, _ = select.select([self.read_fd], [], [], 5)
        assert ready, "the worker did not poke the loop"
        self.callback(os.read(self.read_fd, 4096))


def test_the_questionnaire_is_not_held_up_by_the_suggester() -> None:
    app, suggester = _app(), SlowSuggester()
    session = AiSession(suggester=suggester)

    started = time.monotonic()
    session.attach(tui=app)
    seconds = time.monotonic() - started

    assert suggester.started.wait(timeout=5)
    assert seconds < 0.5
    assert _widget(app, "amount").ai_suggestions == []  # not in yet
    suggester.release.set()
    session.wait()
    assert [s.question for s in _widget(app, "amount").ai_suggestions] == [
        "11.54"
    ]


def test_results_reach_the_questionnaire_through_its_event_loop() -> None:
    # While the TUI runs nobody calls wait(): the worker pokes the urwid
    # loop, which applies the result in the main thread.
    app, suggester = _app(), SlowSuggester()
    app.loop = FakeLoop()
    session = AiSession(suggester=suggester)
    session.attach(tui=app)
    suggester.release.set()

    app.loop.pump()

    assert [s.question for s in _widget(app, "amount").ai_suggestions] == [
        "11.54"
    ]
    del session


def test_a_rebuilt_questionnaire_is_watched_through_its_own_loop() -> None:
    first, second = _app(), _app()
    first.loop, second.loop = FakeLoop(), FakeLoop()
    session = _attached(first, FakeSuggester())

    session.attach(tui=second)

    assert len(first.loop.removed) == 1
    assert second.loop.callback is not None


def test_answers_given_while_the_model_is_busy_are_still_used() -> None:
    app, suggester = _app(), SlowSuggester(quick=1)
    session = _attached(app, suggester)
    _widget(app, "category").set_edit_text("tools")
    app._handle_input("next_question")  # the model gets busy with this
    assert suggester.started.wait(timeout=5)
    _widget(app, "amount").set_edit_text("7.25")
    app._handle_input("next_question")  # the TUI goes on meanwhile

    suggester.release.set()
    session.wait()

    assert suggester.asked[-1] == {"category": "tools", "amount": "7.25"}
    assert _widget(app, "address_selector").question_data.choices[1] == (
        HARDWARE
    )


def test_finishing_waits_for_the_first_guesses() -> None:
    # Corrections are told from the first guesses, so those must be in.
    app, suggester = _app(), SlowSuggester()
    session = AiSession(suggester=suggester)
    session.attach(tui=app)
    threading.Timer(0.2, suggester.release.set).start()

    session.finish(tui=app)

    assert suggester.order == ["suggest", "finish"]


# ---------------------------------------------------------- loading bar


def test_set_progress_draws_a_bar_in_the_header_and_clears_it() -> None:
    app = _app()

    app.set_progress(fraction=0.5)
    assert app.progress_text.text == "AI ▰▰▰▰▰▱▱▱▱▱"

    app.set_progress(fraction=None)
    assert app.progress_text.text == ""
    # The header row stays the single first row of the pile.
    assert app.pile.contents[0][0] is app.header_widget


def test_the_header_shows_a_loading_bar_while_the_model_works() -> None:
    app, suggester = _app(), SlowSuggester()
    session = AiSession(suggester=suggester)
    session.attach(tui=app)
    assert suggester.started.wait(timeout=5)

    assert app.progress_text.text.startswith("AI ")
    assert session.progress_fraction() is not None

    suggester.release.set()
    session.wait()

    assert app.progress_text.text == ""
    assert session.progress_fraction() is None


def test_a_rebuilt_questionnaire_shows_the_bar_of_the_running_work() -> None:
    first, second, suggester = _app(), _app(), SlowSuggester()
    session = AiSession(suggester=suggester)
    session.attach(tui=first)
    assert suggester.started.wait(timeout=5)

    session.attach(tui=second)

    assert second.progress_text.text.startswith("AI ")
    suggester.release.set()
    session.wait()
    assert second.progress_text.text == ""


def test_the_bar_fills_with_the_time_the_model_usually_takes() -> None:
    assert progress_fraction(elapsed=0.3, expected=0.6) == 0.5
    assert progress_fraction(elapsed=0.0, expected=0.6) == 0.0
    # Never quite full until the work is really done.
    assert progress_fraction(elapsed=5.0, expected=0.6) == 0.95


def test_the_bar_sits_in_the_middle_of_the_top_row_next_to_the_header() -> None:
    app = _app()
    app.set_progress(fraction=0.5)

    row = app.header_widget.render((84,)).text[0].decode()

    assert row.startswith("h")  # the header keeps its place and width
    bar = render_progress(fraction=0.5)
    start = row.index(bar)
    assert abs(start + len(bar) / 2 - 84 / 2) <= 2  # centred on the row


# ------------------------------------------------------------- prefill
#
# Every open question starts with the best suggestion filled in, so the
# user corrects the guesses that are wrong instead of accepting each one.


class ReRankingSuggester(FakeSuggester):
    """Another amount once the category is known."""

    def suggest(
        self, *, answers: Dict[str, Any]
    ) -> Dict[str, List[AISuggestion]]:
        suggestions = super().suggest(answers=answers)
        if answers.get("category") == "tools" and "amount" in suggestions:
            suggestions["amount"] = [_ai("20.00")]
        return suggestions


def _toggle_app() -> QuestionnaireApp:
    """A questionnaire with the withdrawal toggle (a horizontal choice)."""
    questions = [
        HorizontalMultipleChoiceQuestionData(
            question="Is this a withdrawal? (y/n)",
            question_id="is_withdrawal",
            choices=["n", "y"],
            ai_suggestions=[],
            ans_required=True,
            reconfigurer=True,
            terminator=False,
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


def test_every_open_question_starts_with_its_best_suggestion() -> None:
    app = _app()

    _attached(app, FakeSuggester())

    assert _widget(app, "amount").get_edit_text() == "11.54"
    assert _widget(app, "address_selector").get_answer() == BAKERY


def test_moving_on_confirms_the_prefilled_answer() -> None:
    app, suggester = _app(), FakeSuggester()
    session = _attached(app, suggester)
    _widget(app, "category").set_edit_text("tools")
    _next(app, session)  # on the amount, prefilled

    _next(app, session)  # Enter: the guess is the answer

    assert suggester.asked[-1] == {"category": "tools", "amount": "11.54"}


def test_a_prefilled_answer_follows_the_reranking_until_touched() -> None:
    app, suggester = _app(), FakeSuggester()
    session = _attached(app, suggester)
    assert _widget(app, "address_selector").get_answer() == BAKERY

    _widget(app, "category").set_edit_text("tools")
    _next(app, session)  # tools: the hardware shop is now more likely

    assert _widget(app, "address_selector").get_answer() == HARDWARE


def test_the_first_keystroke_replaces_a_prefilled_amount() -> None:
    app = _app()
    _attached(app, FakeSuggester())
    amount = _widget(app, "amount")

    amount.keypress((80,), "7")

    assert amount.get_edit_text() == "7"  # not "11.547"


def test_what_the_user_typed_is_never_replaced_by_a_new_guess() -> None:
    app, suggester = _app(), ReRankingSuggester()
    session = _attached(app, suggester)
    amount = _widget(app, "amount")
    amount.keypress((80,), "7")

    _widget(app, "category").set_edit_text("tools")
    _next(app, session)  # the model now says 20.00

    assert amount.get_edit_text() == "7"


def test_the_first_typed_digit_replaces_a_prefilled_choice() -> None:
    app = _app()
    _attached(app, FakeSuggester())
    address = _widget(app, "address_selector")
    assert address.get_edit_text() == "1"

    address.keypress((80,), "2")

    assert address.get_answer() == HARDWARE  # not choice "12"


def test_a_choice_the_user_picked_stays_through_a_rerank() -> None:
    app, suggester = _app(), FakeSuggester()
    session = _attached(app, suggester)
    address = _widget(app, "address_selector")
    address.keypress((80,), "0")  # manual address, over the guess

    _widget(app, "category").set_edit_text("tools")
    _next(app, session)

    assert address.get_answer() == "manual address"


def test_a_pick_keeps_its_shop_when_the_list_is_reordered() -> None:
    app, suggester = _app(), FakeSuggester()
    session = _attached(app, suggester)
    address = _widget(app, "address_selector")
    address.keypress((80,), "2")  # the hardware shop, third in the list
    assert address.get_answer() == HARDWARE

    _widget(app, "category").set_edit_text("tools")
    _next(app, session)  # the model now lists the hardware shop second

    assert address.get_answer() == HARDWARE
    assert address.get_edit_text() == "1"


def test_a_prefilled_guess_leaves_every_suggestion_in_the_panel() -> None:
    class TwoAmounts(FakeSuggester):
        def suggest(self, *, answers: Dict[str, Any]) -> Dict[str, Any]:
            suggestions = super().suggest(answers=answers)
            suggestions["amount"] = [_ai("11.54"), _ai("1.54", 0.1)]
            return suggestions

    app, suggester = _app(), TwoAmounts()
    session = _attached(app, suggester)
    _widget(app, "category").set_edit_text("tools")
    _next(app, session)  # on the amount, prefilled with 11.54

    assert "Alt+b  1.54 (10%)" in _box(app)


def test_leaving_a_question_backwards_does_not_confirm_its_guess() -> None:
    app, suggester = _app(), FakeSuggester()
    session = _attached(app, suggester)
    _widget(app, "category").set_edit_text("tools")
    _next(app, session)  # on the amount, prefilled

    app._handle_input("previous_question")  # back to the category
    session.wait()

    assert suggester.asked[-1] == {"category": "tools"}


def test_a_guess_the_user_passed_can_still_be_typed_over_in_one_go() -> None:
    app, suggester = _app(), FakeSuggester()
    session = _attached(app, suggester)
    _widget(app, "category").set_edit_text("tools")
    _next(app, session)  # on the amount
    _next(app, session)  # past it: 11.54 confirmed
    app._handle_input("previous_question")  # back to the amount
    session.wait()

    _widget(app, "amount").keypress((80,), "7")

    assert _widget(app, "amount").get_edit_text() == "7"


def test_an_answer_that_was_there_before_the_session_is_kept() -> None:
    # A receipt opened again for correction shows its label, not a guess.
    app = _app()
    _widget(app, "amount").set_edit_text("3.00")

    _attached(app, FakeSuggester())

    assert _widget(app, "amount").get_edit_text() == "3.00"


def test_a_suggestion_that_is_no_choice_is_skipped_for_the_next() -> None:
    class Elsewhere(FakeSuggester):
        def suggest(self, *, answers: Dict[str, Any]) -> Dict[str, Any]:
            suggestions = super().suggest(answers=answers)
            suggestions["address_selector"] = [
                _ai("Shop that is not in the list"),
                _ai(HARDWARE, 0.3),
            ]
            return suggestions

    app = _app()
    _attached(app, Elsewhere())

    assert _widget(app, "address_selector").get_answer() == HARDWARE


def test_a_guess_dropped_from_the_list_is_filled_in_again() -> None:
    # The category filters the shop list (a reconfiguration); the guessed
    # shop may fall out of it, and the next best one takes its place.
    app, suggester = _app(), FakeSuggester()
    session = _attached(app, suggester)
    address = _widget(app, "address_selector")
    assert address.get_answer() == BAKERY
    address.question_data.choices = ["manual address", HARDWARE]
    address.question_data.extra_data["shop_ids"] = [
        ShopId(name="manual address", address=Address()),
        _shop(HARDWARE),
    ]
    address.refresh_choices()  # what update_address_list() does
    assert not address.has_answer()

    _widget(app, "category").set_edit_text("tools")
    _next(app, session)

    assert address.get_answer() == HARDWARE


def test_a_focused_prefilled_choice_shows_the_list_to_choose_from() -> None:
    app, suggester = _app(), FakeSuggester()
    session = _attached(app, suggester)
    _widget(app, "category").set_edit_text("tools")
    _next(app, session)
    _next(app, session)  # on the address selector

    caption = _widget(app, "address_selector").caption

    assert BAKERY in caption and HARDWARE in caption


def test_the_withdrawal_toggle_is_set_to_the_suggested_answer() -> None:
    class Withdrawal(FakeSuggester):
        def suggest(self, *, answers: Dict[str, Any]) -> Dict[str, Any]:
            suggestions = super().suggest(answers=answers)
            suggestions["is_withdrawal"] = [_ai("y", 0.8), _ai("n", 0.2)]
            return suggestions

    app = _toggle_app()
    _attached(app, Withdrawal())
    toggle = _widget(app, "is_withdrawal")

    assert toggle.get_answer() == "y"
    # Enter keeps the suggested answer: the focus moved to it.
    assert toggle.keypress((80,), "enter") == "reconfigurer"
    assert toggle.get_answer() == "y"
    # Confidence and source stay in the AI panel, not behind the choices.
    assert b"ST-x" not in b"".join(toggle.render((80,)).text)


# ------------------------------------------------ "nothing" as an answer
#
# Most receipts print no subtotal; hledger-ai then suggests leaving the
# question empty (an empty suggestion), which is filled in like any other.


class SubtotalSuggester(FakeSuggester):
    """Says the receipt has no subtotal, unless the amount is 20.50."""

    def suggest(
        self, *, answers: Dict[str, Any]
    ) -> Dict[str, List[AISuggestion]]:
        suggestions = super().suggest(answers=answers)
        if answers.get("amount") == "20.5":
            suggestions["subtotal"] = [_ai("21.25", 0.7), _ai("", 0.3)]
        else:
            suggestions["subtotal"] = [_ai("", 0.8), _ai("12.79", 0.2)]
        return {k: v for k, v in suggestions.items() if k not in answers}


def _subtotal_app() -> QuestionnaireApp:
    questions = [
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
        InputValidationQuestionData(
            question="\nSubtotal (Optional, press enter to skip):\n",
            question_id="subtotal",
            input_type=InputType.FLOAT,
            ans_required=False,
            reconfigurer=False,
            terminator=False,
            ai_suggestions=[],
            history_suggestions=[],
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


def test_a_suggested_nothing_leaves_the_subtotal_empty() -> None:
    app = _subtotal_app()

    _attached(app, SubtotalSuggester())

    # Not the runner-up 12.79: "nothing" is the best guess.
    assert _widget(app, "subtotal").get_edit_text() == ""


def test_the_panel_calls_the_empty_suggestion_nothing() -> None:
    app, suggester = _subtotal_app(), SubtotalSuggester()
    session = _attached(app, suggester)
    _widget(app, "amount").set_edit_text("7.25")

    _next(app, session)  # on the subtotal

    assert "Alt+a  nothing (80%)" in _box(app)
    assert "Alt+b  12.79 (20%)" in _box(app)


def test_alt_a_takes_nothing_and_alt_b_the_amount() -> None:
    app, suggester = _subtotal_app(), SubtotalSuggester()
    session = _attached(app, suggester)
    _widget(app, "amount").set_edit_text("7.25")
    _next(app, session)
    subtotal = _widget(app, "subtotal")

    assert subtotal.keypress((80,), "meta b") == "next_question"
    assert subtotal.get_edit_text() == "12.79"
    assert subtotal.keypress((80,), "meta a") == "next_question"
    assert subtotal.get_edit_text() == ""


def test_moving_past_an_empty_subtotal_answers_it() -> None:
    app, suggester = _subtotal_app(), SubtotalSuggester()
    session = _attached(app, suggester)
    _widget(app, "amount").set_edit_text("7.25")
    _next(app, session)  # on the subtotal, left empty

    _next(app, session)  # Enter: no subtotal

    assert suggester.asked[-1] == {"amount": "7.25", "subtotal": ""}
    assert suggester.events[-2:] == [
        ("answered", "subtotal"),
        ("reached", "done"),
    ]


def test_an_answered_empty_subtotal_is_not_filled_in_later() -> None:
    app, suggester = _subtotal_app(), SubtotalSuggester()
    session = _attached(app, suggester)
    _widget(app, "amount").set_edit_text("7.25")
    _next(app, session)
    _next(app, session)  # past the subtotal: answered "nothing"

    # Back to the amount, corrected to 20.50: the model now expects a
    # subtotal, but the user already answered that question.
    app.set_focus(0)
    _widget(app, "amount").set_edit_text("20.50")
    session.confirm(tui=app, question_id="amount")
    session.refresh(tui=app)
    session.wait()

    assert _widget(app, "subtotal").get_edit_text() == ""


def test_an_untouched_nothing_follows_the_reranking() -> None:
    app, suggester = _subtotal_app(), SubtotalSuggester()
    session = _attached(app, suggester)
    _widget(app, "amount").set_edit_text("20.50")

    _next(app, session)  # the amount says there is a subtotal after all

    assert _widget(app, "subtotal").get_edit_text() == "21.25"


def test_a_required_question_never_takes_nothing() -> None:
    class EmptyAmount(FakeSuggester):
        def suggest(self, *, answers: Dict[str, Any]) -> Dict[str, Any]:
            suggestions = super().suggest(answers=answers)
            suggestions["amount"] = [_ai("", 0.6), _ai("4.10", 0.4)]
            return suggestions

    app = _subtotal_app()
    _attached(app, EmptyAmount())

    assert float(_widget(app, "amount").get_edit_text()) == 4.10


def test_finishing_reports_an_empty_subtotal_as_answered() -> None:
    app, suggester = _subtotal_app(), SubtotalSuggester()
    session = _attached(app, suggester)
    _widget(app, "amount").set_edit_text("7.25")

    session.finish(tui=app)

    assert suggester.finished == {"amount": "7.25", "subtotal": ""}
