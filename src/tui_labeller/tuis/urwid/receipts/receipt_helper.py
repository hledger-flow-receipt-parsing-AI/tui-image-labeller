from typing import Any, List, Union

from typeguard import typechecked

from tui_labeller.tuis.urwid.question_data_classes import (
    AISuggestion,
    HistorySuggestion,
    InputValidationQuestionData,
)


@typechecked
def get_matching_unique_suggestions(
    suggestions: List[Union[AISuggestion, HistorySuggestion]],
    current_text: str,
    cursor_pos: int,
) -> List[str]:
    # Get the portion of text up to cursor position
    text_to_match = current_text[: cursor_pos + 1]

    # Filter suggestions that match up to the cursor position
    matching_suggestions = [
        suggestion.question
        for suggestion in suggestions
        if suggestion.question.startswith(text_to_match)
    ]
    # Preserve order, remove dupes.
    return list(dict.fromkeys(matching_suggestions))


@typechecked
def has_questions(
    *,
    expected_questions: List[InputValidationQuestionData],
    actual_questions: List[Any],
) -> bool:
    """Determine if questions of a specific payment type are present."""

    nr_of_matching_questions: int = nr_of_questions(
        expected_questions=expected_questions, actual_questions=actual_questions
    )

    if nr_of_matching_questions > 0:
        if nr_of_matching_questions != len(expected_questions):
            raise ValueError(
                "Either all or none of the questions must be present. Found"
                f" {nr_of_matching_questions} out of"
                f" {len(expected_questions)} questions."
            )
        return True
    return False


@typechecked
def nr_of_questions(
    expected_questions: List[InputValidationQuestionData],
    actual_questions: List[Any],
) -> int:
    """Count the number of questions of a specific payment type."""
    question_strings = [q.question for q in expected_questions]
    question_count = 0

    for tui_question in actual_questions:
        tui_text = getattr(
            tui_question, "question", getattr(tui_question, "caption", None)
        )
        if tui_text in question_strings:
            question_count += 1

    return question_count
