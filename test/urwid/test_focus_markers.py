"""Focus markers: an invisible OSC string naming the focused question is
written to stdout whenever focus changes (opt-in via env var).

asciinema records these with exact timestamps; the hledger-preprocessor demo
harness derives receipt-highlight timing from them instead of guessing.
"""

import io

import urwid

from tui_labeller.tuis.urwid.focus_markers import (
    FOCUS_MARKER_ENV,
    format_focus_marker,
)
from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_data_classes import (
    InputValidationQuestionData,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp


def _q(qid: str) -> InputValidationQuestionData:
    return InputValidationQuestionData(
        question=f"{qid}:",
        question_id=qid,
        input_type=InputType.LETTERS,
        ans_required=False,
        reconfigurer=False,
        terminator=False,
        ai_suggestions=[],
        history_suggestions=[],
    )


def _app() -> QuestionnaireApp:
    app = QuestionnaireApp(
        header="h", questions=[_q("date"), _q("category")], labelled_receipts=[]
    )
    app.loop.screen = urwid.raw_display.Screen()
    return app


def test_marker_format() -> None:
    assert (
        format_focus_marker(question_id="date") == "\x1b]9999;hp-focus=date\x07"
    )


def test_markers_emitted_only_on_focus_change(monkeypatch) -> None:
    monkeypatch.setenv(FOCUS_MARKER_ENV, "1")
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    app = _app()
    app.set_focus(0)
    app._emit_focus_marker_if_changed()
    app._emit_focus_marker_if_changed()
    app.set_focus(1)
    app._emit_focus_marker_if_changed()
    assert (
        out.getvalue()
        == "\x1b]9999;hp-focus=date\x07\x1b]9999;hp-focus=category\x07"
    )


def test_draw_screen_hook_emits_marker(monkeypatch) -> None:
    monkeypatch.setenv(FOCUS_MARKER_ENV, "1")
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    app = _app()
    app.set_focus(1)
    monkeypatch.setattr(app.loop, "screen", urwid.raw_display.Screen())
    # draw_screen is wrapped; drawing to a non-started screen is a no-op in
    # urwid but our hook still runs after it.
    monkeypatch.setattr(type(app.loop), "_draw_for_test", None, raising=False)
    app._emit_focus_marker_if_changed()
    assert "hp-focus=category" in out.getvalue()
    assert app.loop.draw_screen.__name__ == "draw_and_mark"


def test_disabled_without_env(monkeypatch) -> None:
    monkeypatch.delenv(FOCUS_MARKER_ENV, raising=False)
    out = io.StringIO()
    monkeypatch.setattr("sys.stdout", out)
    app = _app()
    app.set_focus(1)
    app._emit_focus_marker_if_changed()
    assert out.getvalue() == ""
