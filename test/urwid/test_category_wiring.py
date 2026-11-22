"""The category question inside the real questionnaire: the list is drawn
without moving anything, the new-category screen swaps in and out, and a
receipt cannot be finished with a category that does not exist."""

from types import SimpleNamespace
from typing import Any, Dict, List

import pytest
import urwid

from tui_labeller.categories.category_store import CategoryStore
from tui_labeller.tuis.urwid.ask_urwid_receipt import build_category_store
from tui_labeller.tuis.urwid.category_question.CategoryQuestion import (
    NEW_CATEGORY_KEY,
    CategoryQuestion,
)
from tui_labeller.tuis.urwid.category_question.CategoryTreeScreen import (
    CategoryTreeScreen,
)
from tui_labeller.tuis.urwid.category_question.dropdown import (
    LIST_BOTTOM_PERCENT,
    NEW_ROW_LABEL,
)
from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_app.reconfiguration.reconfiguration import (  # noqa: E501
    handle_withdrawal_toggle,
)
from tui_labeller.tuis.urwid.question_data_classes import (
    HorizontalMultipleChoiceQuestionData,
    InputValidationQuestionData,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp
from tui_labeller.tuis.urwid.receipts.BaseQuestions import BaseQuestions
from tui_labeller.tuis.urwid.receipts.WithdrawalQuestions import (
    WithdrawalQuestions,
)

SCREEN = (120, 40)
CATEGORY = 1  # index of the category question in _app()


def _tree() -> Dict[str, Any]:
    return {
        "groceries": {"ah": {}, "ekoplaza": {}},
        "repairs": {"bike": {}, "car": {}},
        "restaurant": {},
    }


def _shop_question(*, question_id: str) -> InputValidationQuestionData:
    return InputValidationQuestionData(
        question=f"{question_id}:",
        question_id=question_id,
        input_type=InputType.NAME,
        ans_required=False,
        reconfigurer=False,
        terminator=False,
        ai_suggestions=[],
        history_suggestions=[],
    )


def _app(*, store: CategoryStore) -> QuestionnaireApp:
    questions = [
        _shop_question(question_id="shop_name"),
        BaseQuestions(category_store=store).get_category_question(),
        _shop_question(question_id="shop_street"),
        _shop_question(question_id="shop_city"),
        HorizontalMultipleChoiceQuestionData(
            question="Done with this receipt?",
            question_id="done",
            choices=["yes"],
            ai_suggestions=[],
            ans_required=True,
            reconfigurer=False,
            terminator=True,
        ),
    ]
    app = QuestionnaireApp(
        header="h", questions=questions, labelled_receipts=[]
    )
    app.loop.screen = urwid.raw_display.Screen()
    app.set_focus(CATEGORY)
    return app


def _category(app: QuestionnaireApp) -> CategoryQuestion:
    widget = app.inputs[CATEGORY].base_widget
    assert isinstance(widget, CategoryQuestion)
    return widget


def _rows(app: QuestionnaireApp) -> List[str]:
    canvas = app.loop.widget.render(SCREEN, focus=True)
    return [row.decode("utf-8") for row in canvas.text]


# ------------------------------------------------------------ rendering


def test_list_is_drawn_in_the_real_layout_without_moving_anything() -> None:
    app = _app(store=CategoryStore(hierarchy=_tree()))
    opened = _rows(app)
    _category(app).keypress((80,), "esc")
    closed = _rows(app)

    field_row = next(
        index
        for index, row in enumerate(closed)
        if "Bookkeeping expense category:" in row
    )
    assert opened[field_row + 1].startswith("┌")
    assert NEW_ROW_LABEL in opened[field_row + 2]

    changed = [
        index for index, row in enumerate(opened) if row != closed[index]
    ]
    assert changed and min(changed) == field_row + 1
    assert changed == list(range(changed[0], changed[-1] + 1))
    box_width = len(opened[field_row + 1].rstrip())
    for index in changed:
        # Right of the box (rest of the question column and the sidebar)
        # nothing changed.
        assert opened[index][box_width:] == closed[index][box_width:]
    assert "Navigation" in "\n".join(opened)


def test_long_list_leaves_the_bottom_tenth_of_the_real_screen_free() -> None:
    tree = {f"category{number:03d}": {} for number in range(100)}
    app = _app(store=CategoryStore(hierarchy=tree))
    opened = _rows(app)
    _category(app).keypress((80,), "esc")
    closed = _rows(app)

    bottom = SCREEN[1] * LIST_BOTTOM_PERCENT // 100
    assert bottom == 36
    changed = [
        index for index, row in enumerate(opened) if row != closed[index]
    ]
    assert changed[-1] == bottom - 1
    assert opened[bottom - 1].startswith("└")
    assert opened[bottom:] == closed[bottom:]


def test_cursor_stays_in_the_category_field() -> None:
    app = _app(store=CategoryStore(hierarchy=_tree()))
    opened = app.loop.widget.render(SCREEN, focus=True).cursor
    _category(app).keypress((80,), "esc")
    closed = app.loop.widget.render(SCREEN, focus=True).cursor
    assert opened is not None and opened == closed


def test_keys_from_the_main_loop_reach_the_field() -> None:
    app = _app(store=CategoryStore(hierarchy=_tree()))
    for key in "groc":
        assert app.loop.widget.keypress(SCREEN, key) is None
    assert _category(app).edit_text == "groc"
    assert app.loop.widget.keypress(SCREEN, "enter") == "reconfigurer"
    assert _category(app).edit_text == "groceries"


# ----------------------------------------------------------- termination


def test_receipt_cannot_be_finished_with_an_unknown_category() -> None:
    app = _app(store=CategoryStore(hierarchy=_tree()))
    category = _category(app)
    category.set_answer("groceries:ah:zz")  # e.g. an old receipt reopened
    assert category.has_answer()
    assert app.first_unanswered_required() == CATEGORY

    done = app.inputs[4].base_widget
    done.set_answer("yes")
    app.set_focus(4)
    app._handle_input("terminator")  # must NOT raise ExitMainLoop

    assert app.get_focus() == CATEGORY
    assert not done.has_answer()
    error_text = app.error_display.base_widget.contents[1][0].text
    assert "Bookkeeping expense category" in error_text
    assert category.edit_text == "groceries:ah:zz"


def test_receipt_finishes_with_an_existing_category() -> None:
    app = _app(store=CategoryStore(hierarchy=_tree()))
    _category(app).set_answer("groceries:ah")
    assert app.first_unanswered_required() is None
    app.inputs[4].base_widget.set_answer("yes")
    with pytest.raises(urwid.ExitMainLoop):
        app._handle_input("terminator")


# ---------------------------------------------------- new-category screen


def test_new_category_key_opens_the_tree_and_escape_returns() -> None:
    app = _app(store=CategoryStore(hierarchy=_tree()))
    assert app.loop.widget is app.popup_host
    for key in "repairs":
        app.loop.widget.keypress(SCREEN, key)

    app._handle_input(NEW_CATEGORY_KEY)
    screen = app.loop.widget
    assert isinstance(screen, CategoryTreeScreen)
    assert screen.cursor_path == "repairs"

    screen.keypress(SCREEN, "esc")
    assert app.loop.widget is app.popup_host
    assert app.get_focus() == CATEGORY
    assert _category(app).edit_text == "repairs"


def test_created_category_fills_the_field_and_continues() -> None:
    store = CategoryStore(hierarchy=_tree())
    app = _app(store=store)
    for key in "repairs:boat":
        app.loop.widget.keypress(SCREEN, key)
    assert app.loop.widget.keypress(SCREEN, "enter") == NEW_CATEGORY_KEY

    app._handle_input(NEW_CATEGORY_KEY)
    screen = app.loop.widget
    assert screen.adding and screen.input.edit_text == "boat"

    # The category question is a reconfigurer: answering it ends this run
    # of the main loop, exactly as when it is answered in the field.
    with pytest.raises(urwid.ExitMainLoop):
        screen.keypress(SCREEN, "enter")

    assert store.exists(path="repairs:boat")
    assert app.loop.widget is app.popup_host
    assert _category(app).edit_text == "repairs:boat"
    assert _category(app).is_known_category()


def test_category_picked_in_the_tree_fills_the_field() -> None:
    app = _app(store=CategoryStore(hierarchy=_tree()))
    app._handle_input(NEW_CATEGORY_KEY)
    screen = app.loop.widget
    screen.keypress(SCREEN, "down")
    with pytest.raises(urwid.ExitMainLoop):
        screen.keypress(SCREEN, "enter")
    assert _category(app).edit_text == "groceries"
    assert app.loop.widget is app.popup_host


def test_new_category_key_is_ignored_on_other_questions() -> None:
    app = _app(store=CategoryStore(hierarchy=_tree()))
    app.set_focus(0)
    app._handle_input(NEW_CATEGORY_KEY)
    assert app.loop.widget is app.popup_host


# ------------------------------------------------------- reconfiguration


def _withdrawal_tui(*, base: BaseQuestions) -> Any:
    withdrawal = WithdrawalQuestions(
        account_infos_str=["at:triodos:checking"],
        accounts_without_csv={"at:wallet:physical"},
    )
    tui = QuestionnaireApp(
        header="h",
        questions=[
            base.get_withdrawal_toggle(),
            *withdrawal.withdrawal_questions,
        ],
        labelled_receipts=[],
    )
    return tui, withdrawal


def test_withdrawal_toggle_back_to_no_re_adds_the_same_category_question() -> (
    None
):
    store = CategoryStore(hierarchy=_tree())
    base = BaseQuestions(category_store=store)
    tui, withdrawal = _withdrawal_tui(base=base)

    new_tui = handle_withdrawal_toggle(
        tui=tui,
        withdrawal_questions=withdrawal,
        preserved_answers=[None for _ in tui.inputs],
        labelled_receipts=[],
        toggle_answer="n",
        base_questions=base,
    )

    widgets = [entry.base_widget for entry in new_tui.inputs]
    categories = [w for w in widgets if isinstance(w, CategoryQuestion)]
    assert len(categories) == 1
    assert categories[0].store is store
    assert [w.question_data.question_id for w in widgets] == [
        "is_withdrawal",
        "category",
    ]


def test_withdrawal_toggle_without_base_questions_keeps_free_text() -> None:
    base = BaseQuestions()
    tui, withdrawal = _withdrawal_tui(base=base)
    new_tui = handle_withdrawal_toggle(
        tui=tui,
        withdrawal_questions=withdrawal,
        preserved_answers=[None for _ in tui.inputs],
        labelled_receipts=[],
        toggle_answer="n",
    )
    widgets = [entry.base_widget for entry in new_tui.inputs]
    assert not any(isinstance(w, CategoryQuestion) for w in widgets)
    assert widgets[1].question_data.question_id == "category"


# ----------------------------------------------------------------- store


def test_no_store_without_a_category_namespace() -> None:
    assert build_category_store(config=SimpleNamespace()) is None
    assert (
        build_category_store(
            config=SimpleNamespace(
                category_namespace=SimpleNamespace(_hierarchy=None)
            )
        )
        is None
    )


def test_store_shares_the_namespace_tree_and_knows_the_file() -> None:
    tree = _tree()
    config = SimpleNamespace(
        category_namespace=SimpleNamespace(_hierarchy=tree),
        dir_paths="dirs",
        file_names=SimpleNamespace(
            get_filepath=lambda dir_path_config, filename: (
                f"/somewhere/{dir_path_config}/{filename}"
            )
        ),
    )
    store = build_category_store(config=config)
    assert store is not None
    assert store._hierarchy is tree
    assert store._yaml_path == "/somewhere/dirs/categories_filename"


def test_store_without_a_known_file_is_in_memory_only() -> None:
    tree = _tree()
    config = SimpleNamespace(
        category_namespace=SimpleNamespace(_hierarchy=tree)
    )
    store = build_category_store(config=config)
    assert store is not None
    store.add(path="travel")
    assert tree["travel"] == {}
