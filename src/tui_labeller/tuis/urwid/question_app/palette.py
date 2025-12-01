from typing import List

from typeguard import typechecked


@typechecked
def setup_palette() -> List[tuple]:
    """Setup color palette for the UI with format:
    <identifier>, <text colour>, <background colour>."""
    return [
        # ("normal", "white", ""),
        # ("highlight", "white", "dark red"),
        # ("direction", "white", "yellow"),
        # ("navigation", "dark green", ""),
        # ("error", "dark red", ""),
        # ("ai_suggestions", "yellow", ""),
        # ("history_suggestions", "light cyan", ""),
        #
        ("normal", "white", "black"),
        ("highlight", "white", "dark red"),
        ("direction", "white", "yellow"),
        ("navigation", "yellow", "black"),
        ("error", "light red", "black"),
        ("ai_suggestions", "light cyan", "black"),
        ("history_suggestions", "light green", "black"),
        ("mc_question_palette", "white", ""),
        # New colours
        ("border", "white", "dark blue"),
        ("number", "yellow", "dark blue"),
        ("text", "white", "black"),
        ("input", "light cyan", "black"),
        ("starred", "light green", "black"),  # Add starred style
    ]
