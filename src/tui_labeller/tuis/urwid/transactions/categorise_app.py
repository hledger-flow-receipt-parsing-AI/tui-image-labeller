"""Categorise bank transactions: one rule per group of rows.

The screen shows one group of uncategorised rows at a time with a draft
rule (field, op, value) and a category field.  The draft is probed against
every row of the finance root while you type: it is saved only when it is
the single rule on every row it matches, so the store stays one-hot.

Keys: Enter saves and shows the next group; Tab completes the category
from the matching ones; Shift+Tab moves between the value and the
category; Alt+a.. takes the n-th AI suggestion; Alt+n opens the category
tree (new categories); Alt+f / Alt+o change the field / op; Alt+s skips
the group; Alt+w makes the draft win over the rules it conflicts with
(they get an ``unless``); Alt+y makes the draft yield to them (it gets the
``unless``); Alt+p goes back; Esc quits.
"""

from __future__ import annotations

from typing import Any, Callable

import urwid
from hledger_core.categorisation.rules import (
    CategorisationSession,
    Condition,
    Draft,
    Group,
    ProbeReport,
)
from typeguard import typechecked

from tui_labeller.categories.category_store import CategoryStore
from tui_labeller.tuis.urwid.category_question.CategoryTreeScreen import (
    CategoryTreeScreen,
)
from tui_labeller.tuis.urwid.question_app.palette import setup_palette

FIELDS: tuple[str, ...] = (
    "payee",
    "description",
    "counter_account",
    "text",
    "amount",
    "own_account",
)
OPS: tuple[str, ...] = ("contains", "starts_with", "equals")
SUGGESTION_KEYS = "abcde"
MAX_ROWS = 6
MAX_MATCHES = 6
PALETTE: list[tuple[str, str, str]] = [
    ("ok", "light green", "black"),
    ("conflict", "light red", "black"),
    ("legend", "yellow", "black"),
    ("title", "white", "dark blue"),
    ("dim", "dark gray", "black"),
    ("rows", "light gray", "black"),
]
LEGEND = (
    "Enter save+next  Tab complete category  Shift+Tab value/category"
    "  Alt+a.. take suggestion  Alt+n new category  Alt+f field  Alt+o op"
    "  Alt+s skip  Alt+w this rule wins  Alt+y this rule yields"
    "  Alt+p back  Esc quit"
)


@typechecked
def common_start(*, paths: list[str]) -> str:
    """The longest start all *paths* share (compared without case), in the
    spelling of the first."""
    if not paths:
        return ""
    first = paths[0]
    length = len(first)
    for other in paths[1:]:
        length = min(length, len(other))
        for index in range(length):
            if first[index].lower() != other[index].lower():
                length = index
                break
    return first[:length]


@typechecked
def percent(value: float) -> str:
    return f"{round(value * 100)}%"


class CategoryEdit(urwid.Edit):
    """The category field: typing filters the categories, Tab completes
    (the common start of the matches, else the highlighted or first match),
    ↑/↓ highlight a match and Enter takes it.  A prefilled suggestion is
    replaced by the first key typed."""

    def __init__(self, *, store: CategoryStore) -> None:
        super().__init__(("legend", "Category: "), "")
        self.store = store
        self.matches: list[str] = []
        self.highlighted: int = -1
        self.prefilled: bool = False

    def set_prefill(self, *, text: str) -> None:
        self.set_edit_text(text)
        self.set_edit_pos(len(text))
        self.prefilled = bool(text)
        self.refilter()

    def take(self, *, text: str) -> None:
        self.set_edit_text(text)
        self.set_edit_pos(len(text))
        self.prefilled = False
        self.refilter()

    def refilter(self) -> None:
        text = self.edit_text.strip()
        self.matches = (
            self.store.matches(text=text)[:MAX_MATCHES] if text else []
        )
        if text and self.store.exists(path=text):
            self.matches = [m for m in self.matches if m != text]
        self.highlighted = -1

    def complete(self) -> None:
        """Tab: extend the text to what every matching category starts
        with; when that adds nothing, take the highlighted (else the first)
        match."""
        text = self.edit_text.strip()
        if not text:
            return
        candidates = self.store.matches(text=text)
        if not candidates:
            return
        start = common_start(paths=candidates)
        if len(start) > len(text):
            self.take(text=start)
            return
        index = self.highlighted if self.highlighted >= 0 else 0
        if index < len(self.matches):
            self.take(text=self.matches[index])

    def keypress(self, size: tuple[int], key: str) -> str | None:
        if key == "tab":
            self.complete()
            return None
        if key in ("up", "down") and self.matches:
            step = 1 if key == "down" else -1
            self.highlighted = (self.highlighted + step) % len(self.matches)
            self._invalidate()
            return None
        if key == "enter" and 0 <= self.highlighted < len(self.matches):
            self.take(text=self.matches[self.highlighted])
            return None
        if self.prefilled and len(key) == 1 and key.isprintable():
            self.take(text="")
        elif self.prefilled and key in ("backspace", "delete"):
            self.take(text="")
            return None
        result = super().keypress(size, key)
        self.refilter()
        return result

    def dropdown_text(self) -> list[Any]:
        if not self.matches:
            return [("dim", "")]
        parts: list[Any] = []
        for index, path in enumerate(self.matches):
            style = "dropdown_selected" if index == self.highlighted else "dim"
            parts.append((style, f"  {path}"))
            parts.append("\n")
        return parts[:-1]


class CategoriseApp:
    @typechecked
    def __init__(
        self,
        *,
        session: CategorisationSession,
        category_store: CategoryStore,
        model_note: str = "",
        screen: Any | None = None,
        on_exit: Callable[[], None] | None = None,
    ) -> None:
        self.session = session
        self.store = category_store
        self.model_note = model_note
        self._on_exit = on_exit
        self.field_index = 0
        self.op_index = 0
        self.report: ProbeReport | None = None
        self.finished = False

        self.title = urwid.Text(("title", ""), wrap="clip")
        self.group_text = urwid.Text("", wrap="clip")
        self.rows_text = urwid.Text(("rows", ""), wrap="clip")
        self.field_text = urwid.Text("", wrap="clip")
        self.value_edit = urwid.Edit(("legend", "Value: "), "")
        self.probe_text = urwid.Text("", wrap="clip")
        self.category = CategoryEdit(store=category_store)
        self.matches_text = urwid.Text("", wrap="clip")
        self.suggestions_text = urwid.Text(("ai_suggestions", ""), wrap="clip")
        self.status = urwid.Text("", wrap="clip")
        self.pile = urwid.Pile(
            [
                self.group_text,
                self.rows_text,
                urwid.Divider("─"),
                self.field_text,
                urwid.AttrMap(self.value_edit, "input"),
                self.probe_text,
                urwid.Divider("─"),
                urwid.AttrMap(self.category, "input"),
                self.matches_text,
                self.suggestions_text,
                urwid.Divider("─"),
                self.status,
            ]
        )
        self.VALUE_POS = 4
        self.CATEGORY_POS = 7
        self.frame = urwid.Frame(
            body=urwid.Filler(self.pile, valign="top"),
            header=self.title,
            footer=urwid.Text(("legend", LEGEND)),
        )
        urwid.connect_signal(self.value_edit, "postchange", self._value_changed)
        urwid.connect_signal(
            self.category, "postchange", self._category_changed
        )
        loop_kwargs = {} if screen is None else {"screen": screen}
        self.loop = urwid.MainLoop(
            self.frame,
            setup_palette() + PALETTE,
            unhandled_input=self._unhandled,
            input_filter=self._filter,
            handle_mouse=False,
            **loop_kwargs,
        )
        self.show_group()

    # ---------------------------------------------------------- render
    @property
    def group(self) -> Group | None:
        return self.session.current

    def show_group(self) -> None:
        group = self.group
        if group is None:
            self._finish()
            return
        draft = self.session.draft()
        condition = draft.match[0]
        self.field_index = (
            FIELDS.index(condition.field) if condition.field in FIELDS else 0
        )
        self.op_index = OPS.index(condition.op) if condition.op in OPS else 0
        self.value_edit.set_edit_text(str(condition.value))
        self.value_edit.set_edit_pos(len(self.value_edit.edit_text))
        self.category.set_prefill(text=draft.target)
        index, count = self.session.position()
        self.title.set_text(
            (
                "title",
                (
                    f" Categorise transactions — group {index}/{count},"
                    f" {self.session.remaining_rows} row(s) left "
                ),
            )
        )
        word = "expense" if group.direction == "debit" else "income"
        self.group_text.set_text(
            f"{group.field} {group.label()!r}: {group.n} {word} row(s),"
            f" total {group.total:.2f}"
        )
        self._show_suggestions(group)
        self.status.set_text("")
        self._refresh_probe()
        self.pile.focus_position = self.CATEGORY_POS

    def _show_suggestions(self, group: Group) -> None:
        suggestions = self.session.suggestions(group=group)
        if not suggestions:
            self.suggestions_text.set_text(
                (
                    "ai_suggestions",
                    f"AI suggestions: none {self.model_note}".rstrip(),
                )
            )
            return
        parts = [
            f"Alt+{SUGGESTION_KEYS[i]} {path} ({percent(p)})"
            for i, (path, p) in enumerate(suggestions[: len(SUGGESTION_KEYS)])
        ]
        self.suggestions_text.set_text(
            ("ai_suggestions", "AI suggestions:  " + "   ".join(parts))
        )

    def _condition(self) -> Condition | None:
        value = self.value_edit.edit_text.strip()
        if not value:
            return None
        field = FIELDS[self.field_index]
        op = OPS[self.op_index]
        if field == "amount" and op == "equals":
            try:
                value = str(float(value.replace(",", ".")))
            except ValueError:
                pass
        return Condition(field=field, op=op, value=value, case_sensitive=False)

    def draft(self) -> Draft | None:
        group = self.group
        condition = self._condition()
        if group is None or condition is None:
            return None
        return Draft(
            direction=group.direction,
            match=[condition],
            target=self.category.edit_text.strip(),
        )

    def _refresh_probe(self) -> None:
        self.field_text.set_text(
            f"Rule: {FIELDS[self.field_index]} {OPS[self.op_index]}  (Alt+f /"
            " Alt+o)"
        )
        draft = self.draft()
        if draft is None:
            self.report = None
            self.probe_text.set_text(("conflict", "Type a value for the rule."))
            self.rows_text.set_text("")
            return
        self.report = self.session.probe(draft=draft)
        report = self.report
        lines: list[Any] = []
        if not report.matched:
            lines.append(("conflict", "✗ matches no transaction"))
        elif report.is_one_hot:
            lines.append(
                (
                    "ok",
                    (
                        f"✓ matches {len(report.gained)} uncategorised row(s),"
                        " no other rule"
                    ),
                )
            )
        else:
            rules = report.conflicting_rules()
            lines.append(
                (
                    "conflict",
                    (
                        f"✗ also matches {len(report.conflicts)} row(s) that"
                        f" {len(rules)} other rule(s) cover (Alt+w: this rule"
                        " wins them, Alt+y: it yields to them):"
                    ),
                )
            )
            for rule in rules[:3]:
                lines.append("\n")
                lines.append(("conflict", f"   {rule.describe()}"))
            sample, _rules = report.conflicts[0]
            lines.append("\n")
            lines.append(("conflict", "   e.g. " + sample.one_line()))
        self.probe_text.set_text(lines)
        shown = report.gained[:MAX_ROWS]
        # Full lines: the widgets clip at the edge of the terminal.
        row_lines = [row.one_line() for row in shown]
        if len(report.gained) > MAX_ROWS:
            row_lines.append(f"  … {len(report.gained) - MAX_ROWS} more")
        self.rows_text.set_text(("rows", "\n".join(row_lines)))

    def _value_changed(self, *_args: Any) -> None:
        self._refresh_probe()

    def _category_changed(self, *_args: Any) -> None:
        self.matches_text.set_text(self.category.dropdown_text())

    # ------------------------------------------------------------ keys
    def _filter(self, keys: list[Any], raw: list[int]) -> list[Any]:
        kept: list[Any] = []
        for key in keys:
            if key == "meta s":
                self.session.skip()
                self.show_group()
            elif key == "meta w":
                self._accept(win=True)
            elif key == "meta y":
                self._accept(yield_to=True)
            elif key == "meta n":
                self._open_tree()
            elif key == "meta f":
                self.field_index = (self.field_index + 1) % len(FIELDS)
                self._refresh_probe()
            elif key == "meta o":
                self.op_index = (self.op_index + 1) % len(OPS)
                self._refresh_probe()
            elif key == "meta p":
                self.session.previous()
                self.show_group()
            elif (
                isinstance(key, str)
                and key.startswith("meta ")
                and key[5:] in SUGGESTION_KEYS
            ):
                self._take_suggestion(index=SUGGESTION_KEYS.index(key[5:]))
            else:
                kept.append(key)
        return kept

    def _unhandled(self, key: Any) -> None:
        if key == "enter":
            if self.pile.focus_position == self.VALUE_POS:
                self.pile.focus_position = self.CATEGORY_POS
            else:
                self._accept()
        elif key == "shift tab":
            self.pile.focus_position = (
                self.CATEGORY_POS
                if self.pile.focus_position == self.VALUE_POS
                else self.VALUE_POS
            )
        elif key == "esc":
            self._quit()

    def feed(self, key: str) -> None:
        """One key as the main loop would deliver it (tests)."""
        for kept in self._filter([key], []):
            if self.loop.widget.keypress((120, 40), kept) is not None:
                self._unhandled(kept)

    # --------------------------------------------------------- actions
    def _take_suggestion(self, *, index: int) -> None:
        group = self.group
        if group is None:
            return
        suggestions = self.session.suggestions(group=group)
        if index < len(suggestions):
            self.category.take(text=suggestions[index][0])
            self._accept()

    def _accept(self, *, win: bool = False, yield_to: bool = False) -> None:
        draft = self.draft()
        if draft is None:
            self.status.set_text(("conflict", "The rule needs a value."))
            return
        if not draft.target:
            self.status.set_text(
                ("conflict", "Type a category (Alt+n creates a new one).")
            )
            self.pile.focus_position = self.CATEGORY_POS
            return
        if not self.store.exists(path=draft.target):
            self.status.set_text(
                (
                    "conflict",
                    f"Unknown category {draft.target!r}: Alt+n creates it.",
                )
            )
            return
        yielded = 0
        if yield_to:
            draft = self.session.yielded(draft=draft)
            yielded = len(draft.unless)
        result = self.session.accept(draft=draft, win=win)
        if not result.ok:
            self._refresh_probe()
            self.status.set_text(
                (
                    "conflict",
                    (
                        "Not saved: another rule covers some of these rows"
                        " (Alt+w: this rule wins, Alt+y: it yields)."
                    ),
                )
            )
            return
        narrowed = (
            f", {len(result.narrowed)} rule(s) narrowed"
            if result.narrowed
            else ""
        )
        if yielded:
            narrowed += f", yields to {yielded} rule(s)"
        self.status.set_text(
            (
                "ok",
                (
                    f"Saved rule #{result.rule.id} ->"
                    f" {result.rule.target}{narrowed}"
                ),
            )
        )
        saved = self.status.get_text()[0]
        self.show_group()
        if self.group is not None:
            self.status.set_text(("ok", saved))

    def _open_tree(self) -> None:
        def use(path: str) -> None:
            self.loop.widget = self.frame
            self.category.take(text=path)
            self.pile.focus_position = self.CATEGORY_POS

        def cancel() -> None:
            self.loop.widget = self.frame

        self.loop.widget = CategoryTreeScreen(
            store=self.store,
            typed_text=self.category.edit_text,
            on_use=use,
            on_cancel=cancel,
        )

    def _finish(self) -> None:
        self.finished = True
        self.title.set_text(("title", " Every transaction is categorised "))
        self._quit()

    def _quit(self) -> None:
        if self._on_exit is not None:
            self._on_exit()
        raise urwid.ExitMainLoop()

    def run(self) -> None:
        if self.finished:
            return
        try:
            self.loop.run()
        except urwid.ExitMainLoop:
            pass
