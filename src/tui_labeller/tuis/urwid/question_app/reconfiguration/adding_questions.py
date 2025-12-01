from typing import Any, List, Tuple, Union

from hledger_preprocessor.TransactionObjects.Receipt import (
    Receipt,
)
from typeguard import typechecked

from tui_labeller.tuis.urwid.question_app.generator import create_questionnaire
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


@typechecked
def handle_add_account(
    account_questions_to_add: "AccountQuestions",
    current_questions: List[
        Union[
            DateQuestionData,
            VerticalMultipleChoiceQuestionData,
            InputValidationQuestionData,
            HorizontalMultipleChoiceQuestionData,
        ]
    ],
    preserved_answers: List[Union[None, Tuple[str, Any]]],
    selected_accounts: set,
    labelled_receipts: List[Receipt],
) -> "QuestionnaireApp":
    """Handle the addition of a new account question."""

    last_account_idx: int = get_last_account_question_index(
        account_questions_to_add=account_questions_to_add,
        current_questions=current_questions,
    )

    available_accounts: List[str] = get_available_accounts(
        account_questions_to_add=account_questions_to_add,
        selected_accounts=selected_accounts,
    )

    # Create new AccountQuestions with filtered account_infos
    new_account_questions_to_add: List[
        Union[
            VerticalMultipleChoiceQuestionData,
            InputValidationQuestionData,
            HorizontalMultipleChoiceQuestionData,
        ]
    ] = create_new_account_questions_to_add(
        account_questions_to_add=account_questions_to_add,
        available_accounts=available_accounts,
    )

    new_tui: QuestionnaireApp = add_emtpy_shell_account_questions_into_tui(
        current_questions=current_questions,
        last_account_idx=last_account_idx,
        new_account_questions_to_add=new_account_questions_to_add,
        labelled_receipts=labelled_receipts,
    )

    # Calculate the range of indices for new account questions
    new_account_start_idx = last_account_idx + 1
    new_account_end_idx = new_account_start_idx + len(
        new_account_questions_to_add
    )
    actually_set_answers(
        preserved_answers=preserved_answers,
        new_account_start_idx=new_account_start_idx,
        new_account_end_idx=new_account_end_idx,
        new_tui=new_tui,
    )
    return new_tui


@typechecked
def add_emtpy_shell_account_questions_into_tui(
    *,
    current_questions: List[
        Union[
            DateQuestionData,
            VerticalMultipleChoiceQuestionData,
            InputValidationQuestionData,
            HorizontalMultipleChoiceQuestionData,
        ]
    ],
    last_account_idx: int,
    new_account_questions_to_add: List[
        Union[
            VerticalMultipleChoiceQuestionData,
            InputValidationQuestionData,
            HorizontalMultipleChoiceQuestionData,
        ]
    ],
    labelled_receipts: List[Receipt],
) -> QuestionnaireApp:

    # Insert new_account_questions_to_add into current_questions at last_account_idx + 1
    new_questions = (
        current_questions[: last_account_idx + 1]
        + new_account_questions_to_add
        + current_questions[last_account_idx + 1 :]
    )

    new_tui: QuestionnaireApp = create_questionnaire(
        questions=new_questions,
        header="Answer the receipt questions.",
        labelled_receipts=labelled_receipts,
    )
    return new_tui


@typechecked
def get_available_accounts(
    *, account_questions_to_add: "AccountQuestions", selected_accounts: set[str]
) -> List[str]:
    available_accounts = [
        acc
        for acc in account_questions_to_add.belongs_to_options
        if acc not in selected_accounts
    ]
    if not available_accounts:
        raise ValueError(
            "Cannot add another account, as there aren't any unpicked accounts"
            " left."
        )
    return available_accounts


@typechecked
def create_new_account_questions_to_add(
    *,
    account_questions_to_add: "AccountQuestions",
    available_accounts: List[str],
) -> List[
    Union[
        VerticalMultipleChoiceQuestionData,
        InputValidationQuestionData,
        HorizontalMultipleChoiceQuestionData,
    ]
]:
    new_account_questions_to_add: List[
        Union[
            VerticalMultipleChoiceQuestionData,
            InputValidationQuestionData,
            HorizontalMultipleChoiceQuestionData,
        ]
    ] = AccountQuestions(
        account_infos_str=available_accounts,  # Only include available accounts
        accounts_without_csv=account_questions_to_add.accounts_without_csv,  # TODO: verify this is necessary and correct.
    ).account_questions

    for new_account_question in new_account_questions_to_add:
        if isinstance(new_account_question, VerticalMultipleChoiceQuestionData):
            if (
                new_account_question.question
                == "Belongs to bank/accounts_without_csv:"
            ):
                # TODO: ensure the pre-filled receipt answer exists within the available accounts.
                new_account_question.choices = available_accounts  # TODO: ensure they are all the accounts.

    return new_account_questions_to_add


@typechecked
def get_last_account_question_index(
    *,
    account_questions_to_add: "AccountQuestions",
    current_questions: List[
        Union[
            DateQuestionData,
            VerticalMultipleChoiceQuestionData,
            InputValidationQuestionData,
            HorizontalMultipleChoiceQuestionData,
        ]
    ],
) -> int:
    # Finds the highest index in current_questions where a question matches any in account_questions_to_add.account_questions. Returns -1 if no match is found.
    last_account_idx: int = max(
        (
            i
            for i, q in enumerate(current_questions)
            if q.question
            in {q.question for q in account_questions_to_add.account_questions}
        ),
        default=-1,
    )
    return last_account_idx


@typechecked
def actually_set_answers(
    *,
    preserved_answers: List[Union[None, Tuple[str, Any]]],
    new_account_start_idx: int,
    new_account_end_idx: int,
    new_tui: QuestionnaireApp,
):
    # Apply preserved answers only to questions outside the new account questions' indices
    for idx, input_widget in enumerate(new_tui.inputs):

        widget = input_widget.base_widget
        question_text = widget.question_data.question

        if new_account_start_idx <= idx < new_account_end_idx:

            continue  # Skip new account questions
        elif len(preserved_answers) > idx and (
            preserved_answers[idx]
            and question_text == preserved_answers[idx][0]
        ):

            widget.set_answer(preserved_answers[idx][1])
