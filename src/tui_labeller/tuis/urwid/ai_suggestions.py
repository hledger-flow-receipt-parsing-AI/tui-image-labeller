"""Showing and applying AI suggestions in the questionnaire.

The suggestions come from hledger-ai (``hledger_ai.labeller``): ranked
candidates with a confidence per question.  They are shown in the "AI
suggestions" panel, each with the key that accepts it: Alt+0 the first,
Alt+1 the second, and so on (Alt+u also accepts the first).  A plain digit
still answers a multiple choice question with the choice of that number.
Suggestions never replace an answer the user gave.
"""

from typing import Any, List, Optional, Tuple

from hledger_core.AISuggestion import AISuggestion
from hledger_core.TransactionObjects.ShopId import ShopId
from typeguard import typechecked

BOX_HEADER = "AI suggestions (Alt+u accepts):\n"
MAX_SHOWN = 5
_ALT_DIGITS = {f"meta {digit}": digit for digit in range(MAX_SHOWN)}


@typechecked
def alt_digit(*, key: Any) -> Optional[int]:
    """The place (0: first) of the suggestion the key Alt+<place> accepts; None
    for every other key."""
    return _ALT_DIGITS.get(key) if isinstance(key, str) else None


@typechecked
def _percent(*, probability: float) -> str:
    return f"{int(probability * 100 + 1e-9)}%"


@typechecked
def _alt_key(*, place: int) -> str:
    return f"Alt+{place}  "


@typechecked
def format_suggestions(
    *, suggestions: List[AISuggestion], limit: int = MAX_SHOWN
) -> str:
    """One suggestion per line, best first: ``Alt+0  11.54 (91%)``."""
    if not suggestions:
        return "-"
    return "\n".join(
        f"{_alt_key(place=place)}{s.question}"
        f" ({_percent(probability=s.probability)})"
        for place, s in enumerate(suggestions[:limit])
    )


@typechecked
def choice_suggestions(
    *, choices: List[str], suggestions: List[AISuggestion]
) -> List[Tuple[int, AISuggestion]]:
    """The suggestions that are one of *choices*, with the choice number."""
    return [
        (choices.index(s.question), s)
        for s in suggestions
        if s.question in choices
    ]


@typechecked
def format_choice_suggestions(
    *, choices: List[str], suggestions: List[AISuggestion]
) -> str:
    """``Alt+0  1: alex:wallet:physical (90%)`` per suggested choice; 1 is the
    number of the choice in the list."""
    found = choice_suggestions(choices=choices, suggestions=suggestions)
    if not found:
        return "-"
    return "\n".join(
        f"{_alt_key(place=place)}{index}: {s.question}"
        f" ({_percent(probability=s.probability)})"
        for place, (index, s) in enumerate(found[:MAX_SHOWN])
    )


@typechecked
def rank_choices_by_suggestions(
    *,
    choices: List[str],
    shop_ids: List[ShopId],
    suggestions: List[AISuggestion],
) -> Tuple[List[str], List[ShopId]]:
    """Move the suggested shop addresses to the top of the address list.

    The first entry ("manual address") stays first; the suggested ones
    follow in the order of the suggestions; the rest keep their order.
    """
    suggested = [
        index
        for index, _ in choice_suggestions(
            choices=choices, suggestions=suggestions
        )
        if index != 0
    ]
    if not suggested:
        return choices, shop_ids
    order = [0] + suggested
    order += [i for i in range(1, len(choices)) if i not in suggested]
    return [choices[i] for i in order], [shop_ids[i] for i in order]


@typechecked
def show_in_box(*, box: Any, body: str) -> None:
    """Write *body* under the panel header."""
    if box is None:
        return
    box.base_widget.set_text([("ai_suggestions", BOX_HEADER), ("normal", body)])
    box.base_widget._invalidate()
