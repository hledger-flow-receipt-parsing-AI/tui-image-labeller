from typing import List, Union

import urwid
from hledger_preprocessor.Currency import Currency
from typeguard import typechecked
from urwid import AttrMap

from tui_labeller.tuis.urwid.helper import get_matching_unique_suggestions
from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.multiple_choice_question.helper import (
    get_selected_caption,
    get_vc_question,
)
from tui_labeller.tuis.urwid.question_data_classes import (
    VerticalMultipleChoiceQuestionData,
)


class VerticalMultipleChoiceWidget(urwid.Edit):
    BATCH_SIZE = 15

    @typechecked
    def __init__(
        self,
        question_data: VerticalMultipleChoiceQuestionData,
        ai_suggestions=None,
        history_suggestions=None,
        ai_suggestion_box=None,
        history_suggestion_box=None,
        pile=None,
    ):
        self.indentation: int = 1
        self.current_batch: int = 0
        self.question_data: VerticalMultipleChoiceQuestionData = question_data
        super().__init__(caption=self._get_batch_caption())
        self.input_type: InputType = InputType.INTEGER
        self.ai_suggestions = ai_suggestions or []
        self.history_suggestions = history_suggestions or []
        self.ai_suggestion_box = ai_suggestion_box
        self.history_suggestion_box = history_suggestion_box
        self.pile = pile
        self._in_autocomplete: bool = False
        if question_data.navigation_display:
            self.navigation_display: Union[None, AttrMap] = (
                question_data.navigation_display
            )
        else:
            self.navigation_display: Union[None, AttrMap] = None

    @typechecked
    def _get_batch_choices(self) -> List[str]:
        """Returns the choices for the current batch."""
        start = self.current_batch * self.BATCH_SIZE
        end = start + self.BATCH_SIZE
        return self.question_data.choices[start:end]

    @typechecked
    def _get_batch_caption(self) -> str:
        """Returns the caption for the current batch of choices."""
        return get_vc_question(
            vc_question_data=self.question_data,
            indentation=self.indentation,
            batch_start=self.current_batch * self.BATCH_SIZE,
            batch_size=self.BATCH_SIZE,
        )

    @typechecked
    def _get_batch_selected_caption(self, selected_index: int) -> str:
        """Returns the caption for the selected choice in the current batch."""
        return get_selected_caption(
            vc_question_data=self.question_data,
            selected_index=selected_index,
            indentation=self.indentation,
        )

    @typechecked
    def valid_char(self, ch: str):
        """Check if a character is valid based on specified mode.

        Args:
            ch: Character to check (string of length 1)

        Returns:
            bool: True if character is valid for the specified mode
        """
        if len(ch) != 1:

            return False
        if ch.isdigit():
            return True
        return False

    @typechecked
    def is_valid_answer(self):
        if self.edit_text is None:
            return False
        return self.edit_text != ""

    @typechecked
    def safely_go_to_next_question(self) -> Union[str, None]:
        if self.edit_text.strip():  # Check if current input has text
            self.owner.set_attr_map({None: "normal"})
            self.set_caption(
                self._get_batch_selected_caption(
                    selected_index=int(self.get_edit_text())
                )
            )
            return self.return_next_question_or_reconfigurer()
        # Set highlighting to error if required and empty
        if self.question_data.ans_required:
            self.owner.set_attr_map({None: "error"})
            return None
        else:
            self.set_caption(
                self._get_batch_selected_caption(
                    selected_index=int(self.get_edit_text())
                )
            )
            return self.return_next_question_or_reconfigurer()

    @typechecked
    def return_next_question_or_reconfigurer(self) -> str:
        if self.question_data.reconfigurer:
            return "reconfigurer"
        else:
            return "next_question"

    @typechecked
    def handle_attempt_to_navigate_to_previous_question(
        self,
    ) -> Union[str, None]:
        if self.pile.focus_position > 1:  # TODO: parameterise header
            return "previous_question"
        else:
            self.owner.set_attr_map({None: "direction"})
            return None

    @typechecked
    def safely_go_to_previous_question(self) -> Union[str, None]:
        """Allow the user to go up and change an answer unless at the first
        question.

        Returns:
            str: "previous_question" if allowed to proceed to the previous question.
            None: If the answer is required and empty, highlighting is set to error.
        """
        if self.edit_text.strip():  # Check if current input has text.
            self.owner.set_attr_map({None: "normal"})
            return self.handle_attempt_to_navigate_to_previous_question()
        # Set highlighting to error if required and empty.
        if self.question_data.ans_required:
            self.owner.set_attr_map({None: "error"})
            return self.handle_attempt_to_navigate_to_previous_question()
        else:
            return self.handle_attempt_to_navigate_to_previous_question()

    @typechecked
    def _navigate_to_next_batch(self) -> bool:
        """Attempts to navigate to the next batch of choices.

        Returns:
            bool: True if navigation was successful, False otherwise.
        """
        max_batch = (len(self.question_data.choices) - 1) // self.BATCH_SIZE
        if self.current_batch < max_batch:
            self.current_batch += 1
            self.set_caption(self._get_batch_caption())
            self.set_edit_text("")  # Clear input for new batch
            return True
        return False

    @typechecked
    def _navigate_to_previous_batch(self) -> bool:
        """Attempts to navigate to the previous batch of choices.

        Returns:
            bool: True if navigation was successful, False otherwise.
        """
        if self.current_batch > 0:
            self.current_batch -= 1
            self.set_caption(self._get_batch_caption())
            self.set_edit_text("")  # Clear input for new batch
            return True
        return False

    @typechecked
    def keypress(self, size, key):
        """Overrides the internal/urwid pip package method "keypress" to map
        incoming keys into separate behaviour."""
        if key == "tab":
            matching_suggestions: List[str] = get_matching_unique_suggestions(
                suggestions=self.ai_suggestions + self.history_suggestions,
                current_text=self.get_edit_text(),
                cursor_pos=self.edit_pos,
            )
            if len(matching_suggestions) == 1:
                self.apply_suggestion(matching_suggestions=matching_suggestions)
                return self.safely_go_to_next_question()

        if key == "home":
            if self.edit_pos == 0:
                # Home at start of question moves to previous question.
                return self.safely_go_to_previous_question()
            self.set_edit_pos(0)  # Move back to start.
            return None

        if key == "end":
            if self.edit_pos == len(self.edit_text):
                # End at end of question moves to next question.
                return self.safely_go_to_next_question()
            self.set_edit_pos(len(self.edit_text))  # Move to end of input box.
            return None

        if key == "shift tab":
            return self.safely_go_to_previous_question()

        if key == "enter":
            if len(self.edit_text) != 0:
                try:
                    current_index = int(self.edit_text)
                    max_choice = len(self.question_data.choices) - 1
                    if 0 <= current_index <= max_choice:
                        self.set_caption(
                            self._get_batch_selected_caption(
                                selected_index=current_index
                            )
                        )
                        return self.safely_go_to_next_question()
                except ValueError:
                    pass
            return None

        if key == "up":
            return self.safely_go_to_previous_question()

        if key == "down":
            return self.safely_go_to_next_question()

        if key == "right":
            if self._navigate_to_next_batch():
                return None
            return None

        if key == "left":
            if self._navigate_to_previous_batch():
                return None
            return None

        elif key in ("delete", "backspace"):
            # Handle backspace/delete by calling super() first to update the text
            result = super().keypress(size, key)
            # Update caption to show the full batch question
            self.set_caption(self._get_batch_caption())
            return result

        elif self.valid_char(ch=key):
            # Calculate batch boundaries
            batch_start = self.current_batch * self.BATCH_SIZE
            batch_choices = self._get_batch_choices()
            batch_end = batch_start + len(batch_choices)

            # Check if the new input would be valid
            new_text = self.edit_text + key
            try:
                value: int = int(new_text)
                # if batch_start <= value <= batch_end :
                if self.is_valid_batch_choice(
                    value=value,
                    batch_start=batch_start,
                    batch_end=batch_end,
                    batch_choices=batch_choices,
                ):
                    self.set_edit_text(new_text)
                    self.set_edit_pos(len(new_text))
                    self.set_caption(self._get_batch_caption())
                    self.do_something(
                        new_text=new_text,
                        batch_start=batch_start,
                        batch_end=batch_end,
                        value=value,
                    )
            except ValueError:
                input(f"Not a valid input:{new_text}")
            return None

        return None

    @typechecked
    def is_valid_batch_choice(
        self,
        value: int,
        batch_start: int,
        batch_end: int,
        batch_choices: List[str],
    ) -> bool:
        # Check if value is within the valid range
        # if not (batch_start <= value <= batch_end):
        #     return False

        # for choice in batch_choices:
        for index in range(batch_start, batch_end):
            # Exact match: value matches the choice completely
            if value == index:
                return True

            # Partial match: choice starts with value_str, but only if choice is not preceded by other digits
            # if choice.startswith(value_str) and (len(choice) == len(value_str) or choice[len(value_str)].isdigit()):
            if str(index).startswith(str(value)):

                return True
        return False

    @typechecked
    def do_something(
        self, new_text: str, batch_start: int, batch_end: int, value: int
    ) -> Union[None, str]:
        # Check if the input is a complete, non-extendable choice
        max_choice = batch_end
        can_extend = False
        max_digits = len(str(max_choice))

        if len(new_text) < max_digits:
            for digit in range(10):

                extended_text = new_text + str(digit)

                try:
                    extended_value = int(extended_text)

                    if batch_start <= extended_value <= max_choice:
                        can_extend = True
                        break
                except ValueError:
                    continue

        if not can_extend:
            self.set_caption(
                self._get_batch_selected_caption(selected_index=value)
            )
            return self.safely_go_to_next_question()

        return new_text

    @typechecked
    def get_answer(self) -> str:
        choice: int = int(self.get_edit_text())
        return self.question_data.choices[choice]

    @typechecked
    def get_int_answer(self) -> int:
        return int(self.get_edit_text())

    @typechecked
    def has_answer(self) -> bool:
        """Checks if a valid answer can be obtained without errors and edit
        text is not empty.

        Returns:
            bool: True if get_answer() would return a valid result without raising an error
                and edit text is not empty, False otherwise.
        """
        if not self.get_edit_text():  # Check if edit text is empty
            return False
        try:
            self.get_answer()
            return True
        except (
            ValueError,
            IndexError,
        ):  # Handle invalid index or non-integer input
            return False

    @typechecked
    def set_answer(self, value: Union[str, int, Currency]) -> None:
        """Sets the answer for the multiple choice question based on the
        provided value.

        Args:
            value: The value to set. Can be either:
                - str: The exact choice text from question.choices.
                - int: The index of the choice in question.choices.

        Raises:
            ValueError: If the value is not a valid choice or index, or if the type is incorrect.
        """
        if isinstance(value, str):
            # Check if the string is a valid choice
            if value not in self.question_data.choices:
                raise ValueError(
                    f"Value '{value}' is not a valid choice in"
                    f" {self.question_data.choices}"
                )
            # Find the index of the choice.
            index = self.question_data.choices.index(value)
            self.current_batch = index // self.BATCH_SIZE  # Set correct batch
            self.set_edit_text(str(index))
        elif isinstance(value, int):
            # Check if the index is valid
            if not (0 <= value < len(self.question_data.choices)):
                raise ValueError(
                    f"Index {value} is out of range for choices"
                    f" {self.question_data.choices}"
                )
            self.current_batch = value // self.BATCH_SIZE  # Set correct batch
            self.set_edit_text(str(value))

        elif isinstance(value, Currency):
            # Check if the string is a valid choice
            if value.value not in self.question_data.choices:
                raise ValueError(
                    f"Value '{value}' is not a valid choice in"
                    f" {self.question_data.choices}"
                )
            # Find the index of the choice.
            index = self.question_data.choices.index(value.value)
            self.current_batch = index // self.BATCH_SIZE  # Set correct batch
            self.set_edit_text(str(index))
        else:
            raise ValueError(f"Expected str or int, got {type(value)}")

        # Update the caption to reflect the selected choice
        self.set_caption(
            self._get_batch_selected_caption(
                selected_index=int(self.get_edit_text())
            )
        )

    @typechecked
    def refresh_choices(self) -> None:
        """Refresh the widget's choices based on the updated
        question_data.choices.

        Updates the displayed caption to reflect the current batch of
        choices and clears the input text to ensure valid input for the
        new choices. If a valid answer exists, it attempts to preserve
        it if it remains in the new choices. Adjusts the current batch
        to ensure the choices are displayed correctly.
        """
        # Preserve the current answer if it exists and is still valid
        current_answer = None
        if self.has_answer():
            try:
                current_answer = self.get_answer()
            except (ValueError, IndexError):
                current_answer = None

        # Reset the current batch if it's out of bounds for the new choices
        max_batch = (len(self.question_data.choices) - 1) // self.BATCH_SIZE
        if self.current_batch > max_batch:
            self.current_batch = max_batch if max_batch >= 0 else 0

        # Update the caption to reflect the current batch
        self.set_caption(self._get_batch_caption())

        # Clear the current input text
        self.set_edit_text("")

        # If there was a previous valid answer, try to restore it
        if current_answer and current_answer in self.question_data.choices:
            try:
                self.set_answer(current_answer)
            except ValueError:
                # If the answer can't be set (e.g., due to index issues), clear it
                self.set_edit_text("")
