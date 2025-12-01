from datetime import datetime
from typing import Dict, Union

from hledger_preprocessor.TransactionObjects.ExchangedItem import ExchangedItem
from typeguard import typechecked

from tui_labeller.tuis.urwid.date_question.DateTimeQuestion import (
    DateTimeQuestion,
)
from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.input_validation.InputValidationQuestion import (
    InputValidationQuestion,
)
from tui_labeller.tuis.urwid.multiple_choice_question.VerticalMultipleChoiceWidget import (
    VerticalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.question_data_classes import (
    AISuggestion,
    InputValidationQuestionData,
    VerticalMultipleChoiceQuestionData,
)


class ItemQuestionnaire:
    def __init__(
        self, item_type: str, parent_category: str, parent_date: datetime
    ):
        self.item_type = item_type
        self.parent_category = parent_category
        self.parent_date = parent_date
        self.questions = self.create_item_questions(
            item_type=item_type,
            parent_category=parent_category,
            parent_date=parent_date,
        )
        self.verify_unique_questions()

    def create_item_questions(
        self, item_type: str, parent_category: str, parent_date: datetime
    ):
        return [
            InputValidationQuestionData(
                question=f"Name/description (a-Z only): ",
                input_type=InputType.LETTERS,
                ans_required=True,
                ai_suggestions=[
                    AISuggestion("widget", 0.9, "ItemPredictor"),
                    AISuggestion("gadget", 0.85, "ItemPredictor"),
                ],
                history_suggestions=[],
            ),
            InputValidationQuestionData(
                question="Currency (e.g. EUR,BTC,$,YEN): ",
                input_type=InputType.LETTERS,
                ans_required=False,
                ai_suggestions=[
                    AISuggestion("USD", 0.90, "CurrencyNet"),
                    AISuggestion("EUR", 0.95, "CurrencyNet"),
                    AISuggestion("BTC", 0.85, "CurrencyNet"),
                ],
                history_suggestions=[],
            ),
            InputValidationQuestionData(
                question=f"Amount: ",
                input_type=InputType.FLOAT,
                ans_required=True,
                ai_suggestions=[
                    AISuggestion("1", 0.9, "QuantityAI"),
                    AISuggestion("2", 0.85, "QuantityAI"),
                    AISuggestion("1.83", 0.85, "QuantityAI"),
                ],
                history_suggestions=[],
            ),
            InputValidationQuestionData(
                question=f"Price for selected amount:",
                input_type=InputType.FLOAT,
                ans_required=True,
                ai_suggestions=[
                    AISuggestion("9.99", 0.9, "PricePredictor"),
                    AISuggestion("19.99", 0.85, "PricePredictor"),
                ],
                history_suggestions=[],
            ),
            InputValidationQuestionData(
                question=f"Category (empty is: {parent_category}): ",
                input_type=InputType.LETTERS,
                ans_required=True,
                ai_suggestions=[
                    AISuggestion("general", 0.8, "CategoryAI"),
                ],
                history_suggestions=[
                    AISuggestion(parent_category, 0.95, "CategoryAI"),
                ],
            ),
            InputValidationQuestionData(
                question="Tax for selected items (Optional):",
                input_type=InputType.FLOAT,
                ans_required=False,
                ai_suggestions=[
                    AISuggestion("0", 0.9, "TaxAI"),
                    AISuggestion("1.99", 0.7, "TaxAI"),
                ],
                history_suggestions=[],
            ),
            InputValidationQuestionData(
                question="Discount for selected items (Optional):",
                input_type=InputType.FLOAT,
                ans_required=False,
                ai_suggestions=[
                    AISuggestion("0", 0.9, "DiscountAI"),
                    AISuggestion("5.00", 0.7, "DiscountAI"),
                ],
                history_suggestions=[],
            ),
            VerticalMultipleChoiceQuestionData(
                question=f"Add another {item_type} item? (y/n): ",
                choices=["yes", "no"],
                nr_of_ans_per_batch=8,
                ai_suggestions=[],
                terminator=True,
            ),
        ]

    def verify_unique_questions(self) -> None:
        """Verifies all question questions/questions are unique, raises error
        if not."""
        seen = set()
        for q in self.questions:
            # Use question for InputValidationQuestionData, question for VerticalMultipleChoiceQuestionData
            question = getattr(q, "question", getattr(q, "question", None))
            if question is None:
                raise ValueError(
                    "Question object missing question or question attribute"
                )
            if question in seen:
                raise ValueError(
                    f"Duplicate question question found: '{question}'"
                )
            seen.add(question)


@typechecked
def get_exchanged_item(
    *,
    answers: Dict[
        Union[
            DateTimeQuestion,
            InputValidationQuestion,
            VerticalMultipleChoiceWidget,
        ],
        Union[str, float, int, datetime],
    ],
) -> ExchangedItem:
    """Constructs an ExchangedItem from questionnaire answers.

    Args:
        answers: Dictionary of answers from the questionnaire

    Returns:
        ExchangedItem: Constructed item based on the answers
    """
    # Find questions by question and extract answers
    description_q = next(
        q
        for q in answers.keys()
        if q.question == "Name/description (a-Z only): "
    )
    currency_q = next(
        q
        for q in answers.keys()
        if q.question == "Currency (e.g. EUR,BTC,$,YEN): "
    )
    amount_q = next(q for q in answers.keys() if q.question == "Amount: ")
    price_q = next(
        q for q in answers.keys() if q.question == "Price for selected amount:"
    )
    category_q = next(
        q for q in answers.keys() if "Category (empty is:" in q.question
    )
    tax_q = next(
        q
        for q in answers.keys()
        if q.question == "Tax for selected items (Optional):"
    )
    discount_q = next(
        q
        for q in answers.keys()
        if q.question == "Discount for selected items (Optional):"
    )

    description = answers[description_q]
    currency = answers[currency_q] if answers[currency_q] else None
    quantity = float(answers[amount_q])
    payed_unit_price = float(answers[price_q])
    category = (
        answers[category_q]
        if answers[category_q]
        else category_q.question.split("empty is: ")[1].rstrip("): ")
    )
    tax_per_unit = float(answers[tax_q]) if answers[tax_q] else 0
    group_discount = float(answers[discount_q]) if answers[discount_q] else 0

    return ExchangedItem(
        quantity=quantity,
        description=description,
        the_date=(
            answers[description_q].parent_date
            if hasattr(answers[description_q], "parent_date")
            else datetime.now()
        ),
        payed_unit_price=payed_unit_price,
        currency=currency,
        tax_per_unit=tax_per_unit,
        group_discount=group_discount,
        category=category,
        round_amount=None,
    )
