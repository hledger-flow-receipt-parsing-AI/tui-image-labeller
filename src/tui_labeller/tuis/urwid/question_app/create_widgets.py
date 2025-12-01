from typing import Dict, Union

import urwid
from typeguard import typechecked
from urwid import AttrMap, Pile

from tui_labeller.tuis.urwid.date_question.DateTimeQuestion import (
    DateTimeQuestion,
)
from tui_labeller.tuis.urwid.input_validation.InputValidationQuestion import (
    InputValidationQuestion,
)
from tui_labeller.tuis.urwid.multiple_choice_question.HorizontalMultipleChoiceWidget import (
    HorizontalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.multiple_choice_question.VerticalMultipleChoiceWidget import (
    VerticalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.question_data_classes import (
    DateQuestionData,
    HorizontalMultipleChoiceQuestionData,
    InputValidationQuestionData,
    VerticalMultipleChoiceQuestionData,
)


# Manual
@typechecked
def create_question_widget(
    *,
    pile: Pile,
    ai_suggestion_box: AttrMap,
    history_suggestion_box: AttrMap,
    error_display: AttrMap,
    question_data: Union[
        DateQuestionData,
        InputValidationQuestionData,
        VerticalMultipleChoiceQuestionData,
        HorizontalMultipleChoiceQuestionData,
    ],
    history_store: Dict,
    descriptor_col_width: int,
) -> Union[
    VerticalMultipleChoiceWidget, HorizontalMultipleChoiceWidget, AttrMap
]:
    """Create appropriate widget based on question type."""
    if isinstance(question_data, DateQuestionData):
        widget = DateTimeQuestion(
            question_data=question_data,
            # date_only=question_data.date_only,
            # ai_suggestions=question_data.ai_suggestions,
            ai_suggestion_box=ai_suggestion_box,
            pile=pile,
        )
        widget.error_text = error_display
        attr_widget = urwid.AttrMap(widget, "normal")
        widget.owner = attr_widget
        return attr_widget

    elif isinstance(question_data, InputValidationQuestionData):
        widget = InputValidationQuestion(
            question_data=question_data,
            ai_suggestion_box=ai_suggestion_box,
            history_suggestion_box=history_suggestion_box,
            pile=pile,
            history_store=history_store,
        )
        if question_data.default is not None:
            widget.set_edit_text(question_data.default)
        attr_widget = urwid.AttrMap(widget, "normal")
        widget.owner = attr_widget
        return attr_widget

    elif isinstance(question_data, VerticalMultipleChoiceQuestionData):
        widget = VerticalMultipleChoiceWidget(
            question_data=question_data,
            ai_suggestions=question_data.ai_suggestions,
            ai_suggestion_box=ai_suggestion_box,
            history_suggestion_box=history_suggestion_box,
            pile=pile,
        )
        # if question_data.default is not None:
        #     widget.set_edit_text(question_data.default)
        attr_widget = urwid.AttrMap(widget, "normal")
        widget.owner = attr_widget
        return attr_widget
        # return VerticalMultipleChoiceWidget(
        #     question=question_data, ans_required=True
        # )
    elif isinstance(question_data, HorizontalMultipleChoiceQuestionData):
        widget = HorizontalMultipleChoiceWidget(
            question_data=question_data,
        )
        # if question_data.default is not None:
        #     widget.set_edit_text(question_data.default)
        # attr_widget = urwid.AttrMap(widget, "normal")
        # widget.owner = attr_widget
        return widget
    else:
        raise TypeError(f"Unexpected type:{type(question_data)}")
