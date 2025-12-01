from datetime import datetime
from typing import List, Optional, Tuple, Union

import urwid
from hledger_preprocessor.config.load_config import Config
from hledger_preprocessor.receipt_transaction_matching.get_bank_data_from_transactions import (
    HledgerFlowAccountInfo,
)
from hledger_preprocessor.TransactionObjects.Receipt import Receipt
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
from tui_labeller.tuis.urwid.prefill_receipt.pre_fill_receipt import (
    apply_prefilled_receipt,
)
from tui_labeller.tuis.urwid.question_app.generator import create_questionnaire
from tui_labeller.tuis.urwid.question_app.get_answers import (
    get_answers,
    is_terminated,
)
from tui_labeller.tuis.urwid.question_app.reconfiguration.reconfiguration import (
    get_configuration,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp
from tui_labeller.tuis.urwid.receipts.AccountQuestions import AccountQuestions
from tui_labeller.tuis.urwid.receipts.BaseQuestions import (
    BaseQuestions,
)
from tui_labeller.tuis.urwid.receipts.create_receipt import (
    build_receipt_from_answers,
)
from tui_labeller.tuis.urwid.receipts.OptionalQuestions import OptionalQuestions


@typechecked
def build_receipt_from_urwid(
    *,
    config: Config,
    raw_receipt_img_filepath: str,
    hledger_account_infos: set[HledgerFlowAccountInfo],
    accounts_without_csv: set[str],
    labelled_receipts: List[Receipt],
    prefilled_receipt: Optional[Receipt],
) -> Receipt:
    account_infos_str: List[str] = list(
        {x.to_colon_separated_string() for x in hledger_account_infos}
    )
    account_questions = AccountQuestions(
        account_infos_str=account_infos_str,
        accounts_without_csv=accounts_without_csv,
    )
    base_questions = BaseQuestions()
    optional_questions = OptionalQuestions(labelled_receipts=labelled_receipts)

    tui: QuestionnaireApp = create_questionnaire(
        questions=base_questions.base_questions
        + account_questions.account_questions
        + optional_questions.optional_questions,
        header="Answer the receipt questions.",
        labelled_receipts=labelled_receipts,
    )

    tui: QuestionnaireApp = apply_prefilled_receipt(
        config=config,
        tui=tui,
        prefilled_receipt=prefilled_receipt,
        account_infos_str=account_infos_str,
        accounts_without_csv=accounts_without_csv,
    )
    tui.run()  # Start the first run.
    while True:
        if is_terminated(inputs=tui.inputs):
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
            ] = get_answers(inputs=tui.inputs)

            return build_receipt_from_answers(
                config=config,
                raw_receipt_img_filepath=raw_receipt_img_filepath,
                final_answers=final_answers,
                verbose=True,
                hledger_account_infos=hledger_account_infos,
                accounts_without_csv=accounts_without_csv,
            )

        else:
            current_position: int = tui.get_focus()
            tui = get_configuration(
                tui=tui,
                account_questions=account_questions,
                optional_questions=optional_questions,
                labelled_receipts=labelled_receipts,
            )

            # Update the pile based on the reconfiguration.
            pile_contents = [(urwid.Text(tui.header), ("pack", None))]
            for some_widget in tui.inputs:
                pile_contents.append((some_widget, ("pack", None)))
            tui.pile.contents = pile_contents

            tui.run(alternative_start_pos=current_position + tui.nr_of_headers)
