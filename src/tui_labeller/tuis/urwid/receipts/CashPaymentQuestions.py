from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_data_classes import (
    InputValidationQuestionData,
)


class CashPaymentQuestions:
    def __init__(self):
        self.questions = [
            InputValidationQuestionData(
                question="\nAmount paid in cash:\n",
                input_type=InputType.FLOAT,
                ans_required=True,
                ai_suggestions=[],
                history_suggestions=[],
            ),
            InputValidationQuestionData(
                question="\nChange returned (cash):\n",
                input_type=InputType.FLOAT,
                ans_required=True,
                ai_suggestions=[],
                history_suggestions=[],
            ),
        ]
