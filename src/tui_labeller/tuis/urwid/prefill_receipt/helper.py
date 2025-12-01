from typing import List

from hledger_preprocessor.config.load_config import Config
from hledger_preprocessor.TransactionObjects.ExchangedItem import ExchangedItem
from hledger_preprocessor.TransactionObjects.Receipt import Receipt
from typeguard import typechecked

from tui_labeller.tuis.urwid.receipts.AccountQuestions import AccountQuestions


@typechecked
def generate_current_questions(
    *,
    config: Config,
    account_infos_str: List[str],
    accounts_without_csv: set[str],
    prefilled_receipt: Receipt,
) -> List[AccountQuestions]:
    account_questions_list = []

    # for net_bought_item in prefilled_receipt.net_bought_items:
    net_bought_item: ExchangedItem = prefilled_receipt.net_bought_items
    # Create a new AccountQuestions object for each transaction

    # Set answers for the questions based on the transaction.

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
    net_bought_item: ExchangedItem = prefilled_receipt.net_bought_items
    # for net_bought_item in prefilled_receipt.net_bought_items:
    for account_transaction in net_bought_item.account_transactions:

        count += 1
    return count
