"""The currency the user picks most often is the first answer of every currency
question, so the usual choice is always on top (it used to sit on the second
page of the list)."""

from datetime import datetime
from typing import Any, List, Optional, Sequence

import pytest
import urwid
from hledger_core.Currency import Currency
from hledger_core.TransactionObjects.Account import Account
from hledger_core.TransactionObjects.AccountTransaction import (
    AccountTransaction,
)
from hledger_core.TransactionObjects.ExchangedItem import ExchangedItem
from hledger_core.TransactionObjects.Receipt import (
    Receipt,
    WithdrawalMetadata,
)

from tui_labeller.tuis.urwid.multiple_choice_question.VerticalMultipleChoiceWidget import (  # noqa: E501
    VerticalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.question_app.generator import create_questionnaire
from tui_labeller.tuis.urwid.question_app.reconfiguration.reconfiguration import (  # noqa: E501
    handle_withdrawal_toggle,
)
from tui_labeller.tuis.urwid.receipts.AccountQuestions import AccountQuestions
from tui_labeller.tuis.urwid.receipts.BaseQuestions import BaseQuestions
from tui_labeller.tuis.urwid.receipts.currency_order import (
    count_currency_usage,
    currencies_by_usage,
    sort_currency_choices,
)
from tui_labeller.tuis.urwid.receipts.WithdrawalQuestions import (
    WithdrawalQuestions,
)

ENUM_ORDER = [currency.value for currency in Currency]
ACCOUNTS = ["at:triodos:checking"]
WALLETS = {"at:wallet:physical"}
WHEN = datetime(2025, 1, 15, 10, 30)


def _transaction(
    *, chosen: Currency, base: Currency = Currency.EUR
) -> AccountTransaction:
    """An account block as the labeller stores it: the chosen currency is
    the account's own, or ``payment_currency`` when it differs."""
    account = Account(
        base_currency=base,
        account_holder="at",
        bank="triodos",
        account_type="checking",
    )
    return AccountTransaction(
        account=account,
        the_date=WHEN,
        tendered_amount_out=10.0,
        payment_currency=None if chosen == base else chosen,
    )


def _item(*, chosen: Sequence[Currency]) -> Any:
    if not chosen:
        return []  # how a receipt stores "no such items"
    return ExchangedItem(
        quantity=1.0,
        description="x",
        the_date=WHEN,
        account_transactions=[_transaction(chosen=c) for c in chosen],
    )


def _receipt(
    *bought: Currency,
    returned: Sequence[Currency] = (),
    withdrawal_source: Optional[Currency] = None,
) -> Receipt:
    # Built like the labeller's own stub receipt: only what is read here.
    receipt = Receipt.__new__(Receipt)
    receipt.net_bought_items = _item(chosen=bought)
    receipt.net_returned_items = _item(chosen=returned)
    receipt.withdrawal_metadata = (
        None
        if withdrawal_source is None
        else WithdrawalMetadata(
            source_account_transaction=_transaction(chosen=withdrawal_source)
        )
    )
    return receipt


def _mostly_euro() -> List[Receipt]:
    return [
        _receipt(Currency.EUR),
        _receipt(Currency.EUR),
        _receipt(Currency.EUR),
        _receipt(Currency.GBP),
    ]


# ------------------------------------------------------------------ counting


def test_counts_every_chosen_currency() -> None:
    receipts = [
        _receipt(Currency.EUR, Currency.EUR),
        _receipt(Currency.USD, returned=[Currency.EUR]),
        _receipt(Currency.GBP, withdrawal_source=Currency.EUR),
    ]
    assert count_currency_usage(labelled_receipts=receipts) == {
        "EUR": 4,
        "USD": 1,
        "GBP": 1,
    }


def test_a_foreign_payment_counts_as_the_currency_that_was_chosen() -> None:
    """Paying pounds from a euro account was answered with GBP."""
    receipt = _receipt(Currency.GBP)
    transaction = receipt.net_bought_items.account_transactions[0]
    assert transaction.account.base_currency == Currency.EUR
    assert count_currency_usage(labelled_receipts=[receipt]) == {"GBP": 1}


def test_unreadable_receipts_are_skipped_not_fatal() -> None:
    empty = Receipt.__new__(Receipt)  # no attributes at all
    only_returned = _receipt(returned=[Currency.USD])
    assert count_currency_usage(labelled_receipts=[empty, only_returned]) == {
        "USD": 1
    }


# ------------------------------------------------------------------ ordering


def test_without_labelled_receipts_the_order_is_unchanged() -> None:
    """The demo harness in hledger-preprocessor picks currencies by their
    position in the Currency enum and always starts without labels."""
    assert currencies_by_usage(labelled_receipts=[]) == ENUM_ORDER
    assert ENUM_ORDER.index("EUR") == 9


def test_most_used_first_then_the_rest_in_their_usual_order() -> None:
    ordered = currencies_by_usage(labelled_receipts=_mostly_euro())
    assert ordered[:2] == ["EUR", "GBP"]
    assert ordered[2:] == [c for c in ENUM_ORDER if c not in ("EUR", "GBP")]
    assert sorted(ordered) == sorted(ENUM_ORDER)


def test_equally_used_currencies_keep_their_usual_order() -> None:
    receipts = [_receipt(Currency.GBP), _receipt(Currency.USD)]
    ordered = currencies_by_usage(labelled_receipts=receipts)
    assert ordered[:2] == ["USD", "GBP"]  # USD precedes GBP in the enum


def test_least_used_is_last_among_the_used_ones() -> None:
    receipts = (
        [_receipt(Currency.EUR)] * 5
        + [_receipt(Currency.USD)] * 3
        + [_receipt(Currency.BTC)]
    )
    assert currencies_by_usage(labelled_receipts=receipts)[:3] == [
        "EUR",
        "USD",
        "BTC",
    ]


# ------------------------------------------------------------ question data


def test_only_currency_questions_are_reordered() -> None:
    account = AccountQuestions(
        account_infos_str=ACCOUNTS, accounts_without_csv=WALLETS
    ).account_questions
    withdrawal = WithdrawalQuestions(
        account_infos_str=ACCOUNTS, accounts_without_csv=WALLETS
    ).withdrawal_questions
    questions = [*account, *withdrawal]
    by_id = {question.question_id: question for question in questions}
    accounts_before = list(by_id["bank_account"].choices)

    sort_currency_choices(questions=questions, labelled_receipts=_mostly_euro())

    assert by_id["currency"].choices[:2] == ["EUR", "GBP"]
    assert by_id["withdrawal_currency"].choices[:2] == ["EUR", "GBP"]
    assert by_id["bank_account"].choices == accounts_before
    assert by_id["withdrawal_source"].choices == accounts_before


def test_reordering_is_repeatable_and_follows_new_usage() -> None:
    questions = AccountQuestions(
        account_infos_str=ACCOUNTS, accounts_without_csv=WALLETS
    ).account_questions
    currency = next(q for q in questions if q.question_id == "currency")

    sort_currency_choices(questions=questions, labelled_receipts=_mostly_euro())
    first = list(currency.choices)
    sort_currency_choices(questions=questions, labelled_receipts=_mostly_euro())
    assert currency.choices == first

    sort_currency_choices(
        questions=questions, labelled_receipts=[_receipt(Currency.BTC)]
    )
    assert currency.choices[0] == "BTC"
    sort_currency_choices(questions=questions, labelled_receipts=[])
    assert currency.choices == ENUM_ORDER


# ------------------------------------------------------------ questionnaire


def _widget(tui: Any, *, question: str) -> VerticalMultipleChoiceWidget:
    return next(
        entry.base_widget
        for entry in tui.inputs
        if entry.base_widget.question_data.question == question
    )


def _questionnaire(*, labelled_receipts: List[Receipt]) -> Any:
    return create_questionnaire(
        header="h",
        questions=AccountQuestions(
            account_infos_str=ACCOUNTS, accounts_without_csv=WALLETS
        ).account_questions,
        labelled_receipts=labelled_receipts,
    )


def test_questionnaire_lists_the_most_used_currency_first() -> None:
    tui = _questionnaire(labelled_receipts=_mostly_euro())
    currency = _widget(tui, question="Currency:")
    assert currency.question_data.choices[:2] == ["EUR", "GBP"]

    rows = [
        row.decode("utf-8")
        for row in tui.loop.widget.render((120, 40), focus=True).text
    ]
    listed = [row.split()[1] for row in rows if row.startswith((" 0 ", " 1 "))]
    assert "EUR" in listed and listed.index("EUR") < listed.index("GBP")


def test_questionnaire_without_labels_keeps_the_usual_order() -> None:
    tui = _questionnaire(labelled_receipts=[])
    assert _widget(tui, question="Currency:").question_data.choices == (
        ENUM_ORDER
    )


@pytest.mark.parametrize(
    "value, expected",
    [("GBP", "GBP"), (Currency.USD, "USD"), ("BTC", "BTC")],
)
def test_answers_are_set_and_read_by_value_not_position(
    value: Any, expected: str
) -> None:
    """Prefilled and restored answers must survive the new order."""
    tui = _questionnaire(labelled_receipts=_mostly_euro())
    currency = _widget(tui, question="Currency:")
    currency.set_answer(value)
    assert currency.get_answer() == expected


def test_typing_zero_now_selects_the_most_used_currency() -> None:
    tui = _questionnaire(labelled_receipts=_mostly_euro())
    currency = _widget(tui, question="Currency:")
    currency.keypress((80,), "0")
    assert currency.get_answer() == "EUR"


def test_questions_added_by_a_reconfiguration_get_the_same_order() -> None:
    """The withdrawal toggle injects "Source account currency:" later; it must
    not fall back to the usual order."""
    receipts = _mostly_euro()
    base = BaseQuestions()
    withdrawal = WithdrawalQuestions(
        account_infos_str=ACCOUNTS, accounts_without_csv=WALLETS
    )
    tui = create_questionnaire(
        header="h",
        questions=[
            base.get_withdrawal_toggle(),
            base.get_category_question(),
            *AccountQuestions(
                account_infos_str=ACCOUNTS, accounts_without_csv=WALLETS
            ).account_questions,
        ],
        labelled_receipts=receipts,
    )
    tui.loop.screen = urwid.raw_display.Screen()

    new_tui = handle_withdrawal_toggle(
        tui=tui,
        withdrawal_questions=withdrawal,
        preserved_answers=[None for _ in tui.inputs],
        labelled_receipts=receipts,
        toggle_answer="y",
    )

    source = _widget(new_tui, question="Source account currency:")
    wallet = _widget(new_tui, question="Currency:")
    assert source.question_data.choices[:2] == ["EUR", "GBP"]
    assert wallet.question_data.choices[:2] == ["EUR", "GBP"]
