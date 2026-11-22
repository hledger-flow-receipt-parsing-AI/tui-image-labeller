"""The new-category screen: the whole category tree, so the user sees what
already exists, with a deliberate way to add a category under any node."""

from dataclasses import dataclass
from typing import Any, Callable, List, Optional, Set, Tuple

import urwid
from typeguard import typechecked

from tui_labeller.categories.category_store import (
    SEPARATOR,
    AdditionPlan,
    CategoryStore,
)
from tui_labeller.categories.category_yaml import CategorySaveError

ROOT = ""
ROOT_LABEL = "(top level)"
PAGE_ROWS = 10
ATTR_CURSOR = "dropdown_selected"
BROWSING_LEGEND = (
    "Up/Down move   Right/Left open/close   n new child here\n"
    "Enter use this category   Esc back"
)
ADDING_LEGEND = "Enter create   Esc stop adding"
_EDIT_KEYS = ("backspace", "delete", "left", "right", "home", "end")
_SHOWN_ELSEWHERE = 3


@dataclass(frozen=True)
class TreeRow:
    path: str
    depth: int
    has_children: bool
    expanded: bool


@typechecked
def visible_tree_rows(
    *, store: CategoryStore, expanded: Set[str]
) -> List[TreeRow]:
    """The rows to draw: the root row, then every category whose ancestors
    are all expanded, children alphabetical."""
    rows: List[TreeRow] = [
        TreeRow(
            path=ROOT,
            depth=0,
            has_children=bool(store.children(path=ROOT)),
            expanded=True,
        )
    ]

    def walk(parent: str, depth: int) -> None:
        for name in store.children(path=parent):
            path = f"{parent}{SEPARATOR}{name}" if parent else name
            has_children = bool(store.children(path=path))
            is_open = has_children and path in expanded
            rows.append(
                TreeRow(
                    path=path,
                    depth=depth,
                    has_children=has_children,
                    expanded=is_open,
                )
            )
            if is_open:
                walk(path, depth + 1)

    walk(ROOT, 1)
    return rows


@typechecked
def _row_label(*, row: TreeRow, is_cursor: bool) -> str:
    marker = "> " if is_cursor else "  "
    if row.path == ROOT:
        return f"{marker}{ROOT_LABEL}"
    icon = "  "
    if row.has_children:
        icon = "- " if row.expanded else "+ "
    name = row.path.split(SEPARATOR)[-1]
    return f"{marker}{'    ' * (row.depth - 1)}{icon}{name}"


class CategoryTreeScreen(urwid.WidgetWrap):
    """Full-screen tree of the categories.

    Browsing: arrows move and open/close branches, Enter uses the
    highlighted category, ``n`` adds a child under it, Esc goes back.
    Adding: type the new part (``:`` creates several levels), Enter creates
    it and reports it through *on_use*.

    Every key is consumed: the questionnaire behind this screen must not
    see any of them.
    """

    @typechecked
    def __init__(
        self,
        *,
        store: CategoryStore,
        typed_text: str,
        on_use: Callable[[str], Any],
        on_cancel: Callable[[], Any],
    ) -> None:
        self.store = store
        self._on_use = on_use
        self._on_cancel = on_cancel
        self.expanded: Set[str] = set()
        self.cursor_path: str = ROOT
        self.adding: bool = False
        # A look-alike was shown; the next Enter creates the category.
        self.confirm_pending: bool = False
        self.status: str = ""
        self.input = urwid.Edit("")

        self._walker = urwid.SimpleFocusListWalker([])
        self._preview = urwid.Text("")
        self._legend = urwid.Text("")
        self._footer = urwid.Pile(
            [
                urwid.Divider("─"),
                self.input,
                self._preview,
                urwid.Divider("─"),
                urwid.AttrMap(self._legend, "navigation"),
            ]
        )
        self._footer.focus_position = 1
        self._frame = urwid.Frame(
            body=urwid.ListBox(self._walker),
            header=urwid.Pile(
                [
                    urwid.Text(("navigation", "New category")),
                    urwid.Divider("─"),
                ]
            ),
            footer=self._footer,
        )
        super().__init__(self._frame)

        # Start at the deepest existing part of what was typed in the
        # field; whatever follows it is what the user wants to add.
        existing, remainder = store.deepest_existing_ancestor(
            path=typed_text.replace("*", "")
        )
        self.cursor_path = existing
        self._expand_to(path=existing)
        if remainder:
            self.adding = True
            self.input.set_edit_text(remainder)
            self.input.set_edit_pos(len(remainder))
        self._refresh()

    def selectable(self) -> bool:
        return True

    def mouse_event(self, *_args: Any, **_kwargs: Any) -> bool:
        """Keyboard only: a click must not move focus inside the frame."""
        return True

    # ------------------------------------------------------------- state

    def _expand_to(self, *, path: str) -> None:
        """Open *path* and all its ancestors."""
        if not path:
            return
        segments = path.split(SEPARATOR)
        for end in range(1, len(segments) + 1):
            self.expanded.add(SEPARATOR.join(segments[:end]))

    def _rows(self) -> List[TreeRow]:
        return visible_tree_rows(store=self.store, expanded=self.expanded)

    def _cursor_index(self, *, rows: List[TreeRow]) -> int:
        for index, row in enumerate(rows):
            if row.path == self.cursor_path:
                return index
        return 0

    def _plan(self) -> AdditionPlan:
        return self.store.plan_addition(
            parent=self.cursor_path, text=self.input.edit_text
        )

    def _refresh(self) -> None:
        rows = self._rows()
        index = self._cursor_index(rows=rows)
        self.cursor_path = rows[index].path
        self._walker[:] = [
            urwid.AttrMap(
                urwid.Text(
                    _row_label(row=row, is_cursor=position == index),
                    wrap="clip",
                ),
                ATTR_CURSOR if position == index else None,
            )
            for position, row in enumerate(rows)
        ]
        self._walker.set_focus(index)

        where = self.cursor_path or ROOT_LABEL
        if self.adding:
            self.input.set_caption(f"Add under {where}: ")
            self._legend.set_text(ADDING_LEGEND)
            self._frame.focus_position = "footer"
        else:
            self.input.set_caption(f"n: add a category under {where}")
            self._legend.set_text(BROWSING_LEGEND)
            self._frame.focus_position = "body"
        self._preview.set_text(self._preview_markup())

    def _preview_markup(self) -> Any:
        """What Enter would do in adding mode, and any warnings."""
        if not self.adding:
            return ""
        lines: List[Tuple[Optional[str], str]] = []
        if self.status:
            lines.append(("error", self.status))
        plan = self._plan()
        if plan.error is not None:
            empty = not self.input.edit_text.strip()
            lines.append((None if empty else "error", plan.error))
        elif plan.already_exists:
            lines.append((None, f"{plan.full_path} already exists."))
            lines.append((None, "Enter uses it."))
        else:
            for position, path in enumerate(plan.created):
                label = "creates  " if position == 0 else " " * 9
                lines.append((None, f"{label}{path}"))
            if plan.look_alikes:
                alike = ", ".join(plan.look_alikes)
                lines.append(("error", f"Looks like existing: {alike}"))
                if self.confirm_pending:
                    lines.append(
                        (
                            "error",
                            "Press Enter again to create it anyway, or Esc.",
                        )
                    )
            if plan.same_name_elsewhere:
                shown = plan.same_name_elsewhere[:_SHOWN_ELSEWHERE]
                more = len(plan.same_name_elsewhere) - len(shown)
                suffix = f" (+{more} more)" if more else ""
                lines.append(
                    (None, f"Same name elsewhere: {', '.join(shown)}{suffix}")
                )
        markup: List[Any] = []
        for position, (attr, text) in enumerate(lines):
            if position:
                markup.append("\n")
            markup.append((attr, text) if attr else text)
        return markup or ""

    # -------------------------------------------------------------- keys

    def keypress(self, size: Tuple[int, int], key: str) -> None:
        if self.adding:
            self._adding_key(maxcol=size[0], key=key)
        else:
            self._browsing_key(key=key)
        return None

    def _browsing_key(self, *, key: str) -> None:
        rows = self._rows()
        index = self._cursor_index(rows=rows)
        row = rows[index]
        last = len(rows) - 1
        if key == "esc":
            self._on_cancel()
            return
        if key == "enter":
            if row.path != ROOT:
                self._on_use(row.path)
            return
        if key == "n":
            self.adding = True
            self._expand_to(path=row.path)
        elif key == "up":
            index = max(0, index - 1)
        elif key == "down":
            index = min(last, index + 1)
        elif key == "page up":
            index = max(0, index - PAGE_ROWS)
        elif key == "page down":
            index = min(last, index + PAGE_ROWS)
        elif key == "home":
            index = 0
        elif key == "end":
            index = last
        elif key == "right":
            if row.has_children and not row.expanded:
                self.expanded.add(row.path)
            elif row.has_children:
                index = min(last, index + 1)
        elif key == "left":
            if row.path != ROOT and row.expanded:
                self.expanded.discard(row.path)
            elif row.path != ROOT:
                parent = SEPARATOR.join(row.path.split(SEPARATOR)[:-1])
                index = next(
                    position
                    for position, other in enumerate(rows)
                    if other.path == parent
                )
        else:
            return
        self.cursor_path = rows[index].path
        self._refresh()

    def _adding_key(self, *, maxcol: int, key: str) -> None:
        if key == "esc":
            self.adding = False
            self.input.set_edit_text("")
            self.confirm_pending = False
            self.status = ""
            self._refresh()
            return
        if key == "enter":
            self._confirm_addition()
            return
        before = (self.input.edit_text, self.input.edit_pos)
        if key in _EDIT_KEYS:
            self.input.keypress((maxcol,), key)
        elif len(key) == 1:
            character = key.lower()
            if character.isascii() and (
                character.isalnum() or character in f"_{SEPARATOR}"
            ):
                self.input.keypress((maxcol,), character)
        if (self.input.edit_text, self.input.edit_pos) != before:
            if self.input.edit_text != before[0]:
                # A different name: ask again, and drop the old error.
                self.confirm_pending = False
            self.status = ""
            self._refresh()
        elif self.status and len(key) == 1:
            self.status = ""
            self._refresh()

    def _confirm_addition(self) -> None:
        plan = self._plan()
        if plan.error is not None:
            return
        if plan.already_exists:
            self._on_use(plan.full_path)
            return
        if plan.look_alikes and not self.confirm_pending:
            self.confirm_pending = True
            self._refresh()
            return
        try:
            self.store.add(path=plan.full_path)
        except (CategorySaveError, ValueError, OSError) as error:
            # Nothing was written; keep the screen so the user can retry.
            self.status = f"Could not save: {error}"
            self.confirm_pending = False
            self._refresh()
            return
        self._on_use(plan.full_path)
