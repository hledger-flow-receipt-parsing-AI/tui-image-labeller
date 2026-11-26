"""The tags of the receipt being labelled: events and projects (Alt+t).

A tag says what a purchase was for, across categories: a holiday
("seaside-trip"), a project ("workbench").  The journal carries them
(hledger_core.tagging), so the dashboard can show what each cost.  Two
words are special: "traceable" and "untraceable" say whether others can
see the receipt's payments, whatever its accounts say.

Tags are not a question of the questionnaire, so receipts without tags
(most of them) take no extra key.  Alt+t opens a small editor at any
question; the current tags stay at the top right.  The editor offers the
tags of tags.yaml in the finance root and those used on earlier receipts,
events whose period covers the receipt's date first.
"""

import logging
from collections import Counter
from datetime import date, datetime
from typing import Any, Callable, Iterable, List, Optional, Tuple

import urwid
from hledger_core.tagging import (
    TRACEABLE,
    UNTRACEABLE,
    TagDefinition,
    load_tag_definitions,
    normalize_tag,
    parse_tags,
    tags_file_path,
)
from typeguard import typechecked

logger = logging.getLogger(__name__)

TAG_KEY = "meta t"
TAG_KEY_NAME = "Alt+t"
NAVIGATION_HINT = f"{TAG_KEY_NAME}      - tags (events, projects)"
EDITOR_TITLE = "Tags of this receipt"
MAX_OFFERED = 8
PALETTE = [
    ("tags", "light green", "black"),
    ("tags_dialog", "white", "dark blue"),
    ("tags_offer", "light cyan", "dark blue"),
]
_SPECIAL = {
    TRACEABLE: "others (bank, card) see its payments",
    UNTRACEABLE: "nobody else sees its payments",
}


class ReceiptTags:
    """The tags of one receipt, kept while its questionnaire is rebuilt."""

    @typechecked
    def __init__(
        self,
        *,
        tags: Iterable[str] = (),
        definitions: Iterable[TagDefinition] = (),
        used_tags: Iterable[str] = (),
    ) -> None:
        self.tags: List[str] = parse_tags(text=", ".join(tags))
        self.definitions: List[TagDefinition] = list(definitions)
        # Tags of earlier receipts, most used first.
        self.used: List[str] = [
            tag for tag, _ in Counter(used_tags).most_common()
        ]

    @staticmethod
    @typechecked
    def for_receipt(
        *,
        config: Any,
        labelled_receipts: Iterable[Any],
        prefilled_receipt: Any = None,
    ) -> "ReceiptTags":
        """The tags of *prefilled_receipt* (none for a new receipt), with
        tags.yaml of the finance root and the tags of *labelled_receipts* to
        choose from."""
        definitions: List[TagDefinition] = []
        root = getattr(
            getattr(config, "dir_paths", None), "root_finance_path", None
        )
        if isinstance(root, str):
            try:
                definitions = load_tag_definitions(
                    path=tags_file_path(root_finance_path=root)
                )
            except (OSError, ValueError):
                # A broken tags.yaml must not stop the labelling.
                logger.exception("Reading tags.yaml failed")
        used = [
            tag
            for receipt in labelled_receipts
            for tag in (getattr(receipt, "tags", None) or [])
        ]
        return ReceiptTags(
            tags=getattr(prefilled_receipt, "tags", None) or [],
            definitions=definitions,
            used_tags=used,
        )

    @typechecked
    def summary(self) -> str:
        return f"Tags ({TAG_KEY_NAME}): {', '.join(self.tags) or '-'}"

    @typechecked
    def attach(self, *, tui: Any) -> None:
        """Let *tui* show and edit these tags (each rebuilt questionnaire)."""
        tui.receipt_tags = self
        tui.show_receipt_tags(text=self.summary())

    @typechecked
    def set_text(self, *, text: str) -> None:
        self.tags = parse_tags(text=text)

    @typechecked
    def offers(
        self, *, typed: str, day: Optional[date]
    ) -> List[Tuple[str, str]]:
        """(tag, note) pairs that complete the tag being typed (after the last
        comma): events of *day* first, then the tags of tags.yaml, then those
        used before, then the traceability words."""
        current = normalize_tag(text=typed.split(",")[-1])
        chosen = set(
            parse_tags(text=typed)[:-1] if current else parse_tags(text=typed)
        )
        offered: List[Tuple[str, str]] = []

        def offer(tag: str, note: str) -> None:
            if tag in chosen or any(tag == known for known, _ in offered):
                return
            if current and not tag.startswith(current):
                return
            offered.append((tag, note))

        if day is not None:
            for definition in self.definitions:
                if definition.covers(day=day):
                    offer(
                        definition.name,
                        f"this date: {definition.period_text()}",
                    )
        for definition in self.definitions:
            offer(
                definition.name,
                definition.description or definition.period_text(),
            )
        for tag in self.used:
            offer(tag, "used before")
        for tag, note in _SPECIAL.items():
            offer(tag, note)
        return offered[:MAX_OFFERED]


@typechecked
def complete_last_tag(*, typed: str, tag: str) -> str:
    """*typed* with its last (unfinished) tag replaced by *tag*, ready for
    the next one: "shed, sea" + "seaside-trip" -> "shed, seaside-trip, "."""
    done = [part.strip() for part in typed.split(",")[:-1] if part.strip()]
    return ", ".join(done + [tag]) + ", "


class TagsEditor(urwid.WidgetWrap):
    """A small dialog over the questions: type tags (comma separated),
    Tab completes the one being typed, Enter keeps them, Esc cancels."""

    @typechecked
    def __init__(
        self,
        *,
        receipt_tags: ReceiptTags,
        day: Optional[date],
        on_done: Callable[[str], None],
        on_cancel: Callable[[], None],
    ) -> None:
        self._tags = receipt_tags
        self._day = day
        self._on_done = on_done
        self._on_cancel = on_cancel
        text = ", ".join(receipt_tags.tags)
        self.edit = urwid.Edit(
            ("tags_dialog", "> "), text + (", " if text else "")
        )
        self.offers = urwid.Text("")
        body = urwid.Pile(
            [
                urwid.Text("Events and projects, comma separated:"),
                self.edit,
                urwid.Divider(),
                urwid.AttrMap(self.offers, "tags_offer"),
                urwid.Divider(),
                urwid.Text("Tab: complete  Enter: keep  Esc: cancel"),
            ]
        )
        body.focus_position = 1
        box = urwid.LineBox(
            urwid.Padding(body, left=1, right=1), title=EDITOR_TITLE
        )
        super().__init__(urwid.AttrMap(box, "tags_dialog"))
        self._show_offers()

    def _show_offers(self) -> None:
        offers = self._tags.offers(typed=self.edit.edit_text, day=self._day)
        if not offers:
            self.offers.set_text("No known tag starts like this: a new one.")
            return
        self.offers.set_text(
            "\n".join(
                f"{tag}  ({note})" if note else tag for tag, note in offers
            )
        )

    def keypress(self, size: Tuple[int, ...], key: str) -> Optional[str]:
        if key == "enter":
            self._on_done(self.edit.edit_text)
            return None
        if key == "esc":
            self._on_cancel()
            return None
        if key == "tab":
            offers = self._tags.offers(typed=self.edit.edit_text, day=self._day)
            if offers:
                completed = complete_last_tag(
                    typed=self.edit.edit_text, tag=offers[0][0]
                )
                self.edit.set_edit_text(completed)
                self.edit.set_edit_pos(len(completed))
            self._show_offers()
            return None
        if key in ("up", "down", "page up", "page down"):
            return None  # nothing to move to; stay in the dialog
        super().keypress(size, key)
        self._show_offers()
        return None


@typechecked
def receipt_day(*, inputs: Iterable[Any]) -> Optional[date]:
    """The date answered in the questionnaire so far, if any."""
    for widget in inputs:
        base = getattr(widget, "base_widget", widget)
        data = getattr(base, "question_data", None)
        if getattr(data, "question_id", None) != "date":
            continue
        try:
            answer = base.get_answer()
        except (ValueError, AttributeError):
            return None
        if isinstance(answer, datetime):
            return answer.date()
        if isinstance(answer, date):
            return answer
    return None


@typechecked
def editor_overlay(*, editor: TagsEditor, below: Any) -> urwid.Overlay:
    return urwid.Overlay(
        editor,
        below,
        align="center",
        width=("relative", 60),
        valign="middle",
        height="pack",
        min_width=44,
    )
