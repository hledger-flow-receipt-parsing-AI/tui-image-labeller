from datetime import datetime
from typing import List, Optional, Tuple, Union

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
from hledger_preprocessor.TransactionObjects.Receipt import WithdrawalMetadata
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
        # Foreign currency: currency differs from account's base_currency.
        # Fall back to matching by account string only.
        for account_config in config.accounts:
            if account_config.account.to_string() == input_string:
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
            if i + 3 >= len(final_answers):
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

            # Amount paid (may be absent for withdrawal receipts)
            offset = 2
            next_widget, next_answer = final_answers[i + offset]
            next_caption = (
                next_widget.question_data.question
                if isinstance(next_widget, (HorizontalMultipleChoiceWidget, VerticalMultipleChoiceWidget))
                else getattr(next_widget, "caption", "")
            )
            if "Amount paid from account:" in next_caption:
                amount_paid = float(next_answer)
                offset += 1
            else:
                # Withdrawal: "Amount paid" is skipped, default to 0.
                amount_paid = 0.0

            # Change returned
            change_widget, change_answer = final_answers[i + offset]
            if not isinstance(change_widget, InputValidationQuestion):
                raise ValueError(
                    f"Expected InputValidationQuestion at index {i + offset}"
                )
            change_returned = float(change_answer)
            offset += 1

            # Set payment_currency when it differs from the account's base currency
            payment_currency = (
                currency if currency != account.base_currency else None
            )
            account_transactions.append(
                AccountTransaction(
                    account=account,
                    payment_currency=payment_currency,
                    the_date=the_date,
                    tendered_amount_out=amount_paid,
                    change_returned=change_returned,
                )
            )

            # Check for additional account
            if i + offset < len(final_answers):
                add_widget, add_answer = final_answers[i + offset]
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
                            f" {i + offset}"
                        )
                    if str(add_answer).lower() == "y":
                        i += offset + 1
                        continue
                    else:
                        i += offset + 1
                        continue
            i += offset
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
    average_receipt_category: Optional[str],
    the_date: datetime,
) -> Tuple[None, ExchangedItem, Union[None, ExchangedItem]]:

    if average_receipt_category is None:
        average_receipt_category = "withdrawal"

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


@typechecked
def parse_withdrawal_answers(
    *,
    config: Config,
    final_answers: List[
        Tuple[
            Union[
                "DateTimeQuestion",
                "InputValidationQuestion",
                "VerticalMultipleChoiceWidget",
                "HorizontalMultipleChoiceWidget",
            ],
            Union[str, float, int, datetime],
        ]
    ],
    the_date: datetime,
    receipt_amount: Optional[float] = None,
) -> Optional[WithdrawalMetadata]:
    """Parse withdrawal-specific answers from the TUI final answers.

    Looks for the withdrawal source account, ATM fee, and optional
    conversion details.  The source debit amount may be given directly
    or derived from an exchange rate plus the receipt amount.
    """
    source_account_str = None
    source_currency = None
    source_amount = None
    atm_fee = 0.0
    exchange_rate = None
    bank_fee = 0.0

    for i, (widget, value) in enumerate(final_answers):
        caption = (
            widget.question_data.question
            if isinstance(widget, (HorizontalMultipleChoiceWidget,))
            else getattr(widget, "caption", "")
        )
        if isinstance(widget, VerticalMultipleChoiceWidget):
            caption = widget.question_data.question

        if caption == "Withdrawal source account:":
            source_account_str = str(value)
        elif caption == "Source account currency:":
            source_currency = Currency(value)
        elif caption == "Amount debited from source account:":
            source_amount = float(value)
        elif caption == "ATM operator fee (in withdrawn currency, 0 if none):":
            atm_fee = float(value)
        elif caption == "Exchange rate (1 source = X destination):":
            exchange_rate = float(value)
        elif caption == "Bank fee (in source currency, 0 if none):":
            bank_fee = float(value)

    if source_account_str is None or source_currency is None:
        return None

    # Derive source_amount from exchange rate if not given directly.
    if source_amount is None and exchange_rate is not None:
        if receipt_amount is not None and exchange_rate > 0:
            source_amount = receipt_amount / exchange_rate
            if bank_fee:
                source_amount += bank_fee
        else:
            return None
    if source_amount is None:
        return None

    source_account = parse_account_string(
        config=config,
        currency=source_currency,
        input_string=source_account_str,
    )

    source_transaction = AccountTransaction(
        account=source_account,
        payment_currency=(
            source_currency
            if source_currency != source_account.base_currency
            else None
        ),
        the_date=the_date,
        tendered_amount_out=source_amount,
        change_returned=0.0,
    )

    # Determine withdrawn_amount (destination currency) for foreign
    # withdrawal rules.  When the user provided an exchange rate,
    # the destination amount is the receipt amount.  When the user gave
    # a direct source debit, the destination amount is also the receipt
    # amount if currencies differ.
    withdrawn_amount: Optional[float] = None
    if receipt_amount is not None and exchange_rate is not None:
        withdrawn_amount = receipt_amount
    elif receipt_amount is not None and source_currency != Currency(
        source_account.base_currency.value
    ):
        # Foreign withdrawal but user entered source debit directly.
        withdrawn_amount = receipt_amount

    return WithdrawalMetadata(
        source_account_transaction=source_transaction,
        atm_operator_fee=atm_fee,
        withdrawn_amount=withdrawn_amount,
        exchange_rate=exchange_rate,
        bank_fx_fee=bank_fee,
    )
