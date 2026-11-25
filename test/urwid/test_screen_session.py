"""One terminal screen for all the questionnaires of a receipt.

A reconfiguration (withdrawal yes/no, category, account, address) ends the
urwid loop and starts a new one with a rebuilt questionnaire. urwid stops
the screen when a loop ends and starts it again for the next, which used
to flip the terminal out of the TUI and back: the shell flashed through
between questions. Inside a session the screen stays up.
"""

from typing import List

from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_data_classes import (
    InputValidationQuestionData,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp
from tui_labeller.tuis.urwid.screen_session import (
    SharedScreen,
    current_screen,
    shared_screen,
)


def _recording(screen: SharedScreen) -> List[str]:
    """Record the terminal set-up and restore calls instead of doing them (the
    tests have no terminal)."""
    calls: List[str] = []
    screen._start = lambda *args, **kwargs: calls.append("start")
    screen._stop = lambda: calls.append("stop")
    return calls


def _questions() -> List[InputValidationQuestionData]:
    return [
        InputValidationQuestionData(
            question="Category:",
            question_id="category",
            input_type=InputType.CATEGORY,
            ans_required=True,
            reconfigurer=False,
            terminator=False,
            ai_suggestions=[],
            history_suggestions=[],
        )
    ]


def test_the_screen_stays_up_between_the_loops_of_one_session() -> None:
    with shared_screen() as screen:
        calls = _recording(screen)
        screen.start()  # the first questionnaire's loop
        screen.stop()  # it ends: a reconfiguration
        screen.start()  # the rebuilt questionnaire's loop
        screen.stop()

        assert calls == ["start"]

    assert calls == ["start", "stop"]  # restored when the receipt is done


def test_a_suspended_screen_really_stops_and_comes_back() -> None:
    # The matching CLI needs the plain terminal for input().
    with shared_screen() as screen:
        calls = _recording(screen)
        screen.start()

        screen.suspend()
        assert calls == ["start", "stop"]

        screen.resume()
        screen.stop()  # a later loop end: held again
        assert calls == ["start", "stop", "start"]


def test_questionnaires_built_in_a_session_share_its_screen() -> None:
    with shared_screen() as screen:
        first = QuestionnaireApp(
            header="h", questions=_questions(), labelled_receipts=[]
        )
        second = QuestionnaireApp(
            header="h", questions=_questions(), labelled_receipts=[]
        )

        assert first.loop.screen is screen
        assert second.loop.screen is screen

    assert current_screen() is None
    outside = QuestionnaireApp(
        header="h", questions=_questions(), labelled_receipts=[]
    )
    assert outside.loop.screen is not screen
