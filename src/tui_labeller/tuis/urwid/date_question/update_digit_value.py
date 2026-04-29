from typing import List, Tuple

from tui_labeller.tuis.urwid.date_question.helper import (
    adjust_year,
    get_max_days,
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

    # Month adjustments – reconstruct the full 2-digit month from its
    # individual digits so that typing "1" then "2" gives month 12, not
    # a relative adjustment that wraps past 12.
    elif current_pos in [5, 6]:  # Month digits
        current_month = date_values[1] if date_values[1] is not None else 1
        month_digits = [int(d) for d in f"{current_month:02d}"]
        month_digits[current_pos - 5] = new_digit
        new_month = month_digits[0] * 10 + month_digits[1]
        if new_month < 1:
            new_month = 1
        elif new_month > 12:
            new_month = 12
        date_values[1] = new_month
        # Clamp day to the new month's max days.
        if date_values[2] is not None:
            max_days = get_max_days(date_values=date_values)
            if date_values[2] > max_days:
                date_values[2] = max_days

    # Day adjustments – same direct-set approach as month.
    elif current_pos in [8, 9]:  # Day digits
        current_day = date_values[2] if date_values[2] is not None else 1
        day_digits = [int(d) for d in f"{current_day:02d}"]
        day_digits[current_pos - 8] = new_digit
        new_day = day_digits[0] * 10 + day_digits[1]
        max_days = get_max_days(date_values=date_values)
        if new_day < 1:
            new_day = 1
        elif new_day > max_days:
            new_day = max_days
        date_values[2] = new_day
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
