from datetime import datetime
from pprint import pprint
from typing import Any, List, Optional, Tuple, Union

from hledger_config.config.load_config import Config
from hledger_core.TransactionObjects.Address import Address
from hledger_core.TransactionObjects.ExchangedItem import ExchangedItem
from hledger_core.TransactionObjects.Receipt import (
    Receipt,
    WithdrawalMetadata,
)
from hledger_core.TransactionObjects.ShopId import ShopId
from hledger_receipt_processing.receipt_transaction_matching.get_bank_data_from_transactions import (  # noqa: E501
    HledgerFlowAccountInfo,
)
from typeguard import typechecked

from tui_labeller.tuis.urwid.date_question.DateTimeQuestion import (
    DateTimeQuestion,
)
from tui_labeller.tuis.urwid.input_validation.InputValidationQuestion import (
    InputValidationQuestion,
)
from tui_labeller.tuis.urwid.multiple_choice_question.HorizontalMultipleChoiceWidget import (  # noqa: E501
    HorizontalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.multiple_choice_question.VerticalMultipleChoiceWidget import (  # noqa: E501
    VerticalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.receipts.account_parser import (
    get_bought_and_returned_items,
    parse_withdrawal_answers,
)


@typechecked
def build_receipt_from_answers(
    *,
    config: Config,
    raw_receipt_img_filepath: str,
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
    ],
    verbose: bool,
    hledger_account_infos: set[HledgerFlowAccountInfo],
    accounts_without_csv: set[str],
) -> Receipt:
    """Builds a Receipt object from the dictionary of answers returned by
    tui.get_answers()

    Args:
        final_answers: Dictionary containing question widgets as keys and their answers as values  # noqa: E501

    Returns:
        Receipt object with mapped values
    """

    # Helper function to extract value from widget key
    @typechecked
    def get_widget(*, caption: str, required: Optional[bool] = False) -> any:
        for index, answer in enumerate(final_answers):
            widget, value = answer
            # for widget, value in final_answers.items():
            if hasattr(widget, "caption"):
                if caption in widget.caption:
                    # Convert empty strings to None for optional fields
                    return widget
        raise ValueError(f"Was not able to find widget with caption={caption}")

    # Helper function to extract value from widget key
    @typechecked
    def get_value(*, caption: str, required: Optional[bool] = False) -> Any:
        for index, answer in enumerate(final_answers):
            widget, value = answer
            # for widget, value in final_answers.items():
            if hasattr(widget, "caption"):
                if caption in widget.caption:
                    # Convert empty strings to None for optional fields
                    return value if value != "" else None
            elif isinstance(widget, VerticalMultipleChoiceWidget):
                if caption in widget.question_data.question:
                    return value
            elif isinstance(widget, HorizontalMultipleChoiceWidget):
                if caption in widget.question_data.question:
                    return value
            else:
                raise TypeError(f"Did not expect question widget type:{widget}")
        if required:
            pprint(final_answers)
            raise ValueError(
                f"Did not find the answer to:{caption}\n in the answers above."
            )
        return None

    @typechecked
    def get_float(*, caption) -> float:
        found_caption: bool = False
        for index, answer in enumerate(final_answers):
            widget, value = answer
            if hasattr(widget, "caption") and caption in widget.caption:
                found_caption = True
                # Convert empty strings to None for optional fields
                return float(value) if value != "" else 0.0
        if not found_caption:
            print("\n")
            pprint(final_answers)
            raise ValueError(
                f"Did not find caption:{caption} in above answers."
            )
        return 0.0

    def build_address(
        config: Config,
        street: Optional[str] = None,
        house_nr: Optional[str] = None,
        zipcode: Optional[str] = None,
        city: Optional[str] = None,
        country: Optional[str] = None,
    ) -> Address:
        """Build an Address object from individual address components."""
        return Address(
            street=street or None,
            house_nr=house_nr or None,
            zipcode=zipcode or None,
            city=city or None,
            country=country or None,
        )

    is_withdrawal = get_value(
        caption="Is this a withdrawal? (y/n)", required=False
    )
    _is_withdrawal = is_withdrawal and str(is_withdrawal).lower() == "y"
    average_receipt_category: Optional[str] = get_value(
        caption="\nBookkeeping expense category:",
        required=not _is_withdrawal,
    )
    the_date: datetime = get_value(
        caption="Receipt date and time:\n", required=True
    )
    net_bought_items: Union[None, ExchangedItem]
    net_returned_items: Union[None, ExchangedItem]
    net_bought_items, net_returned_items = get_bought_and_returned_items(
        config=config,
        final_answers=final_answers,
        hledger_account_infos=hledger_account_infos,
        accounts_without_csv=accounts_without_csv,
        average_receipt_category=average_receipt_category,
        the_date=the_date,
    )

    # Check if a shop address was selected from multiple choice
    selected_addres_widget = get_widget(caption="Select Shop Address:")
    address_nr: int = selected_addres_widget.get_int_answer()
    if address_nr and address_nr != 0:
        for index, answer in enumerate(final_answers):
            widget, value = answer
            if (
                isinstance(widget, VerticalMultipleChoiceWidget)
                and "Select Shop Address:" in widget.question_data.question
            ):

                # Assuming the extra_data contains shop_ids with address
                # information
                shop_id_data = widget.question_data.extra_data.get(
                    "shop_ids", {}
                )

                # selected_shop = shop_id_data[address_nr]
                selected_shop: ShopId = get_shop_id_from_choice(
                    choice=widget.question_data.choices[address_nr],
                    shop_ids=shop_id_data,
                )
                break
    else:
        shop_address = build_address(
            config=config,
            street=get_value(caption="Shop street:") or None,
            house_nr=get_value(caption="Shop house nr.:") or None,
            zipcode=get_value(caption="Shop zipcode:") or None,
            city=get_value(caption="Shop City:") or None,
            country=get_value(caption="Shop country:") or None,
        )
        selected_shop: ShopId = ShopId(
            name=get_value(caption="\nShop name:\n") or "",
            address=shop_address,
            shop_account_nr=get_value(caption="\nShop account nr:\n"),
        )

    # Parse withdrawal metadata if the withdrawal toggle is 'y'.
    withdrawal_metadata: Optional[WithdrawalMetadata] = None
    if _is_withdrawal:
        # The receipt amount is the net destination-side amount
        # (change_returned - tendered_amount_out on the destination account).
        receipt_amount: Optional[float] = None
        for item in (net_returned_items, net_bought_items):
            if item is not None and item.account_transactions:
                for at in item.account_transactions:
                    receipt_amount = at.change_returned - at.tendered_amount_out
                    break
                if receipt_amount is not None:
                    break
        withdrawal_metadata = parse_withdrawal_answers(
            config=config,
            final_answers=final_answers,
            the_date=the_date,
            receipt_amount=receipt_amount,
        )

    # Map the answers to Receipt parameters
    receipt_params = {
        "raw_img_filepath": raw_receipt_img_filepath,
        "shop_identifier": selected_shop,
        "net_bought_items": net_bought_items,
        "net_returned_items": net_returned_items,
        "the_date": the_date,
        "subtotal": (
            float(
                get_value(
                    caption="\nSubtotal (Optional, press enter to skip):\n"
                )
            )
            if get_value(
                caption="\nSubtotal (Optional, press enter to skip):\n"
            )
            else None
        ),
        "total_tax": (
            float(
                get_value(
                    caption="\nTotal tax (Optional, press enter to skip):\n"
                )
            )
            if get_value(
                caption="\nTotal tax (Optional, press enter to skip):\n"
            )
            else None
        ),
        # TODO: store amount payed and returned per account.
        "receipt_owner_address": get_value(
            caption="\nReceipt owner address (optional):\n"
        ),
        "receipt_category": average_receipt_category,
        "withdrawal_metadata": withdrawal_metadata,
    }
    receipt_params["config"] = config

    if verbose:
        pprint(receipt_params)
        print("OK?")
    return Receipt(**receipt_params)


@typechecked
def get_shop_id_from_choice(choice: str, shop_ids: List[ShopId]) -> ShopId:
    """Maps a choice string to the corresponding ShopId from a list of ShopIds.
    Throws an error if more than one matching ShopId is found or if no match is
    found.

    Args:
        choice: The choice string (e.g., 'Lidl: Urkhovenseweg, 16, 5641KE, Eindhoven, Netherlands').  # noqa: E501
        shop_ids: List of ShopId objects to search through.

    Returns:
        ShopId: The matching ShopId object.

    Raises:
        ValueError: If no matching ShopId is found or if multiple matches are found.  # noqa: E501
    """
    # Handle the 'manual address' case
    if choice == "manual address":
        for shop_id in shop_ids:
            if (
                shop_id.name == "manual address"
                and shop_id.address.to_string() == ""
            ):
                return shop_id
        raise ValueError("No 'manual address' ShopId found in shop_ids")

    # Parse the choice string
    # Remove leading '*' if present (for starred entries)
    choice_clean = choice.lstrip("*")
    # Split into name and address parts
    try:
        shop_name, address_str = choice_clean.split(": ", 1)
    except ValueError:
        raise ValueError(f"Invalid choice format: {choice}")

    # Find matching ShopId
    matches = []
    for shop_id in shop_ids:
        # Generate the address string for comparison
        shop_address_str = shop_id.address.to_string()
        # Check if name and address match
        if shop_id.name == shop_name and shop_address_str == address_str:
            matches.append(shop_id)

    if len(matches) == 0:
        raise ValueError(f"No ShopId found for choice: {choice}")
    if len(matches) > 1:
        raise ValueError(f"Multiple ShopIds found for choice: {choice}")

    return matches[0]
