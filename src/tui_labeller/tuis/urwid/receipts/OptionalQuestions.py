from typing import List, Optional

import urwid
from hledger_preprocessor.TransactionObjects.Receipt import Receipt
from hledger_preprocessor.TransactionObjects.ShopId import ShopId
from typeguard import typechecked

from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_app.addresses.update_addresses import (
    get_initial_complete_list,
)
from tui_labeller.tuis.urwid.question_data_classes import (
    HorizontalMultipleChoiceQuestionData,
    InputValidationQuestionData,
    VerticalMultipleChoiceQuestionData,
)


class OptionalQuestions:
    def __init__(
        self,
        labelled_receipts: List[Receipt],
        category: Optional[str] = None,
    ):
        self.labelled_receipts = labelled_receipts
        self.category = category
        self.optional_questions = self.create_base_questions(
            labelled_receipts=labelled_receipts, category=category
        )
        self.verify_unique_questions(self.optional_questions)

    def create_base_questions(
        self, labelled_receipts: List[Receipt], category: Optional[str] = None
    ):
        # Get filtered shop IDs based on category
        choices, shop_ids = get_initial_complete_list(
            labelled_receipts=labelled_receipts, category_input=category
        )

        # Base questions excluding manual address questions
        return [
            VerticalMultipleChoiceQuestionData(
                question="Select Shop Address:\n",
                choices=choices,
                nr_of_ans_per_batch=8,
                ans_required=True,
                reconfigurer=True,
                terminator=False,
                ai_suggestions=[],
                question_id="address_selector",
                navigation_display=urwid.AttrMap(
                    urwid.Pile(
                        [
                            urwid.Text(("navigation", "Navigation")),
                            urwid.Text("Q          - quit"),
                            urwid.Text(
                                "\n<- Left, Right -> - Show next batch of"
                                " answers."
                            ),
                            urwid.Text(
                                "\nType a number to select that answer."
                            ),
                            urwid.Text(
                                "\nEnter confirm choice, goto next question."
                            ),
                        ]
                    ),
                    "normal",
                ),
                extra_data={"shop_ids": shop_ids},
            ),
            InputValidationQuestionData(
                question="\nSubtotal (Optional, press enter to skip):\n",
                input_type=InputType.FLOAT,
                ai_suggestions=[],
                history_suggestions=[],
                ans_required=False,
                reconfigurer=False,
                terminator=False,
            ),
            InputValidationQuestionData(
                question="\nTotal tax (Optional, press enter to skip):\n",
                input_type=InputType.FLOAT,
                ai_suggestions=[],
                history_suggestions=[],
                ans_required=False,
                reconfigurer=False,
                terminator=False,
            ),
            HorizontalMultipleChoiceQuestionData(
                question="\nDone with this receipt?",
                choices=["yes"],
                ai_suggestions=[],
                ans_required=True,
                reconfigurer=False,
                terminator=True,
            ),
        ]

    @typechecked
    def _is_shop_in_category(self, shop: ShopId, category: str) -> bool:
        # Placeholder method to check if a shop belongs to a category
        return True

    def verify_unique_questions(self, questions):
        seen = set()
        for q in questions:
            question = getattr(q, "question", None)
            if question is None:
                raise ValueError("Question object missing question attribute")
            if question in seen:
                raise ValueError(f"Duplicate question: '{question}'")
            seen.add(question)

    def get_is_done_question_identifier(self) -> str:
        return self.optional_questions[-1].question

    def get_manual_address_questions(self) -> List[InputValidationQuestionData]:
        """Returns the manual address entry questions."""
        return [
            InputValidationQuestionData(
                question="\nShop name:\n",
                input_type=InputType.LETTERS,
                ai_suggestions=[],
                history_suggestions=[],
                ans_required=False,
                reconfigurer=False,
                terminator=False,
                question_id="shop_name",
            ),
            InputValidationQuestionData(
                question="Shop street:",
                input_type=InputType.LETTERS_AND_SPACE,
                ai_suggestions=[],
                history_suggestions=[],
                ans_required=False,
                reconfigurer=False,
                terminator=False,
                question_id="shop_street",
            ),
            InputValidationQuestionData(
                question="Shop house nr.:",
                input_type=InputType.LETTERS_AND_NRS,
                ai_suggestions=[],
                history_suggestions=[],
                ans_required=False,
                reconfigurer=False,
                terminator=False,
                question_id="shop_house_nr",
            ),
            InputValidationQuestionData(
                question="Shop zipcode:",
                input_type=InputType.LETTERS_AND_NRS,
                ai_suggestions=[],
                history_suggestions=[],
                ans_required=False,
                reconfigurer=False,
                terminator=False,
                question_id="shop_zipcode",
            ),
            InputValidationQuestionData(
                question="Shop City:",
                input_type=InputType.LETTERS,
                ai_suggestions=[],
                history_suggestions=[],
                ans_required=False,
                reconfigurer=False,
                terminator=False,
                question_id="shop_city",
            ),
            InputValidationQuestionData(
                question="Shop country:",
                input_type=InputType.LETTERS,
                ai_suggestions=[],
                history_suggestions=[],
                ans_required=False,
                reconfigurer=False,
                terminator=False,
                question_id="shop_country",
            ),
        ]
