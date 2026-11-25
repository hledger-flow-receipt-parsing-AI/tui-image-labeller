import logging
import os
import sys
import tempfile
from typing import Any, Callable, List, Optional, Union

import urwid
from hledger_core.TransactionObjects.Receipt import (  # For image handling
    Receipt,
)
from typeguard import typechecked
from urwid import AttrMap

from tui_labeller.file_read_write_helper import write_to_file
from tui_labeller.tuis.urwid.ai_suggestions import show_in_box
from tui_labeller.tuis.urwid.category_question.CategoryQuestion import (
    NEW_CATEGORY_KEY,
    CategoryQuestion,
)
from tui_labeller.tuis.urwid.category_question.CategoryTreeScreen import (
    CategoryTreeScreen,
)
from tui_labeller.tuis.urwid.category_question.dropdown import (
    DisplayOnlyPopUpTarget,
)
from tui_labeller.tuis.urwid.focus_markers import (
    focus_markers_enabled,
    format_focus_marker,
)
from tui_labeller.tuis.urwid.multiple_choice_question.HorizontalMultipleChoiceWidget import (  # noqa: E501
    HorizontalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.multiple_choice_question.VerticalMultipleChoiceWidget import (  # noqa: E501
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


def _resolve_log_file() -> str:
    """Legacy ``<repo>/../log.txt`` when writable, else ``$TUI_LABELLER_LOG``
    or a file in the temp dir, so a wheel install on another machine works."""
    explicit = os.environ.get("TUI_LABELLER_LOG")
    if explicit:
        return explicit
    legacy = os.path.join(os.path.dirname(__file__), "../../../../../log.txt")
    try:
        with open(legacy, "a", encoding="utf-8"):
            pass
        return legacy
    except OSError:
        return os.path.join(tempfile.gettempdir(), "tui_labeller.log")


log_file = _resolve_log_file()
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
        # Called with (index left, index reached) when the focus moved to
        # another question; ai_session.AiSession uses it.
        self.on_question_change: Optional[Callable[[int, int], None]] = None
        self.pile = urwid.Pile([])
        self.history_store = (
            {}
            # New: Dictionary to store history suggestions {question_id:
            # [suggestions]}
        )

        # Setup UI elements
        indent = self.indentation_spaces * " "
        self.ai_suggestion_box: AttrMap = urwid.AttrMap(
            urwid.Text(
                [
                    ("ai_suggestions", "AI Suggestions:\n"),
                    (
                        "normal",
                        f"{indent}AI Suggestion 1\n",
                    ),
                    (
                        "normal",
                        f"{indent}AI Suggestion 2\n",
                    ),
                    ("normal", f"{indent}AI Suggestion 3"),
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
                        f"{indent}History Option 2\n",
                    ),
                    (
                        "normal",
                        f"{indent}History Option 3",
                    ),
                ]
            ),
            "history_suggestions",
        )
        self.error_display: AttrMap = urwid.AttrMap(
            urwid.Pile(
                [
                    urwid.Text(("normal", "Input Error(s)")),
                    urwid.Text(("error", f"{indent}None")),
                ]
            ),
            "",
        )
        self.navigation_display: AttrMap = urwid.AttrMap(
            urwid.Pile(
                [
                    urwid.Text(("navigation", "Navigation")),
                    urwid.Text(f"{indent}Q          - quit"),
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

        # Setup main loop.  The host draws the category dropdown over the
        # questions below the field; keys, focus and cursor stay with the
        # questionnaire.
        self.popup_host = DisplayOnlyPopUpTarget(self.columns)
        self.loop = urwid.MainLoop(
            self.popup_host, self.palette, unhandled_input=self._handle_input
        )

        # Focus markers (opt-in): after every redraw whose focused question
        # changed, write an invisible OSC string naming it to stdout.  The
        # hledger-preprocessor demo harness records it to time the receipt
        # highlights; terminals and asciinema-agg ignore unknown OSC strings.
        self._focus_markers_enabled: bool = focus_markers_enabled()
        self._last_focus_marker_id: Optional[str] = None
        if self._focus_markers_enabled:
            self._install_focus_marker_hook()

    def _install_focus_marker_hook(self) -> None:
        original_draw = self.loop.draw_screen

        def draw_and_mark() -> None:
            original_draw()
            self._emit_focus_marker_if_changed()

        # urwid's MainLoop.entering_idle() calls self.draw_screen(), so an
        # instance attribute shadows the method.
        self.loop.draw_screen = draw_and_mark

    def _focused_question_id(self) -> Optional[str]:
        index = self.get_focus()
        if index < 0 or index >= len(self.questions):
            return None
        question_data = self.questions[index]
        return question_data.question_id or question_data.question.strip()

    def _emit_focus_marker_if_changed(self) -> None:
        if not self._focus_markers_enabled:
            return
        question_id = self._focused_question_id()
        if question_id is None or question_id == self._last_focus_marker_id:
            return
        self._last_focus_marker_id = question_id
        sys.stdout.write(format_focus_marker(question_id=question_id))
        sys.stdout.flush()

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
            # TODO: verify if this should be used instead:
            # self.pile.focus_position = next_pos + self.nr_of_headers

        elif key == "up":
            next_pos = (
                nr_of_questions - 1 if current_pos == 0 else current_pos - 1
            )
            self.pile.focus_position = next_pos
            # TODO: verify if this should be used instead:
            # self.pile.focus_position = next_pos + self.nr_of_headers
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
                self._move_focus(current_pos, key)

        elif key == "reconfigurer":
            raise urwid.ExitMainLoop()
        elif key == NEW_CATEGORY_KEY:
            self._open_category_tree()
        elif key == "terminator":
            missing = self.first_unanswered_required()
            if missing is None:
                raise urwid.ExitMainLoop()
            self._refuse_termination(question_index=missing)
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
            self._update_navigation_screen()
        elif key == "previous_question":
            if self.pile.focus_position > self.nr_of_headers:
                self.pile.focus_position -= 1
                self._update_navigation_screen()
            else:
                self._move_focus(current_pos=current_pos, key="up")

        reached_pos: int = self.get_focus()
        if reached_pos != current_pos and self.on_question_change is not None:
            self.on_question_change(current_pos, reached_pos)
        self.refresh_suggestion_box()

    def refresh_suggestion_box(self) -> None:
        """Show the suggestions of the question that has the focus (not those
        of the question that was just left)."""
        position: int = self.get_focus()
        if not 0 <= position < len(self.inputs):
            return
        focused_widget = self.inputs[position].base_widget
        if hasattr(focused_widget, "update_autocomplete"):
            focused_widget.update_autocomplete()
        else:
            show_in_box(box=self.ai_suggestion_box, body="-")

    def _open_category_tree(self) -> None:
        """Show the new-category screen instead of the questionnaire until the
        user picks or creates a category, or cancels."""
        widget = self.get_focus_widget()
        if not isinstance(widget, CategoryQuestion):
            return

        def use(path: str) -> None:
            self.loop.widget = self.popup_host
            # Continue exactly as when the category is answered in the
            # field (a reconfigurer ends this run of the main loop).
            result = widget.accept_category(path=path)
            if result is not None:
                self._handle_input(result)

        def cancel() -> None:
            self.loop.widget = self.popup_host

        self.loop.widget = CategoryTreeScreen(
            store=widget.store,
            typed_text=widget.edit_text,
            on_use=use,
            on_cancel=cancel,
        )

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
    def first_unanswered_required(
        self, *, default: Optional[int] = None
    ) -> Optional[int]:
        """Index of the first required question without an answer.

        Returns *default* when every required question is answered.
        """
        for index, input_widget in enumerate(self.inputs):
            widget = input_widget.base_widget
            question_data = getattr(widget, "question_data", None)
            if question_data is None or not question_data.ans_required:
                continue
            if question_data.terminator:
                # "Done with this receipt?" is the finishing action, not an
                # answer to collect; it is never a resume target.
                continue
            if not widget.has_answer():
                return index
            if (
                isinstance(widget, CategoryQuestion)
                and not widget.is_known_category()
            ):
                # Text that is not an existing category is not an answer
                # (e.g. an old receipt reopened with a misspelt category).
                return index
        return default

    @typechecked
    def _refuse_termination(self, *, question_index: int) -> None:
        """Keep the questionnaire open: focus the unanswered required question,
        paint it red, explain in the error panel, and un-select every
        terminator so ``is_terminated()`` stays False."""
        indent = self.indentation_spaces * " "
        question = self.questions[question_index].question.strip()
        for input_widget in self.inputs:
            widget = input_widget.base_widget
            question_data = getattr(widget, "question_data", None)
            if (
                question_data is not None
                and question_data.terminator
                and hasattr(widget, "clear_answer")
            ):
                widget.clear_answer()
        self.set_focus(question_index)
        target = self.inputs[question_index]
        if isinstance(target, AttrMap):
            target.set_attr_map({None: "error"})
        self.error_display.base_widget.contents[1][0].set_text(
            ("error", f"{indent}Answer required: {question}")
        )
        self._update_navigation_screen()

    def _initialise_first_autocomplete(self) -> None:
        if self.inputs and not isinstance(
            self.inputs[0].base_widget,
            (VerticalMultipleChoiceWidget, HorizontalMultipleChoiceWidget),
        ):
            self.inputs[0].base_widget.initalise_autocomplete_suggestions()

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
            self._initialise_first_autocomplete()
            self.announce_focus()
        self.loop.run()

    @typechecked
    def run_from_question(self, *, question_index: int) -> None:
        """Start the loop with focus on the 0-based *question_index*."""
        if self.inputs:
            self.set_focus(question_index)
            self._initialise_first_autocomplete()
            self.announce_focus()
        self.loop.run()

    @typechecked
    def announce_focus(self) -> None:
        """Tell the listener which question has the focus now (nothing was
        left: -1) and show that question's suggestions."""
        if self.on_question_change is not None:
            self.on_question_change(-1, self.get_focus())
        self.refresh_suggestion_box()

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
            nav = focused_widget.navigation_display
            log(f"focused_widget.navigation_display={nav}")
            if focused_widget.navigation_display:
                updated_pile = focused_widget.navigation_display

                self.navigation_display.original_widget = updated_pile

                log("\n\nUpdated navigation_display content.")
