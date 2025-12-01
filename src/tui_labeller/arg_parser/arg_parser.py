"""Parses the CLI args."""

import argparse
import os
from argparse import ArgumentParser, Namespace
from typing import List, Tuple

from hledger_preprocessor.dir_reading_and_writing import assert_dir_exists
from hledger_preprocessor.receipt_transaction_matching.get_bank_data_from_transactions import (
    HledgerFlowAccountInfo,
)
from typeguard import typechecked

from tui_labeller.interface_enum import InterfaceMode


@typechecked
def create_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Generate labels for images using CLI/TUI."
    )

    # Required args.
    parser.add_argument(
        "-i",
        "--image-path",
        type=str,
        required=True,
        help="Path to an image.",
    )
    parser.add_argument(
        "-t",
        "--tui",
        type=str,
        required=True,
        help="Which TUI you would like to use for labelling.",
    )
    parser.add_argument(
        "-o",
        "--output-json-dir",
        type=str,
        required=True,
        help="Where your output json will be stored.",
    )

    parser.add_argument(
        "-a",
        "--accounts",
        type=str,
        required=True,
        help=(
            "Account info in format"
            " receipt_owner_account_holder:receipt_owner_bank:receipt_owner_account_holder_type,"
            " multiple separated by commas."
        ),
    )
    parser.add_argument(
        "-c",
        "--categories",
        type=str,
        required=True,
        help=(
            "Categories in format type:name:category, multiple separated by"
            " commas (e.g., expenses:wholefoods:groceries,assets:gold)."
        ),
    )

    return parser


@typechecked
def assert_file_exists(*, filepath: str) -> None:
    """Asserts that the given file exists.

    Args:
      filepath: The path to the file.

    Raises:
      FileNotFoundError: If the file does not exist.
    """

    if not os.path.isfile(filepath):
        raise FileNotFoundError(f"File '{filepath}' does not exist.")


@typechecked
def assert_dir_exists(*, dirpath: str) -> None:
    """Asserts that the given directory exists.

    Args:
      dirpath: The path to the directory.

    Raises:
      FileNotFoundError: If the directory does not exist.
    """

    if not os.path.isdir(dirpath):
        raise FileNotFoundError(f"Directory '{dirpath}' does not exist.")


@typechecked
def validate_tui(*, tui_arg: str) -> None:
    try:
        InterfaceMode(tui_arg.lower())  # Try to create an Enum member
    except ValueError:
        raise NotImplementedError(f"That TUI '{tui_arg}' is not supported.")


@typechecked
def verify_args(
    *, parser: ArgumentParser
) -> Tuple[Namespace, List[str], set[HledgerFlowAccountInfo]]:
    args: Namespace = parser.parse_args()

    # Verify output directory for jsons exist.
    assert_dir_exists(dirpath=args.output_json_dir)

    # Verify the input image exists.
    assert_file_exists(filepath=args.image_path)

    # Verify the chosen TUI method is supported.
    validate_tui(tui_arg=args.tui)

    categories: List[str] = verify_categories(categories=args.categories)
    accounts: set[HledgerFlowAccountInfo] = verify_account_infos(
        account_infos=args.accounts
    )

    return args, categories, accounts


from typing import List, Tuple


@typechecked
def verify_account_infos(*, account_infos: str) -> set[HledgerFlowAccountInfo]:
    hledgerFlowAccountInfos: set[HledgerFlowAccountInfo] = []
    for info in account_infos.split(","):
        parts = info.split(":")
        assert (
            len(parts) == 3
        ), "Each account info must have 3 parts separated by ':'"
        account_holder, bank, account_type = parts
        assert (
            account_holder and bank and account_type
        ), "All account info fields must be non-empty"
        for part in parts:
            assert part.islower(), "Account info must be lowercase"
            assert all(
                c.islower() or c == "_" for c in part
            ), "Account info can only contain lowercase letters and underscores"
        hledgerFlowAccountInfos.append(
            HledgerFlowAccountInfo(
                account_holder=account_holder,
                bank=bank,
                account_type=account_type,
            )
        )
    return hledgerFlowAccountInfos


@typechecked
def verify_categories(*, categories: str) -> List[str]:
    result = []
    seen = set()
    for cat in categories.split(","):
        assert cat, "Category must be non-empty"
        assert cat.islower(), "Category must be lowercase"
        assert all(c.islower() or c.isdigit() or c == ":" for c in cat), (
            f"Categories:{cat} can only contain lowercase letters, digits, and"
            " colons"
        )
        assert cat not in seen, f"Category:{cat} must be unique"
        seen.add(cat)
        result.append(cat)
    return result
