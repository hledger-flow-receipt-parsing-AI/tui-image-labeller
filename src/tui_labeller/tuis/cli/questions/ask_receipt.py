from datetime import datetime
from typing import List, Union

from hledger_preprocessor.TransactionObjects.Receipt import Receipt
from typeguard import typechecked

from tui_labeller.input_parser.input_parser import (
    ask_yn_question_is_yes,
    get_date_input,
    get_float_input,
    get_input_with_az_chars_answer,
)


@typechecked
def build_receipt_from_cli(
    *,
    receipt_owner_account_holder: str,
    receipt_owner_bank: str,
    receipt_owner_account_holder_type: str,
):
    receipt_date = get_date_input(
        question="Receipt date (YYYY-MM-DD): ", allow_optional=False
    )
    receipt_categorisation: str = "swag:something"
    bought_items = get_items(
        item_type="bought",
        parent_category=receipt_categorisation,
        parent_date=datetime.now(),
    )
    returned_items = get_items(
        item_type="returned",
        parent_category=receipt_categorisation,
        parent_date=datetime.now(),
    )

    shop_account_nr: Union[None, str] = get_input_with_az_chars_answer(
        question=f"Shop account number (Optional, press enter to skip):",
        allowed_empty=True,
        allowed_chars=r"[a-zA-Z0-9:]+",
    )
    subtotal = get_float_input(
        question="Subtotal (Optional, press enter to skip): ",
        allow_optional=True,
    )
    total_tax = get_float_input(
        question="Total tax (Optional, press enter to skip): ",
        allow_optional=True,
    )

    receipt_owner_address = input("Receipt owner address (optional): ") or None

    shop_name: str = input(
        "Shop name: "
    )  # TODO: assert it does not have spaces, newlines or tabs.
    shop_address = input("Shop address: ")

    payed_with_cash: bool = ask_yn_question_is_yes(
        question="Did you pay with cash or receive cash? (y/n): "
    )
    cash_payed = False
    cash_returned = None

    # TODO: facilitate cash and wire transactions.
    if payed_with_cash:
        cash_payed = get_float_input(
            question="Amount paid in cash: ", allow_optional=False
        )
        cash_returned = get_float_input(
            question="Change returned: ", allow_optional=False
        )

    payed_by_card: bool = ask_yn_question_is_yes(
        question="Did you pay by card? (y/n): "
    )

    if payed_by_card:
        amount_payed_by_card = get_float_input(
            question="Amount paid by card: ", allow_optional=False
        )
        amount_returned_to_card = get_float_input(
            question="Change returned: ", allow_optional=False
        )

        # Get card details.
        payed_from_default_account: bool = ask_yn_question_is_yes(
            question=(
                "Was the receipt payed"
                f" from:\n{receipt_owner_account_holder}:{receipt_owner_bank}:{receipt_owner_account_holder_type}\n?(y/n)"
            )
        )
        if not payed_from_default_account:
            receipt_owner_account_holder = (
                get_input_with_az_chars_answer(
                    question=input(
                        "What is your name/the name of the account doing the"
                        " transaction?"
                    ),
                    allowed_empty=False,
                ),
            )
            receipt_owner_bank = (
                get_input_with_az_chars_answer(
                    question=input(
                        "What is the bank associated with the account? (E.g."
                        " triodos, bitfavo, uniswap, monero for bank, exchange,"
                        " dex, wallet respectively)"
                    ),
                    allowed_empty=False,
                ),
            )
            receipt_owner_account_holder_type = (
                get_input_with_az_chars_answer(
                    question=input(
                        "What type of account was used (e.g., checking, credit,"
                        " saving)?"
                    ),
                    allowed_empty=False,
                ),
            )
        # TODO: get to account/shop account.

    receipt_categorisation: str = get_input_with_az_chars_answer(
        question=f"Receipt category:",
        allowed_empty=False,
        allowed_chars=r"[a-zA-Z:]+",
    )

    payed_total_read: float = get_float_input(
        question="Payed total:", allow_optional=False
    )
    return Receipt(
        shop_name=shop_name,
        receipt_owner_account_holder=receipt_owner_account_holder,
        receipt_owner_bank=receipt_owner_bank,
        receipt_owner_account_holder_type=receipt_owner_account_holder_type,
        bought_items=bought_items,
        returned_items=returned_items,
        the_date=receipt_date,
        payed_total_read=payed_total_read,
        shop_address=shop_address,
        shop_account_nr=shop_account_nr,
        subtotal=subtotal,
        total_tax=total_tax,
        cash_payed=cash_payed,
        cash_returned=cash_returned,
        receipt_owner_address=receipt_owner_address,
        receipt_categorisation=receipt_categorisation,
    )


@typechecked
def get_items(
    *, item_type: str, parent_category: str, parent_date: datetime
) -> List[ExchangedItem]:
    items = []
    while True:
        add_another: bool = ask_yn_question_is_yes(
            question=f"Add another {item_type} item? (y/n):"
        )
        if not add_another:
            break
        name: str = get_input_with_az_chars_answer(
            question=f"{item_type} item name (a-Z only): ",
            allowed_empty=False,
            allowed_chars=r"[a-zA-Z:]+",
        )
        currency: str = input(f"Give price currency, e.g. EUR,BTC,$,YEN etc.")
        quantity: float = get_float_input(
            question=f"{item_type} item quantity: ", allow_optional=False
        )
        payed_unit_price: float = get_float_input(
            question=f"{item_type} item price: ", allow_optional=False
        )

        # category = input(f"{item_type} item category (optional): ") or None
        category: str = get_input_with_az_chars_answer(
            question=(
                f"{item_type} item category (empty is: {parent_category})): "
            ),
            allowed_empty=True,
            allowed_chars=r"[a-zA-Z:]+",
        )
        tax_per_unit: Union[None, float] = get_float_input(
            question="Tax per item (Optional, press enter to set to 0.): ",
            allow_optional=True,
        )

        group_discount: Union[None, float] = get_float_input(
            question=(
                "Total discount for this group of items (Optional, press"
                " enter to set to 0): "
            ),
            allow_optional=True,
        )
        items.append(
            ExchangedItem(
                quantity=quantity,
                description=name,
                the_date=parent_date,
                payed_unit_price=payed_unit_price,
                currency=currency,
                tax_per_unit=tax_per_unit if tax_per_unit else 0,
                group_discount=group_discount if group_discount else 0,
                category=category if category else parent_category,
                round_amount=None,
            )
        )
    return items
