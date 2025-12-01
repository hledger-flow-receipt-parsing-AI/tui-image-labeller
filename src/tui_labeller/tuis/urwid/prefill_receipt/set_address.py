from typing import Optional

from hledger_preprocessor.TransactionObjects.Receipt import Receipt
from typeguard import typechecked
from urwid import AttrMap

from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.input_validation.InputValidationQuestion import (
    InputValidationQuestion,
)
from tui_labeller.tuis.urwid.multiple_choice_question.VerticalMultipleChoiceWidget import (
    VerticalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.prefill_receipt.helper import (
    get_number_of_account_transactions,
)
from tui_labeller.tuis.urwid.question_app.reconfiguration.reconfiguration import (
    handle_manual_address_questions,
    is_at_address_selector,
    preserve_current_answers,
    remove_manual_address_questions,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp
from tui_labeller.tuis.urwid.receipts.AccountQuestions import AccountQuestions
from tui_labeller.tuis.urwid.receipts.BaseQuestions import (
    BaseQuestions,
)
from tui_labeller.tuis.urwid.receipts.OptionalQuestions import OptionalQuestions


@typechecked
def set_address_questions(
    *,
    tui: QuestionnaireApp,
    prefilled_receipt: Optional[Receipt],
) -> QuestionnaireApp:

    # optional_questions = OptionalQuestions(labelled_receipts=[])
    set_first_address_question(
        tui=tui, prefilled_receipt=prefilled_receipt, answer="manual address"
    )

    third_tui: QuestionnaireApp = (
        ensure_manual_address_questions_are_added_to_tui(tui=tui)
    )

    set_shop_details(
        prefilled_receipt=prefilled_receipt,
        tui=third_tui,
    )

    return third_tui


@typechecked
def set_shop_details(
    prefilled_receipt: Optional[Receipt], tui: QuestionnaireApp
) -> None:
    if prefilled_receipt is None or prefilled_receipt.shop_identifier is None:
        return  # No prefilled data to set

    # Map question captions to corresponding ShopId/Address fields
    question_field_map = {
        "\nShop name:\n": ("shop_identifier.name", InputType.LETTERS),
        "Shop street:": (
            "shop_identifier.address.street",
            InputType.LETTERS_AND_SPACE,
        ),
        "Shop house nr.:": (
            "shop_identifier.address.house_nr",
            InputType.LETTERS_AND_NRS,
        ),
        "Shop zipcode:": (
            "shop_identifier.address.zipcode",
            InputType.LETTERS_AND_NRS,
        ),
        "Shop City:": ("shop_identifier.address.city", InputType.LETTERS),
        "Shop country:": ("shop_identifier.address.country", InputType.LETTERS),
    }

    found_questions = {key: False for key in question_field_map}

    for i, some_input in enumerate(tui.inputs):
        if (
            isinstance(some_input, AttrMap)
            and "_original_widget" in some_input.__dict__
        ):
            original_widget = some_input._original_widget
            if isinstance(original_widget, InputValidationQuestion):
                for caption, (
                    field_path,
                    expected_type,
                ) in question_field_map.items():
                    if original_widget._caption == caption:
                        # Get the field value using nested attribute access
                        value = prefilled_receipt
                        for attr in field_path.split("."):
                            value = getattr(value, attr, None)
                        if (
                            value is not None
                            and original_widget.input_type == expected_type
                        ):
                            original_widget.set_answer(str(value))
                        found_questions[caption] = True

    # Check if all expected questions were found
    missing_questions = [
        caption for caption, found in found_questions.items() if not found
    ]
    if missing_questions:
        raise ValueError(f"Missing questions: {', '.join(missing_questions)}")


@typechecked
def ensure_manual_address_questions_are_added_to_tui(
    *, tui: QuestionnaireApp
) -> QuestionnaireApp:
    optional_questions = OptionalQuestions(labelled_receipts=[])
    preserved_answers = preserve_current_answers(tui=tui)
    # Handle manual address questions if the address selector is focused
    is_address_selector_focused: bool = is_at_address_selector(tui=tui)
    # if is_address_selector_focused:
    if True:
        new_tui = handle_manual_address_questions(
            tui=tui,
            optional_questions=optional_questions,
            current_questions=tui.inputs,
            preserved_answers=preserved_answers,
        )
        # Remove manual address questions if a non-manual address is selected
        second_tui = remove_manual_address_questions(
            tui=new_tui,
            optional_questions=optional_questions,
            current_questions=tui.inputs,
            preserved_answers=preserved_answers,
        )
    return second_tui


@typechecked
def get_first_address_question_idx(
    prefilled_receipt: Optional[Receipt],
) -> int:

    fixed_fields_count: int = len(BaseQuestions().base_questions)
    nr_of_account_questions: int = get_number_of_account_transactions(
        prefilled_receipt=prefilled_receipt
    )
    account_questions_per_transaction = len(
        AccountQuestions(
            account_infos_str=[], accounts_without_csv=set()
        ).account_questions
    )
    first_address_question_idx: int = (
        fixed_fields_count
        + nr_of_account_questions * account_questions_per_transaction
    )
    return first_address_question_idx


@typechecked
def set_first_address_question(
    tui: QuestionnaireApp, prefilled_receipt: Optional[Receipt], answer: str
):

    first_address_question_idx: int = get_first_address_question_idx(
        prefilled_receipt=prefilled_receipt
    )

    # First select "manual address".
    address_type_question: AttrMap = tui.inputs[first_address_question_idx]
    if not isinstance(address_type_question, AttrMap):
        raise TypeError(
            "Expected first address question input to be of type AttrMap,"
            f" got:{type(address_type_question)}"
        )

    original_widget = address_type_question._original_widget

    if isinstance(original_widget, VerticalMultipleChoiceWidget):
        if "Select Shop Address:\n" in original_widget._caption:
            original_widget.set_answer(answer)
        else:
            raise ValueError(
                f"Did not find the question. Got:{original_widget._caption}END"
            )
    else:
        raise TypeError(
            "Expected first address question _original_widget to be of type"
            f" InputValidationQuestion, got:{type(original_widget)}"
        )
