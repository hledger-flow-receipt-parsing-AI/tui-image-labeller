from pprint import pprint
from typing import List

import pytest
import urwid

from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp


@pytest.fixture
def app():
    app = QuestionnaireApp(header="some_header", questions=[])
    app.loop.screen = urwid.raw_display.Screen()
    return app


def assert_autocomplete_options(
    *, the_question, expected_options: List[str], step: str
):
    """Helper function to compare autocomplete options with expected list."""
    actual_widget = (
        the_question._original_widget.autocomplete_box.original_widget
    )
    actual_text = actual_widget.text
    actual_options = [opt.strip() for opt in actual_text.split(",")]
    actual_options.sort()
    expected_options_sorted = sorted(expected_options)
    assert actual_options == expected_options_sorted, (
        f"After '{step}', expected {expected_options_sorted}, got"
        f" '{actual_options}'"
    )
    pprint(f"Autocomplete text after '{step}': {actual_text}")


# Original test
def test_avocado_selection(app):
    the_question = app.inputs[0]
    the_question.keypress(1, "a")
    assert_autocomplete_options(
        the_question=the_question,
        expected_options=["avocado", "apple", "apricot"],
        step="a",
    )
    the_question.keypress(1, "*")
    assert_autocomplete_options(
        the_question=the_question,
        expected_options=["avocado", "apple", "apricot"],
        step="*",
    )
    the_question.keypress(1, "t")
    assert_autocomplete_options(
        the_question=the_question, expected_options=["apricot"], step="t"
    )


# New test cases
def test_case_sensitivity(app):
    the_question = app.inputs[0]
    the_question.keypress(1, "A")
    the_question.keypress(1, "*")
    the_question.keypress(1, "t")
    assert_autocomplete_options(
        the_question=the_question, expected_options=["apricot"], step="A*t"
    )


def test_multiple_matches_with_wildcard(app):
    the_question = app.inputs[0]
    the_question.keypress(1, "a")
    the_question.keypress(1, "*")
    the_question.keypress(1, "c")
    # Assuming the options list contains these test cases
    assert_autocomplete_options(
        the_question=the_question,
        expected_options=["avocado", "apricot"],
        step="a*c",
    )


def test_wildcard_at_start(app):
    the_question = app.inputs[0]
    the_question.keypress(1, "*")
    the_question.keypress(1, "c")
    the_question.keypress(1, "o")
    assert_autocomplete_options(
        the_question=the_question, expected_options=["apricot"], step="*co"
    )


def test_only_wildcard(app):
    the_question = app.inputs[0]
    the_question.keypress(1, "*")
    assert_autocomplete_options(
        the_question=the_question,
        expected_options=["apple", "apricot", "avocado"],
        step="*",
    )


def test_consecutive_wildcards(app):
    the_question = app.inputs[0]
    the_question.keypress(1, "a")
    the_question.keypress(1, "*")
    the_question.keypress(1, "*")
    the_question.keypress(1, "e")
    assert_autocomplete_options(
        the_question=the_question, expected_options=["apple"], step="a**e"
    )


def test_non_alphanumeric(app):
    the_question = app.inputs[0]
    the_question.keypress(1, "a")
    the_question.keypress(1, "*")
    the_question.keypress(1, "t")
    assert_autocomplete_options(
        the_question=the_question, expected_options=["apricot"], step="a*t"
    )
    the_question.keypress(1, "!")
    # ! is not a valid character, so one would nto expect it to be added.
    assert_autocomplete_options(
        the_question=the_question, expected_options=["apricot"], step="a*t!"
    )


def test_wildcard_at_end(app):
    the_question = app.inputs[0]
    the_question.keypress(1, "a")
    the_question.keypress(1, "p")
    the_question.keypress(1, "*")
    assert_autocomplete_options(
        the_question=the_question,
        expected_options=["apple", "apricot"],
        step="ap*",
    )


# Not supported.
# def test_multiple_wildcards_complex(app):
#     the_question = app.inputs[0]
#     the_question.keypress(1, "a")
#     the_question.keypress(1, "*")
#     the_question.keypress(1, "d")
#     the_question.keypress(1, "*")
#     the_question.keypress(1, "o")
#     assert_autocomplete_options(the_question=the_question, ["avocado", "ado"], step="a*d*o")


# TODO: determine why this test does not recognise the autocomplete field
# with initialised values but with an empty/default value.
# def test_empty_pattern(app):
#     the_question = app.inputs[0]
#     # No keypress, just initial state
#     assert_autocomplete_options(
#         the_question=the_question, expected_options=["apple", "apricot", "avocado"], step="entering nothing"
#     )
