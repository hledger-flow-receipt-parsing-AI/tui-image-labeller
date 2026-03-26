import logging
from datetime import timedelta
from typing import Any, Dict, List, Optional, Tuple, Union

from hledger_preprocessor.config.AccountConfig import AccountConfig
from hledger_preprocessor.config.load_config import Config
from hledger_preprocessor.generics.Transaction import Transaction
from hledger_preprocessor.TransactionObjects.Receipt import (
    Receipt,
    WithdrawalMetadata,
)
from typeguard import typechecked
from urwid import AttrMap

logger = logging.getLogger(__name__)

from tui_labeller.tuis.urwid.date_question.DateTimeQuestion import (
    DateTimeQuestion,
)
from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.input_validation.InputValidationQuestion import (
    InputValidationQuestion,
)
from tui_labeller.tuis.urwid.multiple_choice_question.HorizontalMultipleChoiceWidget import (
    HorizontalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.multiple_choice_question.VerticalMultipleChoiceWidget import (
    VerticalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.question_app.addresses.update_addresses import (
    get_initial_complete_list,
)
from tui_labeller.tuis.urwid.question_app.generator import create_questionnaire
from tui_labeller.tuis.urwid.question_app.reconfiguration.adding_questions import (
    handle_add_account,
)
from tui_labeller.tuis.urwid.question_app.reconfiguration.removing_questions import (
    remove_later_account_questions,
)
from tui_labeller.tuis.urwid.question_data_classes import (
    DateQuestionData,
    HorizontalMultipleChoiceQuestionData,
    InputValidationQuestionData,
    VerticalMultipleChoiceQuestionData,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import (
    QuestionnaireApp,
)
from tui_labeller.tuis.urwid.receipts.AccountQuestions import AccountQuestions
from tui_labeller.tuis.urwid.receipts.OptionalQuestions import OptionalQuestions
from tui_labeller.tuis.urwid.receipts.WithdrawalQuestions import (
    WithdrawalQuestions,
)


@typechecked
def has_later_account_question(
    *,
    current_account_question_index: int,
    reconfig_answers: List[Tuple[int, str, str]],
) -> bool:
    """Check if there is a later account-related reconfiguration question."""
    account_question = "Add another account (y/n)?"
    return any(
        index > current_account_question_index and question == account_question
        for index, question, _ in reconfig_answers
    )


@typechecked
def collect_reconfiguration_questions(
    *, tui: "QuestionnaireApp", answered_only: bool
) -> List[Tuple[int, str, str]]:
    """Collect answers from widgets that trigger reconfiguration."""
    reconfig_answers = []
    for index, input_widget in enumerate(tui.inputs):
        widget = input_widget.base_widget
        if isinstance(
            widget, (HorizontalMultipleChoiceWidget, InputValidationQuestion)
        ):
            if widget.question_data.reconfigurer:
                answer = widget.get_answer() if widget.has_answer() else ""
                if not answered_only or (answered_only and answer):
                    reconfig_answers.append(
                        (index, widget.question_data.question, answer)
                    )
    return reconfig_answers


@typechecked
def collect_selected_accounts(tui: "QuestionnaireApp") -> set:
    """Collect currently selected accounts to prevent reuse."""
    selected_accounts = set()
    for input_widget in tui.inputs:
        widget = input_widget.base_widget
        if isinstance(
            widget,
            (VerticalMultipleChoiceWidget, HorizontalMultipleChoiceWidget),
        ):
            if (
                widget.question_data.question.startswith(
                    "Belongs to account/category:"
                )
                and widget.has_answer()
            ):
                answer = widget.get_answer()
                if answer:
                    selected_accounts.add(answer)
    return selected_accounts


@typechecked
def preserve_current_answers(
    *, tui: "QuestionnaireApp"
) -> List[Union[None, Tuple[str, Any]]]:
    """Preserve all current answers from the questionnaire."""
    preserved_answers: List[Union[None, Tuple[str, Any]]] = [
        None for _ in tui.inputs
    ]

    for i, input_widget in enumerate(tui.inputs):
        widget = input_widget.base_widget
        if isinstance(
            widget,
            (
                VerticalMultipleChoiceWidget,
                HorizontalMultipleChoiceWidget,
                DateTimeQuestion,
                InputValidationQuestion,
            ),
        ):
            if widget.has_answer():
                answer = widget.get_answer()
                if answer != "":
                    preserved_answers[i] = (
                        widget.question_data.question,
                        answer,
                    )
    return preserved_answers


@typechecked
def handle_manual_address_questions(
    *,
    tui: "QuestionnaireApp",
    optional_questions: "OptionalQuestions",
    current_questions: list,
    preserved_answers: List[Union[None, Tuple[str, Any]]],
) -> "QuestionnaireApp":
    """Add or remove manual address questions based on the address selector
    answer."""
    address_selector_question = "Select Shop Address:"
    address_selector_index = None
    address_selector_answer = None

    # Find the address selector question and its answer
    for index, input_widget in enumerate(tui.inputs):
        widget = input_widget.base_widget
        if (
            isinstance(widget, VerticalMultipleChoiceWidget)
            and widget.question_data.question == address_selector_question
            and widget.has_answer()
        ):
            address_selector_index = index
            address_selector_answer = widget.get_answer()
            break

    # Get manual address question identifiers
    manual_address_questions = optional_questions.get_manual_address_questions()
    manual_question_ids = {q.question for q in manual_address_questions}

    # Check if manual address questions are currently present
    current_question_ids = {
        q.base_widget.question_data.question for q in current_questions
    }
    has_manual_questions = any(
        q in manual_question_ids for q in current_question_ids
    )

    # If "manual address" is selected and manual questions are not present, add them
    if address_selector_answer == "manual address" and not has_manual_questions:

        # Find the position to insert manual address questions (after address selector)
        insert_index = (
            address_selector_index + 1
            if address_selector_index is not None
            else len(current_questions)
        )
        new_questions = (
            current_questions[:insert_index]
            + manual_address_questions
            + current_questions[insert_index:]
        )
        converted_questions: List[
            Union[
                DateQuestionData,
                InputValidationQuestionData,
                VerticalMultipleChoiceQuestionData,
                HorizontalMultipleChoiceQuestionData,
            ]
        ] = []

        for i, q in enumerate(new_questions):
            if isinstance(q, AttrMap):
                base_widget = q.base_widget
                if not isinstance(
                    base_widget.question_data,
                    (
                        DateQuestionData,
                        InputValidationQuestionData,
                        VerticalMultipleChoiceQuestionData,
                        HorizontalMultipleChoiceQuestionData,
                    ),
                ):
                    raise ValueError(
                        f"Unexpected type:{base_widget.question_data}"
                    )

                converted_questions.append(base_widget.question_data)
            elif not isinstance(
                q,
                (
                    DateQuestionData,
                    InputValidationQuestionData,
                    VerticalMultipleChoiceQuestionData,
                    HorizontalMultipleChoiceQuestionData,
                ),
            ):
                converted_questions.append(q.question_data)
            else:
                converted_questions.append(q)

        # Create new questionnaire with updated questions
        new_tui = create_questionnaire(
            questions=converted_questions,
            header="Answer the receipt questions.",
            labelled_receipts=optional_questions.labelled_receipts,
        )
        # Restore preserved answers
        return set_default_focus_and_answers(
            tui=new_tui,
            preserved_answers=preserved_answers,
        )
    # No changes needed if manual address is not selected
    return tui


@typechecked
def remove_manual_address_questions(
    *,
    tui: "QuestionnaireApp",
    optional_questions: "OptionalQuestions",
    current_questions: list,
    preserved_answers: List[Union[None, Tuple[str, Any]]],
) -> "QuestionnaireApp":
    """Remove manual address questions when address selector changes to a non-
    manual address."""
    address_selector_question = "Select Shop Address:"
    address_selector_answer = None

    # Find the address selector question and its answer
    for index, input_widget in enumerate(tui.inputs):
        widget = input_widget.base_widget
        if (
            isinstance(widget, VerticalMultipleChoiceWidget)
            and widget.question_data.question == address_selector_question
            and widget.has_answer()
        ):
            address_selector_answer = widget.get_answer()
            break

    # Get manual address question identifiers
    manual_address_questions = optional_questions.get_manual_address_questions()
    manual_question_ids = {q.question for q in manual_address_questions}

    # Check if manual address questions are currently present
    current_question_ids = {
        q.base_widget.question_data.question for q in current_questions
    }
    has_manual_questions = any(
        q in manual_question_ids for q in current_question_ids
    )

    # If a non-manual address is selected and manual questions are present, remove them
    if address_selector_answer != "manual address" and has_manual_questions:
        # Filter out manual address questions
        new_questions = [
            q
            for q in current_questions
            if q.base_widget.question_data.question not in manual_question_ids
        ]
        # Preserve the address selector answer
        preserved_answers = [
            ans
            for ans in preserved_answers
            if ans is None or ans[0] not in manual_question_ids
        ]
        # Create new questionnaire with updated questions
        new_tui = create_questionnaire(
            questions=[q.base_widget.question_data for q in new_questions],
            header="Answer the receipt questions.",
            labelled_receipts=optional_questions.labelled_receipts,
        )
        # Restore preserved answers
        return set_default_focus_and_answers(
            tui=new_tui,
            preserved_answers=preserved_answers,
        )
    return tui


@typechecked
def handle_optional_questions(
    *,
    tui: "QuestionnaireApp",
    optional_questions: "OptionalQuestions",
    current_questions: list,
    preserved_answers: List[Union[None, Tuple[str, Any]]],
) -> "QuestionnaireApp":
    """Handle the addition or focusing of optional questions."""
    optional_question_identifiers = {
        oq.question for oq in optional_questions.optional_questions
    }

    if not any(
        q.base_widget.question_data.question in optional_question_identifiers
        for q in current_questions
    ):
        new_questions = (
            current_questions + optional_questions.optional_questions
        )
        great_tui = create_questionnaire(
            questions=[q.base_widget.question_data for q in new_questions],
            header="Answer the receipt questions.",
            labelled_receipts=optional_questions.labelled_receipts,
        )
        return set_default_focus_and_answers(
            tui=great_tui, preserved_answers=preserved_answers
        )
    return tui


@typechecked
def set_default_focus_and_answers(
    tui: "QuestionnaireApp",
    preserved_answers: List[Union[None, Tuple[str, Any]]],
) -> "QuestionnaireApp":
    """Set preserved answers and focus on the next unanswered question."""
    matched_preserved_indices: set = set()
    matched_widget_indices: set = set()
    # First pass: positional matching (position AND question text must match).
    for i, input_widget in enumerate(tui.inputs):
        widget = input_widget.base_widget
        question_text = widget.question_data.question
        if i < len(preserved_answers):
            if (
                preserved_answers[i] is not None
                and preserved_answers[i][0] == question_text
            ):
                widget.set_answer(preserved_answers[i][1])
                matched_preserved_indices.add(i)
                matched_widget_indices.add(i)

    # Second pass: name-based fallback for answers shifted by question
    # insertion/removal (e.g. withdrawal toggle injecting questions).
    unmatched = [
        pa for i, pa in enumerate(preserved_answers)
        if pa is not None and i not in matched_preserved_indices
    ]
    if unmatched:
        answer_map: dict = {}
        for q_text, ans in unmatched:
            answer_map[q_text] = ans
        for wi, input_widget in enumerate(tui.inputs):
            if wi in matched_widget_indices:
                continue
            widget = input_widget.base_widget
            q = widget.question_data.question
            if q in answer_map:
                widget.set_answer(answer_map[q])
    return tui


CATEGORY_QUESTION = "\nBookkeeping expense category:"
WITHDRAWAL_TOGGLE_QUESTION = "Is this a withdrawal? (y/n)"
WITHDRAWAL_SOURCE_QUESTION = "Withdrawal source account:"
ATM_FEE_QUESTION = "ATM operator fee (in withdrawn currency, 0 if none):"
BANK_FEE_QUESTION = "Bank fee (in source currency, 0 if none):"
AMOUNT_PAID_QUESTION = "Amount paid from account:"


@typechecked
def _has_withdrawal_questions(*, tui: "QuestionnaireApp") -> bool:
    """Check if withdrawal questions are already present in the TUI."""
    for input_widget in tui.inputs:
        widget = input_widget.base_widget
        if hasattr(widget, "question_data"):
            if widget.question_data.question == WITHDRAWAL_SOURCE_QUESTION:
                return True
    return False


@typechecked
def _get_withdrawal_question_ids(
    *, withdrawal_questions: "WithdrawalQuestions"
) -> set:
    """Get the set of all possible withdrawal question strings."""
    ids = {q.question for q in withdrawal_questions.withdrawal_questions}
    ids.add(withdrawal_questions.get_atm_fee_question().question)
    ids.add(withdrawal_questions.get_exchange_rate_question().question)
    ids.add(withdrawal_questions.get_bank_fee_question().question)
    return ids


@typechecked
def _has_category_question(*, tui: "QuestionnaireApp") -> bool:
    """Check if the category question is present in the TUI."""
    for input_widget in tui.inputs:
        widget = input_widget.base_widget
        if hasattr(widget, "question_data"):
            if widget.question_data.question == CATEGORY_QUESTION:
                return True
    return False


@typechecked
def handle_withdrawal_toggle(
    *,
    tui: "QuestionnaireApp",
    withdrawal_questions: "WithdrawalQuestions",
    preserved_answers: List[Union[None, Tuple[str, Any]]],
    labelled_receipts: List[Receipt],
    toggle_answer: str,
) -> "QuestionnaireApp":
    """Handle reconfiguration when the withdrawal toggle is answered.

    When 'y': removes category question, injects withdrawal questions.
    When 'n': removes withdrawal questions, re-adds category question.
    """
    has_withdrawal = _has_withdrawal_questions(tui=tui)
    has_category = _has_category_question(tui=tui)

    # Questions to hide for withdrawals (source-side "Amount debited"
    # replaces the wallet-side "Amount paid").
    withdrawal_hidden_qs = {CATEGORY_QUESTION, AMOUNT_PAID_QUESTION}

    if toggle_answer.lower() == "y" and not has_withdrawal:
        # Find the withdrawal toggle question and insert withdrawal
        # questions after it, removing category and amount paid.
        toggle_index = None
        for i, input_widget in enumerate(tui.inputs):
            widget = input_widget.base_widget
            if (
                isinstance(widget, HorizontalMultipleChoiceWidget)
                and widget.question_data.question == WITHDRAWAL_TOGGLE_QUESTION
            ):
                toggle_index = i
                break

        if toggle_index is None:
            return tui

        # Build new question list: skip hidden questions, add withdrawal questions.
        current_q_data = [
            inp.base_widget.question_data
            for inp in tui.inputs[: toggle_index + 1]
        ]
        current_q_data.extend(withdrawal_questions.withdrawal_questions)
        remaining = [
            inp.base_widget.question_data
            for inp in tui.inputs[toggle_index + 1 :]
            if inp.base_widget.question_data.question not in withdrawal_hidden_qs
        ]
        current_q_data.extend(remaining)

        new_tui = create_questionnaire(
            questions=current_q_data,
            header="Answer the receipt questions.",
            labelled_receipts=labelled_receipts,
        )
        return set_default_focus_and_answers(
            tui=new_tui, preserved_answers=preserved_answers
        )

    elif toggle_answer.lower() == "n" and has_withdrawal:
        # Toggle changed to 'n' — remove withdrawal questions,
        # re-add category and amount paid questions.
        withdrawal_ids = _get_withdrawal_question_ids(
            withdrawal_questions=withdrawal_questions
        )
        new_q_data = [
            inp.base_widget.question_data
            for inp in tui.inputs
            if inp.base_widget.question_data.question not in withdrawal_ids
        ]

        from tui_labeller.tuis.urwid.receipts.BaseQuestions import (
            BaseQuestions,
        )

        # Re-add category question after the toggle if missing.
        if not has_category:
            toggle_idx = None
            for i, q in enumerate(new_q_data):
                if q.question == WITHDRAWAL_TOGGLE_QUESTION:
                    toggle_idx = i
                    break
            if toggle_idx is not None:
                new_q_data.insert(
                    toggle_idx + 1, BaseQuestions().get_category_question()
                )

        # Re-add "Amount paid from account:" before "Change returned".
        has_amount_paid = any(
            q.question == AMOUNT_PAID_QUESTION for q in new_q_data
        )
        if not has_amount_paid:
            change_idx = None
            for i, q in enumerate(new_q_data):
                if q.question == "Change returned to account:":
                    change_idx = i
                    break
            if change_idx is not None:
                new_q_data.insert(
                    change_idx,
                    InputValidationQuestionData(
                        question=AMOUNT_PAID_QUESTION,
                        input_type=InputType.FLOAT,
                        ai_suggestions=[],
                        history_suggestions=[],
                        ans_required=True,
                        reconfigurer=False,
                        terminator=False,
                    ),
                )

        new_tui = create_questionnaire(
            questions=new_q_data,
            header="Answer the receipt questions.",
            labelled_receipts=labelled_receipts,
        )
        return set_default_focus_and_answers(
            tui=new_tui, preserved_answers=preserved_answers
        )

    return tui


AMOUNT_DEBITED_QUESTION = "Amount debited from source account:"


@typechecked
def _has_post_account_withdrawal_questions(*, tui: "QuestionnaireApp") -> bool:
    """Check if post-account withdrawal questions (ATM fee etc.) are present."""
    for input_widget in tui.inputs:
        widget = input_widget.base_widget
        if hasattr(widget, "question_data"):
            if widget.question_data.question == ATM_FEE_QUESTION:
                return True
    return False


@typechecked
def _has_exchange_rate_question(*, tui: "QuestionnaireApp") -> bool:
    """Check if the exchange rate question is present in the TUI."""
    for input_widget in tui.inputs:
        widget = input_widget.base_widget
        if hasattr(widget, "question_data"):
            if widget.question_data.question == "Exchange rate (1 source = X destination):":
                return True
    return False


@typechecked
def _get_tui_answer(tui: "QuestionnaireApp", question_str: str) -> Optional[str]:
    """Read a specific answer from the TUI by question string."""
    for inp in tui.inputs:
        w = inp.base_widget
        if hasattr(w, "question_data") and w.question_data.question == question_str:
            if w.has_answer():
                return str(w.get_answer())
    return None


@typechecked
def handle_post_account_withdrawal_questions(
    *,
    tui: "QuestionnaireApp",
    withdrawal_questions: "WithdrawalQuestions",
    preserved_answers: List[Union[None, Tuple[str, Any]]],
    labelled_receipts: List[Receipt],
) -> "QuestionnaireApp":
    """Inject ATM fee (+ exchange rate + bank fee if foreign) after the last
    'Add another account = n', before optional questions.

    Also re-checks whether exchange rate questions need to be added or
    removed when currencies change.
    """
    # Read source and target currencies to detect foreign withdrawal.
    source_currency = _get_tui_answer(tui, "Source account currency:")
    target_currency = _get_tui_answer(tui, "Currency:")
    is_foreign = (
        source_currency is not None
        and target_currency is not None
        and source_currency != target_currency
    )

    has_post = _has_post_account_withdrawal_questions(tui=tui)
    has_exchange = _has_exchange_rate_question(tui=tui)

    # Check if we need to rebuild: either not yet injected, or foreign
    # status changed (exchange rate present but not foreign, or vice versa).
    needs_rebuild = (
        not has_post
        or (is_foreign and not has_exchange)
        or (not is_foreign and has_exchange)
    )
    if not needs_rebuild:
        return tui

    # Find the last "Add another account (y/n)?" position.
    last_account_idx = None
    for i, inp in enumerate(tui.inputs):
        if inp.base_widget.question_data.question == "Add another account (y/n)?":
            last_account_idx = i

    if last_account_idx is None:
        return tui

    # Build the desired post-account questions.
    post_questions = [
        withdrawal_questions.get_atm_fee_question(),
        withdrawal_questions.get_bank_fee_question(),
    ]
    if is_foreign:
        post_questions.append(withdrawal_questions.get_exchange_rate_question())
    post_question_ids = {q.question for q in post_questions}

    # Strip any existing post-account withdrawal questions from the rest.
    all_post_ids = {
        ATM_FEE_QUESTION,
        "Exchange rate (1 source = X destination):",
        "Bank fee (in source currency, 0 if none):",
    }

    # Build new question list: up to last account question, then new post
    # questions, then the rest (without old post-account withdrawal questions).
    new_q_data = [
        inp.base_widget.question_data
        for inp in tui.inputs[: last_account_idx + 1]
    ]
    new_q_data.extend(post_questions)
    new_q_data.extend([
        inp.base_widget.question_data
        for inp in tui.inputs[last_account_idx + 1 :]
        if inp.base_widget.question_data.question not in all_post_ids
    ])

    new_tui = create_questionnaire(
        questions=new_q_data,
        header="Answer the receipt questions.",
        labelled_receipts=labelled_receipts,
    )
    new_tui = set_default_focus_and_answers(
        tui=new_tui, preserved_answers=preserved_answers
    )

    # Prefill "Change returned to account:" with
    # amount_debited - atm_fee - bank_fee for domestic withdrawals.
    if not is_foreign:
        amount_debited = _get_tui_answer(new_tui, AMOUNT_DEBITED_QUESTION)
        atm_fee_val = _get_tui_answer(new_tui, ATM_FEE_QUESTION)
        bank_fee_val = _get_tui_answer(new_tui, BANK_FEE_QUESTION)
        if amount_debited is not None:
            fees = (
                float(atm_fee_val) if atm_fee_val is not None else 0.0
            ) + (
                float(bank_fee_val) if bank_fee_val is not None else 0.0
            )
            change = float(amount_debited) - fees
            for inp in new_tui.inputs:
                w = inp.base_widget
                if (
                    hasattr(w, "question_data")
                    and w.question_data.question == "Change returned to account:"
                    and not w.has_answer()
                ):
                    w.set_answer(change)
                    break

    # Domestic balance validation: amount_debited == change + atm_fee + bank_fee.
    if not is_foreign:
        amount_debited = _get_tui_answer(new_tui, AMOUNT_DEBITED_QUESTION)
        change_returned = _get_tui_answer(new_tui, "Change returned to account:")
        atm_fee = _get_tui_answer(new_tui, ATM_FEE_QUESTION)
        bank_fee = _get_tui_answer(new_tui, BANK_FEE_QUESTION)

        if all(
            v is not None
            for v in [amount_debited, change_returned, atm_fee, bank_fee]
        ):
            debited = round(float(amount_debited), 2)
            expected = round(
                float(change_returned) + float(atm_fee) + float(bank_fee), 2
            )
            for inp in new_tui.inputs:
                w = inp.base_widget
                if (
                    hasattr(w, "question_data")
                    and w.question_data.question == BANK_FEE_QUESTION
                ):
                    if debited != expected:
                        inp.set_attr_map({None: "error"})
                    else:
                        inp.set_attr_map({None: "normal"})
                    break

    return new_tui


def _try_background_withdrawal_match(
    *,
    tui,
    config: Optional["Config"],
    csv_transactions_per_account: Optional[
        Dict[AccountConfig, Dict[int, List[Transaction]]]
    ],
) -> None:
    """Search CSV transactions for a withdrawal match and pre-fill the amount.

    Runs after the user selects a withdrawal source account.  Looks for
    CSV transactions near the receipt date whose amount could match.
    If exactly one match is found, sets the default on the "Amount
    debited from source account" question.
    """
    if config is None or csv_transactions_per_account is None:
        return

    from hledger_preprocessor.matching.helper import (
        get_transactions_in_date_range,
    )

    # Collect the source account answer and the receipt date from the TUI.
    source_account_str: Optional[str] = None
    receipt_date = None
    receipt_amount: Optional[float] = None

    for inp in tui.inputs:
        w = inp.base_widget
        q = w.question_data.question
        if q == WITHDRAWAL_SOURCE_QUESTION and w.has_answer():
            source_account_str = str(w.get_answer())
        elif q == "Receipt date and time:\n" and w.has_answer():
            receipt_date = w.get_answer()
        elif q == "Amount paid from account:" and w.has_answer():
            try:
                receipt_amount = float(w.get_answer())
            except (ValueError, TypeError):
                pass

    if source_account_str is None or receipt_date is None:
        return

    # Find the matching AccountConfig for the source account string.
    matching_account_config: Optional[AccountConfig] = None
    for ac in csv_transactions_per_account:
        if ac.account.to_string() == source_account_str and ac.has_input_csv():
            matching_account_config = ac
            break

    if matching_account_config is None:
        return

    txns_per_year = csv_transactions_per_account.get(
        matching_account_config, {}
    )
    if not txns_per_year:
        return

    # Search within configured date margin (default 7 days).
    day_margin = config.matching_algo.days if hasattr(config, "matching_algo") else 7
    candidates = get_transactions_in_date_range(
        transactions_per_year=txns_per_year,
        target_date=receipt_date,
        date_margin=timedelta(days=day_margin),
    )

    if not candidates:
        return

    # If the user already entered an amount on the receipt side, narrow
    # candidates by absolute value (within the configured amount margin).
    if receipt_amount is not None and receipt_amount > 0:
        amount_margin = (
            config.matching_algo.amount_range
            if hasattr(config, "matching_algo")
            else 0.05
        )
        narrowed = []
        for txn in candidates:
            net = abs(txn.tendered_amount_out - txn.change_returned)
            if abs(net - receipt_amount) <= amount_margin * max(receipt_amount, 0.01):
                narrowed.append(txn)
        if narrowed:
            candidates = narrowed

    # Pick the best match: prefer exact count == 1, else pick the one
    # closest in time to the receipt date.
    if len(candidates) == 1:
        best = candidates[0]
    else:
        best = min(
            candidates,
            key=lambda t: abs((t.the_date - receipt_date).total_seconds()),
        )

    matched_amount = abs(best.tendered_amount_out - best.change_returned)
    matched_date_str = best.the_date.strftime("%Y-%m-%d")

    # Pre-fill the "Amount debited from source account" question.
    for inp in tui.inputs:
        w = inp.base_widget
        if w.question_data.question == AMOUNT_DEBITED_QUESTION:
            if not w.has_answer() or w.get_answer() == "":
                w.set_answer(matched_amount)
                logger.info(
                    "Background match: pre-filled amount %.2f from CSV"
                    " transaction on %s",
                    matched_amount,
                    matched_date_str,
                )
            break


def _prefill_withdrawal_from_metadata(
    *,
    tui: "QuestionnaireApp",
    metadata: "WithdrawalMetadata",
) -> None:
    """Set withdrawal question answers from existing WithdrawalMetadata."""
    source_acct = metadata.source_account_transaction.account.to_string()
    source_currency = metadata.source_account_transaction.account.base_currency.value
    source_amount = abs(metadata.source_account_transaction.tendered_amount_out)

    question_values = {
        "ATM operator fee (in withdrawn currency, 0 if none):": float(
            metadata.atm_operator_fee
        ),
        WITHDRAWAL_SOURCE_QUESTION: source_acct,
        "Source account currency:": source_currency,
        "Amount debited from source account:": float(source_amount),
        "Bank fee (in source currency, 0 if none):": float(
            metadata.bank_fx_fee
        ),
    }
    if metadata.exchange_rate is not None:
        question_values["Exchange rate (1 source = X destination):"] = float(
            metadata.exchange_rate
        )

    for inp in tui.inputs:
        w = inp.base_widget
        q = w.question_data.question
        if q in question_values:
            w.set_answer(question_values[q])


@typechecked
def get_configuration(
    tui: "QuestionnaireApp",
    account_questions: "AccountQuestions",
    optional_questions: "OptionalQuestions",
    labelled_receipts: List[Receipt],
    withdrawal_questions: Optional["WithdrawalQuestions"] = None,
    config: Optional["Config"] = None,
    csv_transactions_per_account: Optional[
        Dict[AccountConfig, Dict[int, List[Transaction]]]
    ] = None,
    prefilled_receipt: Optional[Receipt] = None,
) -> "QuestionnaireApp":
    """Reconfigure the questionnaire based on user answers."""
    reconfig_answers = collect_reconfiguration_questions(
        tui=tui, answered_only=False
    )
    selected_accounts = collect_selected_accounts(tui)
    preserved_answers = preserve_current_answers(tui=tui)
    current_questions = tui.questions
    transaction_question = (
        account_questions.get_transaction_question_identifier()
    )

    is_address_selector_focused: bool = is_at_address_selector(tui=tui)
    # Handle manual address questions if the address selector is focused
    if is_address_selector_focused:
        tui = handle_manual_address_questions(
            tui=tui,
            optional_questions=optional_questions,
            current_questions=tui.inputs,
            preserved_answers=preserved_answers,
        )
        # Remove manual address questions if a non-manual address is selected
        tui = remove_manual_address_questions(
            tui=tui,
            optional_questions=optional_questions,
            current_questions=tui.inputs,
            preserved_answers=preserved_answers,
        )

    # Handle withdrawal toggle reconfigurer.
    for question_nr, question_str, answer in reconfig_answers:
        if question_str == WITHDRAWAL_TOGGLE_QUESTION and withdrawal_questions is not None:
            tui = handle_withdrawal_toggle(
                tui=tui,
                withdrawal_questions=withdrawal_questions,
                preserved_answers=preserve_current_answers(tui=tui),
                labelled_receipts=labelled_receipts,
                toggle_answer=str(answer),
            )
            # Prefill withdrawal questions from existing receipt metadata.
            if (
                prefilled_receipt is not None
                and prefilled_receipt.withdrawal_metadata is not None
            ):
                _prefill_withdrawal_from_metadata(
                    tui=tui,
                    metadata=prefilled_receipt.withdrawal_metadata,
                )
            # Re-collect after potential reconfiguration.
            preserved_answers = preserve_current_answers(tui=tui)

    # Update address list whenever reconfiguration runs (e.g. after
    # answering the category question) so the shop addresses reflect the
    # current category immediately.
    update_address_list(
        tui=tui,
        account_questions=account_questions,
        labelled_receipts=labelled_receipts,
    )

    # Background matching: try to pre-fill withdrawal amount from CSV.
    if _has_withdrawal_questions(tui=tui):
        _try_background_withdrawal_match(
            tui=tui,
            config=config,
            csv_transactions_per_account=csv_transactions_per_account,
        )

    # Process account-related reconfiguration answers
    reconfig_answers = collect_reconfiguration_questions(
        tui=tui, answered_only=False
    )
    for question_nr, question_str, answer in reconfig_answers:
        if question_str != transaction_question:
            continue  # Only process "Add another account (y/n)?" questions

        has_later_reconfig = has_later_account_question(
            current_account_question_index=question_nr,
            reconfig_answers=reconfig_answers,
        )

        if answer == "y" and not has_later_reconfig:
            # Add a new block of account questions
            return handle_add_account(
                account_questions_to_add=account_questions,
                current_questions=current_questions,
                preserved_answers=preserved_answers,
                selected_accounts=selected_accounts,
                labelled_receipts=labelled_receipts,
            )
        elif answer == "y" and has_later_reconfig:
            pass
        elif answer == "n":
            update_address_list(
                tui=tui,
                account_questions=account_questions,
                labelled_receipts=labelled_receipts,
            )
            if has_later_reconfig:
                # Remove subsequent account questions
                preserved_answers = remove_later_account_questions(
                    tui=tui,
                    account_questions=account_questions,
                    start_question_nr=question_nr,
                    preserved_answers=preserved_answers,
                )

            # Inject post-account withdrawal questions (ATM fee,
            # exchange rate, bank fee) if this is a withdrawal receipt.
            if (
                _has_withdrawal_questions(tui=tui)
                and withdrawal_questions is not None
            ):
                tui = handle_post_account_withdrawal_questions(
                    tui=tui,
                    withdrawal_questions=withdrawal_questions,
                    preserved_answers=preserve_current_answers(tui=tui),
                    labelled_receipts=labelled_receipts,
                )
                # Prefill post-account withdrawal answers from metadata.
                if (
                    prefilled_receipt is not None
                    and prefilled_receipt.withdrawal_metadata is not None
                ):
                    _prefill_withdrawal_from_metadata(
                        tui=tui,
                        metadata=prefilled_receipt.withdrawal_metadata,
                    )
                preserved_answers = preserve_current_answers(tui=tui)

            if has_later_reconfig:
                tui = handle_optional_questions(
                    tui=tui,
                    optional_questions=optional_questions,
                    current_questions=tui.inputs,
                    preserved_answers=preserved_answers,
                )

    # Re-check post-account withdrawal questions on every pass (handles
    # currency changes that toggle foreign status after initial injection).
    if (
        _has_withdrawal_questions(tui=tui)
        and _has_post_account_withdrawal_questions(tui=tui)
        and withdrawal_questions is not None
    ):
        tui = handle_post_account_withdrawal_questions(
            tui=tui,
            withdrawal_questions=withdrawal_questions,
            preserved_answers=preserve_current_answers(tui=tui),
            labelled_receipts=labelled_receipts,
        )
        if (
            prefilled_receipt is not None
            and prefilled_receipt.withdrawal_metadata is not None
        ):
            _prefill_withdrawal_from_metadata(
                tui=tui,
                metadata=prefilled_receipt.withdrawal_metadata,
            )
        preserved_answers = preserve_current_answers(tui=tui)

    # Set focus to the next unanswered question
    return set_default_focus_and_answers(tui, preserved_answers)


@typechecked
def is_at_address_selector(*, tui: QuestionnaireApp) -> bool:
    focused_widget = tui.get_focus_widget()

    if isinstance(focused_widget, VerticalMultipleChoiceWidget):
        if focused_widget.question_data.question == "Select Shop Address:":
            return True
    return False


@typechecked
def get_category(*, tui: "QuestionnaireApp") -> Optional[str]:
    """Retrieve the selected category from the account questions in the
    questionnaire.

    Args:
        tui: The QuestionnaireApp instance containing the input widgets.

    Returns:
        The selected category if found, or None when the category question
        is absent (e.g. withdrawal receipts).
    """
    for i, input_widget in enumerate(tui.inputs):
        widget = input_widget.base_widget
        if isinstance(
            widget,
            (InputValidationQuestion),
        ):

            if "Bookkeeping expense category:" in widget.question_data.question:
                if not widget.has_answer():
                    raise ValueError("Must have category by now.")
                answer = widget.get_answer()
                if answer:
                    return answer
                if not widget.has_answer():
                    raise ValueError(
                        "Cannot allow empty category at this point."
                    )
    # Category question may be absent for withdrawal receipts.
    return None


@typechecked
def update_address_list(
    *,
    tui: "QuestionnaireApp",
    account_questions: "AccountQuestions",
    labelled_receipts: List[Receipt],
) -> None:
    """Update the address selector's choices based on the selected category.

    Args:
        tui: The QuestionnaireApp instance containing the input widgets.
        account_questions: The AccountQuestions instance containing question data.
        labelled_receipts: List of Receipt objects for generating shop choices.
    """

    try:
        category = get_category(tui=tui)
    except ValueError:
        # Category question exists but hasn't been answered yet — skip.
        return
    if category is None:
        # Withdrawal receipts don't have a category question — skip address
        # filtering.
        return

    address_selector_question = "Select Shop Address:"

    # Find the address selector widget
    for input_widget in tui.inputs:
        widget = input_widget.base_widget
        if (
            isinstance(widget, VerticalMultipleChoiceWidget)
            and widget.question_data.question == address_selector_question
        ):
            # Get updated choices based on the selected category
            choices, shop_ids = get_initial_complete_list(
                labelled_receipts=labelled_receipts,
                category_input=category,
            )
            # Update the widget's choices and shop_ids
            widget.question_data.choices = choices
            if widget.question_data.extra_data is None:
                widget.question_data.extra_data = {}
            widget.question_data.extra_data["shop_ids"] = shop_ids
            # Refresh the widget to reflect the new choices
            widget.refresh_choices()
            break
