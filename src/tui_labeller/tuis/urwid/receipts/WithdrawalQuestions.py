from typing import List, Union

import urwid
from hledger_core.Currency import Currency
from typeguard import typechecked

from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_data_classes import (
    AISuggestion,
    HorizontalMultipleChoiceQuestionData,
    InputValidationQuestionData,
    VerticalMultipleChoiceQuestionData,
)


@typechecked
class WithdrawalQuestions:
    """Questions for the withdrawal flow.

    When the withdrawal toggle is 'y', the user enters source account
    details first, then the normal wallet account questions, then
    post-account questions (ATM fee, and exchange rate + bank fee if
    foreign).

    Base questions (injected after toggle):
    1. Withdrawal source account
    2. Source account currency
    3. Amount debited from source account

    Post-account questions (injected after "Add another account = n"):
    4. ATM operator fee (always, default 0)
    5. Exchange rate (only if foreign, default 1)
    6. Bank fee (only if foreign, default 0)
    """

    def __init__(
        self,
        account_infos_str: List[str],
        accounts_without_csv: set[str],
    ):
        self.account_infos_str: List[str] = account_infos_str
        self.accounts_without_csv: set[str] = accounts_without_csv
        self.belongs_to_options: List[str] = sorted(
            list(
                set(
                    list(self.account_infos_str)
                    + list(self.accounts_without_csv)
                )
            )
        )
        self.withdrawal_questions: List[
            Union[
                VerticalMultipleChoiceQuestionData,
                InputValidationQuestionData,
                HorizontalMultipleChoiceQuestionData,
            ]
        ] = self.create_questions()

    @typechecked
    def create_questions(
        self,
    ) -> List[
        Union[
            VerticalMultipleChoiceQuestionData,
            InputValidationQuestionData,
            HorizontalMultipleChoiceQuestionData,
        ]
    ]:
        return [
            # 1. Source account selection.
            VerticalMultipleChoiceQuestionData(
                question="Withdrawal source account:",
                ans_required=True,
                reconfigurer=False,
                terminator=False,
                choices=self.belongs_to_options,
                ai_suggestions=[],
                nr_of_ans_per_batch=8,
                navigation_display=urwid.AttrMap(
                    urwid.Pile(
                        [
                            urwid.Text(("navigation", "Navigation")),
                            urwid.Text("Q          - quit"),
                            urwid.Text(
                                "\n<- Left, Right -> - Show next batch of"
                                " answers."
                            ),
                            urwid.Text(
                                "\nType a number to select that answer."
                            ),
                            urwid.Text(
                                "\nEnter confirm choice, goto next question."
                            ),
                        ]
                    ),
                    "normal",
                ),
            ),
            # 2. Source account currency.
            VerticalMultipleChoiceQuestionData(
                question="Source account currency:",
                ans_required=True,
                nr_of_ans_per_batch=8,
                reconfigurer=False,
                terminator=False,
                choices=[currency.value for currency in Currency],
                ai_suggestions=[],
            ),
            # 3. Amount debited from source account (always asked).
            InputValidationQuestionData(
                question="Amount debited from source account:",
                input_type=InputType.FLOAT,
                ai_suggestions=[],
                history_suggestions=[],
                ans_required=True,
                reconfigurer=False,
                terminator=False,
            ),
        ]

    @typechecked
    def get_atm_fee_question(self) -> InputValidationQuestionData:
        """ATM operator fee in withdrawn currency (default 0)."""
        return InputValidationQuestionData(
            question="ATM operator fee (in withdrawn currency, 0 if none):",
            input_type=InputType.FLOAT,
            ai_suggestions=[],
            history_suggestions=[],
            ans_required=True,
            reconfigurer=False,
            terminator=False,
            default="0",
        )

    @typechecked
    def get_exchange_rate_question(self) -> InputValidationQuestionData:
        """Exchange rate for foreign withdrawals (default 1)."""
        return InputValidationQuestionData(
            question="Exchange rate (1 source = X destination):",
            input_type=InputType.FLOAT,
            ai_suggestions=[],
            history_suggestions=[],
            ans_required=True,
            reconfigurer=False,
            terminator=False,
            default="1",
        )

    @typechecked
    def get_bank_fee_question(self) -> InputValidationQuestionData:
        """Bank fee charged by the source bank (default 0)."""
        return InputValidationQuestionData(
            question="Bank fee (in source currency, 0 if none):",
            input_type=InputType.FLOAT,
            ai_suggestions=[],
            history_suggestions=[],
            ans_required=True,
            reconfigurer=False,
            terminator=False,
            default="0",
        )
