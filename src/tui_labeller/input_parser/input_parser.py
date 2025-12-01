import re
from datetime import datetime
from typing import Union

from typeguard import typechecked


@typechecked
def get_float_input(
    *, question: str, allow_optional: bool
) -> Union[None, float]:
    while True:
        try:
            answer = input(question)
            if answer == "":
                if allow_optional:
                    return None
                else:
                    raise ValueError(
                        "Invalid empty input. Please enter a number."
                    )
            return float(answer)
        except ValueError:
            print("Invalid input. Please enter a number.")


@typechecked
def get_date_input(
    *, question: str, allow_optional: bool
) -> Union[None, datetime]:
    while True:
        try:
            answer = input(question)
            if answer == "":
                if allow_optional:
                    return None
                else:
                    raise ValueError(
                        "Invalid empty input. Please use YYYY-MM-DD."
                    )
            return datetime.strptime(answer, "%Y-%m-%d")
        except ValueError:
            print("Invalid date format. Please use YYYY-MM-DD.")


@typechecked
def ask_yn_question_is_yes(*, question: str) -> bool:

    while True:
        try:
            answer = input(question).lower()
            if answer in ("y", "n"):
                return answer == "y"
            else:
                raise ValueError(
                    "Invalid empty input. Please enter 'y' or 'n'."
                )
        except ValueError:
            print("Invalid input. Please enter 'y' or 'n'.")


@typechecked
def get_input_with_az_chars_answer(
    *,
    question: str,
    allowed_empty: bool,
    allowed_chars: str = r"[a-zA-Z]",
    case_sensitive: bool = False,
) -> Union[None, str]:
    """Asks a question and validates the answer against allowed characters.

    Args:
        question: The question to ask.
        allowed_chars: A regular expression string specifying the allowed characters.
        case_sensitive: Whether the check should be case-sensitive.

    Returns:
        The validated answer (as a string).
        Raises a TypeError if the input is not a string.
    """
    flags = 0
    if not case_sensitive:
        flags = re.IGNORECASE

    while True:
        the_answer = input(
            f"{question} "
        ).strip()  # added strip to remove whitespace
        if allowed_empty and the_answer == "":
            return None
        if not isinstance(the_answer, str):
            raise TypeError("Input must be a string")  # explicit type check

        if re.fullmatch(allowed_chars, the_answer, flags=flags):
            if the_answer != "":
                return the_answer
            else:
                print(
                    "Invalid empty input. Please enter characters matching:"
                    f" {allowed_chars}"
                )
        else:
            print(f"allowed_chars:{allowed_chars}")
            print(f"the_answer:{the_answer}")
            print(f"flags:{flags}")
            print(
                f"Your input:{the_answer} is invalid. Please enter characters"
                f" matching: {allowed_chars}"
            )
