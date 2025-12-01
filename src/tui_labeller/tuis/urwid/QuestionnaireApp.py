import logging
import os
from typing import Any, List, Optional, Union

import urwid
from hledger_preprocessor.TransactionObjects.Receipt import (  # For image handling
    Receipt,
)
from typeguard import typechecked
from urwid import AttrMap

from tui_labeller.file_read_write_helper import write_to_file
from tui_labeller.tuis.urwid.multiple_choice_question.HorizontalMultipleChoiceWidget import (
    HorizontalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.multiple_choice_question.VerticalMultipleChoiceWidget import (
    VerticalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.question_app.build_questionnaire import (
    build_questionnaire,
)
from tui_labeller.tuis.urwid.question_app.palette import (
    setup_palette,
)
from tui_labeller.tuis.urwid.question_data_classes import (
    DateQuestionData,
    InputValidationQuestionData,
    VerticalMultipleChoiceQuestionData,
)

log_file = os.path.join(os.path.dirname(__file__), "../../../../../log.txt")
logging.basicConfig(
    filename=log_file,
    level=logging.INFO,
    format="%(asctime)s - %(message)s",
    force=True,
)
log = logging.info


class QuestionnaireApp:
    def __init__(
        self,
        header: str,
        questions: List[
            Union[
                DateQuestionData,
                InputValidationQuestionData,
                VerticalMultipleChoiceQuestionData,
            ]
        ],
        labelled_receipts: List[Receipt],
    ):
        """Initialize the questionnaire application with a list of
        questions."""
        self.indentation_spaces: int = 1
        self.descriptor_col_width: int = 20
        self.header = header
        self.nr_of_headers: int = len(self.header.splitlines())
        self.palette = setup_palette()
        self.questions = questions
        self.inputs: List[
            Union[
                VerticalMultipleChoiceWidget,
                HorizontalMultipleChoiceWidget,
                urwid.WidgetWrap,
                AttrMap,
            ]
        ] = []
        self.labelled_receipts: List[Receipt] = labelled_receipts
        self.pile = urwid.Pile([])
        self.history_store = (
            {}
        )  # New: Dictionary to store history suggestions {question_id: [suggestions]}

        # Setup UI elements
        self.ai_suggestion_box: AttrMap = urwid.AttrMap(
            urwid.Text(
                [
                    ("ai_suggestions", "AI Suggestions:\n"),
                    (
                        "normal",
                        f"{self.indentation_spaces*" "}AI Suggestion 1\n",
                    ),
                    (
                        "normal",
                        f"{self.indentation_spaces*" "}AI Suggestion 2\n",
                    ),
                    ("normal", f"{self.indentation_spaces*" "}AI Suggestion 3"),
                ]
            ),
            "ai_suggestions",
        )
        self.history_suggestion_box = urwid.AttrMap(
            urwid.Text(
                [
                    ("history_suggestions", "History Suggestions:\n"),
                    (
                        "normal",
                        f"{self.indentation_spaces*" "}History Option 2\n",
                    ),
                    (
                        "normal",
                        f"{self.indentation_spaces*" "}History Option 3",
                    ),
                ]
            ),
            "history_suggestions",
        )
        self.error_display: AttrMap = urwid.AttrMap(
            urwid.Pile(
                [
                    urwid.Text(("normal", "Input Error(s)")),
                    urwid.Text(("error", f"{self.indentation_spaces*" "}None")),
                ]
            ),
            "",
        )
        self.navigation_display: AttrMap = urwid.AttrMap(
            urwid.Pile(
                [
                    urwid.Text(("navigation", "Navigation")),
                    urwid.Text(
                        f"{self.indentation_spaces*" "}Q          - quit"
                    ),
                    urwid.Text(
                        f"{self.indentation_spaces*' '}Shift+tab  - previous"
                        " question"
                    ),
                    urwid.Text(
                        f"{self.indentation_spaces*' '}Enter      - next"
                        " question"
                    ),
                ]
            ),
            "normal",
        )

        # Build questionnaire
        build_questionnaire(
            header=header,
            inputs=self.inputs,
            questions=self.questions,
            descriptor_col_width=self.descriptor_col_width,
            pile=self.pile,
            ai_suggestion_box=self.ai_suggestion_box,
            history_suggestion_box=self.history_suggestion_box,
            error_display=self.error_display,
            history_store=self.history_store,
        )

        # Calculate the height for each section (4 sections + 3 dividers)
        screen = urwid.raw_display.Screen()
        term_width, term_height = screen.get_cols_rows()
        section_height = max(
            3, term_height // 8
        )  # Divide by 4 for equal sections

        # Create the sidebar pile with four sections, each with fixed height
        sidebar_pile = urwid.Pile(
            [
                (
                    section_height * 3,
                    urwid.Filler(self.navigation_display, valign="top"),
                ),  # Stretch vertically
                (urwid.Divider("─")),  # Divider takes 1 line
                (
                    section_height,
                    urwid.Filler(self.error_display, valign="top"),
                ),
                (urwid.Divider("─")),
                (
                    section_height * 2,
                    urwid.Filler(self.ai_suggestion_box, valign="top"),
                ),
                (urwid.Divider("─")),
                (
                    section_height * 2,
                    urwid.Filler(self.history_suggestion_box, valign="top"),
                ),
            ]
        )

        # Create columns: main content (80%) and sidebar (20%)
        self.fill = urwid.Filler(self.pile, valign="top")
        self.columns = urwid.Columns(
            [
                ("weight", 7, self.fill),  # 80% width
                (
                    "weight",
                    3,
                    urwid.Filler(sidebar_pile, valign="top"),
                ),  # 20% width
            ]
        )

        # Setup main loop
        self.loop = urwid.MainLoop(
            self.columns, self.palette, unhandled_input=self._handle_input
        )

    def _move_focus(self, current_pos: int, key: str) -> None:
        """Move focus to next/previous question with wrap-around."""
        nr_of_questions = len(self.questions)
        if not nr_of_questions:
            raise ValueError("Should have questions.")

        if key in ["enter", "down", "tab"]:

            next_pos = (
                0 if current_pos == nr_of_questions - 1 else current_pos + 1
            )
            self.pile.focus_position = next_pos
            # self.pile.focus_position = next_pos + self.nr_of_headers # TODO: verify if this should be used instead.

        elif key == "up":
            next_pos = (
                nr_of_questions - 1 if current_pos == 0 else current_pos - 1
            )
            self.pile.focus_position = next_pos
            # self.pile.focus_position = next_pos + self.nr_of_headers # TODO: verify if this should be used instead.
        else:
            raise ValueError(
                f"Unexpected key={key}, current_pos={current_pos}."
            )
        self._update_navigation_screen()

    def _handle_input(self, key: str):
        """Handle user keyboard input."""
        current_pos: int = self.get_focus()

        log(
            f"DEBUG: QuestionnaireApp handling key={key!r},"
            f" current_pos={current_pos}"
        )
        if key in ("enter", "down", "tab", "up"):
            if current_pos >= 0:
                focused_widget = self.get_focus_widget()

                self._move_focus(current_pos, key)

        elif key == "reconfigurer":
            raise urwid.ExitMainLoop()
        elif key == "terminator":
            raise urwid.ExitMainLoop()
        elif key == "q":
            self._save_results()
            raise urwid.ExitMainLoop()
        elif key == "next_question":
            if (
                self.pile.focus_position
                < len(self.questions) - 1 + self.nr_of_headers
            ):
                self.pile.focus_position += 1
            else:
                self.pile.focus_position = self.nr_of_headers
            focused_widget = self.inputs[
                self.pile.focus_position - self.nr_of_headers
            ].base_widget
            self._update_navigation_screen()
        elif key == "previous_question":
            if self.pile.focus_position > self.nr_of_headers:
                self.pile.focus_position -= 1
                self._update_navigation_screen()
            else:
                self._move_focus(current_pos=current_pos, key="up")

        if current_pos >= 0:
            focused_widget = self.inputs[current_pos].base_widget
            if not isinstance(
                focused_widget,
                (
                    VerticalMultipleChoiceWidget,
                    HorizontalMultipleChoiceWidget,
                ),
            ):
                focused_widget.update_autocomplete()

    def _save_results(self):
        """Save questionnaire results before exit."""
        results = {}
        # for i, input_widget in enumerate(self.inputs):
        #     results[f"question_{i}"] = input_widget.base_widget.edit_text
        for i, input_widget in enumerate(self.inputs):
            question_id = self.questions[i].question_id
            results[question_id] = input_widget.base_widget.edit_text
        write_to_file("results.txt", str(results), append=True)

    @typechecked
    def run(self, alternative_start_pos: Optional[int] = None) -> None:
        """Start the questionnaire application."""
        if self.inputs:
            if alternative_start_pos is None:
                self.pile.focus_position = self.nr_of_headers  # Skip header
            else:
                self.pile.focus_position = (
                    alternative_start_pos + self.nr_of_headers
                )
            # self.inputs[1].base_widget.initalise_autocomplete_suggestions()
            if not isinstance(
                self.inputs[0].base_widget,
                (VerticalMultipleChoiceWidget, HorizontalMultipleChoiceWidget),
            ):
                self.inputs[0].base_widget.initalise_autocomplete_suggestions()
        self.loop.run()

    @typechecked
    def set_focus(self, target_position: int) -> None:
        """Set the focus to the specified question position."""
        if 0 <= target_position < len(self.questions):
            self.pile.focus_position = target_position + self.nr_of_headers
        else:
            raise ValueError(f"Invalid focus position: {target_position}")

    @typechecked
    def get_focus(self) -> int:
        current_pos = self.pile.focus_position - self.nr_of_headers
        return current_pos

    @typechecked
    def get_focus_widget(self) -> Any:
        current_pos: int = self.get_focus()
        focused_widget = self.inputs[current_pos].base_widget
        return focused_widget

    def _update_navigation_screen(self) -> None:
        focused_widget = self.get_focus_widget()
        log(f"focused_widget={focused_widget}")

        if isinstance(focused_widget, VerticalMultipleChoiceWidget):
            log("FOUND QUESTION")
            log(
                f"focused_widget.navigation_display={focused_widget.navigation_display}"
            )
            if focused_widget.navigation_display:
                updated_pile = focused_widget.navigation_display

                self.navigation_display.original_widget = updated_pile

                log(f"\n\nUpdated navigation_display content.")
