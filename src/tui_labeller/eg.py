import json
from copy import deepcopy
from pprint import pprint

from hledger_preprocessor.load_config import Config, load_config
from hledger_preprocessor.management.get_all_hledger_flow_accounts import (
    get_all_accounts,
)
from hledger_preprocessor.receipt_transaction_matching.get_bank_data_from_transactions import (
    HledgerFlowAccountInfo,
)

# from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp
from hledger_preprocessor.receipts_to_objects.get_asset_categories import (
    get_hledger_pure_accounts_without_csv,
)
from hledger_preprocessor.TransactionObjects.AccountTransaction import (
    AccountTransaction,
)
from hledger_preprocessor.TransactionObjects.Receipt import Receipt

from tui_labeller.tuis.urwid.ask_urwid_receipt import build_receipt_from_urwid


def pre_fill():
    """Load receipt, feed into tui, ask userinput check if it is shown."""
    eg_path: str = (
        "/home/a/finance/receipt_labels/2025-5-24_15:58:377753_3ea1051d1496297ca25c1fb22a02e0d7cd324d4fe35643d3973b08736b0435bb/receipt_image_to_obj_label.json"
    )
    with open(eg_path, encoding="utf-8") as f:
        receipt_data = json.load(f)

        prefilled_receipt = Receipt(
            **receipt_data
        )  # Assuming Receipt is a dataclass or similar
    prefilled_receipt.subtotal = 0.3
    prefilled_receipt.total_tax = 0.4

    if True:
        some_transaction: AccountTransaction = deepcopy(
            prefilled_receipt.net_bought_items.account_transactions[0]
        )
        some_transaction.amount_paid = 10
        prefilled_receipt.net_bought_items.account_transactions.append(
            some_transaction
        )

    pprint(prefilled_receipt)

    config: Config = load_config(
        config_path="/home/a/finance/config.yaml",
        pre_processed_output_dir="/some/",
    )
    hledger_account_infos: set[HledgerFlowAccountInfo] = get_all_accounts(
        config=config
    )
    accounts_without_csv: set[str] = get_hledger_pure_accounts_without_csv()

    build_receipt_from_urwid(
        raw_receipt_img_filepath=prefilled_receipt.raw_img_filepath,
        hledger_account_infos=hledger_account_infos,
        accounts_without_csv=accounts_without_csv,
        labelled_receipts=[],
        prefilled_receipt=prefilled_receipt,
    )

    assert 1 == 1, f"Unexpected result."


pre_fill()
