from typing import List, Union

import urwid
from typeguard import typechecked

from tui_labeller.tuis.urwid.question_data_classes import (
    DateQuestionData,
    HorizontalMultipleChoiceQuestionData,
    InputValidationQuestionData,
    VerticalMultipleChoiceQuestionData,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp


@typechecked
def move_questions_to_end(
    *,
    app: QuestionnaireApp,
    questions_to_move: List[
        Union[
            DateQuestionData,
            InputValidationQuestionData,
            VerticalMultipleChoiceQuestionData,
            HorizontalMultipleChoiceQuestionData,
        ]
    ],
) -> None:
    """Move specified questions to the end of the QuestionnaireApp's question
    list and update the UI.

    Args:
        app: The running QuestionnaireApp instance to modify.
        questions_to_move: List of question data objects to move to the end.
    """
    # Remove questions from their current positions
    for q in questions_to_move:
        if q in app.questions:
            idx = app.questions.index(q)
            app.questions.pop(idx)
            app.inputs.pop(idx)

    # Append questions to the end
    app.questions.extend(questions_to_move)

    # Create new widgets for moved questions
    new_widgets = [
        app._create_question_widget(q, len(app.questions))
        for q in questions_to_move
    ]
    app.inputs.extend(new_widgets)

    # Update pile contents
    current_contents = app.pile.contents[: app.nr_of_headers]  # Keep header
    current_contents.extend((widget, ("pack", None)) for widget in app.inputs)
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

    # Refocus to the first moved question
    if new_widgets:
        app.pile.focus_position = (
            app.nr_of_headers + len(app.inputs) - len(new_widgets)
        )
