from typing import List, Tuple

from tui_labeller.tuis.urwid.date_question.helper import (
    adjust_day,
    adjust_month,
    adjust_year,
)


def update_digit_value(
    *,
    edit_text: str,
    current_pos: int,
    new_digit: int,
    date_only: bool,
    date_values: List,
    time_values: List,
) -> Tuple[List[int], List[int]]:
    """Update the active value based on cursor position and incoming digit
    value."""
    # edit_text = get_edit_text()
    # current_pos: int = edit_pos  # Use the cursor position
    current_digit = int(
        edit_text[current_pos]
    )  # Get the digit at the cursor position

    # edit_text.split(date_separator)
    # Year adjustments (format: yyyy-mm-dd)
    if current_pos in [0, 1, 2, 3]:  # Year digits
        place_values = [1000, 100, 10, 1]
        digit_index = current_pos
        change = (new_digit - current_digit) * place_values[digit_index]
        adjust_year(
            date_values=date_values,
            direction="up" if change >= 0 else "down",
            amount=abs(change),
        )

    # Month adjustments
    elif current_pos in [5, 6]:  # Month digits
        place_values = [10, 1]
        digit_index = current_pos - 5  # Adjust for position offset
        change = (new_digit - current_digit) * place_values[digit_index]
        adjust_month(
            date_values=date_values,
            direction="up" if change >= 0 else "down",
            amount=abs(change),
        )
    # Day adjustments
    elif current_pos in [8, 9]:  # Day digits
        place_values = [10, 1]
        digit_index = current_pos - 8  # Adjust for position offset
        change = (new_digit - current_digit) * place_values[digit_index]
        adjust_day(
            date_values=date_values,
            direction="up" if change >= 0 else "down",
            amount=abs(change),
        )
    # Time adjustments (only if not date_only, format: yyyy-mm-dd hh:mm)
    if not date_only:
        if current_pos in [11, 12]:  # Hour digits
            digit_index = current_pos - 11
            current_hour = time_values[0] or 0
            hour_digits = [int(d) for d in f"{current_hour:02d}"]
            hour_digits[digit_index] = new_digit
            new_hour = int("".join(map(str, hour_digits)))
            if new_hour > 23:
                new_hour = 23
            elif new_hour < 0:
                new_hour = 0
            time_values[0] = new_hour
        elif current_pos in [14, 15]:  # Minute digits
            digit_index = current_pos - 14
            current_minute = time_values[1] or 0
            minute_digits = [int(d) for d in f"{current_minute:02d}"]
            minute_digits[digit_index] = new_digit
            new_minute = int("".join(map(str, minute_digits)))
            if new_minute > 59:
                new_minute = 59
            elif new_minute < 0:
                new_minute = 0
            time_values[1] = new_minute

    return date_values, time_values
