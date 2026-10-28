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
