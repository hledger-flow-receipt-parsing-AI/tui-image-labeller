"""Tags of a receipt (events, projects), edited with Alt+t.

All tags and dates here are invented.
"""

from datetime import date, datetime
from pathlib import Path
from types import SimpleNamespace

import urwid
from hledger_core.tagging import TagDefinition

from tui_labeller.tuis.urwid.input_validation.InputType import InputType
from tui_labeller.tuis.urwid.question_data_classes import (
    InputValidationQuestionData,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp
from tui_labeller.tuis.urwid.receipt_tags import (
    ReceiptTags,
    TagsEditor,
    complete_last_tag,
    receipt_day,
)

SIZE = (110, 30)
TRIP = TagDefinition(
    name="summer-trip",
    description="A week by the sea",
    start=date(2023, 7, 1),
    end=date(2023, 7, 8),
)
SHED = TagDefinition(name="shed", description="Building the shed")


def _tags(**kwargs) -> ReceiptTags:
    return ReceiptTags(definitions=[TRIP, SHED], used_tags=["sauna"], **kwargs)


def test_an_event_of_the_receipts_date_is_offered_first() -> None:
    offers = _tags().offers(typed="", day=date(2023, 7, 3))

    assert offers[0][0] == "summer-trip"
    assert "this date" in offers[0][1]
    assert [tag for tag, _ in offers] == [
        "summer-trip",
        "shed",
        "sauna",
        "traceable",
        "untraceable",
    ]


def test_offers_complete_the_tag_being_typed() -> None:
    tags = _tags()

    assert [t for t, _ in tags.offers(typed="sh", day=None)] == ["shed"]
    assert [t for t, _ in tags.offers(typed="shed, s", day=None)] == [
        "summer-trip",
        "sauna",
    ]
    assert tags.offers(typed="zz", day=None) == []


def test_complete_last_tag() -> None:
    assert (
        complete_last_tag(typed="shed, sum", tag="summer-trip")
        == "shed, summer-trip, "
    )
    assert complete_last_tag(typed="", tag="shed") == "shed, "


def test_tags_file_and_earlier_receipts(tmp_path: Path) -> None:
    (tmp_path / "tags.yaml").write_text(
        "summer-trip:\n  from: 2023-07-01\n  to: 2023-07-08\n",
        encoding="utf-8",
    )
    config = SimpleNamespace(
        dir_paths=SimpleNamespace(root_finance_path=str(tmp_path))
    )
    earlier = [SimpleNamespace(tags=["shed"]), SimpleNamespace(tags=None)]

    tags = ReceiptTags.for_receipt(
        config=config,
        labelled_receipts=earlier,
        prefilled_receipt=SimpleNamespace(tags=["sauna"]),
    )

    assert tags.tags == ["sauna"]
    assert [d.name for d in tags.definitions] == ["summer-trip"]
    assert tags.used == ["shed"]


def test_a_broken_tags_file_does_not_stop_the_labelling(tmp_path: Path) -> None:
    (tmp_path / "tags.yaml").write_text("- not a mapping\n", encoding="utf-8")
    config = SimpleNamespace(
        dir_paths=SimpleNamespace(root_finance_path=str(tmp_path))
    )

    tags = ReceiptTags.for_receipt(config=config, labelled_receipts=[])

    assert tags.definitions == [] and tags.tags == []


def _app() -> QuestionnaireApp:
    return QuestionnaireApp(
        header="Answer the receipt questions.",
        questions=[
            InputValidationQuestionData(
                question="Shop note:",
                question_id="note",
                input_type=InputType.NAME,
                ans_required=False,
                reconfigurer=False,
                terminator=False,
                ai_suggestions=[],
                history_suggestions=[],
            )
        ],
        labelled_receipts=[],
    )


def _screen(app: QuestionnaireApp) -> str:
    canvas = app.loop.widget.render(SIZE, focus=True)
    return "\n".join(row.decode("utf-8") for row in canvas.text)


def _editor_open(app: QuestionnaireApp) -> bool:
    widget = app.loop.widget
    return isinstance(widget, urwid.Overlay) and isinstance(
        widget.top_w, TagsEditor
    )


def _type(app: QuestionnaireApp, text: str) -> None:
    for key in text:
        app.loop.widget.keypress(SIZE, key)


def test_the_tags_are_shown_at_the_top_right() -> None:
    app = _app()
    _tags(tags=["shed"]).attach(tui=app)

    assert "Tags (Alt+t): shed" in "\n".join(_screen(app).splitlines()[:2])


def test_alt_t_without_tags_attached_passes_on() -> None:
    app = _app()

    assert app._filter_input(["meta t"], []) == ["meta t"]
    assert not _editor_open(app)


def test_type_complete_and_keep_tags() -> None:
    app = _app()
    tags = _tags()
    tags.attach(tui=app)

    assert app._filter_input(["meta t"], []) == []
    assert _editor_open(app)
    _type(app, "sh")
    app.loop.widget.keypress(SIZE, "tab")
    _type(app, "Sauna")
    app.loop.widget.keypress(SIZE, "enter")

    assert not _editor_open(app)
    assert tags.tags == ["shed", "sauna"]
    assert "Tags (Alt+t): shed, sauna" in _screen(app)


def test_esc_keeps_the_tags_as_they_were() -> None:
    app = _app()
    tags = _tags(tags=["shed"])
    tags.attach(tui=app)
    app._filter_input(["meta t"], [])

    _type(app, "sauna")
    app.loop.widget.keypress(SIZE, "esc")

    assert not _editor_open(app)
    assert tags.tags == ["shed"]


def test_receipt_day_reads_the_date_question() -> None:
    date_question = SimpleNamespace(
        question_data=SimpleNamespace(question_id="date"),
        get_answer=lambda: datetime(2023, 7, 3, 12, 30),
    )
    other = SimpleNamespace(question_data=SimpleNamespace(question_id="note"))

    assert receipt_day(inputs=[other, date_question]) == date(2023, 7, 3)
    assert receipt_day(inputs=[other]) is None
