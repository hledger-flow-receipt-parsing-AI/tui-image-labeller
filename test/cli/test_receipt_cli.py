"""Tests whether the script correctly handles multiline arguments and verifies
directory structure."""

import os
import tempfile
import unittest
import uuid
from io import StringIO
from unittest.mock import patch

from typeguard import typechecked

from tui_labeller.tuis.cli.questions.ask_receipt import (
    build_receipt_from_cli,
)


class Test_script_with_multiline_args(unittest.TestCase):
    """Object used to test a script handling multiline arguments and directory
    verification."""

    # Initialize test object
    @typechecked
    def __init__(self, *args, **kwargs):  # type:ignore[no-untyped-def]
        super().__init__(*args, **kwargs)
        self.existent_tmp_dir: str = tempfile.mkdtemp()
        self.nonexistant_tmp_dir: str = self.get_random_nonexistent_dir()

    @typechecked
    def get_random_nonexistent_dir(
        self,
    ) -> str:
        """Generates and returns a random directory path that does not
        exist."""
        random_dir = f"/tmp/{uuid.uuid4()}"
        while os.path.exists(random_dir):
            random_dir = f"/tmp/{uuid.uuid4()}"
        return random_dir

    def test_multiline_args_and_dirs(self):
        account_holder: str = "some_holder"
        bank_name: str = "some_bank"
        account_type: str = "checking"

        # Simulate the CLI args.

        cli_args = [
            "tui_labeller_filler_name_to_skip_script_at_arg[0]",  # Dummy program name
            "-iimages/receipts/0.jpg",
            f"{self.existent_tmp_dir}",
            "--output-json-dir",
            "test/test_jsons/--tui",
            "CLI",
        ]
        print(f"self.existent_tmp_dir={self.existent_tmp_dir}")

        some_date: str = "2202-04-15"
        add_first_item: str = "y"
        bought_item_name: str = "milK"
        item_currency: str = "EUR"
        item_quantity: float = 3.6  # liters, units etc.
        item_price: float = 55.23  # Euros
        item_category: str = "groceries:drinks"
        item_tax: str = ""
        item_discount: str = ""
        add_second_item: str = "n"
        add_first_returned_item: str = "n"
        shop_account_nr: str = ""
        subtotal: str = ""
        total_tax: str = ""
        shop_name: str = "lidl"
        shop_address: str = "some street"
        is_cash_payment: str = "y"
        is_cash_payment: str = "y"
        cash_payed: float = item_quantity * item_price + 10
        cash_returned: float = 20
        payed_by_card: str = "y"
        amount_payed_by_card: float = 15
        amount_returned_to_card: float = 5
        payed_from_default_account: str = "y"
        receipt_category: str = "groceries"
        payed_total_read: float = round(item_quantity * item_price, 2)

        # Simulate user input for `ask_user_for_starting_info(..)`
        user_input = StringIO(
            f"{some_date}\n"
            + f"{add_first_item}\n"
            + f"{bought_item_name}\n"
            + f"{item_currency}\n"
            + f"{item_quantity}\n"
            + f"{item_price}\n"
            + f"{item_category}\n"
            + f"{item_tax}\n"
            + f"{item_discount}\n"
            + f"{add_second_item}\n"
            + f"{add_first_returned_item}\n"
            + f"{shop_account_nr}\n"
            + f"{subtotal}\n"
            + f"{total_tax}\n"
            + f"{shop_name}\n"
            + f"{shop_address}\n"
            + f"{is_cash_payment}\n"
            + f"{is_cash_payment}\n"
            + f"{cash_payed}\n"
            + f"{cash_returned}\n"
            + f"{payed_by_card}\n"
            + f"{amount_payed_by_card}\n"
            + f"{amount_returned_to_card}\n"
            + f"{payed_from_default_account}\n"
            + f"{receipt_category}\n"
            + f"{payed_total_read}\n"
        )

        with patch("sys.argv", cli_args), patch("sys.stdin", user_input):
            # main()
            build_receipt_from_cli(
                receipt_owner_account_holder="account_placeholder",
                receipt_owner_bank="bank_placeholder",
                receipt_owner_account_holder_type="account_type_placeholder",
            )
