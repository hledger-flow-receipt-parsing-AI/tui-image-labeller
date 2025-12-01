import calendar
from typing import List, Tuple


def update_values(
    *,
    direction,
    edit_text: str,
    current_pos: int,
    date_only: bool,
    date_values: List,
    time_values: List,
) -> Tuple[List[int], List[int]]:
    """Main function to orchestrate updating values based on cursor
    position."""
    # edit_text = get_edit_text()
    # current_pos = edit_pos  # Use the cursor position

    # edit_text.split(date_separator)
    # Year adjustments (format: yyyy-mm-dd)
    if current_pos == 0:  # Thousands place of year
        adjust_year(date_values=date_values, direction=direction, amount=1000)
    elif current_pos == 1:  # Hundreds place of year
        adjust_year(date_values=date_values, direction=direction, amount=100)
    elif current_pos == 2:  # Tens place of year
        adjust_year(date_values=date_values, direction=direction, amount=10)
    elif current_pos == 3:  # Ones place of year
        adjust_year(date_values=date_values, direction=direction, amount=1)
    # Month adjustments
    elif current_pos == 5:  # Tens place of month
        adjust_month(date_values=date_values, direction=direction, amount=10)
    elif current_pos == 6:  # Ones place of month
        adjust_month(date_values=date_values, direction=direction, amount=1)
    # Day adjustments
    elif current_pos == 8:  # Tens place of day
        adjust_day(date_values=date_values, direction=direction, amount=10)
    elif current_pos == 9:  # Ones place of day
        adjust_day(date_values=date_values, direction=direction, amount=1)
    if not date_only:
        # Hour adjustments (after space at pos 10)
        if current_pos == 11:  # Tens place of hour
            adjust_hour(time_values=time_values, direction=direction, amount=10)
        elif current_pos == 12:  # Ones place of hour
            adjust_hour(time_values=time_values, direction=direction, amount=1)
        # Minute adjustments
        elif current_pos == 14:  # Tens place of minute
            adjust_minute(
                time_values=time_values, direction=direction, amount=10
            )
        elif current_pos == 15:  # Ones place of minute
            adjust_minute(
                time_values=time_values, direction=direction, amount=1
            )
    return date_values, time_values


def adjust_year(*, date_values, direction, amount):
    if date_values[0] is None:
        date_values[0] = 2024
    if direction == "up":
        date_values[0] += amount
    elif direction == "down":
        if (date_values[0] - amount) < 1:
            date_values[0] = 1970
        else:
            date_values[0] -= amount
    # Apply leap year bounds on day.
    if date_values[2] is not None:
        max_days = get_max_days(date_values=date_values)
        if date_values[2] > max_days:
            date_values[2] = max_days


def adjust_month(*, date_values, direction, amount):
    if date_values[1] is None:
        date_values[1] = amount
    if direction == "up":
        if (date_values[1] + amount) > 12:
            date_values[1] = 1
        else:
            date_values[1] += amount
    elif direction == "down":
        if (date_values[1] - amount) < 1:
            date_values[1] = 12
        else:
            date_values[1] -= amount
    # Apply month and leap year bounds on day.
    if date_values[2] is not None:
        max_days = get_max_days(date_values=date_values)
        if date_values[2] > max_days:
            date_values[2] = max_days


def adjust_day(*, date_values, direction, amount):
    if date_values[2] is None:
        date_values[2] = amount
    max_days = get_max_days(date_values=date_values)
    if direction == "up":
        if (date_values[2] + amount) > max_days:
            date_values[2] = 1
        else:
            date_values[2] += amount
    elif direction == "down":
        if (date_values[2] - amount) < 1:
            date_values[2] = max_days
        else:
            date_values[2] -= amount


def adjust_hour(*, time_values, direction, amount):
    if time_values[0] is None:
        time_values[0] = 0  # Default to midnight hour
    if direction == "up":
        if (time_values[0] + amount) > 23:  # 23 is max hour in 24-hour format
            time_values[0] = 0  # Wrap to start of day
        else:
            time_values[0] += amount
    elif direction == "down":
        if (time_values[0] - amount) < 0:  # 0 is min hour
            time_values[0] = 23  # Wrap to end of day
        else:
            time_values[0] -= amount


def adjust_minute(*, time_values, direction, amount):
    if time_values[1] is None:
        time_values[1] = 0  # Default to start of hour
    if direction == "up":
        if (time_values[1] + amount) > 59:  # 59 is max minute
            time_values[1] = 0  # Wrap to start of hour
        else:
            time_values[1] += amount
    elif direction == "down":
        if (time_values[1] - amount) < 0:  # 0 is min minute
            time_values[1] = 59  # Wrap to end of hour
        else:
            time_values[1] -= amount


def get_max_days(*, date_values):
    if date_values[0] is None or date_values[1] is None:
        return 31
    try:
        _, max_days = calendar.monthrange(date_values[0], date_values[1])
        return max_days
    except ValueError:
        return 31
