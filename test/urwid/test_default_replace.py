"""A prefilled default is replaced by the first typed character.

Before: the cursor sat at position 0 and typing "1.175" into a field holding
"1.0" produced "1.1751.0", which the TUI then silently reset to the default
(the US-2b.3 demo recorded exchange_rate 1.0 instead of 1.175).
"""

import urwid

from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_app.create_widgets import (
    create_question_widget,
)
from tui_labeller.tuis.urwid.question_data_classes import (
    InputValidationQuestionData,
)

SIZE = (80,)


def _make(default: str):
    data = InputValidationQuestionData(
        question="Exchange rate:",
        input_type=InputType.FLOAT,
        ans_required=True,
        reconfigurer=False,
        terminator=False,
        ai_suggestions=[],
        history_suggestions=[],
        default=default,
    )
    attr = create_question_widget(
        pile=urwid.Pile([]),
        ai_suggestion_box=urwid.AttrMap(urwid.Text(""), ""),
        history_suggestion_box=urwid.AttrMap(urwid.Text(""), ""),
        error_display=urwid.AttrMap(urwid.Pile([urwid.Text("")]), ""),
        question_data=data,
        history_store={},
        descriptor_col_width=20,
    )
    return attr.base_widget


def test_cursor_starts_at_end_of_default() -> None:
    assert _make("0.0").edit_pos == 3


def test_first_keystroke_replaces_untouched_default() -> None:
    w = _make("1.0")
    for ch in "1.175":
        w.keypress(SIZE, ch)
    assert w.edit_text == "1.175"


def test_editing_key_keeps_the_default() -> None:
    w = _make("1.0")
    w.keypress(SIZE, "left")
    w.keypress(SIZE, "5")
    assert w.edit_text == "1.50"


def test_untouched_default_is_still_the_answer() -> None:
    assert _make("0.0").get_answer() == 0.0


def test_restored_default_after_rebuild_is_still_replaced() -> None:
    """Reconfiguration rebuilds the questionnaire and restores the untouched
    default through set_answer(); the first keystroke must still replace it.

    (This is how the US-2b.3 demo ended up with exchange_rate 1.0: the
    injected "Exchange rate" field was rebuilt once more before the user
    typed, and "1.175" became "11.175.0".)
    """
    w = _make("1")
    w.set_answer(1.0)  # what set_default_focus_and_answers() does on rebuild
    assert w.edit_text == "1.0"
    for ch in "1.175":
        w.keypress(SIZE, ch)
    assert w.edit_text == "1.175"


def test_user_edit_survives_rebuild_restore() -> None:
    w = _make("1")
    w.keypress(SIZE, "2")  # user typed over the default
    assert w.edit_text == "2"
    w2 = _make("1")
    w2.question_data.user_edited = w.question_data.user_edited
    w2.set_answer(2.0)  # restored on rebuild
    w2.keypress(SIZE, "5")  # a further edit appends, nothing is wiped
    assert w2.edit_text == "2.05"
