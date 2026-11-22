"""The category dropdown: a box listing the matching categories, drawn over
the questions below the category field.

It is a view only.  The field keeps keyboard focus and the cursor; the box
shows the field's state (see CategoryQuestion).
"""

from typing import Any, List, Optional, Tuple

import urwid
from typeguard import typechecked

NEW_ROW_LABEL = "+ new category..."
# The list may reach down to this share of the screen height; the rows
# below it stay visible.
LIST_BOTTOM_PERCENT = 90
MIN_WIDTH = 40
KEY_HINT = "Up/Down Enter Tab Esc"
ATTR_DROPDOWN = "dropdown"
ATTR_SELECTED = "dropdown_selected"
# Borders, the "> " marker and one space of padding on the right.
_CHROME_COLS = 6
_BORDER_ROWS = 2


@typechecked
def dropdown_size(
    *, row_count: int, longest: int, maxcol: int
) -> Tuple[int, int]:
    """Preferred (width, height) of the box.

    *longest* is the longest category of the whole tree, not of the
    current matches, so the box keeps its width while the user types.
    The height has room for every match; DisplayOnlyPopUpTarget, which
    knows the screen, cuts it to what fits.
    """
    width = min(maxcol, max(MIN_WIDTH, longest + _CHROME_COLS))
    height = _BORDER_ROWS + 1 + row_count
    return width, height


@typechecked
def _fit(*, text: str, width: int) -> str:
    """Cut or pad *text* to exactly *width* characters."""
    if width <= 0:
        return ""
    if len(text) > width:
        return text[: width - 1] + "…"
    return text.ljust(width)


@typechecked
def _bottom_border(*, shown: int, total: int, width: int) -> str:
    inner = width - 2
    count = f" {shown} of {total} "
    hint = f" {KEY_HINT} "
    for parts in ((hint, count), ("", count)):
        used = sum(len(part) for part in parts)
        if used + 3 <= inner:
            left, right = parts
            fill = "─" * (inner - used - 2)
            return f"└─{left}{fill}{right}─┘"
    return "└" + "─" * inner + "┘"


@typechecked
def dropdown_lines(
    *,
    matches: List[str],
    highlight: int,
    total: int,
    width: int,
    height: int,
) -> List[Tuple[str, str]]:
    """The box as (attribute, text) per screen row: exactly *height* rows of
    *width* characters.

    Row 0 of the list is the "+ new category" row and stays in place; the
    matches below it scroll so the highlighted one is visible.  *highlight*
    0 is the new row, ``i`` is ``matches[i - 1]``, -1 is no row.
    """
    if height <= 0 or width < 2:
        return []
    inner = width - 2
    lines: List[Tuple[str, str]] = [(ATTR_DROPDOWN, "┌" + "─" * inner + "┐")]
    if height == 1:
        return lines

    def row(*, label: str, selected: bool) -> Tuple[str, str]:
        marker = "> " if selected else "  "
        body = _fit(text=f"{marker}{label}", width=inner)
        return (ATTR_SELECTED if selected else ATTR_DROPDOWN, f"│{body}│")

    content_rows = height - _BORDER_ROWS
    if content_rows >= 1:
        lines.append(row(label=NEW_ROW_LABEL, selected=highlight == 0))
    capacity = max(0, content_rows - 1)
    selected_match = highlight - 1
    start = max(0, selected_match - capacity + 1)
    start = max(0, min(start, len(matches) - capacity))
    for index in range(start, start + capacity):
        if index < len(matches):
            lines.append(
                row(label=matches[index], selected=index == selected_match)
            )
        else:
            lines.append((ATTR_DROPDOWN, "│" + " " * inner + "│"))
    lines.append(
        (
            ATTR_DROPDOWN,
            _bottom_border(shown=len(matches), total=total, width=width),
        )
    )
    return lines


class CategoryDropdown(urwid.Widget):
    """Box widget that draws the list at whatever size it is given, so it
    shrinks when there is little room below the field."""

    _sizing = frozenset([urwid.BOX])
    _selectable = False
    no_cache = ["render"]

    @typechecked
    def __init__(
        self, *, matches: List[str], highlight: int, total: int
    ) -> None:
        super().__init__()
        self._matches = matches
        self._highlight = highlight
        self._total = total

    def render(self, size: Tuple[int, int], focus: bool = False) -> Any:
        maxcol, maxrow = size
        lines = dropdown_lines(
            matches=self._matches,
            highlight=self._highlight,
            total=self._total,
            width=maxcol,
            height=maxrow,
        )
        markup: List[Any] = []
        for index, (attr, text) in enumerate(lines):
            if index:
                markup.append((ATTR_DROPDOWN, "\n"))
            if attr == ATTR_SELECTED:
                # Keep the border in the box colour.
                markup.extend(
                    [
                        (ATTR_DROPDOWN, text[:1]),
                        (ATTR_SELECTED, text[1:-1]),
                        (ATTR_DROPDOWN, text[-1:]),
                    ]
                )
            else:
                markup.append((attr, text))
        return urwid.Text(markup or "", wrap="clip").render((maxcol,))


class DisplayOnlyPopUpTarget(
    urwid.delegate_to_widget_mixin("_original_widget"),
    urwid.WidgetDecoration,
):
    """Draws a pop-up that a widget below attached to its canvas, and leaves
    everything else to the wrapped widget.

    urwid's own PopUpTarget sends every key to the pop-up and renders
    the widgets beneath it without focus.  The dropdown is only a view
    of the category field, so keys, focus and cursor must stay with the
    questionnaire.

    The pop-up reaches down to LIST_BOTTOM_PERCENT of the screen height
    at most, so the bottom of the screen stays visible.
    """

    MIN_COLS = 10
    MIN_ROWS = 3
    no_cache = ["render"]

    def render(self, size: Tuple[int, int], focus: bool = False) -> Any:
        bottom = self._original_widget.render(size, focus=focus)
        pop_up: Optional[Any] = bottom.get_pop_up()
        if not pop_up:
            return bottom
        left, top, (widget, width, height) = pop_up
        maxcol, maxrow = size
        width = min(width, maxcol - left)
        room = maxrow * LIST_BOTTOM_PERCENT // 100 - top
        if room < self.MIN_ROWS:
            # The field sits low on the screen: use the rows that are left
            # rather than show no list at all.
            room = maxrow - top
        height = min(height, room)
        if width < self.MIN_COLS or height < self.MIN_ROWS:
            return bottom
        box = urwid.CompositeCanvas(widget.render((width, height)))
        return urwid.CanvasOverlay(box, bottom, left, top)
