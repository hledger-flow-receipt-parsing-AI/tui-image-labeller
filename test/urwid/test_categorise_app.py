"""The transaction categorisation screen, driven key by key.

All payees, descriptions and categories are invented.
"""

from pathlib import Path
from typing import List

import pytest
import urwid
from hledger_core.categorisation.rules import (
    CategorisationSession,
    Condition,
    RowView,
    Rule,
    RuleStore,
)

from tui_labeller.categories.category_store import CategoryStore
from tui_labeller.tuis.urwid.category_question.CategoryTreeScreen import (
    CategoryTreeScreen,
)
from tui_labeller.tuis.urwid.transactions.categorise_app import (
    CategoriseApp,
    CategoryEdit,
)


def row(
    row_id: str,
    *,
    payee: str,
    description: str = "pas",
    amount: float = 5.0,
    direction: str = "debit",
) -> RowView:
    return RowView(
        row_id=row_id,
        direction=direction,
        payee=payee,
        description=description,
        counter_account="",
        own_account="alex:examplebank:checking",
        amount=amount,
        date="2026-03-01-00-00-00",
    )


ROWS = [
    row("a", payee="Voorbeeld Supermarkt"),
    row("b", payee="Voorbeeld Supermarkt"),
    row("c", payee="Bakker Jansen", description="brood"),
    row(
        "d",
        payee="Werkgever",
        description="salaris",
        amount=-900.0,
        direction="credit",
    ),
]
CATEGORIES = {
    "groceries": {"voorbeeld": {}, "bakker": {}},
    "income": {"salary": {}},
}


def _store(tmp_path: Path, rules: List[Rule] = ()) -> RuleStore:
    return RuleStore(rules=rules, path=str(tmp_path / "rules.yaml"))


def _app(
    tmp_path: Path, *, rules: List[Rule] = (), suggest=None
) -> CategoriseApp:
    session = CategorisationSession(
        store=_store(tmp_path, rules), rows=ROWS, suggest=suggest
    )
    return CategoriseApp(
        session=session,
        category_store=CategoryStore(hierarchy=dict(CATEGORIES)),
        model_note="(no model)",
    )


def _type(app: CategoriseApp, text: str) -> None:
    for char in text:
        app.feed(char)


def _text(widget) -> str:
    return widget.get_text()[0]


class TestScreen:
    def test_shows_the_largest_group_first_with_its_draft(self, tmp_path):
        app = _app(tmp_path)
        assert "group 1/3, 4 row(s) left" in _text(app.title)
        assert "payee 'Voorbeeld Supermarkt': 2 expense row(s)" in _text(
            app.group_text
        )
        assert app.value_edit.edit_text == "Voorbeeld Supermarkt"
        assert "Rule: payee contains" in _text(app.field_text)
        assert "✓ matches 2 uncategorised" in _text(app.probe_text)
        assert _text(app.rows_text).count("\n") == 1
        assert "none (no model)" in _text(app.suggestions_text)

    def test_typing_a_category_and_enter_saves_the_rule(self, tmp_path):
        app = _app(tmp_path)
        _type(app, "groceries:voorbeeld")
        app.feed("enter")
        store = app.session.store
        assert len(store) == 1
        assert store.rules[0].target == "groceries:voorbeeld"
        assert store.rules[0].match == (
            Condition(
                field="payee", op="contains", value="Voorbeeld Supermarkt"
            ),
        )
        assert (tmp_path / "rules.yaml").exists()
        assert "Saved rule #1" in _text(app.status)
        assert "group 1/2, 2 row(s) left" in _text(app.title)

    def test_unknown_category_is_refused(self, tmp_path):
        app = _app(tmp_path)
        _type(app, "groceries:nope")
        app.feed("enter")
        assert len(app.session.store) == 0
        assert "Unknown category" in _text(app.status)

    def test_prefilled_suggestion_is_accepted_with_one_enter(self, tmp_path):
        app = _app(
            tmp_path,
            suggest=lambda g: [
                ("groceries:voorbeeld", 0.9),
                ("groceries:bakker", 0.05),
            ],
        )
        assert app.category.edit_text == "groceries:voorbeeld"
        assert "Alt+a groceries:voorbeeld (90%)" in _text(app.suggestions_text)
        app.feed("enter")
        assert app.session.store.rules[0].target == "groceries:voorbeeld"

    def test_first_key_replaces_the_prefill(self, tmp_path):
        app = _app(tmp_path, suggest=lambda g: [("groceries:voorbeeld", 0.9)])
        _type(app, "inc")
        assert app.category.edit_text == "inc"
        assert "income" in _text(app.matches_text)

    def test_alt_letter_takes_a_suggestion_and_saves(self, tmp_path):
        app = _app(
            tmp_path,
            suggest=lambda g: [
                ("groceries:voorbeeld", 0.6),
                ("groceries:bakker", 0.3),
            ],
        )
        app.feed("meta b")
        assert app.session.store.rules[0].target == "groceries:bakker"

    def test_dropdown_arrow_and_enter_fill_the_match(self, tmp_path):
        app = _app(tmp_path)
        _type(app, "bak")
        assert app.category.matches == ["groceries:bakker"]
        app.feed("down")
        app.feed("enter")  # takes the highlighted match
        assert app.category.edit_text == "groceries:bakker"
        assert len(app.session.store) == 0
        app.feed("enter")  # now saves
        assert len(app.session.store) == 1

    def test_shift_tab_edits_the_value_and_the_probe_follows(self, tmp_path):
        app = _app(tmp_path)
        app.feed("shift tab")
        assert app.pile.focus_position == app.VALUE_POS
        for _ in range(len("Voorbeeld Supermarkt")):
            app.feed("backspace")
        _type(app, "Supermarkt")
        assert "✓ matches 2" in _text(app.probe_text)
        _type(app, "x")
        assert "matches no transaction" in _text(app.probe_text)

    def test_alt_f_and_alt_o_cycle_field_and_op(self, tmp_path):
        app = _app(tmp_path)
        app.feed("meta f")
        assert "Rule: description contains" in _text(app.field_text)
        app.feed("meta o")
        assert "description starts_with" in _text(app.field_text)

    def test_skip_shows_the_next_group_and_comes_back_later(self, tmp_path):
        app = _app(tmp_path)
        app.feed("meta s")
        assert "group 1/3" in _text(app.title)
        assert "Bakker Jansen" in _text(app.group_text)
        app.feed("meta p")  # the skipped group sits at the end
        assert "Voorbeeld Supermarkt" in _text(app.group_text)

    def test_conflict_is_refused_until_alt_w(self, tmp_path):
        broad = Rule(
            id=1,
            direction="debit",
            match=(Condition(field="text", op="contains", value="pas"),),
            target="groceries:bakker",
        )
        app = _app(tmp_path, rules=[broad])
        # Only the credit row and the bakker row are uncategorised now; make
        # the draft reach into the rows rule #1 covers.
        assert "Bakker Jansen" in _text(app.group_text) or "Werkgever" in _text(
            app.group_text
        )
        while "Bakker Jansen" not in _text(app.group_text):
            app.feed("meta s")
        app.feed("shift tab")
        for _ in range(len("Bakker Jansen")):
            app.feed("backspace")
        _type(app, "a")  # 'a' is in every payee: conflicts with rule #1
        assert "Alt+w" in _text(app.probe_text)
        app.feed("shift tab")
        _type(app, "groceries:voorbeeld")
        app.feed("enter")
        assert len(app.session.store) == 1
        assert "Not saved" in _text(app.status)
        app.feed("meta w")
        assert len(app.session.store) == 2
        assert app.session.store.get(rule_id=1).unless
        assert "1 rule(s) narrowed" in _text(app.status)

    def test_tab_completes_the_common_start_then_walks_the_matches(
        self, tmp_path
    ):
        app = _app(tmp_path)
        _type(app, "groc")
        app.feed("tab")
        assert app.category.edit_text == "groceries"
        assert app.pile.focus_position == app.CATEGORY_POS  # never moves
        app.feed("tab")  # nothing more in common: the first match
        assert app.category.edit_text == "groceries:bakker"
        assert len(app.session.store) == 0
        _type(app, "x")
        app.feed("tab")  # no match: nothing happens
        assert app.category.edit_text == "groceries:bakkerx"

    def test_tab_completion_ignores_case_and_uses_the_highlight(self, tmp_path):
        app = _app(tmp_path)
        _type(app, "GROCERIES:")
        app.feed("down")
        app.feed("down")
        app.feed("tab")
        assert app.category.edit_text == "groceries:voorbeeld"

    def test_alt_y_lets_a_broad_draft_yield_to_the_specific_rule(
        self, tmp_path
    ):
        specific = Rule(
            id=1,
            direction="debit",
            match=(
                Condition(
                    field="payee", op="contains", value="Voorbeeld Supermarkt"
                ),
            ),
            target="groceries:voorbeeld",
        )
        rows = ROWS + [
            row("e", payee="Voorbeeld Bakkerij", description="brood")
        ]
        session = CategorisationSession(
            store=_store(tmp_path, [specific]), rows=rows
        )
        app = CategoriseApp(
            session=session,
            category_store=CategoryStore(hierarchy=dict(CATEGORIES)),
        )
        while "Voorbeeld Bakkerij" not in _text(app.group_text):
            app.feed("meta s")
        app.feed("shift tab")
        for _ in range(len("Voorbeeld Bakkerij")):
            app.feed("backspace")
        _type(app, "Voorbeeld")  # broader than rule #1
        assert "Alt+y" in _text(app.probe_text)
        app.feed("shift tab")
        _type(app, "groceries:bakker")
        app.feed("meta y")
        store = app.session.store
        assert len(store) == 2
        assert store.get(rule_id=1).unless == ()
        assert store.get(rule_id=2).unless == (specific.match,)
        assert "yields to 1 rule(s)" in _text(app.status)

    def test_long_rows_are_not_cut_by_the_screen_code(self, tmp_path):
        long_rows = [
            row("z", payee="Voorbeeld Supermarkt", description="x" * 200)
        ]
        session = CategorisationSession(store=_store(tmp_path), rows=long_rows)
        app = CategoriseApp(
            session=session,
            category_store=CategoryStore(hierarchy=dict(CATEGORIES)),
        )
        assert "…" not in _text(app.rows_text)
        assert "x" * 200 in _text(app.rows_text)

    def test_alt_n_opens_the_category_tree_and_a_new_category_comes_back(
        self, tmp_path
    ):
        app = _app(tmp_path)
        app.feed("meta n")
        assert isinstance(app.loop.widget, CategoryTreeScreen)
        app.loop.widget.keypress((120, 40), "esc")
        assert app.loop.widget is app.frame

    def test_finishing_the_last_group_ends_the_screen(self, tmp_path):
        app = _app(tmp_path, suggest=lambda g: [("groceries:voorbeeld", 0.9)])
        app.feed("enter")
        app.feed("enter")
        with pytest.raises(urwid.ExitMainLoop):
            app.category.take(text="income:salary")
            app.feed("enter")
        assert app.finished
        assert app.session.remaining_rows == 0

    def test_esc_quits(self, tmp_path):
        app = _app(tmp_path)
        with pytest.raises(urwid.ExitMainLoop):
            app.feed("esc")


class TestCategoryEdit:
    def test_backspace_on_a_prefill_clears_it(self):
        edit = CategoryEdit(store=CategoryStore(hierarchy=dict(CATEGORIES)))
        edit.set_prefill(text="groceries:voorbeeld")
        edit.keypress((40,), "backspace")
        assert edit.edit_text == ""
        assert not edit.prefilled
