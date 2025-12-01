from datetime import datetime
from typing import List, Union

import urwid
from typeguard import typechecked
from urwid.widget.pile import Pile

from tui_labeller.tuis.urwid.date_question.helper import (
    update_values,
)
from tui_labeller.tuis.urwid.date_question.update_digit_value import (
    update_digit_value,
)
from tui_labeller.tuis.urwid.helper import get_matching_unique_suggestions
from tui_labeller.tuis.urwid.question_data_classes import (
    AISuggestion,
    DateQuestionData,
)


@typechecked
class DateTimeQuestion(urwid.Edit):
    @typechecked
    def __init__(
        self,
        question_data: DateQuestionData,
        # ai_suggestions: List[AISuggestion],
        ai_suggestion_box: urwid.AttrMap,
        pile: Pile = None,
        # date_only: bool = False,
        **kwargs,
    ):
        super().__init__(question_data.question, **kwargs)
        self.ai_suggestions: List[AISuggestion] = question_data.ai_suggestions
        self.ai_suggestion_box = ai_suggestion_box
        self.question_data: DateQuestionData = question_data
        self.pile = pile
        self.date_only = question_data.date_only
        self._in_autocomplete: bool = False
        self.error_text = urwid.Text("")
        self.help_text = urwid.Text("")
        self.date_parts = [4, 2, 2]  # year, month, day
        self.time_parts = [2, 2]  # hour, minute
        self.current_part = 0
        self.date_values = [None, None, None]  # year, month, day
        self.time_values = [None, None]  # hour, minute
        self.date_separator = "-"
        self.time_separator = ":"
        # Start with today as default value.
        today = datetime.now()
        self.date_values = [today.year, today.month, today.day]
        if not self.date_only:
            self.time_values = [today.hour, today.minute]
        self.update_text()  # Set initial text based on today's date/time
        self.initalise_autocomplete_suggestions()

    def keypress(self, size, key):
        current_pos: int = self.edit_pos
        if key == "ctrl h":
            self.show_help()
            return None

        if key == "meta u":
            if (
                self.ai_suggestions
            ):  # If there's at least 1 suggestion, accept it.
                self.apply_first_ai_suggestion()
                return "next_question"

        if key == "page up":
            # Set error message for page up from the first question
            self.error_text.base_widget.contents[1][0].set_text(
                "Go down by pressing enter"
            )
            return None

        if key == "enter":
            return (  # Signal to move to the next box (already implemented)
                "next_question"
            )
        if key in ["delete", "backspace"]:
            return None
        # TODO 3: Ensure that pressing "Tab" moves it to the next segment
        if key == "tab":
            matching_suggestions: List[str] = get_matching_unique_suggestions(
                suggestions=self.ai_suggestions,
                current_text=self.get_edit_text(),
                cursor_pos=self.edit_pos,
            )
            if len(matching_suggestions) == 1:
                self.apply_first_ai_suggestion()
                return "next_question"
            else:
                return self.move_to_next_part()
        if key == "end":
            if self.edit_pos == len(self.edit_text) - 1:
                # End at end of question moves to next question.
                return "next_question"
            self.set_edit_pos(
                len(self.edit_text) - 1
            )  # Move to last input digit.
            return None  # Do not further process the keystroke.
        if key == "home":
            if self.edit_pos == 0:
                # Home at start of question moves to previous question
                return "previous_question"
            self.set_edit_pos(0)  # Move to first input digit
            return None  # Do not further process the keystroke

        if key == "shift tab":

            if current_pos == 0:
                return "previous_question"
            return self.move_to_previous_part()
        if key == "left":
            return self.move_cursor_to_left(current_pos=current_pos)

        if key == "right":

            return self.move_cursor_to_right(current_pos=current_pos)

        if key == "up" or key == "down":
            self.date_values, self.time_values = update_values(
                direction=key,
                edit_text=self.get_edit_text(),
                current_pos=current_pos,
                date_only=self.date_only,
                date_values=self.date_values,
                time_values=self.time_values,
            )
            self.update_text()
            self.update_autocomplete()
            return None

        if key.isdigit():
            # self.update_digit_value(new_digit=key)
            self.date_values, self.time_values = update_digit_value(
                edit_text=self.get_edit_text(),
                current_pos=current_pos,
                new_digit=int(key),
                date_only=self.date_only,
                date_values=self.date_values,
                time_values=self.time_values,
            )
            self.update_text()
            return self.move_cursor_to_right(current_pos=current_pos)

        return None

    def _move_to_part(self, direction: int) -> str | None:
        """Helper method to move between parts in given direction (1 for next,
        -1 for prev)."""
        part_starts = [0, 5, 8] if self.date_only else [0, 5, 8, 11, 14]

        # Find which part we're in based on edit_pos
        current_part = 0
        for i, pos in enumerate(part_starts):
            if self.edit_pos >= pos:
                current_part = i
            else:
                break

        # Calculate new part index
        new_part = current_part + direction

        # Handle boundary conditions
        if new_part >= len(part_starts):
            self.current_part = 0
            self.set_edit_pos(0)
            return "next_question"
        elif new_part < 0:
            self.current_part = 0
            self.set_edit_pos(0)
            return "prev_question"
        else:
            self.current_part = new_part
            self.set_edit_pos(part_starts[self.current_part])
            return None

    def move_to_next_part(self):
        result = self._move_to_part(1)
        # if result == "next_question" and not self.date_only:
        return result

    def move_to_previous_part(self):
        return self._move_to_part(-1)

    def update_text(
        self,
    ):
        date_str = self.date_separator.join(
            map(
                lambda x: str(x).zfill(2) if x is not None else "00",
                self.date_values,
            )
        )
        if self.date_only:
            self.set_edit_text(date_str)
        else:
            time_str = self.time_separator.join(
                map(
                    lambda x: str(x).zfill(2) if x is not None else "00",
                    self.time_values,
                )
            )
            self.set_edit_text(date_str + " " + time_str)

    def show_help(self):
        self.help_text.set_text(
            "Use arrows to adjust, Tab to move parts, Enter to next field"
        )

    def move_cursor_to_right(self, current_pos):
        if current_pos < len(self.get_edit_text()) - 1:
            if self.date_only:
                if current_pos in [3, 6]:  # Skip date separators: yyyy-mm-dd
                    self.set_edit_pos(current_pos + 2)
                else:
                    self.set_edit_pos(current_pos + 1)
            else:
                if current_pos in [
                    3,
                    6,
                    9,
                    12,
                ]:  # Skip separators: yyyy-mm-dd hh:mm
                    self.set_edit_pos(current_pos + 2)
                else:
                    self.set_edit_pos(current_pos + 1)
            return None
        else:
            return "next_question"

    def move_cursor_to_left(self, current_pos):
        if current_pos > 0:
            if self.date_only:
                if current_pos in [5, 8]:  # Skip date separators: yyyy-mm-dd
                    self.set_edit_pos(current_pos - 2)
                else:
                    self.set_edit_pos(current_pos - 1)
            else:
                if current_pos in [
                    5,
                    8,
                    11,
                    14,
                ]:  # Skip separators: yyyy-mm-dd hh:mm
                    self.set_edit_pos(current_pos - 2)
                else:
                    self.set_edit_pos(current_pos - 1)
            return None
        else:
            return "previous_question"

    def update_autocomplete(self):
        if self._in_autocomplete:  # Prevent recursion
            return

        if not self.ai_suggestion_box:
            return

        matching_suggestions: List[str] = get_matching_unique_suggestions(
            suggestions=self.ai_suggestions,
            current_text=self.get_edit_text(),
            cursor_pos=self.edit_pos,
        )
        suggestions_text = ", ".join(matching_suggestions)

        self._in_autocomplete = True  # Set flag

        self.ai_suggestion_box.base_widget.set_text(suggestions_text)
        self.ai_suggestion_box.base_widget._invalidate()

        if "*" in self.edit_text and len(matching_suggestions) == 1:
            new_text = matching_suggestions[0]
            self.set_edit_text(new_text)
            self.set_edit_pos(len(new_text) - 1)

        self._in_autocomplete = False  # Reset flag

    def apply_first_ai_suggestion(self) -> None:
        matching_suggestions: List[str] = get_matching_unique_suggestions(
            suggestions=self.ai_suggestions,
            current_text=self.get_edit_text(),
            cursor_pos=self.edit_pos,
        )
        self.set_edit_text(matching_suggestions[0])
        self.set_edit_pos(len(matching_suggestions[0]) - 1)
        return None

    def initalise_autocomplete_suggestions(self):
        self.ai_suggestion_box.base_widget.set_text(
            ",".join(
                map(lambda x: x.question, self.ai_suggestions)
            )  # TODO: determine if question should become question_data
        )
        self.ai_suggestion_box.base_widget._invalidate()

    @typechecked
    def get_answer(self) -> Union[str, datetime]:
        """Returns the current date/time value either as a formatted string or
        datetime object.

        Returns:
            Union[str, datetime]: The current date/time value. Returns a string if any value is None,
                                otherwise returns a datetime object.
        """
        # Check if any values are None
        if any(v is None for v in self.date_values) or (
            not self.date_only and any(v is None for v in self.time_values)
        ):
            # Return the current text representation if any value is missing
            # return self.get_edit_text()
            raise ValueError(
                f"Unable to convert: {self.get_edit_text()} to date and time."
            )

        # Construct datetime object from values
        if self.date_only:
            return datetime(
                year=self.date_values[0],
                month=self.date_values[1],
                day=self.date_values[2],
            )
        else:
            return datetime(
                year=self.date_values[0],
                month=self.date_values[1],
                day=self.date_values[2],
                hour=self.time_values[0],
                minute=self.time_values[1],
            )

    @typechecked
    def has_answer(self) -> bool:
        """Checks if a valid answer can be obtained without errors.

        Returns:
            bool: True if get_answer() would return a valid result without raising an error,
                False otherwise.
        """
        try:
            self.get_answer()
            return True
        except ValueError:
            return False

    @typechecked
    def set_answer(self, value: Union[str, datetime]) -> None:
        """Sets the date/time value from either a string or datetime object.

        Args:
            value: The date/time value to set. Can be a string in the format 'YYYY-MM-DD'
                (for date_only) or 'YYYY-MM-DD HH:MM' (for date and time), or a datetime object.

        Raises:
            ValueError: If the input string format is invalid or cannot be parsed into a valid date/time.
        """
        if isinstance(value, datetime):
            self.date_values = [value.year, value.month, value.day]
            if not self.date_only:
                self.time_values = [value.hour, value.minute]
        elif isinstance(value, str):
            try:
                if self.date_only:
                    # Parse date-only string (YYYY-MM-DD)
                    parsed_date = datetime.strptime(value, "%Y-%m-%d")
                    self.date_values = [
                        parsed_date.year,
                        parsed_date.month,
                        parsed_date.day,
                    ]
                else:
                    # Parse date and time string (YYYY-MM-DD HH:MM)
                    parsed_datetime = datetime.strptime(value, "%Y-%m-%d %H:%M")
                    self.date_values = [
                        parsed_datetime.year,
                        parsed_datetime.month,
                        parsed_datetime.day,
                    ]
                    self.time_values = [
                        parsed_datetime.hour,
                        parsed_datetime.minute,
                    ]
            except ValueError as e:
                raise ValueError(
                    f"Invalid date/time string format: {value}. Expected"
                    " 'YYYY-MM-DD' or 'YYYY-MM-DD HH:MM'."
                ) from e
        else:
            raise ValueError(
                "Input must be a datetime object or a string in the correct"
                " format."
            )

        self.update_text()
        self.update_autocomplete()
