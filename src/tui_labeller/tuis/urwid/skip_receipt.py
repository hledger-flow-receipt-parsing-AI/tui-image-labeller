"""Skipping a receipt for now.

While receipts are labelled one after the other, a receipt the user does
not want to fill in right now can be skipped with Alt+s or the "Skip"
button at the top right.  A red dialog asks "Are you sure?" first; after
a yes the questionnaire ends with ReceiptSkipped and the labelling loop
(hledger-receipt-processing) goes on with the next receipt.  No label is
made, so the receipt comes back the next time receipts are labelled.

The option exists only inside ``receipt_skipping()``: other users of the
questionnaire (editing one receipt, tests) have nothing to skip to.
"""

import contextlib
from typing import Any, Callable, Iterator, Optional, Tuple

import urwid
from typeguard import typechecked

SKIP_KEY = "meta s"
SKIP_KEY_NAME = "Alt+s"
BUTTON_LABEL = f"[ Skip receipt: {SKIP_KEY_NAME} ]"
NAVIGATION_HINT = f"{SKIP_KEY_NAME}      - skip this receipt"
DIALOG_TITLE = "Skip this receipt?"
DIALOG_TEXT = (
    "It stays unlabelled and comes back the next time you label"
    " receipts. The answers given for it are not kept."
)
PALETTE = [
    ("skip_button", "white", "dark red"),
    ("skip_dialog", "white", "dark red"),
    ("skip_dialog_focus", "dark red", "white"),
]


class ReceiptSkipped(Exception):
    """The user skipped this receipt for now; it gets no label."""


_depth: int = 0


@contextlib.contextmanager
def receipt_skipping() -> Iterator[None]:
    """Questionnaires built inside offer to skip the receipt."""
    global _depth
    _depth += 1
    try:
        yield
    finally:
        _depth -= 1


@typechecked
def skipping_allowed() -> bool:
    return _depth > 0


class SkipButton(urwid.Text):
    """The "Skip" button in the header row: a click opens the dialog.

    A Text, so it never takes the focus from the questions (urwid hands
    mouse clicks to widgets that cannot take the focus as well).
    """

    def __init__(self, *, on_click: Callable[[], None]) -> None:
        super().__init__(("skip_button", BUTTON_LABEL), align="right")
        self._on_click = on_click

    def mouse_event(
        self,
        size: Tuple[int, ...],
        event: str,
        button: int,
        col: int,
        row: int,
        focus: bool,
    ) -> bool:
        if event == "mouse press" and button == 1:
            self._on_click()
            return True
        return False


class SkipConfirmation(urwid.WidgetWrap):
    """The red "Are you sure?" dialog.

    y or "Yes, skip" skips; n, Esc or "No" goes back to the questions,
    which keep their answers.  "No" has the focus, so an Enter by
    accident skips nothing.
    """

    def __init__(
        self, *, on_yes: Callable[[], None], on_no: Callable[[], None]
    ) -> None:
        self._on_yes = on_yes
        self._on_no = on_no
        yes_label, no_label = "Yes, skip (y)", "No (n)"
        yes = urwid.Button(yes_label, on_press=lambda _button: on_yes())
        no = urwid.Button(no_label, on_press=lambda _button: on_no())
        # A button draws "< label >"; three columns between the two.
        buttons_width = len(yes_label) + len(no_label) + 2 * 4 + 3
        self.buttons = urwid.Columns(
            [
                (
                    "pack",
                    urwid.AttrMap(yes, "skip_dialog", "skip_dialog_focus"),
                ),
                ("pack", urwid.AttrMap(no, "skip_dialog", "skip_dialog_focus")),
            ],
            dividechars=3,
        )
        self.buttons.focus_position = 1
        body = urwid.Pile(
            [
                urwid.Text(DIALOG_TEXT),
                urwid.Divider(),
                urwid.Text("Are you sure?"),
                urwid.Divider(),
                urwid.Padding(
                    self.buttons, align="center", width=buttons_width
                ),
            ]
        )
        box = urwid.LineBox(
            urwid.Padding(body, left=1, right=1), title=DIALOG_TITLE
        )
        super().__init__(urwid.AttrMap(box, "skip_dialog"))

    def keypress(self, size: Tuple[int, ...], key: str) -> Optional[str]:
        if key in ("y", "Y"):
            self._on_yes()
            return None
        if key in ("n", "N", "esc"):
            self._on_no()
            return None
        if key in ("tab", "shift tab"):
            self.buttons.focus_position = 1 - self.buttons.focus_position
            return None
        # Enter presses the focused button, Left/Right move between them;
        # nothing else reaches the questions below the dialog.
        super().keypress(size, key)
        return None


@typechecked
def confirmation_overlay(
    *,
    dialog: SkipConfirmation,
    below: Any,
) -> urwid.Overlay:
    """*dialog* in the middle of the screen, over the questionnaire."""
    return urwid.Overlay(
        dialog,
        below,
        align="center",
        width=("relative", 60),
        valign="middle",
        height="pack",
        min_width=44,
    )
