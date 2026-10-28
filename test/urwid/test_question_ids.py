"""Every receipt question carries a stable ``question_id`` and the text fields
accept the characters real shop data contains (spaces, ampersands).

The ids are the contract between the TUI and the demo/scenario harness in
hledger-preprocessor: focus markers, receipt-image boxes and scripted answers
are all keyed by them, so they must not drift silently.
"""

from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.input_validation.InputValidationQuestion import (
    InputValidationQuestion,
)
from tui_labeller.tuis.urwid.question_app.reconfiguration.reconfiguration import (  # noqa: E501
    make_amount_paid_question,
    make_match_choice_question,
)
from tui_labeller.tuis.urwid.question_data_classes import (
    InputValidationQuestionData,
)
from tui_labeller.tuis.urwid.receipts.AccountQuestions import AccountQuestions
from tui_labeller.tuis.urwid.receipts.BaseQuestions import BaseQuestions
from tui_labeller.tuis.urwid.receipts.OptionalQuestions import OptionalQuestions
from tui_labeller.tuis.urwid.receipts.WithdrawalQuestions import (
    WithdrawalQuestions,
)

ACCOUNTS = ["at:triodos:checking"]
WALLETS = {"at:wallet:physical"}


def _ids(questions) -> list:
    return [q.question_id for q in questions]


def test_base_question_ids() -> None:
    assert _ids(BaseQuestions().base_questions) == [
        "date",
        "is_withdrawal",
        "category",
    ]


def test_account_question_ids() -> None:
    qs = AccountQuestions(
        account_infos_str=ACCOUNTS, accounts_without_csv=WALLETS
    ).account_questions
    assert _ids(qs) == [
        "bank_account",
        "currency",
        "amount",
        "change",
        "add_another",
    ]


def test_withdrawal_question_ids() -> None:
    wq = WithdrawalQuestions(
        account_infos_str=ACCOUNTS, accounts_without_csv=WALLETS
    )
    assert _ids(wq.withdrawal_questions) == [
        "withdrawal_source",
        "withdrawal_currency",
        "withdrawal_amount",
    ]
    assert wq.get_atm_fee_question().question_id == "atm_fee"
    assert wq.get_bank_fee_question().question_id == "bank_fee"
    assert wq.get_exchange_rate_question().question_id == "exchange_rate"


def test_optional_question_ids() -> None:
    oq = OptionalQuestions(labelled_receipts=[])
    assert _ids(oq.optional_questions) == [
        "address_selector",
        "subtotal",
        "total_tax",
        "done",
    ]
    assert _ids(oq.get_manual_address_questions()) == [
        "shop_name",
        "shop_street",
        "shop_house_nr",
        "shop_zipcode",
        "shop_city",
        "shop_country",
    ]


def test_reconfiguration_question_ids() -> None:
    assert make_match_choice_question().question_id == "match_choice"
    assert make_amount_paid_question().question_id == "amount"


def _widget(input_type: InputType) -> InputValidationQuestion:
    data = InputValidationQuestionData(
        question="q",
        input_type=input_type,
        ans_required=False,
        reconfigurer=False,
        terminator=False,
        ai_suggestions=[],
        history_suggestions=[],
    )
    return InputValidationQuestion(question_data=data, history_store={})


def test_shop_name_accepts_real_names() -> None:
    w = _widget(InputType.NAME)
    for name in ("Koffie Leute", "H&M", "Restaurant De Kas", "Barclays ATM"):
        assert all(w.valid_char(ch=c) for c in name), name


def test_zipcode_accepts_space() -> None:
    w = _widget(InputType.LETTERS_AND_NRS)
    assert all(w.valid_char(ch=c) for c in "W1D 1BS")


def test_city_country_accept_space() -> None:
    oq = OptionalQuestions(labelled_receipts=[])
    by_id = {q.question_id: q for q in oq.get_manual_address_questions()}
    assert by_id["shop_city"].input_type == InputType.LETTERS_AND_SPACE
    assert by_id["shop_country"].input_type == InputType.LETTERS_AND_SPACE
    assert by_id["shop_name"].input_type == InputType.NAME


def test_letters_still_rejects_symbols() -> None:
    w = _widget(InputType.LETTERS)
    assert not w.valid_char(ch="&")
    assert not w.valid_char(ch=" ")
