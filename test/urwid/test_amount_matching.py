"""Tests for _try_non_withdrawal_amount_match and _validate_account_date_range.

Scenarios:
  1. Exact match: receipt amount matches one CSV transaction → green.
  2. No match (date out of range): bank processed the transaction a day
     later than the config's matching margin allows → red.
  3. No match (amount mismatch): receipt amount doesn't match → red.
  4. Ambiguous: multiple CSV transactions match → red.
  5. Wallet account (no CSV): matching is skipped, fields stay normal.
  6. Date-range validation: account's CSV has no data for the
     receipt year → red.
"""

from datetime import datetime
from types import SimpleNamespace
from typing import List, Optional

import pytest
import urwid
from hledger_config.config.AccountConfig import AccountConfig
from hledger_config.config.MatchingAlgoConfig import MatchingAlgoConfig
from hledger_core.Currency import Currency
from hledger_core.TransactionObjects.Account import Account
from hledger_core.TransactionObjects.AccountTransaction import (
    AccountTransaction,
)

from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_app.generator import (
    create_questionnaire,
)
from tui_labeller.tuis.urwid.question_app.reconfiguration.reconfiguration import (  # noqa: E501
    _try_non_withdrawal_amount_match,
    _validate_account_date_range,
)
from tui_labeller.tuis.urwid.question_data_classes import (
    DateQuestionData,
    HorizontalMultipleChoiceQuestionData,
    InputValidationQuestionData,
    VerticalMultipleChoiceQuestionData,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_account(
    holder: str = "at",
    bank: str = "triodos",
    acct_type: str = "checking",
    currency: Currency = Currency.EUR,
) -> Account:
    return Account(
        base_currency=currency,
        account_holder=holder,
        bank=bank,
        account_type=acct_type,
    )


def _make_account_config(
    account: Account, has_csv: bool = True
) -> AccountConfig:
    from hledger_core.config.CsvColumnMapping import CsvColumnMapping

    if has_csv:
        mapping = CsvColumnMapping(
            csv_column_mapping=(
                ("the_date", "date"),
                ("tendered_amount_out", "amount"),
            )
        )
        return AccountConfig(
            account=account,
            input_csv_filename="test.csv",
            csv_column_mapping=mapping,
            tnx_date_columns=CsvColumnMapping(csv_column_mapping=None),
        )
    return AccountConfig(
        account=account,
        input_csv_filename=None,
        csv_column_mapping=None,
        tnx_date_columns=None,
    )


def _make_transaction(
    account: Account, date: datetime, amount: float
) -> AccountTransaction:
    """Create a CSV transaction (negative amount = debit)."""
    return AccountTransaction(
        account=account,
        the_date=date,
        tendered_amount_out=amount,
        change_returned=0.0,
    )


def _make_config(days: int = 2, amount_range: float = 0) -> SimpleNamespace:
    """Lightweight config with only matching_algo."""
    return SimpleNamespace(
        matching_algo=MatchingAlgoConfig(
            days=days,
            amount_range=amount_range,
            days_month_swap=False,
            multiple_receipts_per_transaction=False,
        )
    )


def _build_tui(
    *,
    receipt_date: datetime,
    account_str: str,
    amount_paid: str,
    change_returned: str = "0",
    is_withdrawal: bool = False,
    account_choices: Optional[List[str]] = None,
):
    """Build a QuestionnaireApp with pre-filled receipt answers."""
    if account_choices is None:
        account_choices = [account_str]

    questions = [
        DateQuestionData(
            question="Receipt date and time:\n",
            date_only=False,
            ai_suggestions=[],
            ans_required=True,
            reconfigurer=False,
            terminator=False,
        ),
        HorizontalMultipleChoiceQuestionData(
            question="Is this a withdrawal? (y/n)",
            choices=["y", "n"],
            ai_suggestions=[],
            ans_required=True,
            reconfigurer=True,
            terminator=False,
        ),
        VerticalMultipleChoiceQuestionData(
            question="Belongs to bank/accounts_without_csv:",
            choices=account_choices,
            nr_of_ans_per_batch=10,
            ai_suggestions=[],
            ans_required=True,
            reconfigurer=True,
            terminator=False,
        ),
        InputValidationQuestionData(
            question="Amount paid from account:",
            input_type=InputType.FLOAT,
            ai_suggestions=[],
            history_suggestions=[],
            ans_required=True,
            reconfigurer=False,
            terminator=False,
        ),
        InputValidationQuestionData(
            question="Change returned to account:",
            input_type=InputType.FLOAT,
            ai_suggestions=[],
            history_suggestions=[],
            ans_required=False,
            reconfigurer=False,
            terminator=False,
        ),
        HorizontalMultipleChoiceQuestionData(
            question="Add another account (y/n)?",
            choices=["y", "n"],
            ai_suggestions=[],
            ans_required=True,
            reconfigurer=True,
            terminator=False,
        ),
    ]

    tui = create_questionnaire(
        header="Test", questions=questions, labelled_receipts=[]
    )
    tui.loop.screen = urwid.raw_display.Screen()

    # Set answers on the widgets.
    for inp in tui.inputs:
        w = inp.base_widget
        q = w.question_data.question
        if q == "Receipt date and time:\n":
            w.set_answer(receipt_date)
        elif q == "Is this a withdrawal? (y/n)":
            w.set_answer("y" if is_withdrawal else "n")
        elif q == "Belongs to bank/accounts_without_csv:":
            w.set_answer(account_str)
        elif q == "Amount paid from account:":
            w.set_answer(float(amount_paid))
        elif q == "Change returned to account:":
            w.set_answer(float(change_returned))
        elif q == "Add another account (y/n)?":
            w.set_answer("n")

    return tui


def _get_attr(tui, question_substr: str) -> Optional[dict]:
    """Read the attr_map from a widget matching the question substring."""
    for inp in tui.inputs:
        if question_substr in inp.base_widget.question_data.question:
            return inp.attr_map
    return None


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def bank_account():
    return _make_account()


@pytest.fixture
def bank_config(bank_account):
    return _make_account_config(bank_account, has_csv=True)


@pytest.fixture
def wallet_account():
    return _make_account(bank="wallet", acct_type="physical")


@pytest.fixture
def wallet_config(wallet_account):
    return _make_account_config(wallet_account, has_csv=False)


# ---------------------------------------------------------------------------
# Tests: _try_non_withdrawal_amount_match
# ---------------------------------------------------------------------------


class TestAmountMatch:
    """Tests for _try_non_withdrawal_amount_match."""

    def test_exact_match_turns_green(self, bank_account, bank_config):
        """Receipt 42.17 on Jan 15, CSV has -42.17 on Jan 15 → green."""
        receipt_date = datetime(2025, 1, 15, 10, 30)
        txn = _make_transaction(bank_account, datetime(2025, 1, 15), -42.17)
        csv_data = {bank_config: {2025: [txn]}}
        config = _make_config(days=2, amount_range=0)
        tui = _build_tui(
            receipt_date=receipt_date,
            account_str=bank_account.to_string(),
            amount_paid="42.17",
        )

        _try_non_withdrawal_amount_match(
            tui=tui,
            config=config,
            csv_transactions_per_account=csv_data,
        )

        assert _get_attr(tui, "Amount paid") == {None: "matched"}
        assert _get_attr(tui, "Change returned") == {None: "matched"}

    def test_date_out_of_range_turns_red(self, bank_account, bank_config):
        """Receipt on Jan 15, CSV transaction on Jan 18, margin=2 days → red.

        This simulates the scenario where the bank processes the
        transaction a day later than the matching margin allows.
        """
        receipt_date = datetime(2025, 1, 15, 10, 30)
        # Bank processed 3 days later; margin is only 2.
        txn = _make_transaction(bank_account, datetime(2025, 1, 18), -42.17)
        csv_data = {bank_config: {2025: [txn]}}
        config = _make_config(days=2, amount_range=0)
        tui = _build_tui(
            receipt_date=receipt_date,
            account_str=bank_account.to_string(),
            amount_paid="42.17",
        )

        _try_non_withdrawal_amount_match(
            tui=tui,
            config=config,
            csv_transactions_per_account=csv_data,
        )

        assert _get_attr(tui, "Amount paid") == {None: "error"}
        assert _get_attr(tui, "Change returned") == {None: "error"}

    def test_amount_mismatch_turns_red(self, bank_account, bank_config):
        """Receipt 42.17, CSV has 50.00 on the same date → red."""
        receipt_date = datetime(2025, 1, 15, 10, 30)
        txn = _make_transaction(bank_account, datetime(2025, 1, 15), -50.00)
        csv_data = {bank_config: {2025: [txn]}}
        config = _make_config(days=2, amount_range=0)
        tui = _build_tui(
            receipt_date=receipt_date,
            account_str=bank_account.to_string(),
            amount_paid="42.17",
        )

        _try_non_withdrawal_amount_match(
            tui=tui,
            config=config,
            csv_transactions_per_account=csv_data,
        )

        assert _get_attr(tui, "Amount paid") == {None: "error"}

    def test_ambiguous_match_turns_red(self, bank_account, bank_config):
        """Two transactions for 42.17 within the date range → red."""
        receipt_date = datetime(2025, 1, 15, 10, 30)
        txn1 = _make_transaction(bank_account, datetime(2025, 1, 15), -42.17)
        txn2 = _make_transaction(bank_account, datetime(2025, 1, 16), -42.17)
        csv_data = {bank_config: {2025: [txn1, txn2]}}
        config = _make_config(days=2, amount_range=0)
        tui = _build_tui(
            receipt_date=receipt_date,
            account_str=bank_account.to_string(),
            amount_paid="42.17",
        )

        _try_non_withdrawal_amount_match(
            tui=tui,
            config=config,
            csv_transactions_per_account=csv_data,
        )

        assert _get_attr(tui, "Amount paid") == {None: "error"}

    def test_wallet_account_skips_matching(self, wallet_account, wallet_config):
        """Wallet (no CSV) → fields stay 'normal'."""
        receipt_date = datetime(2025, 2, 10, 8, 15)
        csv_data = {}  # wallet has no CSV data
        config = _make_config(days=2, amount_range=0)
        tui = _build_tui(
            receipt_date=receipt_date,
            account_str=wallet_account.to_string(),
            amount_paid="20",
            change_returned="15",
        )

        _try_non_withdrawal_amount_match(
            tui=tui,
            config=config,
            csv_transactions_per_account=csv_data,
        )

        # Not in csv_transactions_per_account → no colour change.
        assert _get_attr(tui, "Amount paid") == {None: "normal"}
        assert _get_attr(tui, "Change returned") == {None: "normal"}

    def test_match_with_change_returned(self, bank_account, bank_config):
        """Receipt: paid 50, change 7.83 → net 42.17. CSV -42.17 → green."""
        receipt_date = datetime(2025, 1, 15, 10, 30)
        txn = _make_transaction(bank_account, datetime(2025, 1, 15), -42.17)
        csv_data = {bank_config: {2025: [txn]}}
        config = _make_config(days=2, amount_range=0)
        tui = _build_tui(
            receipt_date=receipt_date,
            account_str=bank_account.to_string(),
            amount_paid="50",
            change_returned="7.83",
        )

        _try_non_withdrawal_amount_match(
            tui=tui,
            config=config,
            csv_transactions_per_account=csv_data,
        )

        assert _get_attr(tui, "Amount paid") == {None: "matched"}
        assert _get_attr(tui, "Change returned") == {None: "matched"}

    def test_wider_margin_finds_delayed_transaction(
        self, bank_account, bank_config
    ):
        """Margin=5 days catches a bank transaction 3 days after receipt."""
        receipt_date = datetime(2025, 1, 15, 10, 30)
        txn = _make_transaction(bank_account, datetime(2025, 1, 18), -42.17)
        csv_data = {bank_config: {2025: [txn]}}
        config = _make_config(days=5, amount_range=0)
        tui = _build_tui(
            receipt_date=receipt_date,
            account_str=bank_account.to_string(),
            amount_paid="42.17",
        )

        _try_non_withdrawal_amount_match(
            tui=tui,
            config=config,
            csv_transactions_per_account=csv_data,
        )

        assert _get_attr(tui, "Amount paid") == {None: "matched"}

    def test_none_csv_data_skips(self, bank_account, bank_config):
        """csv_transactions_per_account=None → no-op."""
        tui = _build_tui(
            receipt_date=datetime(2025, 1, 15, 10, 30),
            account_str=bank_account.to_string(),
            amount_paid="42.17",
        )

        _try_non_withdrawal_amount_match(
            tui=tui,
            config=_make_config(),
            csv_transactions_per_account=None,
        )

        assert _get_attr(tui, "Amount paid") == {None: "normal"}


# ---------------------------------------------------------------------------
# Tests: _validate_account_date_range
# ---------------------------------------------------------------------------


class TestDateRangeValidation:
    """Tests for _validate_account_date_range."""

    def test_year_present_stays_normal(self, bank_account, bank_config):
        """CSV has transactions for 2025, receipt is 2025 → normal."""
        receipt_date = datetime(2025, 1, 15, 10, 30)
        txn = _make_transaction(bank_account, datetime(2025, 6, 1), -10.0)
        csv_data = {bank_config: {2025: [txn]}}
        tui = _build_tui(
            receipt_date=receipt_date,
            account_str=bank_account.to_string(),
            amount_paid="42.17",
        )

        _validate_account_date_range(
            tui=tui,
            csv_transactions_per_account=csv_data,
        )

        assert _get_attr(tui, "Belongs to") == {None: "normal"}

    def test_year_missing_turns_red(self, bank_account, bank_config):
        """CSV has 2024 data only, receipt is 2025 → red."""
        receipt_date = datetime(2025, 1, 15, 10, 30)
        txn = _make_transaction(bank_account, datetime(2024, 6, 1), -10.0)
        csv_data = {bank_config: {2024: [txn]}}
        tui = _build_tui(
            receipt_date=receipt_date,
            account_str=bank_account.to_string(),
            amount_paid="42.17",
        )

        _validate_account_date_range(
            tui=tui,
            csv_transactions_per_account=csv_data,
        )

        assert _get_attr(tui, "Belongs to") == {None: "error"}

    def test_wallet_skips_validation(self, wallet_account, wallet_config):
        """Wallet (no CSV) → account widget stays normal."""
        receipt_date = datetime(2025, 2, 10, 8, 15)
        csv_data = {}  # wallet not in dict
        tui = _build_tui(
            receipt_date=receipt_date,
            account_str=wallet_account.to_string(),
            amount_paid="20",
            account_choices=[wallet_account.to_string()],
        )

        _validate_account_date_range(
            tui=tui,
            csv_transactions_per_account=csv_data,
        )

        # Not in csv_transactions_per_account → no change.
        assert _get_attr(tui, "Belongs to") == {None: "normal"}
