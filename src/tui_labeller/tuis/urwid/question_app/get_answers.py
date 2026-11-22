from datetime import datetime
from typing import Dict, List, Tuple, Union

from typeguard import typechecked
from urwid import AttrMap

from tui_labeller.tuis.urwid.date_question.DateTimeQuestion import (
    DateTimeQuestion,
)
from tui_labeller.tuis.urwid.input_validation.InputValidationQuestion import (
    InputValidationQuestion,
)
from tui_labeller.tuis.urwid.multiple_choice_question.HorizontalMultipleChoiceWidget import (  # noqa: E501
    HorizontalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.multiple_choice_question.VerticalMultipleChoiceWidget import (  # noqa: E501
    VerticalMultipleChoiceWidget,
)


@typechecked
def is_terminated(
    inputs: List[
        Union[
            VerticalMultipleChoiceWidget,
            HorizontalMultipleChoiceWidget,
            AttrMap,
        ]
    ],
) -> bool:
    for i, input_widget in enumerate(inputs):
        widget = input_widget.base_widget
        if isinstance(widget, VerticalMultipleChoiceWidget) or isinstance(
            widget, HorizontalMultipleChoiceWidget
        ):
            if widget.question_data.terminator:
                if widget.has_answer():
                    answer = widget.get_answer()
                    if answer:
                        return True
    return False


# Questions that steer the questionnaire instead of describing the receipt.
FLOW_QUESTION_IDS = ("match_choice",)


@typechecked
def get_answers_so_far(
    *,
    inputs: List[
        Union[
            VerticalMultipleChoiceWidget,
            HorizontalMultipleChoiceWidget,
            AttrMap,
        ]
    ],
) -> Dict[str, str]:
    """The answers given up to now, as text, keyed by question id.

    Unlike get_answers() this never fails on an unanswered question: it
    is used when a receipt is abandoned halfway ("This receipt is not
    mine") and whatever was typed is kept as a partial label.
    """
    answers: Dict[str, str] = {}
    for input_widget in inputs:
        widget = input_widget.base_widget
        question_data = getattr(widget, "question_data", None)
        if question_data is None or question_data.terminator:
            continue
        question_id = question_data.question_id or question_data.question
        if question_id in FLOW_QUESTION_IDS:
            continue
        try:
            if not widget.has_answer():
                continue
            answer = widget.get_answer()
        except (ValueError, IndexError):
            continue
        if answer is None or answer == "":
            continue
        answers[question_id.strip()] = (
            answer.isoformat(sep=" ")
            if isinstance(answer, datetime)
            else str(answer)
        )
    return answers


@typechecked
def get_answers(
    *,
    inputs: List[
        Union[
            VerticalMultipleChoiceWidget,
            HorizontalMultipleChoiceWidget,
            AttrMap,
        ]
    ],
) -> List[
    Tuple[
        Union[
            DateTimeQuestion,
            InputValidationQuestion,
            VerticalMultipleChoiceWidget,
            HorizontalMultipleChoiceWidget,
        ],
        Union[str, float, int, datetime],
    ]
]:
    """Collects answers from all questions in the questionnaire.

    Returns:
        Dict[str, Union[str, float, int, datetime]]: A dictionary mapping question captions  # noqa: E501
            to their answers. Answer types depend on question type:
            - DateTimeQuestion: datetime
            - InputValidationQuestion: str, float, or int
            - VerticalMultipleChoiceWidget: str

    Raises:
        ValueError: If any question's answer cannot be retrieved or validated
    """

    results_list: List[
        Tuple[
            Union[
                DateTimeQuestion,
                InputValidationQuestion,
                VerticalMultipleChoiceWidget,
                HorizontalMultipleChoiceWidget,
            ],
            Union[str, float, int, datetime],
        ]
    ] = [] * len(inputs)

    for i, input_widget in enumerate(inputs):

        widget = input_widget.base_widget
        if isinstance(widget, DateTimeQuestion):
            answer = widget.get_answer()
            # results[widget] = answer

        elif isinstance(widget, InputValidationQuestion):
            answer = widget.get_answer()
            # results[widget] = answer

        elif isinstance(
            widget,
            (VerticalMultipleChoiceWidget, HorizontalMultipleChoiceWidget),
        ):
            if widget.has_answer():
                answer = widget.get_answer()
            elif widget.question_data.ans_required:
                # Name the question instead of crashing with int('') deep
                # inside the widget.
                raise ValueError(
                    "No answer selected for required question"
                    f" '{widget.question_data.question.strip()}'"
                )
            else:
                answer = ""

        else:
            raise ValueError(
                f"Unknown widget type at index {i}: {type(widget)}"
            )
        results_list.append((widget, answer))
        results_list[i] = (widget, answer)
    return results_list
