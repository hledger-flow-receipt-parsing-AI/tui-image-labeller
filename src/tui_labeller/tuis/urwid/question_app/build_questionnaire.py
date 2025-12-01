from typing import Dict, List, Union

import urwid
from typeguard import typechecked
from urwid import AttrMap, Pile

from tui_labeller.tuis.urwid.multiple_choice_question.HorizontalMultipleChoiceWidget import (
    HorizontalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.multiple_choice_question.VerticalMultipleChoiceWidget import (
    VerticalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.question_app.create_widgets import (
    create_question_widget,
)
from tui_labeller.tuis.urwid.question_data_classes import (
    DateQuestionData,
    HorizontalMultipleChoiceQuestionData,
    InputValidationQuestionData,
    VerticalMultipleChoiceQuestionData,
)


# Manual
@typechecked
def build_questionnaire(
    *,
    header: str,
    inputs: List[
        Union[
            VerticalMultipleChoiceWidget,
            HorizontalMultipleChoiceWidget,
            AttrMap,
        ]
    ],
    questions: List[
        Union[
            AttrMap,
            DateQuestionData,
            InputValidationQuestionData,
            VerticalMultipleChoiceQuestionData,
            HorizontalMultipleChoiceQuestionData,
        ]
    ],
    descriptor_col_width: int,
    pile: Pile,
    ai_suggestion_box: AttrMap,
    history_suggestion_box: AttrMap,
    error_display: AttrMap,
    history_store: Dict,
) -> None:
    # Manual
    """Build the complete questionnaire UI."""

    # pile.contents = [(Text(header), ("pack", None))]

    question_counts = {}  # Track duplicates
    for question in questions:
        base_id = question.question_id or question.question
        question_counts[base_id] = question_counts.get(base_id, 0) + 1
        if question_counts[base_id] > 1:
            question.question_id = (  # Append counter
                f"{base_id}_{question_counts[base_id]}"
            )

    pile_contents = [(urwid.Text(header), ("pack", None))]

    for i, question_data in enumerate(questions):
        widget: Union[
            VerticalMultipleChoiceWidget,
            HorizontalMultipleChoiceWidget,
            AttrMap,
        ] = create_question_widget(
            pile=pile,
            ai_suggestion_box=ai_suggestion_box,
            history_suggestion_box=history_suggestion_box,
            error_display=error_display,
            question_data=question_data,
            history_store=history_store,
            descriptor_col_width=descriptor_col_width,
        )
        inputs.append(widget)  # Add all widgets to inputs
        pile_contents.append((widget, ("pack", None)))

    pile.contents = pile_contents
