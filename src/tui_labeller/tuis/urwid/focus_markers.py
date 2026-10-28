"""Invisible focus markers for demo recordings.

When ``TUI_LABELLER_FOCUS_MARKERS`` is set, the questionnaire writes an OSC
string naming the focused question to stdout every time the focus changes::

    ESC ] 9999 ; hp-focus=<question_id> BEL

Terminals (and asciinema-agg) ignore unknown OSC strings, so nothing is drawn,
but asciinema records them with exact timestamps.  The hledger-preprocessor
demo harness (``gifs/automation/markers.py``) turns them into the receipt
highlight timeline, replacing guesswork about when each field was active.
"""

import os

from typeguard import typechecked

FOCUS_MARKER_ENV = "TUI_LABELLER_FOCUS_MARKERS"
FOCUS_MARKER_OSC = 9999
FOCUS_MARKER_TAG = "hp-focus"


@typechecked
def focus_markers_enabled() -> bool:
    """True when the recording harness asked for focus markers."""
    return bool(os.environ.get(FOCUS_MARKER_ENV))


@typechecked
def format_focus_marker(*, question_id: str) -> str:
    """The exact byte sequence written for a focus change."""
    return f"\x1b]{FOCUS_MARKER_OSC};{FOCUS_MARKER_TAG}={question_id}\x07"
