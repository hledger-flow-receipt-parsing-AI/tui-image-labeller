"""Typing letters in the shop address list keeps only the addresses that
contain them, so the user sees at once whether a shop is already known instead
of scrolling through 100+ addresses.

All shops and addresses are invented.
"""

from typing import Any, List

import pytest
from hledger_core.TransactionObjects.Address import Address
from hledger_core.TransactionObjects.ShopId import ShopId

from tui_labeller.tuis.urwid.multiple_choice_question.choice_filter import (
    choice_matches,
    visible_choices,
)
from tui_labeller.tuis.urwid.multiple_choice_question.VerticalMultipleChoiceWidget import (  # noqa: E501
    VerticalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.question_data_classes import (
    VerticalMultipleChoiceQuestionData,
)

SHOPS = [
    "manual address",  # 0
    "Bakkerij Voorbeeld: Dorpsstraat, 4, 9999 ZZ, Voorbeeldstad",  # 1
    "Biologica Markt: Zandweg, 12, 9998 YY, Testdorp",  # 2
    "Fietsenmaker Proef: Kerkplein, 7, 9997 XX, Voorbeeldstad",  # 3
    "Bio Groente: Laan, 3, 9996 WW, Ergensveen",  # 4
]
# Enough shops for two-digit choice numbers.
MANY = SHOPS + [
    f"Winkel {n}: Straat, {n}, 9990 AA, Plaats" for n in range(5, 30)
]


# ---------------------------------------------------------------- matching


@pytest.mark.parametrize(
    "typed, choice, expected",
    [
        ("bio", "Biologica Markt: Zandweg", True),  # anywhere, any case
        ("markt", "Biologica Markt: Zandweg", True),
        ("zandweg", "Biologica Markt: Zandweg", True),  # the address too
        ("bio*weg", "Biologica Markt: Zandweg", True),  # bio ... weg
        ("weg*bio", "Biologica Markt: Zandweg", False),  # in that order
        ("bio*", "Bio Groente", True),
        ("*", "anything", True),
        ("bio**weg", "Biologica Markt: Zandweg", True),
        ("b o", "Bio Groente", False),  # a space is a space
        ("o g", "Bio Groente", True),
        ("cafe", "Café Voorbeeld", True),  # accents are ignored
        ("café", "Cafe Voorbeeld", True),
        ("9999 zz", "Dorpsstraat, 4, 9999 ZZ", True),
        ("a.b", "axb", False),  # no regular expressions
    ],
)
def test_a_choice_matches_when_it_contains_the_typed_text(
    typed: str, choice: str, expected: bool
) -> None:
    assert choice_matches(choice=choice, typed=typed) is expected


def test_manual_address_stays_visible_whatever_is_typed() -> None:
    assert visible_choices(choices=SHOPS, typed="bio") == [0, 2, 4]
    assert visible_choices(choices=SHOPS, typed="nothing like it") == [0]


def test_without_typed_text_every_choice_is_visible() -> None:
    assert visible_choices(choices=SHOPS, typed="") == [0, 1, 2, 3, 4]


# ------------------------------------------------------------------ widget


def _widget(choices: List[str] = SHOPS) -> VerticalMultipleChoiceWidget:
    import urwid

    data = VerticalMultipleChoiceQuestionData(
        question="Select Shop Address:",
        question_id="address_selector",
        choices=list(choices),
        ai_suggestions=[],
        nr_of_ans_per_batch=12,
        ans_required=True,
        reconfigurer=True,
        terminator=False,
        extra_data={
            "shop_ids": [ShopId(name=c, address=Address()) for c in choices],
            "scrollable": True,
            "filterable": True,
        },
    )
    widget = VerticalMultipleChoiceWidget(question_data=data)
    widget.owner = urwid.AttrMap(widget, "normal")
    widget.pile = urwid.Pile([urwid.Text("header"), widget.owner])
    return widget


def _type(widget: VerticalMultipleChoiceWidget, text: str) -> List[Any]:
    return [widget.keypress((120,), key) for key in text]


def _listed(widget: VerticalMultipleChoiceWidget) -> List[str]:
    """The choice numbers the list shows now."""
    rows = widget.caption.splitlines()
    return [
        row.lstrip("> ").split(" ", 1)[0]
        for row in rows
        if row.lstrip("> ")[:1].isdigit()
    ]


def test_letters_filter_the_list_and_show_how_many_are_left() -> None:
    widget = _widget()
    _type(widget, "bio")
    assert _listed(widget) == ["0", "2", "4"]
    assert "Filter: bio" in widget.caption
    assert "2 of 4 match" in widget.caption


def test_the_numbers_stay_those_of_the_full_list() -> None:
    widget = _widget()
    _type(widget, "fiets")
    assert _listed(widget) == ["0", "3"]
    # A complete number selects, as without a filter; Enter goes on.
    assert widget.keypress((120,), "3") is None
    assert widget.get_answer() == SHOPS[3]
    assert widget.keypress((120,), "enter") == "reconfigurer"


def test_the_first_match_is_highlighted_and_enter_takes_it() -> None:
    widget = _widget()
    _type(widget, "bio")
    assert "> 2 Biologica" in widget.caption.replace(">  ", "> ")
    assert widget.keypress((120,), "enter") == "reconfigurer"
    assert widget.get_answer() == SHOPS[2]


def test_nothing_found_highlights_manual_address() -> None:
    widget = _widget()
    _type(widget, "zzz")
    assert _listed(widget) == ["0"]
    assert widget.keypress((120,), "enter") == "reconfigurer"
    assert widget.get_answer() == "manual address"


def test_a_number_not_in_the_filtered_list_is_refused() -> None:
    widget = _widget()
    _type(widget, "bio")
    assert widget.keypress((120,), "3") is None  # 3 is filtered out
    assert widget.get_answer() == SHOPS[2]  # still the highlighted match


def test_two_digit_numbers_wait_for_the_second_digit() -> None:
    widget = _widget(MANY)
    _type(widget, "winkel")  # Winkel 5 to 29; digits select, not filter
    assert widget.keypress((120,), "2") is None  # 2 is hidden, 20..29 shown
    widget.keypress((120,), "7")
    assert widget.get_answer() == MANY[27]


def test_backspace_removes_the_filter_letters_again() -> None:
    widget = _widget()
    _type(widget, "biox")
    assert _listed(widget) == ["0"]
    widget.keypress((120,), "backspace")
    assert _listed(widget) == ["0", "2", "4"]
    for _ in "bio":
        widget.keypress((120,), "backspace")
    assert "Filter:" not in widget.caption
    assert _listed(widget) == ["0", "1", "2", "3", "4"]


def test_backspace_first_takes_back_a_typed_digit() -> None:
    widget = _widget(MANY)
    _type(widget, "winkel")
    widget.keypress((120,), "1")  # waits: 10..19 are listed
    widget.keypress((120,), "backspace")
    assert "Filter: winkel" in widget.caption  # the filter is untouched


def test_escape_clears_the_whole_filter() -> None:
    widget = _widget()
    _type(widget, "bio*markt")
    assert _listed(widget) == ["0", "2"]
    widget.keypress((120,), "esc")
    assert "Filter:" not in widget.caption
    assert _listed(widget) == ["0", "1", "2", "3", "4"]


def test_up_and_down_move_through_the_matches_only() -> None:
    widget = _widget()
    _type(widget, "bio")  # 2 is highlighted
    widget.keypress((120,), "down")
    assert widget.get_answer() == SHOPS[4]
    widget.keypress((120,), "down")
    assert widget.get_answer() == "manual address"  # wraps around
    widget.keypress((120,), "up")
    assert widget.get_answer() == SHOPS[4]


def test_a_prefilled_guess_that_still_matches_stays_selected() -> None:
    widget = _widget()
    widget.set_answer(SHOPS[4])
    widget.mark_default_untouched()
    _type(widget, "bio")
    assert widget.get_answer() == SHOPS[4]


def test_a_prefilled_guess_that_no_longer_matches_gives_way() -> None:
    widget = _widget()
    widget.set_answer(SHOPS[1])
    widget.mark_default_untouched()
    _type(widget, "fiets")
    assert widget.get_answer() == SHOPS[3]


def test_lists_without_the_filter_ignore_letters() -> None:
    widget = _widget()
    widget.question_data.extra_data["filterable"] = False
    widget = VerticalMultipleChoiceWidget(question_data=widget.question_data)
    before = widget.caption
    widget.keypress((120,), "b")
    assert widget.caption == before


def test_without_typing_the_list_looks_as_before() -> None:
    plain = _widget()
    data = plain.question_data
    data.extra_data = {
        "shop_ids": data.extra_data["shop_ids"],
        "scrollable": True,
    }
    assert VerticalMultipleChoiceWidget(question_data=data).caption == (
        plain.caption
    )


def test_enter_does_not_take_a_number_the_filter_hides() -> None:
    widget = _widget(MANY)
    _type(widget, "winkel")
    widget.keypress((120,), "2")  # waiting for 20..29; 2 itself is hidden
    assert widget.keypress((120,), "enter") is None


def test_a_number_after_up_or_down_replaces_the_highlight() -> None:
    widget = _widget(MANY)
    _type(widget, "winkel")  # 5 highlighted
    widget.keypress((120,), "down")  # 6
    widget.keypress((120,), "2")
    widget.keypress((120,), "7")
    assert widget.get_answer() == MANY[27]


def test_backspace_after_up_or_down_removes_a_filter_letter() -> None:
    widget = _widget(MANY)
    _type(widget, "winkel")
    for _ in range(7):
        widget.keypress((120,), "down")  # 12
    widget.keypress((120,), "backspace")
    assert "Filter: winke  (" in widget.caption
    assert widget.get_answer() == MANY[12]  # still the pick, still shown


def test_end_does_not_take_a_number_the_filter_hides() -> None:
    widget = _widget(MANY)
    _type(widget, "winkel")
    widget.keypress((120,), "2")  # waiting for 20..29; 2 itself is hidden
    assert widget.keypress((120,), "end") is None


def test_reordering_while_filtering_keeps_the_filtered_list() -> None:
    """The AI re-ranks the addresses about half a second after the list is
    reached, often while the user is typing."""
    widget = _widget()
    widget.set_answer(SHOPS[1])  # the AI's first guess
    widget.mark_default_untouched()
    _type(widget, "bio")
    data = widget.question_data
    order = [0, 3, 4, 1, 2]
    data.choices = [SHOPS[i] for i in order]
    data.extra_data["shop_ids"] = [
        data.extra_data["shop_ids"][i] for i in order
    ]
    widget.refresh_choices()

    assert "Filter: bio" in widget.caption
    assert widget.get_answer() in (SHOPS[2], SHOPS[4])  # a shown match
    widget.keypress((120,), "esc")
    # The guess from before the filter is back, by its text.
    assert widget.get_answer() == SHOPS[1]


def test_an_ai_guess_hidden_by_the_filter_gives_way_to_a_match() -> None:
    widget = _widget()
    _type(widget, "bio")
    widget.set_answer(SHOPS[3])  # the AI fills in a shop the filter hides
    assert widget.get_answer() in (SHOPS[2], SHOPS[4])
    assert "Filter: bio" in widget.caption


def test_an_empty_list_can_still_be_typed_in() -> None:
    widget = _widget(["manual address"])
    widget.question_data.choices = []
    assert _type(widget, "x") == [None]  # nothing to highlight, no error
    assert widget.keypress((120,), "down") is None


def test_accented_names_show_without_losing_letters() -> None:
    widget = _widget(SHOPS + ["Bäckerei Probe: Weg, 1, 12345, Ort"])
    assert "5 Backerei Probe" in widget.caption
    _type(widget, "back")
    assert _listed(widget) == ["0", "5"]
