"""AI suggestions in the questionnaire: shown with their confidence, accepted
with Alt+u, and never applied on their own to a field the user answered.

All names, shops and amounts here are invented.
"""

from datetime import datetime
from typing import List

import urwid
from hledger_core.AISuggestion import AISuggestion
from hledger_core.TransactionObjects.Address import Address
from hledger_core.TransactionObjects.ShopId import ShopId

from tui_labeller.tuis.urwid.ai_suggestions import (
    format_suggestions,
    rank_choices_by_suggestions,
)
from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_app.create_widgets import (
    create_question_widget,
)
from tui_labeller.tuis.urwid.question_data_classes import (
    DateQuestionData,
    InputValidationQuestionData,
    VerticalMultipleChoiceQuestionData,
)

SIZE = (80,)


def _ai(text: str, probability: float) -> AISuggestion:
    return AISuggestion(
        question=text, probability=probability, model_name="ST-x"
    )


def _widget(question_data):
    box = urwid.AttrMap(urwid.Text(""), "")
    attr = create_question_widget(
        pile=urwid.Pile([]),
        ai_suggestion_box=box,
        history_suggestion_box=urwid.AttrMap(urwid.Text(""), ""),
        error_display=urwid.AttrMap(urwid.Pile([urwid.Text("")]), ""),
        question_data=question_data,
        history_store={},
        descriptor_col_width=20,
    )
    return attr.base_widget, box


def _box_text(box) -> str:
    return box.base_widget.text


def _accounts(suggestions: List[AISuggestion]):
    return _widget(
        VerticalMultipleChoiceQuestionData(
            question="Belongs to bank/accounts_without_csv:",
            question_id="bank_account",
            choices=["alex:examplebank:checking", "alex:wallet:physical"],
            nr_of_ans_per_batch=8,
            ans_required=True,
            reconfigurer=True,
            terminator=False,
            ai_suggestions=suggestions,
        )
    )


# ------------------------------------------------------------ formatting


def test_suggestions_are_listed_best_first_with_their_alt_key() -> None:
    text = format_suggestions(
        suggestions=[_ai("11.54", 0.912), _ai("20.00", 0.05)]
    )

    assert text == "Alt+a  11.54 (91%)\nAlt+b  20.00 (5%)"


def test_the_panel_shows_five_suggestions_one_per_key() -> None:
    text = format_suggestions(
        suggestions=[_ai(f"{n}.00", 0.1) for n in range(1, 8)]
    )

    assert text.splitlines() == [
        "Alt+a  1.00 (10%)",
        "Alt+b  2.00 (10%)",
        "Alt+c  3.00 (10%)",
        "Alt+d  4.00 (10%)",
        "Alt+e  5.00 (10%)",
    ]


def test_no_suggestions_reads_as_none() -> None:
    assert format_suggestions(suggestions=[]) == "-"


# ---------------------------------------------------- multiple choice


def test_alt_u_selects_the_suggested_choice() -> None:
    widget, _ = _accounts([_ai("alex:wallet:physical", 0.9)])

    result = widget.keypress(SIZE, "meta u")

    assert widget.get_answer() == "alex:wallet:physical"
    assert result == "reconfigurer"


def test_suggested_choice_is_shown_with_its_number_and_confidence() -> None:
    widget, box = _accounts(
        [
            _ai("alex:wallet:physical", 0.9),
            _ai("alex:examplebank:checking", 0.1),
        ]
    )

    widget.update_autocomplete()

    # The header names no key: every line names its own.
    assert _box_text(box).splitlines()[0] == "AI suggestions:"
    assert "Alt+a  1: alex:wallet:physical (90%)" in _box_text(box)
    assert "Alt+b  0: alex:examplebank:checking (10%)" in _box_text(box)


def test_alt_a_and_b_select_the_first_and_second_suggested_choice() -> None:
    # Alt+a is the first suggestion, Alt+b the second, Alt+c the third, ...
    # (Alt+u also the first); a plain digit still answers with that choice.
    for key, expected in (
        ("meta a", "alex:wallet:physical"),
        ("meta b", "alex:examplebank:checking"),
    ):
        widget, _ = _accounts(
            [
                _ai("alex:wallet:physical", 0.6),
                _ai("alex:examplebank:checking", 0.3),
            ]
        )

        result = widget.keypress(SIZE, key)

        assert widget.get_answer() == expected
        assert result == "reconfigurer"


def test_alt_digits_also_pick_by_place_where_the_terminal_passes_them() -> None:
    # Ptyxis and GNOME Terminal take Alt+<digit> for their tabs; other
    # terminals pass it on: Alt+0 is then the first, Alt+1 the second.
    widget, _ = _accounts(
        [
            _ai("alex:wallet:physical", 0.6),
            _ai("alex:examplebank:checking", 0.3),
        ]
    )

    widget.keypress(SIZE, "meta 1")

    assert widget.get_answer() == "alex:examplebank:checking"


def test_alt_key_past_the_last_suggestion_does_nothing() -> None:
    widget, _ = _accounts([_ai("alex:wallet:physical", 0.9)])

    assert widget.keypress(SIZE, "meta c") is None
    assert widget.has_answer() is False


def test_choice_list_has_no_confidence_or_model_behind_the_choices() -> None:
    # The AI panel shows them; behind the choices they hide the choice.
    widget, _ = _accounts([_ai("alex:wallet:physical", 0.9)])

    assert "alex:wallet:physical" in widget.caption
    assert "0.90" not in widget.caption
    assert "ST-x" not in widget.caption


def test_chosen_answer_has_no_confidence_or_model_behind_it() -> None:
    widget, _ = _accounts([_ai("alex:wallet:physical", 0.9)])

    widget.keypress(SIZE, "meta u")

    assert "alex:wallet:physical" in widget.caption
    assert "ST-x" not in widget.caption


def test_scrolling_address_list_has_no_confidence_or_model() -> None:
    widget, _ = _widget(
        VerticalMultipleChoiceQuestionData(
            question="Select Shop Address:",
            question_id="address_selector",
            choices=["manual address", "Bakker Bart: Dorpsstraat, Stad"],
            nr_of_ans_per_batch=8,
            ans_required=True,
            reconfigurer=False,
            terminator=False,
            ai_suggestions=[_ai("Bakker Bart: Dorpsstraat, Stad", 0.9)],
            extra_data={"scrollable": True},
        )
    )

    widget.keypress(SIZE, "down")

    assert "Bakker Bart" in widget.caption
    assert "ST-x" not in widget.caption


def test_suggestion_that_is_not_a_choice_is_ignored() -> None:
    widget, box = _accounts([_ai("someone:else:account", 0.9)])

    result = widget.keypress(SIZE, "meta u")
    widget.update_autocomplete()

    assert result is None
    assert widget.has_answer() is False
    assert "someone:else" not in _box_text(box)


def test_multiple_choice_without_suggestions_clears_the_box() -> None:
    widget, box = _accounts([])
    box.base_widget.set_text("left over from the previous question")

    widget.update_autocomplete()

    assert "left over" not in _box_text(box)


# --------------------------------------------------------------- date


def _date(suggestions: List[AISuggestion]):
    return _widget(
        DateQuestionData(
            question="Receipt date and time:\n",
            question_id="date",
            date_only=False,
            ai_suggestions=suggestions,
            ans_required=True,
            reconfigurer=False,
            terminator=False,
        )
    )


def test_date_question_starts_at_the_suggested_date() -> None:
    widget, _ = _date([_ai("2025-03-17 14:32", 0.9)])

    assert widget.get_answer() == datetime(2025, 3, 17, 14, 32)
    assert widget.get_edit_text() == "2025-03-17 14:32"


def test_alt_u_on_the_date_really_changes_the_answer() -> None:
    # It used to change the text on screen only: the saved date stayed.
    widget, _ = _date([_ai("2025-03-17 14:32", 0.9)])
    widget.set_answer(datetime(2024, 1, 1, 8, 0))

    result = widget.keypress(SIZE, "meta u")

    assert widget.get_answer() == datetime(2025, 3, 17, 14, 32)
    assert result == "next_question"


def test_unreadable_date_suggestion_is_ignored() -> None:
    widget, _ = _date([_ai("not a date", 0.9)])

    assert isinstance(widget.get_answer(), datetime)
    assert widget.keypress(SIZE, "meta u") is None


def test_date_suggestions_are_shown_with_confidence() -> None:
    widget, box = _date([_ai("2025-03-17 14:32", 0.9)])

    widget.update_autocomplete()

    assert "Alt+a  2025-03-17 14:32 (90%)" in _box_text(box)


def test_alt_b_on_the_date_takes_the_second_suggestion() -> None:
    widget, _ = _date(
        [_ai("2025-03-17 14:32", 0.6), _ai("2025-03-18 09:05", 0.3)]
    )

    result = widget.keypress(SIZE, "meta b")

    assert widget.get_answer() == datetime(2025, 3, 18, 9, 5)
    assert result == "next_question"


def test_alt_key_without_that_date_suggestion_keeps_the_date() -> None:
    widget, _ = _date([_ai("2025-03-17 14:32", 0.9)])

    assert widget.keypress(SIZE, "meta c") is None
    assert widget.get_answer() == datetime(2025, 3, 17, 14, 32)


# -------------------------------------------------------- typed fields


def _amount(suggestions: List[AISuggestion]):
    return _widget(
        InputValidationQuestionData(
            question="Amount paid from account:",
            question_id="amount",
            input_type=InputType.FLOAT,
            ans_required=True,
            reconfigurer=False,
            terminator=False,
            ai_suggestions=suggestions,
            history_suggestions=[],
        )
    )


def test_typed_field_stays_empty_until_the_user_accepts() -> None:
    widget, box = _amount([_ai("11.54", 0.91), _ai("20.00", 0.05)])

    widget.update_autocomplete()

    assert widget.get_edit_text() == ""
    assert "11.54 (91%)" in _box_text(box)
    assert "20.00 (5%)" in _box_text(box)


def test_alt_u_fills_the_best_suggestion_and_moves_on() -> None:
    widget, _ = _amount([_ai("11.54", 0.91), _ai("20.00", 0.05)])

    result = widget.keypress(SIZE, "meta u")

    assert widget.get_answer() == 11.54
    assert result == "next_question"


def test_typing_narrows_the_suggestions_shown() -> None:
    widget, box = _amount([_ai("11.54", 0.91), _ai("20.00", 0.05)])

    widget.keypress(SIZE, "2")

    assert "20.00 (5%)" in _box_text(box)
    assert "11.54" not in _box_text(box)


def test_alt_a_to_e_fill_the_suggestion_at_that_place_and_move_on() -> None:
    suggestions = [
        _ai("11.54", 0.5),
        _ai("20.00", 0.2),
        _ai("25.00", 0.1),
        _ai("30.00", 0.05),
        _ai("35.00", 0.04),
    ]
    for key, expected in (
        ("meta a", 11.54),
        ("meta b", 20.0),
        ("meta c", 25.0),
        ("meta d", 30.0),
        ("meta e", 35.0),
        ("meta u", 11.54),
    ):
        widget, _ = _amount(suggestions)

        result = widget.keypress(SIZE, key)

        assert widget.get_answer() == expected
        assert result == "next_question"


def test_alt_key_counts_the_suggestions_the_panel_still_shows() -> None:
    widget, box = _amount(
        [_ai("11.54", 0.6), _ai("20.00", 0.3), _ai("25.00", 0.1)]
    )
    widget.keypress(SIZE, "2")  # the panel now lists 20.00 and 25.00

    widget.keypress(SIZE, "meta b")

    assert "Alt+b  25.00 (10%)" in _box_text(box)
    assert widget.get_answer() == 25.0


def test_alt_key_past_the_last_typed_suggestion_does_nothing() -> None:
    widget, _ = _amount([_ai("11.54", 0.91)])

    assert widget.keypress(SIZE, "meta b") is None
    assert widget.get_edit_text() == ""


def test_a_decimal_comma_is_typed_as_a_decimal_point() -> None:
    # It used to be dropped: "6,35" became 635.
    widget, _ = _amount([_ai("6.35", 0.9)])

    for key in "6,35":
        widget.keypress(SIZE, key)

    assert widget.get_edit_text() == "6.35"
    assert widget.get_answer() == 6.35


def test_alt_b_on_the_category_picks_the_second_suggested_category() -> None:
    from tui_labeller.categories.category_store import CategoryStore
    from tui_labeller.tuis.urwid.receipts.BaseQuestions import BaseQuestions

    data = BaseQuestions(
        ai_suggestions={
            "category": [_ai("food:bakery", 0.7), _ai("tools:garden", 0.2)]
        },
        category_store=CategoryStore(
            hierarchy={"food": {"bakery": {}}, "tools": {"garden": {}}}
        ),
    ).get_category_question()
    widget, _ = _widget(data)

    result = widget.keypress(SIZE, "meta b")

    assert widget.get_answer() == "tools:garden"
    assert result == "reconfigurer"


# ------------------------------------------------------- address order


def _shop(name: str) -> ShopId:
    return ShopId(name=name, address=Address(street="Straat", city="Stad"))


def test_suggested_shops_move_to_the_top_of_the_address_list() -> None:
    choices = [
        "manual address",
        "A: Straat, Stad",
        "B: Straat, Stad",
        "C: Straat, Stad",
    ]
    shops = [_shop("manual address"), _shop("A"), _shop("B"), _shop("C")]

    new_choices, new_shops = rank_choices_by_suggestions(
        choices=choices,
        shop_ids=shops,
        suggestions=[
            _ai("C: Straat, Stad", 0.6),
            _ai("Unknown: nowhere", 0.3),
            _ai("A: Straat, Stad", 0.1),
        ],
    )

    assert new_choices == [
        "manual address",
        "C: Straat, Stad",
        "A: Straat, Stad",
        "B: Straat, Stad",
    ]
    assert [s.name for s in new_shops] == ["manual address", "C", "A", "B"]


def test_address_list_without_suggestions_keeps_its_order() -> None:
    choices = ["manual address", "A: Straat, Stad", "B: Straat, Stad"]
    shops = [_shop("manual address"), _shop("A"), _shop("B")]

    assert rank_choices_by_suggestions(
        choices=choices, shop_ids=shops, suggestions=[]
    ) == (choices, shops)
