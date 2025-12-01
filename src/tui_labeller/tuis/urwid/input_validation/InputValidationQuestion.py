import re
from typing import Dict, List, Optional, Union

import urwid
from typeguard import typechecked

from tui_labeller.tuis.urwid.helper import get_matching_unique_suggestions
from tui_labeller.tuis.urwid.input_validation.autocomplete_filtering import (
    get_filtered_suggestions,
)
from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_data_classes import (
    InputValidationQuestionData,
)


class InputValidationQuestion(urwid.Edit):
    @typechecked
    def __init__(
        self,
        question_data: InputValidationQuestionData,
        # ans_required: bool,
        # ai_suggestions=None,
        # history_suggestions=None,
        history_store: Dict,
        ai_suggestion_box=None,
        history_suggestion_box=None,
        pile=None,
        question_id: Optional[str] = None,
    ):
        super().__init__(caption=question_data.question)
        self.question_data: InputValidationQuestionData = question_data
        self.input_type: InputType = question_data.input_type
        self.ai_suggestions = question_data.ai_suggestions or []
        self.history_suggestions = question_data.history_suggestions or []
        self.ai_suggestion_box = ai_suggestion_box
        self.history_suggestion_box = history_suggestion_box
        self.pile = pile
        self._in_autocomplete: bool = False
        self.question_id = (
            question_id or question_data.question
        )  # TODO: improve naming.
        self.history_store = history_store

    # def valid_char(self, ch):
    #     return len(ch) == 1 and (ch.isalpha() or ch in [":", "*"])
    def valid_char(self, ch: str):
        """Check if a character is valid based on specified mode.

        Args:
            ch: Character to check (string of length 1)
            mode: InputType enum - LETTERS for a-Z/:/* or NUMBERS for digits and .

        Returns:
            bool: True if character is valid for the specified mode
        """
        if len(ch) != 1:
            return False

        if self.input_type == InputType.LETTERS:
            return ch.isalpha() or ch in ["*"]
        elif self.input_type == InputType.LETTERS_SEMICOLON:
            return ch.isalpha() or ch in [":", "*"]
        elif self.input_type == InputType.FLOAT:
            return ch.isdigit() or ch == "."
        elif self.input_type == InputType.INTEGER:
            return ch.isdigit()
        elif self.input_type == InputType.LETTERS_AND_SPACE:
            return ch.isalpha() or ch == " "
        elif self.input_type == InputType.LETTERS_AND_NRS:
            return ch.isalpha() or ch.isdigit()
        else:
            raise ValueError(
                "Mode must be a InputType enum value, found"
                f" type:{type(self.input_type)} with value:{self.input_type}"
            )

    def is_valid_answer(self):
        if self.inputs is None:
            return False
        return self.inputs != ""

    def safely_go_to_next_question(self) -> Union[str, None]:
        if self.edit_text.strip():  # Check if current input has text
            self.owner.set_attr_map({None: "normal"})
            return "next_question"
        # Set highlighting to error if required and empty
        if self.question_data.ans_required:
            self.owner.set_attr_map({None: "error"})
            return None
        else:
            return "next_question"

    def handle_attempt_to_navigate_to_previous_question(
        self,
    ) -> Union[str, None]:
        if self.pile.focus_position > 1:  # TODO: parameterise header
            return "previous_question"
        else:
            self.owner.set_attr_map({None: "direction"})
            return None

    def safely_go_to_previous_question(self) -> Union[str, None]:
        """Allow the user to go up and change an answer unless at the first
        question.

        If the user is not at the first question, they can move to the previous question
        even if the current answer is invalid. However, if the user is at the first question,
        they are not allowed to go back to prevent looping to the last question.

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

    def keypress(self, size, key):
        """Overrides the internal/urwid pip package method "keypress" to map
        incoming keys into separate behaviour."""
        if key == "meta u":
            matching_suggestions: List[str] = get_matching_unique_suggestions(
                suggestions=self.ai_suggestions,
                current_text=self.get_edit_text(),
                cursor_pos=self.edit_pos,
            )
            if len(matching_suggestions) >= 1:
                self.apply_suggestion(matching_suggestions=matching_suggestions)
                return self.safely_go_to_next_question()
        if key == "ctrl u":
            matching_suggestions: List[str] = get_matching_unique_suggestions(
                suggestions=self.history_suggestions,
                current_text=self.get_edit_text(),
                cursor_pos=self.edit_pos,
            )
            if len(matching_suggestions) >= 1:
                self.apply_suggestion(matching_suggestions=matching_suggestions)
                return self.safely_go_to_next_question()

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
            # return "enter"
            return self.safely_go_to_next_question()
        if key == "up":
            return self.safely_go_to_previous_question()
        if key == "down":
            return self.safely_go_to_next_question()
        elif key in ("delete", "backspace", "left", "right"):
            result = super().keypress(size, key)
            self.update_autocomplete()
            return result
        elif self.valid_char(ch=key):
            result = super().keypress(size, key)
            self.update_autocomplete()
            return result
        return None

    def _match_pattern(self, suggestion):
        pattern = self.edit_text.lower().replace("*", ".*")
        return bool(re.match(f"^{pattern}$", suggestion.lower()))

    def update_autocomplete(self):
        if self._in_autocomplete:  # Prevent recursion
            raise NotImplementedError("Prevented recursion.")

        # See if flag can be deleted.
        self._in_autocomplete = True  # Set flag
        self._update_ai_suggestions()
        self._update_history_suggestions()

        self._handle_autocomplete()
        self._in_autocomplete = False  # Reset flag

    def _update_ai_suggestions(self):
        """Update the AI suggestion box with filtered suggestions."""
        if not self.ai_suggestion_box or not self.ai_suggestions:
            return

        ai_remaining_suggestions = get_filtered_suggestions(
            input_text=self.edit_text,
            available_suggestions=list(
                map(lambda x: x.question, self.ai_suggestions)
            ),
        )
        ai_suggestions_text = ", ".join(ai_remaining_suggestions)
        self._set_suggestion_text(self.ai_suggestion_box, ai_suggestions_text)
        return ai_remaining_suggestions

    def _update_history_suggestions(self):
        """Update the history suggestion box with filtered suggestions."""
        if not self.history_suggestion_box:
            self._set_suggestion_text(self.history_suggestion_box, "")
            return []

        # history_remaining_suggestions = get_filtered_suggestions(
        #     input_text=self.edit_text,
        #     available_suggestions=list(
        #         map(lambda x: x.question, self.history_suggestions)
        #     ),
        # )

        # history_suggestions_text = ", ".join(history_remaining_suggestions)
        # self._set_suggestion_text(
        #     self.history_suggestion_box, history_suggestions_text
        # )
        # return history_remaining_suggestions

        # Fetch suggestions from global history_store
        history_remaining_suggestions = get_filtered_suggestions(
            input_text=self.edit_text,
            available_suggestions=self.history_store.get(
                self.question_data.question_id, []
            ),
        )
        history_suggestions_text = ", ".join(history_remaining_suggestions)
        self._set_suggestion_text(
            self.history_suggestion_box, history_suggestions_text
        )
        return history_remaining_suggestions

    def _set_suggestion_text(self, suggestion_box, text):
        """Set text in a suggestion box and invalidate it."""
        suggestion_box.base_widget.set_text(text)
        suggestion_box.base_widget._invalidate()

    def _handle_autocomplete(self):
        """Handle wildcard-based autocompletion."""
        if "*" not in self.edit_text:
            self.owner.set_attr_map({None: "normal"})
            return
        ai_suggestions = self._update_ai_suggestions() or []
        history_suggestions = self._update_history_suggestions() or []

        if len(ai_suggestions) == 1:
            self._apply_autocomplete(ai_suggestions[0])
        elif len(history_suggestions) == 1:
            self._apply_autocomplete(history_suggestions[0])

    def _apply_autocomplete(self, new_text):
        """Apply the autocompleted text and move cursor to the end."""
        self.set_edit_text(new_text)
        self.set_edit_pos(len(new_text))

    def apply_suggestion(self, matching_suggestions: List[str]) -> None:
        self.set_edit_text(matching_suggestions[0])
        self.set_edit_pos(len(matching_suggestions[0]))
        return None

    def initalise_autocomplete_suggestions(self):
        self.update_autocomplete()

    @typechecked
    def get_answer(self) -> Union[str, float, int]:
        """Returns the current input value converted to the appropriate type
        based on input_type.

        Returns:
            Union[str, float, int]: The current input value as:
                - str for InputType.LETTERS
                - float for InputType.FLOAT
                - int for InputType.INTEGER

        Raises:
            ValueError: If the input cannot be converted to the specified type or is empty when required
        """
        current_text = self.get_edit_text().strip()

        # Check if answer is required but empty
        if self.question_data.ans_required and not current_text:

            raise ValueError(
                "Answer is required but input is empty for"
                f" '{self.question_data.question.replace('\n','')}'"
            )

        # Return empty string if no input and not required
        if not current_text:

            return ""

        # Convert based on input type

        if self.input_type in [
            InputType.LETTERS,
            InputType.LETTERS_SEMICOLON,
            InputType.LETTERS_AND_SPACE,
            InputType.LETTERS_AND_NRS,
        ]:

            return current_text
        elif self.input_type == InputType.FLOAT:

            return float(current_text)
        elif self.input_type == InputType.INTEGER:

            return int(current_text)
        else:

            raise ValueError(f"Unknown input type: {self.input_type}")

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
    def set_answer(self, value: Union[str, float, int]) -> None:
        """Sets the input value based on the input_type.

        Args:
            value: The value to set. Must match the expected type based on input_type:
                - str for InputType.LETTERS, InputType.LETTERS_SEMICOLON, InputType.LETTERS_AND_SPACE, or InputType.LETTERS_AND_NRS
                - float for InputType.FLOAT
                - int for InputType.INTEGER

        Raises:
            ValueError: If the value type does not match the expected input_type or is invalid.
        """
        # Validate input based on input_type
        if self.input_type in [
            InputType.LETTERS,
            InputType.LETTERS_SEMICOLON,
            InputType.LETTERS_AND_SPACE,
            InputType.LETTERS_AND_NRS,
        ]:
            if not isinstance(value, str):
                raise ValueError(
                    f"Expected string for input_type {self.input_type}, got"
                    f" {type(value)}"
                )
            # Validate characters
            if value and not all(self.valid_char(ch) for ch in value):
                raise ValueError(
                    f"Invalid characters in '{value}' for input_type"
                    f" {self.input_type}"
                )
        elif self.input_type == InputType.FLOAT:
            if not isinstance(value, (float, int)):
                raise ValueError(
                    f"Expected float or int for input_type {self.input_type},"
                    f" got {type(value)}"
                )
            value = str(float(value))  # Convert to string for edit_text
        elif self.input_type == InputType.INTEGER:
            if not isinstance(value, int):
                raise ValueError(
                    f"Expected int for input_type {self.input_type}, got"
                    f" {type(value)}"
                )
            value = str(value)  # Convert to string for edit_text
        else:
            raise ValueError(f"Unknown input_type: {self.input_type}")

        # Set the text and update autocomplete
        self.set_edit_text(str(value))
        self.update_autocomplete()

        # Store answer in history_store
        question_id = self.question_id
        if question_id not in self.history_store:
            self.history_store[question_id] = []
        if str(value) not in self.history_store[question_id]:
            self.history_store[question_id].append(str(value))

        # Update address history if this is the categories question
        if "\nbookkeeping expense category:" in question_id.lower():
            address_question_id = None
            if hasattr(self, "questions"):
                for q in self.questions:
                    if "address" in q.question_id.lower():
                        address_question_id = q.question_id
                        break
            if address_question_id and str(value) not in self.history_store.get(
                address_question_id, []
            ):
                self.history_store.setdefault(address_question_id, []).append(
                    str(value)
                )
