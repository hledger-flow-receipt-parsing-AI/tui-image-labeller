from typing import Any, List, Tuple, Union

import urwid
from typeguard import typechecked

from tui_labeller.tuis.urwid.question_data_classes import (
    InputValidationQuestionData,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import (
    QuestionnaireApp,
)
from tui_labeller.tuis.urwid.receipts.AccountQuestions import AccountQuestions


@typechecked
def remove_later_account_questions(
    *,
    tui: "QuestionnaireApp",
    account_questions: "AccountQuestions",
    start_question_nr: int,
    preserved_answers: List[Union[None, Tuple[str, Any]]],
) -> List[Tuple[str, Any]]:
    """Remove account questions after the given question number, validate
    preserved answers, and update accordingly."""
    account_question_identifiers = get_account_question_identifiers(
        account_questions
    )
    validate_preserved_answers(tui, preserved_answers)
    updated_preserved, offset, non_account_question_found = process_questions(
        tui, account_question_identifiers, start_question_nr, preserved_answers
    )
    validate_final_state(tui, updated_preserved)
    update_remaining_answers(tui, updated_preserved)
    return preserved_answers


def update_remaining_answers(
    tui: "QuestionnaireApp",
    updated_preserved: List[Tuple[str, Any]],
) -> None:
    """Update answers for remaining questions."""
    for i, preserved_q_and_a in enumerate(updated_preserved):
        if preserved_q_and_a is not None:
            preserved_question, preserved_answer = preserved_q_and_a
            if (
                tui.inputs[i].base_widget.question_data.question
                != preserved_question
            ):
                raise ValueError(
                    "Mismatch in input questions and preserved answers."
                )
            tui.inputs[i].base_widget.set_answer(preserved_answer)


def validate_final_state(
    tui: "QuestionnaireApp",
    updated_preserved: List[Tuple[str, Any]],
) -> None:
    """Validate that the number of remaining questions matches preserved
    answers."""
    if len(tui.inputs) != len(updated_preserved):
        raise ValueError(
            f"Length mismatch: {len(tui.inputs)} remaining questions "
            f"vs {len(updated_preserved)} preserved items"
        )


def get_account_question_identifiers(
    account_questions: "AccountQuestions",
) -> set:
    """Extract identifiers for account questions."""
    return {q.question for q in account_questions.account_questions}


def validate_preserved_answers(
    tui: "QuestionnaireApp",
    preserved_answers: List[Union[None, Tuple[str, Any]]],
) -> None:
    """Validate preserved answers against current questions."""
    current_questions = tui.questions
    for idx, preserved_q_and_a in enumerate(preserved_answers):
        if preserved_q_and_a is not None:
            preserved_question, _ = preserved_q_and_a
            if (
                idx < len(current_questions)
                and preserved_question != current_questions[idx].question
            ):
                raise ValueError(
                    f"Preserved answer at index {idx} has question "
                    f"'{preserved_question}' but expected "
                    f"'{current_questions[idx].question}'"
                )


@typechecked
def remove_specific_questions_from_list(
    *,
    app: QuestionnaireApp,
    expected_questions: List[InputValidationQuestionData],
) -> None:
    """Remove specific questions from the QuestionnaireApp's question list that
    match the expected_questions, and update the UI accordingly.

    Args:
        app: The running QuestionnaireApp instance to modify.
        expected_questions: List of questions to remove if found in app.questions.

    Raises:
        ValueError: If expected_questions is empty.
    """
    if not expected_questions:
        raise ValueError("expected_questions list cannot be empty")

    # Get the question strings to match against
    question_strings = [q.question for q in expected_questions]
    if not question_strings:
        return  # No questions to remove

    # Create new lists excluding the matching questions
    new_questions = []
    new_inputs = []
    indices_to_remove = set()

    # Identify indices of questions to remove
    for i, (question, widget) in enumerate(zip(app.questions, app.inputs)):
        question_text = getattr(
            question, "question", getattr(question, "caption", None)
        )
        if question_text in question_strings:
            indices_to_remove.add(i)
        else:
            new_questions.append(question)
            new_inputs.append(widget)

    if not indices_to_remove:
        return  # No matching questions found to remove

    # Update the app's lists
    app.questions = new_questions
    app.inputs = new_inputs

    # Update pile contents: preserve header, use updated inputs list
    current_contents = app.pile.contents[: app.nr_of_headers]  # Keep header
    current_contents.extend((widget, ("pack", None)) for widget in app.inputs)

    # Re-append suggestion boxes
    current_contents.extend(
        [
            (urwid.Divider(), ("pack", None)),
            (
                urwid.Columns(
                    [
                        (
                            app.descriptor_col_width,
                            urwid.Text("AI suggestions: "),
                        ),
                        app.ai_suggestion_box,
                    ]
                ),
                ("pack", None),
            ),
            (
                urwid.Columns(
                    [
                        (
                            app.descriptor_col_width,
                            urwid.Text("History suggestions: "),
                        ),
                        app.history_suggestion_box,
                    ]
                ),
                ("pack", None),
            ),
        ]
    )
    app.pile.contents = current_contents

    # Adjust focus position if necessary
    if app.inputs:
        app.pile.focus_position = min(
            app.pile.focus_position,
            len(current_contents) - 1,  # Account for suggestion boxes
        )
    elif current_contents:
        app.pile.focus_position = 0  # Focus on header if no inputs remain


def process_questions(
    tui: "QuestionnaireApp",
    account_question_identifiers: set,
    start_question_nr: int,
    preserved_answers: List[Union[None, Tuple[str, Any]]],
) -> Tuple[List[Tuple[str, Any]], int, bool]:
    """Process questions to remove account questions after
    start_question_nr."""
    updated_preserved = preserved_answers.copy()
    non_account_question_found = False
    offset = 0
    original_inputs = tui.inputs.copy()

    for i, input_widget in enumerate(original_inputs):
        widget = input_widget.base_widget
        question_text = widget.question_data.question

        if i > start_question_nr:
            if question_text not in account_question_identifiers:
                non_account_question_found = True
            else:
                if non_account_question_found:
                    raise ValueError(
                        f"Account question '{question_text}' found "
                        f"after a non-account question at index {i}"
                    )
                if updated_preserved[i - offset] is not None:
                    if question_text != updated_preserved[i - offset][0]:
                        raise ValueError(
                            f"updated_preserved[{i - offset}][0] answer at"
                            f" i={i}, offset={offset} has question"
                            f" '{updated_preserved[i - offset][0]}' but"
                            f" expected '{question_text}'"
                        )

                updated_preserved.pop(i - offset)
                tui.inputs.pop(i - offset)
                offset += 1

    return updated_preserved, offset, non_account_question_found
