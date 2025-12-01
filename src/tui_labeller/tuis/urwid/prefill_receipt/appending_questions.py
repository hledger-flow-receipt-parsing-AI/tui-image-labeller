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
def append_questions_to_list(
    *,
    app: QuestionnaireApp,
    new_questions: List[
        Union[
            DateQuestionData,
            InputValidationQuestionData,
            VerticalMultipleChoiceQuestionData,
            HorizontalMultipleChoiceQuestionData,
        ]
    ],
) -> None:
    """Append new questions to the existing QuestionnaireApp's question list
    and update the UI.

    Args:
        app: The running QuestionnaireApp instance to modify.
        new_questions: List of new question data objects to append.
    """
    # Verify no duplicate captions/questions with existing ones
    existing_captions = {
        getattr(q, "question", getattr(q, "caption", None))
        for q in app.questions
    }
    for q in new_questions:
        caption = getattr(q, "question", getattr(q, "caption", None))
        if caption in existing_captions:
            raise ValueError(
                f"Duplicate question caption/question: '{caption}'"
            )
        existing_captions.add(caption)

    # Append new questions to the list
    app.questions.extend(new_questions)

    # Create widgets for new questions
    new_widgets = [
        app._create_question_widget(q, len(app.questions))
        for q in new_questions
    ]
    app.inputs.extend(new_widgets)

    # Update pile contents: preserve existing, append new widgets
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

    # Optionally refocus to the first new question
    if new_widgets:
        app.pile.focus_position = (
            app.nr_of_headers + len(app.inputs) - len(new_widgets)
        )
