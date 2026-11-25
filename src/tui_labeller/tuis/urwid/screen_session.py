"""One terminal screen for all the questionnaires of a receipt.

A reconfiguration (withdrawal yes/no, category, account, address) ends the
urwid loop and starts a new one with a rebuilt questionnaire. urwid stops
the screen when a loop ends and starts it again for the next, which flips
the terminal out of the TUI and back: the shell flashes through between
two questions and the eyes have to find their place again. Inside a
session the screen stays up and the next questionnaire draws over the
previous one in place; the terminal is given back when the session ends,
or for as long as something else needs it (the matching CLI's input()).
"""

import contextlib
from typing import Any, Iterator, Optional

import urwid
from typeguard import typechecked


class SharedScreen(urwid.raw_display.Screen):
    """A terminal screen that stays up when a loop ends, while held."""

    def __init__(self) -> None:
        super().__init__()
        self.held: bool = False

    def stop(self) -> None:
        if self.held:
            return  # the next questionnaire draws over this one
        super().stop()

    @typechecked
    def suspend(self) -> None:
        """Give the terminal back for real."""
        self.held = False
        self.stop()

    @typechecked
    def resume(self) -> None:
        """Take the terminal again and keep it between loops."""
        self.start()
        self.held = True


_current: Optional[SharedScreen] = None


@contextlib.contextmanager
def shared_screen() -> Iterator[SharedScreen]:
    """Questionnaires built inside share one screen that stays up between their
    loops; the terminal is restored at the end."""
    global _current
    screen = SharedScreen()
    screen.held = True
    previous, _current = _current, screen
    try:
        yield screen
    finally:
        _current = previous
        screen.suspend()


@typechecked
def current_screen() -> Optional[SharedScreen]:
    """The screen of the session that is open, if any."""
    return _current


@typechecked
def suspend_screen(*, screen: Any) -> None:
    """Stop *screen* for real, shared or not."""
    if isinstance(screen, SharedScreen):
        screen.suspend()
    else:
        screen.stop()


@typechecked
def resume_screen(*, screen: Any) -> None:
    """Start *screen* again, shared (and held) or not."""
    if isinstance(screen, SharedScreen):
        screen.resume()
    else:
        screen.start()
