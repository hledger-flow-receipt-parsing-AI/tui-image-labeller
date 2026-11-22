"""The dropdown is drawn over the questions below the category field without
moving them, and without taking keys, focus or cursor away from the field."""

from typing import Any, Dict, List, Optional

import urwid

from tui_labeller.categories.category_store import CategoryStore
from tui_labeller.tuis.urwid.category_question.dropdown import (
    ATTR_DROPDOWN,
    ATTR_SELECTED,
    LIST_BOTTOM_PERCENT,
    NEW_ROW_LABEL,
    DisplayOnlyPopUpTarget,
    dropdown_lines,
    dropdown_size,
)
from tui_labeller.tuis.urwid.question_app.create_widgets import (
    create_question_widget,
)
from tui_labeller.tuis.urwid.receipts.BaseQuestions import BaseQuestions

MATCHES = [f"groceries:shop{number:02d}" for number in range(20)]


def _tree() -> Dict[str, Any]:
    return {
        "groceries": {"ah": {}, "ekoplaza": {}},
        "repairs": {"bike": {}, "car": {}, "house": {"kitchen": {}}},
        "restaurant": {},
        "transportation": {"benzine": {}, "parking": {}},
    }


def _texts(lines: List[Any]) -> List[str]:
    return [text for _, text in lines]


def test_every_line_has_the_requested_width_and_count() -> None:
    lines = dropdown_lines(
        matches=MATCHES, highlight=1, total=120, width=40, height=11
    )
    assert len(lines) == 11
    assert {len(text) for text in _texts(lines)} == {40}


def test_new_row_is_first_and_the_highlight_is_marked() -> None:
    lines = dropdown_lines(
        matches=MATCHES[:3], highlight=2, total=120, width=40, height=6
    )
    texts = _texts(lines)
    assert texts[0].startswith("┌") and texts[-1].startswith("└")
    assert NEW_ROW_LABEL in texts[1]
    assert "groceries:shop00" in texts[2]
    assert "groceries:shop01" in texts[3]
    assert [attr for attr, _ in lines] == [
        ATTR_DROPDOWN,
        ATTR_DROPDOWN,
        ATTR_DROPDOWN,
        ATTR_SELECTED,
        ATTR_DROPDOWN,
        ATTR_DROPDOWN,
    ]
    assert texts[3].startswith("│> ")
    assert texts[2].startswith("│  ")


def test_new_row_can_be_highlighted() -> None:
    lines = dropdown_lines(
        matches=[], highlight=0, total=120, width=40, height=3
    )
    assert lines[1][0] == ATTR_SELECTED
    assert NEW_ROW_LABEL in lines[1][1]


def test_no_row_is_marked_when_nothing_is_highlighted() -> None:
    lines = dropdown_lines(
        matches=MATCHES, highlight=-1, total=120, width=40, height=11
    )
    assert {attr for attr, _ in lines} == {ATTR_DROPDOWN}
    assert "groceries:shop00" in lines[2][1]


def test_window_follows_the_highlight_and_keeps_the_new_row() -> None:
    lines = dropdown_lines(
        matches=MATCHES, highlight=16, total=120, width=40, height=11
    )
    texts = _texts(lines)
    assert NEW_ROW_LABEL in texts[1]
    selected = [text for attr, text in lines if attr == ATTR_SELECTED]
    assert len(selected) == 1 and "groceries:shop15" in selected[0]
    assert not any("groceries:shop00" in text for text in texts)


def test_bottom_border_counts_matches_of_total() -> None:
    lines = dropdown_lines(
        matches=MATCHES[:3], highlight=1, total=120, width=50, height=6
    )
    assert "3 of 120" in lines[-1][1]
    assert "Enter" in lines[-1][1]


def test_a_small_box_still_has_exactly_the_requested_rows() -> None:
    lines = dropdown_lines(
        matches=MATCHES, highlight=1, total=120, width=40, height=4
    )
    texts = _texts(lines)
    assert len(texts) == 4
    assert NEW_ROW_LABEL in texts[1]
    assert "groceries:shop00" in texts[2]
    assert texts[3].startswith("└")


def test_long_names_are_cut_to_the_width() -> None:
    lines = dropdown_lines(
        matches=["a" * 80], highlight=1, total=1, width=30, height=4
    )
    assert {len(text) for text in _texts(lines)} == {30}
    assert "…" in lines[2][1]


def test_size_is_stable_in_width_and_asks_room_for_every_match() -> None:
    # The pop-up host, which knows the screen, cuts the height to fit.
    assert dropdown_size(row_count=20, longest=30, maxcol=100) == (40, 23)
    assert dropdown_size(row_count=2, longest=60, maxcol=100) == (66, 5)
    assert dropdown_size(row_count=0, longest=60, maxcol=50) == (50, 3)


# ---------------------------------------------------------------- pop-up host


def _long_tree() -> Dict[str, Any]:
    return {f"category{number:03d}": {} for number in range(100)}


def _list_bottom(*, screen_rows: int) -> int:
    """First screen row the list must leave free."""
    return screen_rows * LIST_BOTTOM_PERCENT // 100


def _screen(*, focus_position: int = 2, tree: Optional[Dict[str, Any]] = None):
    """Eight single-line questions with the category question third."""
    store = CategoryStore(hierarchy=tree or _tree())
    data = BaseQuestions(category_store=store).get_category_question()
    pile = urwid.Pile([])
    category = create_question_widget(
        pile=pile,
        ai_suggestion_box=urwid.AttrMap(urwid.Text(""), ""),
        history_suggestion_box=urwid.AttrMap(urwid.Text(""), ""),
        error_display=urwid.AttrMap(urwid.Pile([urwid.Text("")]), ""),
        question_data=data,
        history_store={},
        descriptor_col_width=20,
    )
    widgets = [urwid.Edit(f"Question {number}: ") for number in range(8)]
    widgets[2] = category
    pile.contents = [(widget, ("pack", None)) for widget in widgets]
    pile.focus_position = focus_position
    host = DisplayOnlyPopUpTarget(urwid.Filler(pile, valign="top"))
    return host, category.base_widget


def _rows(host: urwid.Widget, size: tuple) -> List[str]:
    return [row.decode("utf-8") for row in host.render(size, focus=True).text]


def test_box_is_drawn_directly_under_the_field() -> None:
    host, question = _screen()
    rows = _rows(host, (80, 20))
    assert "Bookkeeping expense category:" in rows[3]
    assert rows[4].startswith("┌")
    assert NEW_ROW_LABEL in rows[5]
    assert "groceries" in rows[6]


def test_nothing_else_on_the_screen_moves() -> None:
    size = (80, 20)
    host, question = _screen()
    opened = _rows(host, size)
    question.keypress((80,), "esc")
    closed = _rows(host, size)

    assert "Question 3" in closed[4]
    box_rows = [
        index for index, row in enumerate(opened) if row != closed[index]
    ]
    # Twelve categories would need 15 rows; the list stops at 90% of the
    # 20 screen rows.
    assert _list_bottom(screen_rows=20) == 18
    assert box_rows == list(range(4, 18))
    width = len(opened[4].rstrip())
    for index in box_rows:
        assert opened[index][width:] == closed[index][width:]


def test_long_list_reaches_down_to_ninety_percent_of_the_screen() -> None:
    size = (80, 50)
    host, question = _screen(tree=_long_tree())
    opened = _rows(host, size)
    question.keypress((80,), "esc")
    closed = _rows(host, size)

    bottom = _list_bottom(screen_rows=50)
    assert bottom == 45
    box_rows = [
        index for index, row in enumerate(opened) if row != closed[index]
    ]
    assert box_rows == list(range(4, bottom))
    assert opened[bottom - 1].startswith("└")
    # The bottom tenth of the screen stays free.
    assert opened[bottom:] == closed[bottom:]
    # Borders and the "+ new" row leave 38 rows for categories.
    shown = [row for row in opened if row.startswith("│  category")]
    assert len(shown) == bottom - 4 - 3


def test_short_list_is_only_as_tall_as_it_needs() -> None:
    host, question = _screen(tree=_long_tree())
    for character in "category00":  # category000 .. category009
        question.keypress((80,), character)
    rows = _rows(host, (80, 50))
    assert rows[4].startswith("┌")
    assert "category009" in rows[15]
    assert rows[16].startswith("└")
    assert "Question" not in rows[16] and not rows[17].strip()


def test_cursor_and_keys_stay_with_the_field() -> None:
    size = (80, 20)
    host, question = _screen()
    opened_cursor = host.render(size, focus=True).cursor
    assert host.get_cursor_coords(size) == opened_cursor
    assert opened_cursor is not None and opened_cursor[1] == 3

    assert host.keypress(size, "g") is None
    assert question.edit_text == "g"

    question.keypress((80,), "esc")
    assert host.render(size, focus=True).cursor == host.get_cursor_coords(size)


def test_unfocused_question_shows_no_box() -> None:
    host, _ = _screen(focus_position=0)
    assert not any(row.startswith("┌") for row in _rows(host, (80, 20)))


def test_box_shrinks_to_the_rows_below_the_field() -> None:
    host, _ = _screen()
    rows = _rows(host, (80, 8))
    assert len(rows) == 8
    assert rows[4].startswith("┌")
    assert NEW_ROW_LABEL in rows[5]
    assert rows[6].startswith("└")
    assert "Question 6" in rows[7]  # below 90%: not covered


def test_field_near_the_bottom_still_gets_a_list() -> None:
    """With no room above the 90% line the list uses the rows that are
    left: a list over the last rows beats no list at all."""
    host, _ = _screen()
    rows = _rows(host, (80, 7))
    assert rows[4].startswith("┌")
    assert NEW_ROW_LABEL in rows[5]
    assert rows[6].startswith("└")


def test_no_box_when_there_is_no_room_for_one() -> None:
    host, _ = _screen()
    rows = _rows(host, (80, 6))
    assert not any(row.startswith("┌") for row in rows)
