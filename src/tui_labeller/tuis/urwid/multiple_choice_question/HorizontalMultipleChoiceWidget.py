from typing import List, Union

import urwid
from typeguard import typechecked

from tui_labeller.tuis.urwid.question_data_classes import (
    AISuggestion,
    HorizontalMultipleChoiceQuestionData,
)


@typechecked
class HorizontalMultipleChoiceWidget(urwid.WidgetWrap):
    def __init__(self, question_data: HorizontalMultipleChoiceQuestionData):
        self.question_data: HorizontalMultipleChoiceQuestionData = question_data
        self.ai_suggestions: List[AISuggestion] = question_data.ai_suggestions
        self.selected = None
        self.choice_widgets = []
        self.radio_group = []
        self.setup_widgets()

    def get_answer_in_focus(self) -> int:
        """Returns the column index of the answer you just selected."""
        monitored_nr: int = self._wrapped_widget._contents.focus
        the_obj = self._wrapped_widget._contents[monitored_nr]
        for i, elem in enumerate(the_obj):
            if isinstance(elem, urwid.Columns):
                focus_column: int = elem.get_focus_column()
        if focus_column is not None:
            return focus_column
        raise ValueError("Did not find which column was in focus.")

    def setup_widgets(self):
        # Find the choice with the highest probability for auto-selection
        max_prob = -1
        auto_select_label = None
        if self.ai_suggestions:
            for suggestion in self.ai_suggestions:
                if suggestion.probability > max_prob:
                    max_prob = suggestion.probability
                    auto_select_label = suggestion.question_data

        # Create radio buttons and AI suggestion text for each choice in question.choices
        for i, choice in enumerate(
            self.question_data.choices
        ):  # Ensures all choices are included
            radio_button = urwid.RadioButton(
                self.radio_group,
                choice,
                state=(
                    choice == auto_select_label
                ),  # Auto-select highest probability
                on_state_change=self.on_select,
            )

            # Collect all AI suggestions for this choice
            suggestion_texts = []
            if self.ai_suggestions:  # Check if there are any suggestions at all
                for suggestion in self.ai_suggestions:
                    if suggestion.question_data == choice:
                        suggestion_texts.append(
                            urwid.Text(
                                (
                                    "ai_suggestion",
                                    (
                                        f"{suggestion.probability:.2f} {suggestion.ai_suggestions}"
                                    ),
                                ),
                                align="left",
                            )
                        )
            # If no suggestions exist for this choice, add an empty placeholder
            if not suggestion_texts:
                suggestion_texts.append(
                    urwid.Text(("ai_suggestion", ""), align="left")
                )

            # Stack the radio button and all suggestions in a Pile
            choice_column = urwid.Pile(
                [
                    urwid.AttrMap(radio_button, "normal", "selected"),
                    *suggestion_texts,  # Unpack all suggestion widgets
                ]
            )
            self.choice_widgets.append(choice_column)

        # Display choices horizontally
        choices_row = urwid.Columns(self.choice_widgets, dividechars=2)
        question_text = urwid.Text(
            ("mc_question_palette", self.question_data.question)
        )
        pile = urwid.Pile(
            [question_text, choices_row, urwid.Divider()]
        )  # Divider is new line after choices and AI suggestions.
        super().__init__(pile)

    def on_select(self, radio_button, new_state):
        if new_state:
            self.selected = radio_button.label
            self.confirm_selection()
        else:
            pass

    def confirm_selection(self):
        for widget in self.choice_widgets:
            radio = widget.contents[0][
                0
            ].base_widget  # Access radio button from Pile
            if radio.label == self.selected:
                widget.contents[0][0].set_attr_map({None: "selected"})
            else:
                radio.set_state(False, do_callback=False)
                widget.contents[0][0].set_attr_map({None: "normal"})

    def keypress(self, size, key):
        if key in ["enter", "tab", "shift tab", "end", "home", "up", "down"]:
            return self._handle_navigation_keys(key)
        if key == "left" and self.get_answer_in_focus() == 0:
            return "previous_question"
        if (
            key == "right"
            and self.get_answer_in_focus() == len(self.choice_widgets) - 1
        ):
            return self.safely_go_to_next_question()
        return super().keypress(size, key)

    def _handle_navigation_keys(self, key):
        """Handle Enter, Tab, and Shift+Tab key navigation."""

        # TODO: distinguish moving forward, backward, if forward check if has answer.
        selected_ans_col = self.get_answer_in_focus()
        if key == "tab":
            return self._handle_tab(selected_ans_col)
        if key == "shift tab":
            return self._handle_shift_tab(selected_ans_col)
        if key == "home":
            return self._handle_home(selected_ans_col)
        if key == "end":
            return self._handle_end(selected_ans_col)
        if key == "enter":
            return self._handle_enter(selected_ans_col)
        if key == "up":
            return "previous_question"
        if key == "down":
            return self.safely_go_to_next_question()
        return None

    @typechecked
    def safely_go_to_next_question(self) -> Union[str, None]:
        if not self.has_answer():
            # TODO: highlight question with red in error.
            return None
        return "next_question"

    def _handle_home(self, selected_ans_col):
        """Handle navigation to the first option."""
        if selected_ans_col == 0:
            return "previous_question"
        return self._update_focus(selected_ans_col=0, select_ans=False)

    def _handle_end(self, selected_ans_col):
        """Handle Tab key navigation to next option or question."""
        if selected_ans_col == len(self.choice_widgets) - 1:
            return self.safely_go_to_next_question()
        return self._update_focus(
            selected_ans_col=len(self.choice_widgets) - 1, select_ans=False
        )

    def _handle_tab(self, selected_ans_col):
        """Handle Tab key navigation to next option or question."""
        if selected_ans_col == len(self.choice_widgets) - 1:
            return self.safely_go_to_next_question()
        return self._move_to_next_answer(selected_ans_col)

    def _handle_shift_tab(self, selected_ans_col):
        """Handle Shift+Tab key navigation to previous option or question."""
        if selected_ans_col == 0:
            return "previous_question"
        return self._move_to_previous_answer(selected_ans_col)

    def _handle_enter(self, selected_ans_col):
        """Handle Enter key selection confirmation."""
        self._update_selection(selected_ans_col)
        self.confirm_selection()
        if self.question_data.reconfigurer:
            return "reconfigurer"
        if self.question_data.terminator:
            return "terminator"

        return self.safely_go_to_next_question()

    def _move_to_next_answer(self, selected_ans_col):
        """Move focus to the next answer option."""
        selected_ans_col = (selected_ans_col + 1) % len(self.choice_widgets)
        return self._update_focus(
            selected_ans_col=selected_ans_col, select_ans=True
        )

    def _move_to_previous_answer(self, selected_ans_col):
        """Move focus to the previous answer option."""
        selected_ans_col = (selected_ans_col - 1) % len(self.choice_widgets)
        return self._update_focus(
            selected_ans_col=selected_ans_col, select_ans=True
        )

    def _update_focus(self, selected_ans_col: int, select_ans: bool):
        """Update the selection and focus position."""
        if select_ans:
            self._update_selection(selected_ans_col)
        choices_row = self._wrapped_widget.contents[1][0]
        if isinstance(choices_row, urwid.Columns):
            choices_row.focus_position = selected_ans_col
        return None

    def _update_selection(self, selected_ans_col):
        """Helper method to update radio button states and selection."""
        for i, widget in enumerate(self.choice_widgets):
            # Iterate over each choice widget (e.g., radio button options) with its index
            radio = widget.contents[0][0].base_widget
            # Extract the actual RadioButton widget from the nested structure

            if i == selected_ans_col:
                # If this widget corresponds to the selected answer
                radio.set_state(True, do_callback=False)
                # Select it by setting its state to True, without triggering callbacks
                self.selected = radio.label
                # Store the label of the selected radio button as the current selection
            else:
                # For all other radio buttons
                radio.set_state(False, do_callback=False)
                # Ensure they are deselected, without triggering callbacks

    @typechecked
    def get_answer(self) -> str:
        """Returns the currently selected answer as a string.

        Returns:
            str: The label of the selected radio button

        Raises:
            ValueError: If no answer is selected
        """
        if self.selected is None:
            # Check if any radio button is selected in the group
            for widget in self.choice_widgets:
                radio = widget.contents[0][0].base_widget
                if radio.get_state():
                    self.selected = radio.label
                    break

            if self.selected is None:
                raise ValueError(
                    "No answer selected for question:"
                    f" '{self.question_data.question}'"
                )

        return self.selected

    @typechecked
    def has_answer(self) -> bool:
        """Checks if an answer has been selected for the multiple choice
        question.

        Returns:
            bool: True if an answer is selected, False otherwise
        """
        # If selected is already set, return True
        if self.selected is not None:
            return True

        # Check all radio buttons in the group
        for widget in self.choice_widgets:
            radio = widget.contents[0][0].base_widget
            if radio.get_state():
                # Optionally cache the result in self.selected
                self.selected = radio.label
                return True

        # No answer found
        return False

    @typechecked
    def set_answer(self, value: str) -> None:
        """Sets the selected answer for the horizontal multiple choice
        question.

        Args:
            value: The choice to select. Must be one of the valid choices in question.choices.

        Raises:
            ValueError: If the provided value is not a valid choice.
        """
        if value not in self.question_data.choices:
            raise ValueError(
                f"Value '{value}' is not a valid choice in"
                f" {self.question_data.choices}"
            )

        self.selected = value
        self._update_selection(self.question_data.choices.index(value))
        self.confirm_selection()
