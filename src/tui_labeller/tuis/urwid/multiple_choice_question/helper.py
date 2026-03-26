from typeguard import typechecked

from tui_labeller.tuis.urwid.question_data_classes import (
    VerticalMultipleChoiceQuestionData,
)


def input_is_in_int_range(
    *, char: str, start: int, ceiling: int, current: str = ""
) -> bool:
    # Validate that the input is a single digit
    if not char.isdigit():
        return False

    # Combine the current input with the new digit
    new_input = current + char

    # If the new input is empty, reject it
    if not new_input:
        return False

    try:
        # Convert the combined input to an integer
        num = int(new_input)
        # Check if the number is within the range [start, ceiling]
        return start <= num < ceiling

    except ValueError:
        return False


@typechecked
def get_selected_caption(
    *,
    vc_question_data: VerticalMultipleChoiceQuestionData,
    selected_index: int,
    indentation: int,
) -> str:

    @typechecked
    def get_selected_answer(
        *,
        vc_question_data: VerticalMultipleChoiceQuestionData,
        selected_index: int,
        indentation: int,
    ) -> str:
        max_choice_length = max(
            len(choice) for choice in vc_question_data.choices
        )
        suggestion_text = ""
        for suggestion in vc_question_data.ai_suggestions:
            if suggestion.question == vc_question_data.choices[selected_index]:
                # Use fixed-width spacing instead of tabs for consistent rendering
                suggestion_text = (
                    f"{suggestion.probability:.2f} {suggestion.ai_suggestions}"
                )
        # Replace tabs with spaces and ensure consistent indentation
        return (
            f"{' ' * indentation}{selected_index} {vc_question_data.choices[selected_index]:<{max_choice_length}} "
            f" {suggestion_text}"
        )

    new_caption: str = vc_question_data.question
    new_caption += (
        f"\n{
        get_selected_answer(
            vc_question_data=vc_question_data,
            selected_index=selected_index,
            indentation=indentation,
        )}"
    )

    return f"{new_caption}\n"


def get_vc_question(
    *,
    vc_question_data: VerticalMultipleChoiceQuestionData,
    indentation: int,
    batch_start: int = 0,
    batch_size: int = None,
) -> str:
    result = [vc_question_data.question]
    # If batch_size is None, show all choices from batch_start
    choices = (
        vc_question_data.choices[batch_start : batch_start + batch_size]
        if batch_size
        else vc_question_data.choices[batch_start:]
    )
    max_choice_length = max(len(choice) for choice in choices) if choices else 0

    for i, choice in enumerate(choices):
        suggestion_text = ""
        for suggestion in vc_question_data.ai_suggestions:
            if suggestion.question == choice:
                # Use fixed-width spacing instead of tabs for consistent rendering
                suggestion_text = (
                    f"{suggestion.probability:.2f} {suggestion.ai_suggestions}"
                )
        # Replace tabs with spaces and ensure consistent indentation
        global_index = batch_start + i
        line = (
            f"{' ' * indentation}{global_index} {choice:<{max_choice_length}} "
            f" {suggestion_text}"
        )
        result.append(line)

    options_text: str = "\n".join(result)
    # Ensure the output is clean ASCII to avoid encoding issues
    options_text = options_text.encode("ascii", errors="ignore").decode("ascii")
    return f"\n{options_text}\n"


def get_vc_question_with_highlight(
    *,
    vc_question_data: VerticalMultipleChoiceQuestionData,
    indentation: int,
    highlighted_index: int,
    window_size: int = 12,
) -> str:
    """Render the choice list with a visible window that scrolls to keep
    the highlighted item visible.  Index 0 is always pinned at the top.

    The visible window contains up to *window_size* entries.  When the
    highlighted index moves beyond the window, the window shifts so the
    highlighted item stays visible.
    """
    all_choices = vc_question_data.choices
    total = len(all_choices)
    if total == 0:
        return f"\n{vc_question_data.question}\n"

    highlighted_index = max(0, min(highlighted_index, total - 1))

    # Determine which indices to show.
    if total <= window_size:
        visible_indices = list(range(total))
    else:
        # Index 0 is always pinned; the remaining (window_size - 1) slots
        # form a sliding window over indices 1..total-1.
        slots = window_size - 1
        # Ensure the highlighted index is visible.
        if highlighted_index == 0:
            window_start = 1
        else:
            # Centre the highlight in the sliding portion.
            half = slots // 2
            window_start = highlighted_index - half
            window_start = max(1, window_start)
            window_start = min(window_start, total - slots)
            window_start = max(1, window_start)
        window_end = min(window_start + slots, total)
        visible_indices = [0] + list(range(window_start, window_end))

    max_choice_length = (
        max(len(all_choices[i]) for i in visible_indices) if visible_indices else 0
    )

    result = [vc_question_data.question]
    for idx in visible_indices:
        choice = all_choices[idx]
        suggestion_text = ""
        for suggestion in vc_question_data.ai_suggestions:
            if suggestion.question == choice:
                suggestion_text = (
                    f"{suggestion.probability:.2f} {suggestion.ai_suggestions}"
                )
        marker = ">" if idx == highlighted_index else " "
        line = (
            f"{marker}{' ' * indentation}{idx} {choice:<{max_choice_length}} "
            f" {suggestion_text}"
        )
        result.append(line)

    options_text: str = "\n".join(result)
    options_text = options_text.encode("ascii", errors="ignore").decode("ascii")
    return f"\n{options_text}\n"
