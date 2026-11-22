"""The "Bookkeeping expense category" question when the categories file is
known: an autocomplete field over the existing categories."""

from typing import Any, Dict, List, Optional, Tuple

import urwid
from typeguard import typechecked

from tui_labeller.categories.category_store import CategoryStore
from tui_labeller.tuis.urwid.category_question.dropdown import (
    CategoryDropdown,
    dropdown_size,
)
from tui_labeller.tuis.urwid.input_validation.InputValidationQuestion import (
    InputValidationQuestion,
)
from tui_labeller.tuis.urwid.question_data_classes import (
    CategoryQuestionData,
)

# Returned from keypress(); QuestionnaireApp opens the new-category screen.
NEW_CATEGORY_KEY = "new_category"
_LEAVING_KEYS = ("reconfigurer", "next_question", "previous_question")
NO_ROW = -1


class CategoryQuestion(InputValidationQuestion):
    """Typing filters the categories; a list under the field shows them.

    The field never accepts text that is not an existing category, so a typo
    cannot silently become a new category.  Row 0 of the list ("+ new
    category") leads to the screen where one is created deliberately.

    ``highlighted_row`` 0 is that row, ``i`` is ``matches[i - 1]``, and -1
    is no row at all: while the field is empty nothing is highlighted, so a
    stray Enter cannot pick whichever category happens to come first.
    """

    # The list depends on state the canvas cache does not know about.
    no_cache = ["render"]

    @typechecked
    def __init__(
        self,
        question_data: CategoryQuestionData,
        history_store: Dict,
        ai_suggestion_box: Any = None,
        history_suggestion_box: Any = None,
        pile: Any = None,
        question_id: Optional[str] = None,
    ) -> None:
        # Set before Edit.__init__, which already calls set_edit_text().
        self.store: CategoryStore = question_data.category_store
        self.matches: List[str] = []
        self.highlighted_row: int = NO_ROW
        self.dropdown_open: bool = True
        self._total: int = 0
        self._longest: int = 0
        super().__init__(
            question_data=question_data,
            history_store=history_store,
            ai_suggestion_box=ai_suggestion_box,
            history_suggestion_box=history_suggestion_box,
            pile=pile,
            question_id=question_id,
        )
        self._refilter()

    # ------------------------------------------------------------- state

    def _refilter(self) -> None:
        """Recompute the matches for the current text; highlight the best."""
        all_paths = self.store.paths()
        self._total = len(all_paths)
        self._longest = max((len(path) for path in all_paths), default=0)
        self.matches = self.store.matches(text=self.edit_text)
        if not self.edit_text.strip():
            self.highlighted_row = NO_ROW
        else:
            self.highlighted_row = 1 if self.matches else 0
        self._invalidate()

    def set_edit_text(self, text: str) -> None:
        super().set_edit_text(text)
        self._refilter()

    def _set_open(self, *, is_open: bool) -> None:
        self.dropdown_open = is_open
        self._invalidate()

    def _fill(self, *, path: str) -> None:
        self._default_untouched = False
        self.question_data.user_edited = True
        self.set_edit_text(path)
        self.set_edit_pos(len(path))

    @typechecked
    def is_known_category(self) -> bool:
        """True when the text is a category that exists."""
        return self.store.exists(path=self.edit_text)

    @typechecked
    def accept_category(self, *, path: str) -> Optional[str]:
        """Put *path* in the field and continue to the next question."""
        self._fill(path=path)
        return self.safely_go_to_next_question()

    # -------------------------------------------------------------- keys

    def safely_go_to_next_question(self) -> Optional[str]:
        """Continue only when the text is an existing category."""
        text = self.edit_text.strip().lower()
        if not self.store.exists(path=text):
            self.owner.set_attr_map({None: "error"})
            self._set_open(is_open=True)
            return None
        if self.edit_text != text:
            self.set_edit_text(text)
            self.set_edit_pos(len(text))
        self.owner.set_attr_map({None: "normal"})
        if self.question_data.reconfigurer:
            return "reconfigurer"
        return "next_question"

    def _handle_autocomplete(self) -> None:
        """The list does the completing; a typed '*' only filters.

        (The parent replaces the text with a unique AI/history
        suggestion.)
        """

    def keypress(self, size: Tuple[int], key: str) -> Optional[str]:
        result = self._handle_key(size=size, key=key)
        if result in _LEAVING_KEYS:
            # Open again the next time the field gets focus.
            self.dropdown_open = True
        return result

    def _handle_key(self, *, size: Tuple[int], key: str) -> Optional[str]:
        if key == "esc":
            self._set_open(is_open=False)
            return None
        if key == "enter":
            if not self.dropdown_open or self.highlighted_row == NO_ROW:
                return self.safely_go_to_next_question()
            if self.highlighted_row == 0:
                return NEW_CATEGORY_KEY
            return self.accept_category(
                path=self.matches[self.highlighted_row - 1]
            )
        if key == "down":
            if not self.dropdown_open:
                return self.safely_go_to_next_question()
            if self.highlighted_row < len(self.matches):
                self.highlighted_row += 1
                self._invalidate()
            return None
        if key == "up":
            if self.dropdown_open and self.highlighted_row > 0:
                self.highlighted_row -= 1
                self._invalidate()
                return None
            return self.safely_go_to_previous_question()
        if key == "tab":
            if self.dropdown_open and self.highlighted_row > 0:
                self._fill(path=self.matches[self.highlighted_row - 1])
            return None

        before = self.edit_text
        result: Optional[str] = super().keypress(size, key)
        if self.edit_text != before:
            # Typing clears the red and brings the list back.
            self.owner.set_attr_map({None: "normal"})
            self._set_open(is_open=True)
        return result

    # ------------------------------------------------------------ render

    def render(self, size: Tuple[int], focus: bool = False) -> Any:
        canvas = super().render(size, focus)
        if not (focus and self.dropdown_open):
            return canvas
        width, height = dropdown_size(
            row_count=len(self.matches),
            longest=self._longest,
            maxcol=size[0],
        )
        # Attach the list to this canvas; DisplayOnlyPopUpTarget draws it
        # under the field, over the questions below.
        with_list = urwid.CompositeCanvas(canvas)
        with_list.set_pop_up(
            CategoryDropdown(
                matches=self.matches,
                highlight=self.highlighted_row,
                total=self._total,
            ),
            left=0,
            top=canvas.rows(),
            overlay_width=width,
            overlay_height=height,
        )
        return with_list
