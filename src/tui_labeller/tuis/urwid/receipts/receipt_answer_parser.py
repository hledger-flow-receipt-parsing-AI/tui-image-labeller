from datetime import datetime
from typing import Dict, Union

from hledger_preprocessor.TransactionObjects.Receipt import Receipt
from typeguard import typechecked

from tui_labeller.target_objects import Receipt
from tui_labeller.tuis.urwid.date_question.DateTimeQuestion import (
    DateTimeQuestion,
)
from tui_labeller.tuis.urwid.input_validation.InputValidationQuestion import (
    InputValidationQuestion,
)
from tui_labeller.tuis.urwid.multiple_choice_question.VerticalMultipleChoiceWidget import (
    VerticalMultipleChoiceWidget,
)


@typechecked
def get_payment_details(
    *,
    answers: Dict[
        Union[
            DateTimeQuestion,
            InputValidationQuestion,
            VerticalMultipleChoiceWidget,
        ],
        Union[str, float, int, datetime],
    ],
) -> Receipt:
    owner_address_q = next(
        q
        for q in answers.keys()
        if q.question == "Receipt owner address (optional): "
    )
    shop_name_q = next(q for q in answers.keys() if q.question == "Shop name: ")
    shop_address_q = next(
        q for q in answers.keys() if q.question == "Shop address: "
    )
    subtotal_q = next(
        q
        for q in answers.keys()
        if q.question == "Subtotal (Optional, press enter to skip): "
    )
    total_tax_q = next(
        q
        for q in answers.keys()
        if q.question == "Total tax (Optional, press enter to skip): "
    )
    # payed_total_q = next(
    #     q for q in answers.keys() if q.question == "Payed total:"
    # )
    payed_total_q = 9001  # TODO: get from card and cash questions.
    payment_details = {
        "receipt_owner_address": (
            answers[owner_address_q] if answers[owner_address_q] else None
        ),
        "shop_name": answers[shop_name_q],
        "shop_address": answers[shop_address_q],
        "subtotal": float(answers[subtotal_q]) if answers[subtotal_q] else None,
        "total_tax": (
            float(answers[total_tax_q]) if answers[total_tax_q] else None
        ),
        "payed_total": float(answers[payed_total_q]),
    }

    try:
        cash_payed_q = next(
            q for q in answers.keys() if q.question == "Amount paid in cash: "
        )
        cash_returned_q = next(
            q
            for q in answers.keys()
            if q.question == "Change returned (cash): "
        )
        payment_details["cash_payed"] = float(answers[cash_payed_q])
        payment_details["cash_returned"] = float(answers[cash_returned_q])
    except StopIteration:
        pass

    try:
        card_payed_q = next(
            q for q in answers.keys() if q.question == "Amount paid by card: "
        )
        card_returned_q = next(
            q
            for q in answers.keys()
            if q.question == "Change returned (card): "
        )
        account_holder_q = next(
            q for q in answers.keys() if q.question == "Account holder name: "
        )
        bank_name_q = next(
            q
            for q in answers.keys()
            if q.question == "Bank name (e.g., triodos, bitfavo): "
        )
        account_type_q = next(
            q
            for q in answers.keys()
            if q.question == "Account type (e.g., checking, credit): "
        )
        payment_details.update(
            {
                "amount_payed_by_card": float(answers[card_payed_q]),
                "amount_returned_to_card": float(answers[card_returned_q]),
                "receipt_owner_account_holder": answers[account_holder_q],
                "receipt_owner_bank": answers[bank_name_q],
                "receipt_owner_account_holder_type": answers[account_type_q],
            }
        )
    except StopIteration:
        pass

    # return PaymentDetails(**payment_details)
    return Receipt(**payment_details)
