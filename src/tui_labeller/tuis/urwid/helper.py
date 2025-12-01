from typing import List, Union

from typeguard import typechecked

from tui_labeller.tuis.urwid.question_data_classes import (
    AISuggestion,
    HistorySuggestion,
)


@typechecked
def get_matching_unique_suggestions(
    suggestions: List[Union[AISuggestion, HistorySuggestion]],
    current_text: str,
    cursor_pos: int,
) -> List[str]:
    # Get the portion of text up to cursor position
    text_to_match = current_text[: cursor_pos + 1]

    # Filter suggestions that match up to the cursor position
    matching_suggestions = [
        suggestion.question
        for suggestion in suggestions
        if suggestion.question.startswith(text_to_match)
    ]
    # Preserve order, remove dupes.
    return list(dict.fromkeys(matching_suggestions))
