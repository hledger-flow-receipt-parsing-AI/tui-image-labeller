from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_data_classes import (
    InputValidationQuestionData,
)


class CardPaymentQuestions:
    def __init__(
        self,
        receipt_owner_account_holder: str,
        receipt_owner_bank: str,
        receipt_owner_account_holder_type: str,
    ):
        self.questions = [
            InputValidationQuestionData(
                question="\nAmount paid by card:\n",
                input_type=InputType.FLOAT,
                ans_required=True,
                ai_suggestions=[],
                history_suggestions=[],
            ),
            InputValidationQuestionData(
                question="\nChange returned (card):\n",
                input_type=InputType.FLOAT,
                ans_required=True,
                ai_suggestions=[],
                history_suggestions=[],
            ),
            InputValidationQuestionData(
                question="\nAccount holder name:\n",
                input_type=InputType.LETTERS,
                ans_required=True,
                ai_suggestions=[],
                history_suggestions=[],
                default=receipt_owner_account_holder,
            ),
            InputValidationQuestionData(
                question="\nBank name (e.g., triodos, bitfavo):\n",
                input_type=InputType.LETTERS,
                ans_required=True,
                ai_suggestions=[],
                history_suggestions=[],
                default=receipt_owner_bank,
            ),
            InputValidationQuestionData(
                question="\nAccount type (e.g., checking, credit):\n",
                input_type=InputType.LETTERS,
                ans_required=True,
                ai_suggestions=[],
                history_suggestions=[],
                default=receipt_owner_account_holder_type,
            ),
            InputValidationQuestionData(
                question="\nShop account nr:\n",
                input_type=InputType.LETTERS,
                ans_required=False,
                ai_suggestions=[],
                history_suggestions=[],
                default=receipt_owner_account_holder,
            ),
        ]
