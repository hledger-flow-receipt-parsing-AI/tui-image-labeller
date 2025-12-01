from typing import Any, List, Tuple, Union

from hledger_preprocessor.config.load_config import Config
from hledger_preprocessor.TransactionObjects.Receipt import Receipt
from typeguard import typechecked
from urwid import AttrMap

from tui_labeller.tuis.urwid.date_question.DateTimeQuestion import (
    DateTimeQuestion,
)
from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.input_validation.InputValidationQuestion import (
    InputValidationQuestion,
)
from tui_labeller.tuis.urwid.prefill_receipt.helper import (
    generate_current_questions,
    get_number_of_account_transactions,
)
from tui_labeller.tuis.urwid.prefill_receipt.set_address import (
    set_address_questions,
)
from tui_labeller.tuis.urwid.question_app.reconfiguration.pre_filling_receipt_answers0 import (
    answer_prefilled_account_questions,
)
from tui_labeller.tuis.urwid.question_app.reconfiguration.reconfiguration import (
    preserve_current_answers,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp
from tui_labeller.tuis.urwid.receipts.AccountQuestions import AccountQuestions
from tui_labeller.tuis.urwid.receipts.BaseQuestions import (
    BaseQuestions,
)


@typechecked
def apply_prefilled_receipt(
    *,
    config: Config,
    tui: QuestionnaireApp,
    account_infos_str: List[str],
    accounts_without_csv: set[str],
    prefilled_receipt: Union[None, Receipt],
) -> QuestionnaireApp:
    if prefilled_receipt:
        # set_prefilled_date(tui=tui, prefilled_receipt=prefilled_receipt)
        # set_bookkeeping_category(tui=tui, prefilled_receipt=prefilled_receipt)

        new_tui: QuestionnaireApp = set_account_questions(
            config=config,
            tui=tui,
            prefilled_receipt=prefilled_receipt,
            account_infos_str=account_infos_str,
            accounts_without_csv=accounts_without_csv,
        )

        # TODO: add call to update the address_question using the entered category.
        # Update the address selector with the selected category.
        third_tui: QuestionnaireApp = set_address_questions(
            tui=new_tui, prefilled_receipt=prefilled_receipt
        )

        set_receipt_details(tui=third_tui, prefilled_receipt=prefilled_receipt)
        return third_tui
    else:
        return tui


@typechecked
def set_receipt_details(
    *,
    tui: QuestionnaireApp,
    prefilled_receipt: Receipt,
) -> None:
    if prefilled_receipt is None:
        return  # No prefilled data to set

    # Map question captions/types to corresponding Receipt fields
    question_field_map = {
        "date": {
            "type": DateTimeQuestion,
            "field": "the_date",
            "caption": None,  # DateTimeQuestion doesn't rely on caption
        },
        "receipt_category": {
            "type": InputValidationQuestion,
            "field": "receipt_category",
            "caption": BaseQuestions().get_category_question().question,
            "input_type": InputType.LETTERS_SEMICOLON,
        },
        "subtotal": {
            "type": InputValidationQuestion,
            "field": "subtotal",
            "caption": "\nSubtotal (Optional, press enter to skip):\n",
            "input_type": InputType.FLOAT,
        },
        "total_tax": {
            "type": InputValidationQuestion,
            "field": "total_tax",
            "caption": "\nTotal tax (Optional, press enter to skip):\n",
            "input_type": InputType.FLOAT,
        },
    }

    found_questions = {key: False for key in question_field_map}

    for i, some_input in enumerate(tui.inputs):
        if (
            isinstance(some_input, AttrMap)
            and "_original_widget" in some_input.__dict__
        ):
            original_widget = some_input._original_widget
            for key, config in question_field_map.items():
                if isinstance(original_widget, config["type"]):
                    if (
                        config["caption"] is None
                        or original_widget._caption == config["caption"]
                    ):
                        if (
                            "input_type" not in config
                            or original_widget.input_type
                            == config["input_type"]
                        ):
                            value = getattr(
                                prefilled_receipt, config["field"], None
                            )
                            if value is not None:
                                original_widget.set_answer(value=value)
                            found_questions[key] = True

    # Check if all expected questions were found
    missing_questions = [
        key for key, found in found_questions.items() if not found
    ]
    if missing_questions:
        raise ValueError(f"Missing questions: {', '.join(missing_questions)}")


@typechecked
def set_account_questions(
    *,
    config: Config,
    tui: QuestionnaireApp,
    account_infos_str: List[str],
    accounts_without_csv: set[str],
    prefilled_receipt: Receipt,
) -> QuestionnaireApp:
    pre_filled_accounts_questions: List[AccountQuestions] = (
        generate_current_questions(
            config=config,
            prefilled_receipt=prefilled_receipt,
            account_infos_str=account_infos_str,
            accounts_without_csv=accounts_without_csv,
        )
    )
    # TODO: Remove current AccountQuestions from the preserve_current_answers function, because in this case they are not useful.
    pre_filled_accounts_questions.append(pre_filled_accounts_questions[0])

    # In the context of creating the pre-filled receipt, only the first 2 answers are set above, get them.
    prefilled_answers_to_base_questions: List[Union[None, Tuple[str, Any]]] = (
        preserve_current_answers(tui=tui)
    )
    new_tui: QuestionnaireApp = answer_prefilled_account_questions(
        account_infos_str=account_infos_str,
        accounts_without_csv=accounts_without_csv,
        prefilled_answers_to_base_questions=prefilled_answers_to_base_questions,
        current_questions=tui.questions,
        nr_of_account_transactions=get_number_of_account_transactions(
            prefilled_receipt=prefilled_receipt
        ),
        prefilled_receipt=prefilled_receipt,
        labelled_receipts=[],
    )
    return new_tui
