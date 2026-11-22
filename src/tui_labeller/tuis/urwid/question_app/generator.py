from typing import List, Union

from hledger_core.TransactionObjects.Receipt import (
    Receipt,
)
from typeguard import typechecked

from tui_labeller.tuis.urwid.question_data_classes import (
    DateQuestionData,
    HorizontalMultipleChoiceQuestionData,
    InputValidationQuestionData,
    VerticalMultipleChoiceQuestionData,
)
from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp
from tui_labeller.tuis.urwid.receipts.currency_order import (
    sort_currency_choices,
)


# Manual generator
@typechecked
def create_questionnaire(
    header: str,
    questions: List[
        Union[
            DateQuestionData,
            InputValidationQuestionData,
            VerticalMultipleChoiceQuestionData,
            HorizontalMultipleChoiceQuestionData,
        ]
    ],
    labelled_receipts: List[Receipt],
) -> QuestionnaireApp:
    """Create and run a questionnaire with the given questions."""
    # Every questionnaire is built here, also after a reconfiguration adds
    # questions, so the currency answers are ordered the same way throughout:
    # the currency chosen most often in *labelled_receipts* first.
    sort_currency_choices(
        questions=questions, labelled_receipts=labelled_receipts
    )
    app = QuestionnaireApp(
        header=header, questions=questions, labelled_receipts=labelled_receipts
    )
    # write_to_file(filename="eg.txt", content="STARTED", append=False)
    return app
