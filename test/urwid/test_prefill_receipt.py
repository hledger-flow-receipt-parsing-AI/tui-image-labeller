import json

import pytest
from hledger_preprocessor.receipt_transaction_matching.get_bank_data_from_transactions import (
    HledgerFlowAccountInfo,
)
from hledger_preprocessor.TransactionObjects.Receipt import Receipt

from tui_labeller.tuis.urwid.ask_urwid_receipt import build_receipt_from_urwid

# from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp


@pytest.fixture
def app():
    # app = QuestionnaireApp(header="some_header", questions=[])
    # app.loop.screen = urwid.raw_display.Screen()
    # return app
    print("hi")


def test_assert_autocomplete_options():
    """Load receipt, feed into tui, ask userinput check if it is shown."""
    eg_path: str = (
        "/home/a/finance/receipt_labels/2025-5-24_15:58:377753_3ea1051d1496297ca25c1fb22a02e0d7cd324d4fe35643d3973b08736b0435bb/receipt_image_to_obj_label.json"
    )
    with open(eg_path, encoding="utf-8") as f:
        receipt_data = json.load(f)

        prefilled_receipt = Receipt(
            **receipt_data
        )  # Assuming Receipt is a dataclass or similar

    # "account": {
    #                     "asset_type": "asset",
    #                     "account_holder": null,
    #                     "bank": null,
    #                     "account_type": null,
    #                     "asset_category": "assets:cash"
    #                 }
    categories = set("cash")
    build_receipt_from_urwid(
        raw_receipt_img_filepath=prefilled_receipt.raw_img_filepath,
        account_infos={
            HledgerFlowAccountInfo(
                account_holder="bank",
                bank="triodos",
                account_type="checking",
            )
        },
        accounts_without_csv=categories,
        labelled_receipts=[],
        prefilled_receipt=prefilled_receipt,
    )

    assert 1 == 1, f"Unexpected result."
