"""Entry point for the project."""

from argparse import ArgumentParser

from hledger_preprocessor.receipt_transaction_matching.get_bank_data_from_transactions import (
    HledgerFlowAccountInfo,
)

from tui_labeller.arg_parser.arg_parser import create_arg_parser, verify_args
from tui_labeller.interface_enum import InterfaceMode
from tui_labeller.tuis.cli.questions.ask_receipt import (
    build_receipt_from_cli,
)
from tui_labeller.tuis.urwid.ask_urwid_receipt import build_receipt_from_urwid

parser: ArgumentParser = create_arg_parser()
args, categories, account_infos = verify_args(parser=parser)


if __name__ == "__main__":

    if args.tui.lower() == InterfaceMode.CLI.value:

        build_receipt_from_cli(
            receipt_owner_account_holder="account_placeholder",
            receipt_owner_bank="bank_placeholder",
            receipt_owner_account_holder_type="account_type_placeholder",
        )
    elif args.tui.lower() == InterfaceMode.URWID.value:

        # app = create_row_questionnaire()
        # app.run()

        build_receipt_from_urwid(
            config=config,
            hledger_account_infos=[
                HledgerFlowAccountInfo(
                    account_holder="account_placeholder",
                    bank="bank_placeholder",
                    account_type="account_type_placeholder",
                )
            ],
            accounts_without_csv=categories,
        )
    else:
        print(f"Please select a CLI/TUI. You choose:{args.tui.lower()}")
