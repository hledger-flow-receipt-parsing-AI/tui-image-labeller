from typing import List, Optional

from hledger_preprocessor.config.load_config import Config
from hledger_preprocessor.TransactionObjects.ExchangedItem import ExchangedItem
from hledger_preprocessor.TransactionObjects.Receipt import Receipt
from typeguard import typechecked

from tui_labeller.tuis.urwid.receipts.AccountQuestions import AccountQuestions


def _get_exchanged_item(prefilled_receipt: Receipt) -> ExchangedItem:
    """Return the ExchangedItem holding account transactions.

    For normal receipts this is ``net_bought_items``; for withdrawal
    receipts (amount_paid=0, so not a "purchase") it is
    ``net_returned_items``.
    """
    item: Optional[ExchangedItem] = prefilled_receipt.net_bought_items
    if item is None:
        item = prefilled_receipt.net_returned_items
    if item is None:
        raise ValueError(
            "Receipt has neither net_bought_items nor net_returned_items"
        )
    return item


@typechecked
def generate_current_questions(
    *,
    config: Config,
    account_infos_str: List[str],
    accounts_without_csv: set[str],
    prefilled_receipt: Receipt,
) -> List[AccountQuestions]:
    account_questions_list = []

    net_bought_item: ExchangedItem = _get_exchanged_item(prefilled_receipt)

    for account_transaction in net_bought_item.account_transactions:
        new_account_questions = AccountQuestions(
            account_infos_str=account_infos_str,
            accounts_without_csv=accounts_without_csv,
        )
        # if transaction.account:
        account_str = (
            f"{account_transaction.account.bank or ''}:{account_transaction.account.account_holder or ''}"
        )

        # Validate account if it is a bank account and exists in account_infos
        # print(f'account_transaction={account_transaction}')
        # if has_input_csv(config=config, account=account_transaction.account):
        # # if (
        # #     account_transaction.account
        # #     and account_transaction.account.asset_type == "bank"
        # #     and account_transaction.account.bank
        # #     in account_infos_str  # TODO: if can switch comparison from HledgerFlowAccount to str.
        # # ):
        #     new_account_questions.validate_account(account_str)

        account_questions_list.append(new_account_questions)

    return account_questions_list


@typechecked
def get_number_of_account_transactions(*, prefilled_receipt: Receipt) -> int:
    count = 0
    net_bought_item: ExchangedItem = _get_exchanged_item(prefilled_receipt)
    for account_transaction in net_bought_item.account_transactions:
        count += 1
    return count
