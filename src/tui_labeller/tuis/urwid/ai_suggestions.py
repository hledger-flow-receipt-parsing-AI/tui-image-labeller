"""Showing and applying AI suggestions in the questionnaire.

The suggestions come from hledger-ai (``hledger_ai.labeller``): ranked
candidates with a confidence per question.  They are shown in the "AI
suggestions" panel, each with the key that accepts it: Alt+a the first,
Alt+b the second, Alt+c the third, and so on (Alt+u also accepts the
first).  A plain digit still answers a multiple choice question with the
choice of that number.  Suggestions never replace an answer the user gave.

An empty suggestion means "leave this optional question empty" (most
receipts print no subtotal); the panel calls it "nothing".
"""

from typing import Any, List, Optional, Tuple

from hledger_core.AISuggestion import AISuggestion
from hledger_core.TransactionObjects.ShopId import ShopId
from typeguard import typechecked

BOX_HEADER = "AI suggestions:\n"
# The suggestion to leave an optional question empty, and its panel text.
NOTHING = ""
NOTHING_SHOWN = "nothing"
# One key per suggestion shown (hledger-ai sends five at most). Not
# Alt+<digit>: Ptyxis and GNOME Terminal switch tabs with it, so the TUI
# never gets it. No terminal, desktop or question here uses Alt+a to Alt+e.
ALT_KEYS = "abcde"
MAX_SHOWN = len(ALT_KEYS)
_PLACES = {f"meta {key}": place for place, key in enumerate(ALT_KEYS)}
# Terminals that do pass Alt+<digit> on: Alt+0 the first, Alt+1 the second.
_PLACES.update({f"meta {place}": place for place in range(MAX_SHOWN)})


@typechecked
def alt_place(*, key: Any) -> Optional[int]:
    """The place (0: first) of the suggestion that *key* accepts: Alt+a 0,
    Alt+b 1, ...; None for every other key.

    (Alt+u, which accepted the first suggestion before these keys
    existed, is handled by each question itself.)
    """
    return _PLACES.get(key) if isinstance(key, str) else None


@typechecked
def _percent(*, probability: float) -> str:
    return f"{int(probability * 100 + 1e-9)}%"


@typechecked
def _alt_key(*, place: int) -> str:
    return f"Alt+{ALT_KEYS[place]}  "


@typechecked
def format_suggestions(
    *, suggestions: List[AISuggestion], limit: int = MAX_SHOWN
) -> str:
    """One suggestion per line, best first: ``Alt+u  11.54 (91%)``."""
    if not suggestions:
        return "-"
    return "\n".join(
        f"{_alt_key(place=place)}{s.question or NOTHING_SHOWN}"
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
    """``Alt+u  1: alex:wallet:physical (90%)`` per suggested choice; 1 is the
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
