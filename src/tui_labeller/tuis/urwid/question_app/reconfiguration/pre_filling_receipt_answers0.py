from copy import deepcopy
from typing import Any, List, Tuple, Union

from hledger_preprocessor.TransactionObjects.Receipt import (
    Receipt,
)
from typeguard import typechecked

from tui_labeller.tuis.urwid.question_app.generator import create_questionnaire
from tui_labeller.tuis.urwid.question_app.reconfiguration.adding_questions import (
    create_new_account_questions_to_add,
    get_last_account_question_index,
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
from tui_labeller.tuis.urwid.receipts.BaseQuestions import BaseQuestions


@typechecked
def build_prefilled_tui(
    *,
    account_infos_str: List[str],
    accounts_without_csv: set[str],
    prefilled_receipt: Receipt,
    current_questions: List[
        Union[
            DateQuestionData,
            VerticalMultipleChoiceQuestionData,
            InputValidationQuestionData,
            HorizontalMultipleChoiceQuestionData,
        ]
    ],
    labelled_receipts: List[Receipt],
) -> QuestionnaireApp:
    """Builds a QuestionnaireApp instance for a pre-filled receipt by inserting
    account question blocks for each transaction in the receipt.

    Args:
        prefilled_receipt (Any): The pre-filled receipt object containing net_bought_items with account transactions.
        labelled_receipts (List[Receipt]): List of labelled receipts for the QuestionnaireApp.

    Returns:
        QuestionnaireApp: The constructed QuestionnaireApp with questions for the pre-filled receipt.
    """
    net_bought_item = prefilled_receipt.net_bought_items
    account_transactions = net_bought_item.account_transactions
    len(account_transactions)

    # Template for account questions
    template = AccountQuestions(
        account_infos_str=account_infos_str,
        accounts_without_csv=accounts_without_csv,  # TODO: verify these can be empty.
    )

    fixed_fields_count = len(BaseQuestions().base_questions)

    current_questions: List[
        Union[
            DateQuestionData,
            VerticalMultipleChoiceQuestionData,
            InputValidationQuestionData,
            HorizontalMultipleChoiceQuestionData,
        ]
    ] = add_missing_account_questions(
        account_infos_str=account_infos_str,
        accounts_without_csv=accounts_without_csv,
        account_transactions=account_transactions,
        template=template,
        fixed_fields_count=fixed_fields_count,
        current_questions=current_questions,
    )

    # Create the QuestionnaireApp
    new_tui: QuestionnaireApp = create_questionnaire(
        questions=current_questions,
        header="Answer the receipt questions.",
        labelled_receipts=labelled_receipts,
    )

    return new_tui


@typechecked
def count_account_question_sets(
    current_questions: List[
        Union[
            DateQuestionData,
            VerticalMultipleChoiceQuestionData,
            InputValidationQuestionData,
            HorizontalMultipleChoiceQuestionData,
        ]
    ],
) -> int:
    """Count the number of account question sets in current_questions.

    Args:
        current_questions: List of current questions, including account questions.

    Returns:
        Number of account question sets (each set assumed to have 5 questions).
    """
    account_question_texts = {
        "Belongs to bank/accounts_without_csv:",
        "Currency:",
        "Amount paid from account:",
        "Change returned to account:",
        "Add another account (y/n)?",
    }
    account_questions = [
        q
        for q in current_questions
        if hasattr(q, "question") and q.question in account_question_texts
    ]
    return len(account_questions) // 5  # Each set has 5 questions


@typechecked
def add_missing_account_questions(
    *,
    account_infos_str: List[str],
    accounts_without_csv: set[str],
    account_transactions: List[Any],  # Assuming transaction has 'account' field
    template: AccountQuestions,
    fixed_fields_count: int,
    current_questions: List[
        Union[
            DateQuestionData,
            VerticalMultipleChoiceQuestionData,
            InputValidationQuestionData,
            HorizontalMultipleChoiceQuestionData,
        ]
    ],
) -> List[
    Union[
        DateQuestionData,
        VerticalMultipleChoiceQuestionData,
        InputValidationQuestionData,
        HorizontalMultipleChoiceQuestionData,
    ]
]:
    """Add account question sets to match the number of transactions.

    Args:
        account_transactions: List of transactions, each requiring one set of account questions.
        template: Template for generating account questions.
        fixed_fields_count: Number of base questions before account questions.
        current_questions: Current list of questions, including one set of account questions by default.

    Returns:
        Updated list of questions with account question sets matching the number of transactions.
    """
    # Count existing account question sets
    existing_sets = count_account_question_sets(current_questions)

    # Number of transactions
    num_transactions = len(account_transactions)

    # Add sets for remaining transactions (num_transactions - existing_sets)
    for i in range(existing_sets, num_transactions):
        transaction = account_transactions[i]

        last_account_idx = get_last_account_question_index(
            account_questions_to_add=template,
            current_questions=current_questions,
        )

        # For the first insertion, insert after base questions
        if last_account_idx == -1:
            last_account_idx = fixed_fields_count - 1

        input(f"accounts_without_csv={accounts_without_csv}")
        # Set available accounts to the specific transaction account
        if (
            transaction.account.to_string() not in account_infos_str
            and transaction.account.to_string() not in accounts_without_csv
        ):
            raise ValueError(
                f"The transaction.account:{transaction.account.to_string()} from"
                " the prefilled receipt should be available in the accounts"
                f" loaded from hledger:{account_infos_str}"
            )

        new_account_questions_to_add: List[
            Union[
                VerticalMultipleChoiceQuestionData,
                InputValidationQuestionData,
                HorizontalMultipleChoiceQuestionData,
            ]
        ] = create_new_account_questions_to_add(
            account_questions_to_add=template,
            available_accounts=template.belongs_to_options,
        )

        # Insert the new account questions
        current_questions = (
            current_questions[: last_account_idx + 1]
            + new_account_questions_to_add
            + current_questions[last_account_idx + 1 :]
        )

    # Verify the final number of account question sets
    final_sets = count_account_question_sets(current_questions)
    assert final_sets == num_transactions, (
        f"Expected {num_transactions} account question sets, but found"
        f" {final_sets}"
    )
    return current_questions


@typechecked
def answer_prefilled_account_questions(
    *,
    account_infos_str: List[str],
    accounts_without_csv: set[str],
    prefilled_answers_to_base_questions: List[Union[None, Tuple[str, Any]]],
    current_questions: List[
        Union[
            DateQuestionData,
            VerticalMultipleChoiceQuestionData,
            InputValidationQuestionData,
            HorizontalMultipleChoiceQuestionData,
        ]
    ],
    nr_of_account_transactions: int,
    prefilled_receipt: Receipt,
    labelled_receipts: List[Receipt],
) -> QuestionnaireApp:
    """Sets pre-filled answers for a receipt in a QuestionnaireApp instance,
    handling both fixed receipt fields and dynamic account transaction fields.
    The function builds the QuestionnaireApp, applies pre-filled answers to
    matching questions and uses account transaction data from the prefilled
    receipt.

    Args:
        pre_filled_receipt_answers (List[Union[None, Tuple[str, Any]]]): A list of pre-filled answers for
            the receipt, where each element is either None or a tuple of (question_text, answer).
        nr_of_account_transactions (int): The number of account transactions to include.
        prefilled_receipt (Any): The receipt object containing net_bought_items with account transactions.
        labelled_receipts (List[Receipt]): List of labelled receipts for creating the QuestionnaireApp.

    Returns:
        None: The function modifies the QuestionnaireApp instance in place.
    """

    # Copy prefilled_answers into new array with answers:
    receipt_answers: List[Union[None, Tuple[str, Any]]] = (
        initialize_receipt_answers(
            prefilled_answers_to_base_questions=prefilled_answers_to_base_questions,
            nr_of_account_transactions=nr_of_account_transactions,
        )
    )
    # receipt_answers: List[Union[None, Tuple[str, Any]]] = deepcopy(
    #     prefilled_answers_to_base_questions
    # )

    # Build the QuestionnaireApp with appropriate questions
    new_tui: QuestionnaireApp = build_prefilled_tui(
        account_infos_str=account_infos_str,
        accounts_without_csv=accounts_without_csv,
        prefilled_receipt=prefilled_receipt,
        current_questions=current_questions,
        labelled_receipts=labelled_receipts,
    )

    # Extract account transactions from prefilled receipt
    net_bought_item = prefilled_receipt.net_bought_items
    net_returned_item = prefilled_receipt.net_returned_items
    account_questions_per_transaction = len(
        AccountQuestions(
            account_infos_str=[], accounts_without_csv=set()
        ).account_questions
    )
    fixed_fields_count = len(BaseQuestions().base_questions)
    new_account_start_idx = fixed_fields_count
    new_account_end_idx = new_account_start_idx + (
        nr_of_account_transactions * account_questions_per_transaction
    )

    # Create new AccountQuestions for each transaction and update pre_filled_receipt_answers
    answer_idx = fixed_fields_count
    if net_bought_item:
        answer_idx = set_answers(
            bought_and_returned_transactions=net_bought_item.account_transactions,
            new_account_end_idx=new_account_end_idx,
            answer_idx=answer_idx,
            receipt_answers=receipt_answers,
        )
    if net_returned_item:
        answer_idx = set_answers(
            bought_and_returned_transactions=net_returned_item.account_transactions,
            new_account_end_idx=new_account_end_idx,
            answer_idx=answer_idx,
            receipt_answers=receipt_answers,
        )

    # Validate pre-filled answers
    # validate_prefilled_answers(
    #     pre_filled_receipt_answers=receipt_answers,
    #     nr_of_account_transactions=nr_of_account_transactions,
    # )

    # Apply answers to TUI
    for idx, input_widget in enumerate(new_tui.inputs):
        widget = input_widget.base_widget
        question_text = widget.question_data.question
        if (
            len(receipt_answers) > idx
            and receipt_answers[idx]
            and question_text == receipt_answers[idx][0]
        ):

            widget.set_answer(receipt_answers[idx][1])

    if len(receipt_answers) != len(new_tui.inputs):
        raise ValueError(
            f"\nnr of answers{len(receipt_answers)} !=  nr of"
            f" tui{len(new_tui.inputs)}"
        )
    return new_tui


@typechecked
def set_answers(
    *,
    bought_and_returned_transactions: List,
    new_account_end_idx: int,
    answer_idx: int,
    receipt_answers: List,
):
    for account_transaction in bought_and_returned_transactions:
        account_questions = AccountQuestions(
            account_infos_str=[],
            accounts_without_csv=set(),
        ).account_questions

        # Set answers for account transaction questions
        for question in account_questions:
            if answer_idx < new_account_end_idx:
                question_text = question.question
                if question_text == "Belongs to bank/accounts_without_csv:":
                    answer = str(account_transaction.account.to_string())
                elif question_text == "Currency:":
                    answer = account_transaction.currency
                elif question_text == "Amount paid from account:":
                    answer = account_transaction.amount_paid
                elif question_text == "Change returned to account:":
                    answer = account_transaction.change_returned
                elif question_text == "Add another account (y/n)?":
                    # Set 'y' for all but the last transaction
                    is_last = answer_idx + 1 == new_account_end_idx
                    answer = "n" if is_last else "y"

                # Update pre_filled_receipt_answers with transaction data
                if answer_idx >= len(receipt_answers):
                    receipt_answers.append(None)
                receipt_answers[answer_idx] = (
                    question_text,
                    answer,
                )
                answer_idx += 1
    return answer_idx


@typechecked
def initialize_receipt_answers(
    *,
    prefilled_answers_to_base_questions: List[Union[None, Tuple[str, Any]]],
    nr_of_account_transactions: int,
) -> List[Union[None, Tuple[str, Any]]]:
    """Initializes the receipt answers list by creating a deep copy of the
    provided base question answers and extending it to the required length
    based on the number of account transactions.

    Args:
        prefilled_answers_to_base_questions (List[Union[None, Tuple[str, Any]]]): The pre-filled answers for base questions.
        nr_of_account_transactions (int): The number of account transactions to account for in the answer list.

    Returns:
        List[Union[None, Tuple[str, Any]]]: A new list initialized with base question answers and extended with None
        for account transaction and remaining questions.
    """
    fixed_fields_count = len(BaseQuestions().base_questions)
    account_questions_per_transaction = len(
        AccountQuestions(
            account_infos_str=[], accounts_without_csv=set()
        ).account_questions
    )
    # TODO: create EndingQuestions object.
    # total_required_answers = fixed_fields_count + (nr_of_account_transactions * account_questions_per_transaction) + len(EndingQuestions().ending_questions)
    total_required_answers = (
        fixed_fields_count
        + (nr_of_account_transactions * account_questions_per_transaction)
        + 4  # For end questions.
    )

    # Create a deep copy of the base question answers
    receipt_answers = deepcopy(prefilled_answers_to_base_questions)

    # Extend the list with None to match the total required length
    while len(receipt_answers) < total_required_answers:
        receipt_answers.append(None)

    return receipt_answers
