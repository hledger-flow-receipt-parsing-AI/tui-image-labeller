from typing import List

from typeguard import typechecked


@typechecked
def get_filtered_suggestions(
    *, input_text: str, available_suggestions: List[str]
) -> List[str]:
    """
    Filter suggestions based on input text, matching from start with wildcard support.
    Special case: '*' alone shows all available suggestions.

    Args:
        input_text (str): The text entered by user, can include '*' as wildcard
        available_suggestions (list): List of possible suggestion strings

    Returns:
        list: Filtered suggestions based on input criteria
    """
    input_text = input_text.strip()

    # Special case: if input is '*', return all suggestions
    if input_text == "*":
        return available_suggestions

    # If no input, return all suggestions
    if not input_text:
        return available_suggestions

    # Handle wildcard case
    if "*" in input_text:
        # Split input by wildcard
        parts = input_text.lower().split("*")
        prefix = parts[0]  # What comes before the wildcard

        # Filter suggestions
        filtered = [
            suggestion
            for suggestion in available_suggestions
            if suggestion.lower().startswith(prefix)
            and all(part in suggestion.lower() for part in parts[1:] if part)
        ]
    else:
        # Original filtering for non-wildcard case
        filtered = [
            suggestion
            for suggestion in available_suggestions
            if suggestion.lower().startswith(input_text.lower())
        ]

    # If no matches found, return ['-']
    return filtered if filtered else ["-"]
