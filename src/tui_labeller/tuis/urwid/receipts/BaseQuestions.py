from typing import Dict, List, Optional, Union

from typeguard import typechecked

from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_data_classes import (
    AISuggestion,
    DateQuestionData,
    HorizontalMultipleChoiceQuestionData,
    InputValidationQuestionData,
)


def validate_category(value: str) -> Optional[str]:
    """Validate the category input.

    Returns None if valid, or an error message string if invalid.
    """
    return None


class BaseQuestions:
    def __init__(
        self,
        ai_suggestions: Optional[Dict[str, List[AISuggestion]]] = None,
    ):
        self._ai = ai_suggestions or {}
        self.base_questions = self.create_base_questions()
        self.verify_unique_questions(self.base_questions)

    @typechecked
    def create_base_questions(
        self,
    ) -> List[
        Union[
            DateQuestionData,
            InputValidationQuestionData,
            HorizontalMultipleChoiceQuestionData,
        ]
    ]:
        return [
            self.create_date_question(),
            self.get_withdrawal_toggle(),
            self.get_category_question(),
        ]

    @typechecked
    def get_withdrawal_toggle(self) -> HorizontalMultipleChoiceQuestionData:
        return HorizontalMultipleChoiceQuestionData(
            question="Is this a withdrawal? (y/n)",
            choices=["n", "y"],
            ai_suggestions=[],
            ans_required=True,
            reconfigurer=True,
            terminator=False,
        )

    @typechecked
    def create_date_question(self) -> DateQuestionData:
        return DateQuestionData(
            question="Receipt date and time:\n",
            date_only=False,
            ai_suggestions=self._ai.get("receipt_date", []),
            ans_required=True,
            reconfigurer=False,
            terminator=False,
        )

    @typechecked
    def get_category_question(self) -> InputValidationQuestionData:
        return InputValidationQuestionData(
            question="\nBookkeeping expense category:",
            input_type=InputType.LETTERS_SEMICOLON,
            ai_suggestions=self._ai.get("category", []),
            history_suggestions=[],
            ans_required=True,
            reconfigurer=True,
            terminator=False,
            custom_validator=validate_category,
        )

    def verify_unique_questions(self, questions):
        seen = set()
        for q in questions:
            question = getattr(q, "question", getattr(q, "question", None))
            if question is None:
                raise ValueError("Question object missing question/question")
            if question in seen:
                raise ValueError(f"Duplicate question question: '{question}'")
            seen.add(question)

    def get_transaction_question_identifier(self) -> str:
        if not isinstance(self, BaseQuestions):
            raise TypeError(f"This {type(self)} is not a BaseQuestions object.")
        return self.base_questions[-1].question
