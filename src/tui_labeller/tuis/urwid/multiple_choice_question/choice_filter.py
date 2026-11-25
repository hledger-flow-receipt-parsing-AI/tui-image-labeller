"""Which choices of a long list stay visible while the user types letters.

The shop address list has 100+ entries. Typed letters keep only the entries
that contain them ("bio" keeps every address with "bio" in it), so the user
sees at once whether a shop is already known. A ``*`` stands for anything:
"bio*xz" keeps the entries with "bio" and, somewhere after it, "xz".
Upper and lower case and accents do not matter. The first choice ("manual
address") always stays visible: it is the way out when nothing matches.
"""

import re
import unicodedata
from typing import List, Sequence

from typeguard import typechecked

WILDCARD = "*"
# Choices that are visible whatever is typed (0: "manual address").
PINNED = (0,)


@typechecked
def _plain(*, text: str) -> str:
    """Lower case without accents: "Café" -> "cafe"."""
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(
        c for c in decomposed if not unicodedata.combining(c)
    ).casefold()


@typechecked
def choice_matches(*, choice: str, typed: str) -> bool:
    """Whether *choice* contains *typed* (``*``: anything in between)."""
    parts = [re.escape(part) for part in _plain(text=typed).split(WILDCARD)]
    return re.search(".*?".join(parts), _plain(text=choice)) is not None


@typechecked
def visible_choices(*, choices: Sequence[str], typed: str) -> List[int]:
    """Numbers of the choices to show for *typed*, in list order."""
    return [
        index
        for index, choice in enumerate(choices)
        if index in PINNED
        or not typed
        or choice_matches(choice=choice, typed=typed)
    ]
