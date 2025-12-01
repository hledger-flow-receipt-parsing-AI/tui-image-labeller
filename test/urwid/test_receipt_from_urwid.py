from datetime import datetime
from pprint import pprint
from test.urwid.generate_tui import generate_test_tui
from typing import List, Tuple, Union

import pytest
import urwid
from hledger_preprocessor.receipt_transaction_matching.get_bank_data_from_transactions import (
    HledgerFlowAccountInfo,
)
from hledger_preprocessor.TransactionObjects.ExchangedItem import ExchangedItem
from hledger_preprocessor.TransactionObjects.Receipt import Receipt

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
from tui_labeller.tuis.urwid.question_app.get_answers import (
    get_answers,
    is_terminated,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp
from tui_labeller.tuis.urwid.receipts.create_receipt import (
    build_receipt_from_answers,
)


@pytest.fixture
def some_dict():
    account_info: HledgerFlowAccountInfo = HledgerFlowAccountInfo(
        account_holder="account_placeholder",
        bank="bank_placeholder",
        account_type="account_type_placeholder",
    )

    accounts_without_csv: set[str] = ["assets:gold", "assets:btc:2342323"]

    app: QuestionnaireApp = generate_test_tui(
        account_info=account_info,
        accounts_without_csv=accounts_without_csv,
    )
    app.loop.screen = urwid.raw_display.Screen()
    return {
        "app": app,
        "account_info": account_info,
        "accounts_without_csv": accounts_without_csv,
    }


def test_asset_selection(some_dict):
    """Test buying bananas from an account."""
    amount_payed: float = 54.23
    change_returned: float = 20.01
    app: QuestionnaireApp = some_dict["app"]
    account_info = some_dict["account_info"]
    accounts_without_csv = some_dict["accounts_without_csv"]

    # Set date
    the_question = app.inputs[0]
    the_question.keypress(1, "enter")
    print(f"\nthe_question={the_question.__dict__}")

    # Set boookkeeping category.
    the_question = app.inputs[
        1
    ]  # Assuming inputs[0] is the widget we’re testing
    for some_char in list("groceries:fruit:banananas"):
        the_question.keypress(1, some_char)

    print(f"\n bookkeeping category the_question={the_question.__dict__}")

    # Set account
    the_question = app.inputs[2]
    the_question.keypress(1, "1")
    the_question.keypress(1, "enter")
    print(f"\n account the_question={the_question.__dict__}")

    # Set currency
    the_question = app.inputs[3]
    the_question.keypress(1, "4")
    print(f"\n currencythe_question={the_question.__dict__}")

    # Set amount from
    the_question = app.inputs[4]
    for some_char in list(str(amount_payed)):
        the_question.keypress(1, some_char)
    print(f"\n amount from the_question={the_question.__dict__}")

    # Set amount refunded.
    the_question = app.inputs[5]
    for some_char in list(str(change_returned)):
        the_question.keypress(1, some_char)
    print(f"\n refund the_question={the_question.__dict__}")

    print(f"len={len(app.inputs)}")
    # Set add another account.
    the_question = app.inputs[6]
    print(f"\n add another account?the_question={the_question.__dict__}")
    the_question.keypress(1, "tab")
    the_question.keypress(1, "enter")

    print(f"len={len(app.inputs)}")
    the_question = app.inputs[7]
    print(f"\n new account?the_question={the_question.__dict__}")
    the_question.keypress(1, "tab")

    # Set question is done.
    the_question = app.inputs[
        15
    ]  # Assuming inputs[0] is the widget we’re testing
    the_question.keypress(1, "enter")
    print(f"\nthe_question={the_question.__dict__}")

    assert is_terminated(
        inputs=app.inputs
    ), "TUI did not reach terminated state"
    final_answers: List[
        Tuple[
            Union[
                DateTimeQuestion,
                InputValidationQuestion,
                VerticalMultipleChoiceWidget,
                HorizontalMultipleChoiceWidget,
            ],
            Union[str, float, int, datetime],
        ]
    ] = get_answers(inputs=app.inputs)
    receipt_obj: Receipt = build_receipt_from_answers(
        final_answers=final_answers,
        verbose=True,
        account_infos=[account_info],
        accounts_without_csv=accounts_without_csv,
    )
    print("\n\n\n")
    pprint(receipt_obj.__dict__)

    bought_item: ExchangedItem = receipt_obj.net_bought_items
    assert bought_item.account_transactions[0].amount_paid == amount_payed, (
        f"Expected amount_payed{amount_payed},"
        f" got:{bought_item.account_transactions[0].amount_paid}"
    )

    assert (
        bought_item.account_transactions[0].change_returned == change_returned
    ), (
        f"Expected change_returned{change_returned},"
        f" got:{bought_item.account_transactions[0].change_returned}"
    )


# TODO:
"""Test buying bananas from an account."""
"""Test buying bananas with cash and getting some money back."""
"""Test buying gold from an account."""
"""Test buying gold with bitcoin."""
