from datetime import datetime
from typing import List, Tuple, Union

from hledger_preprocessor.config.AccountConfig import AccountConfig
from hledger_preprocessor.config.load_config import Config
from hledger_preprocessor.Currency import Currency
from hledger_preprocessor.receipt_transaction_matching.get_bank_data_from_transactions import (
    HledgerFlowAccountInfo,
)
from hledger_preprocessor.TransactionObjects.Account import Account
from hledger_preprocessor.TransactionObjects.AccountTransaction import (
    AccountTransaction,
)
from hledger_preprocessor.TransactionObjects.ExchangedItem import ExchangedItem
from typeguard import typechecked

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


@typechecked
def parse_account_string(
    *,
    config: Config,
    currency: Currency,
    input_string: str,
    # hledger_account_infos: set[HledgerFlowAccountInfo],
    # accounts_without_csv: set[str],
) -> Account:
    """Parse input string and match to exactly one bank or asset account.

    Returns an Account object or raises ValueError for no matches or
    multiple matches.
    """
    # print(f"hledger_account_infos={hledger_account_infos}")
    # print(f"accounts_without_csv={accounts_without_csv}")
    print(f"input_string={input_string}")

    found_account_configs: List[AccountConfig] = []
    for account_config in config.accounts:
        if (
            account_config.account.to_string() == input_string
            and currency == account_config.account.base_currency
        ):
            found_account_configs.append(account_config)
    if len(found_account_configs) < 1:
        raise ValueError(f"Did not find account for:{input_string}")
    if len(found_account_configs) > 1:
        raise ValueError(f"Found more than 1 account for:{input_string}")

    return found_account_configs[0].account


@typechecked
def get_accounts_from_answers(
    *,
    the_date: datetime,
    config: Config,
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
    ],
    hledger_account_infos: set[HledgerFlowAccountInfo],
    accounts_without_csv: set[str],
) -> List[AccountTransaction]:
    account_transactions: List[AccountTransaction] = []
    i = 0
    while i < len(final_answers):
        widget, _ = final_answers[i]
        caption = (
            widget.question_data.question
            if isinstance(widget, HorizontalMultipleChoiceWidget)
            else widget.caption
        )

        first_account_question_id: str = "Belongs to bank/accounts_without_csv:"
        if (
            caption[: len(first_account_question_id)]
            == first_account_question_id
        ):
            if not isinstance(widget, VerticalMultipleChoiceWidget):
                raise ValueError(
                    f"Expected VerticalMultipleChoiceWidget at index {i}"
                )
            if i + 4 >= len(final_answers):
                raise ValueError("Incomplete account transaction questions")

            # Currency
            currency_widget, currency_answer = final_answers[i + 1]
            if not isinstance(currency_widget, VerticalMultipleChoiceWidget):
                raise ValueError(
                    f"Expected VerticalMultipleChoiceWidget at index {i + 1}"
                )
            currency = Currency(currency_answer)

            # Account
            account_str = str(final_answers[i][1])
            account = parse_account_string(
                config=config,
                currency=currency,
                input_string=account_str,
                # hledger_account_infos=hledger_account_infos,
                # accounts_without_csv=accounts_without_csv,
            )

            # Amount paid
            amount_widget, amount_answer = final_answers[i + 2]
            if not isinstance(amount_widget, InputValidationQuestion):
                raise ValueError(
                    f"Expected InputValidationQuestion at index {i + 2}"
                )
            amount_paid = float(amount_answer)

            # Change returned
            change_widget, change_answer = final_answers[i + 3]
            if not isinstance(change_widget, InputValidationQuestion):
                raise ValueError(
                    f"Expected InputValidationQuestion at index {i + 3}"
                )
            change_returned = float(change_answer)

            account_transactions.append(
                AccountTransaction(
                    account=account,
                    # currency=currency,
                    the_date=the_date,
                    amount_out_account=amount_paid,
                    change_returned=change_returned,
                )
            )

            # Check for additional account
            if i + 4 < len(final_answers):
                add_widget, add_answer = final_answers[i + 4]
                add_caption = (
                    add_widget.question_data.question
                    if isinstance(add_widget, HorizontalMultipleChoiceWidget)
                    else add_widget.caption
                )
                if add_caption == "Add another account (y/n)?:":
                    if not isinstance(
                        add_widget, HorizontalMultipleChoiceWidget
                    ):
                        raise ValueError(
                            "Expected HorizontalMultipleChoiceWidget at index"
                            f" {i + 4}"
                        )
                    if str(add_answer).lower() == "y":
                        i += 5  # Move to the next account question
                        continue
                    else:
                        i += 5  # Move past the "y/n" question, but continue checking
                        continue
            i += 4  # Move past the current transaction questions
        else:
            i += 1  # Move to the next question if not an account question

    return account_transactions


@typechecked
def has_purchase_account_transactions(
    *, account_transactions: List[AccountTransaction]
) -> bool:
    for account_transaction in account_transactions:
        if account_transaction.is_purchase():
            return True
    return False


@typechecked
def separate_account_transactions(
    *, account_transactions: List[AccountTransaction]
) -> Tuple[List[AccountTransaction], List[AccountTransaction]]:
    purchase_account_transactions: List[AccountTransaction] = []
    non_purchase_account_transactions: List[AccountTransaction] = []
    for account_transaction in account_transactions:
        if account_transaction.is_purchase():
            purchase_account_transactions.append(account_transaction)
        else:
            non_purchase_account_transactions.append(account_transaction)
    return non_purchase_account_transactions, purchase_account_transactions


def get_bought_and_returned_items(
    *,
    config: Config,
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
    ],
    hledger_account_infos: set[HledgerFlowAccountInfo],
    accounts_without_csv: set[str],
    average_receipt_category: str,
    the_date: datetime,
) -> Tuple[None, ExchangedItem, Union[None, ExchangedItem]]:

    # Get the AccountTransactions.
    account_transactions: List[AccountTransaction] = get_accounts_from_answers(
        the_date=the_date,
        config=config,
        final_answers=final_answers,
        hledger_account_infos=hledger_account_infos,
        accounts_without_csv=accounts_without_csv,
    )

    # Map currency string back to Enum.
    non_purchase_account_transactions, purchase_account_transactions = (
        separate_account_transactions(account_transactions=account_transactions)
    )
    if (
        len(non_purchase_account_transactions) == 0
        and len(purchase_account_transactions) == 0
    ):
        raise ValueError("Must have at least 1 transaction in receipt.")

    net_bought_items = None
    if len(purchase_account_transactions) > 0:
        net_bought_items: ExchangedItem = ExchangedItem(
            quantity=1,
            account_transactions=purchase_account_transactions,
            description=average_receipt_category,
            the_date=the_date,
            tax_per_unit=0,
            group_discount=0,
            category=None,
            round_amount=None,
        )

    net_returned_items = None
    if len(non_purchase_account_transactions) > 0:
        net_returned_items: ExchangedItem = ExchangedItem(
            quantity=1,
            account_transactions=non_purchase_account_transactions,
            description=average_receipt_category,
            the_date=the_date,
            tax_per_unit=0,
            group_discount=0,
            category=None,
            round_amount=None,
        )
    return net_bought_items, net_returned_items
