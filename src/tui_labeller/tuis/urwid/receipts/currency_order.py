"""Order the currency answers by how often each was chosen in the receipts
labelled so far: the usual currency on top, never-used ones at the bottom.

Answers are stored and restored by value (the currency code), never by
position, so the order can change between receipts without affecting any
saved or prefilled answer.
"""

from collections import Counter
from typing import Any, Dict, Iterator, List, Optional

from hledger_core.Currency import Currency
from hledger_core.TransactionObjects.Receipt import Receipt
from typeguard import typechecked

from tui_labeller.tuis.urwid.question_data_classes import (
    VerticalMultipleChoiceQuestionData,
)

# The order of the Currency enum: what the questions list when nothing has
# been labelled yet.
ALL_CURRENCIES: List[str] = [currency.value for currency in Currency]


@typechecked
def _chosen_currency(*, transaction: Any) -> Optional[str]:
    """The currency answered for one account block of a labelled receipt.

    The labeller stores it as ``payment_currency`` when it differs from the
    account's own currency, and leaves that empty when it is the same.
    """
    chosen = getattr(transaction, "payment_currency", None)
    if chosen is None:
        account = getattr(transaction, "account", None)
        chosen = getattr(account, "base_currency", None)
    if isinstance(chosen, Currency):
        return chosen.value
    if isinstance(chosen, str) and chosen in ALL_CURRENCIES:
        return chosen
    return None


def _account_blocks(*, receipt: Any) -> Iterator[Any]:
    """Every account block of a receipt for which a currency was chosen."""
    for name in ("net_bought_items", "net_returned_items"):
        # An absent item is stored as an empty list.
        item = getattr(receipt, name, None)
        yield from getattr(item, "account_transactions", None) or []
    withdrawal = getattr(receipt, "withdrawal_metadata", None)
    source = getattr(withdrawal, "source_account_transaction", None)
    if source is not None:
        yield source


@typechecked
def count_currency_usage(*, labelled_receipts: List[Receipt]) -> Dict[str, int]:
    """How often each currency was chosen while labelling.

    A receipt that cannot be read is skipped: the order of a list must never
    stop the user from labelling.
    """
    usage: Counter = Counter()
    for receipt in labelled_receipts:
        for transaction in _account_blocks(receipt=receipt):
            chosen = _chosen_currency(transaction=transaction)
            if chosen is not None:
                usage[chosen] += 1
    return dict(usage)


@typechecked
def currencies_by_usage(*, labelled_receipts: List[Receipt]) -> List[str]:
    """All currencies, most chosen first.

    Equally used ones (and those never used) keep the order of the Currency
    enum, so without labelled receipts the list is unchanged.  The demo
    harness in hledger-preprocessor relies on that: it starts without
    labels and selects a currency by its position in the enum.
    """
    usage = count_currency_usage(labelled_receipts=labelled_receipts)
    # sorted() is stable, which keeps the enum order within equal counts.
    return sorted(ALL_CURRENCIES, key=lambda code: -usage.get(code, 0))


@typechecked
def sort_currency_choices(
    *, questions: List[Any], labelled_receipts: List[Receipt]
) -> None:
    """Put the most chosen currency first in every currency question.

    A currency question is a multiple-choice question that offers
    exactly the currencies; that also covers the "Source account
    currency" of a withdrawal and the currency of a second account.
    """
    ordered = currencies_by_usage(labelled_receipts=labelled_receipts)
    for question in questions:
        if isinstance(question, VerticalMultipleChoiceQuestionData) and sorted(
            question.choices
        ) == sorted(ALL_CURRENCIES):
            question.choices = list(ordered)
