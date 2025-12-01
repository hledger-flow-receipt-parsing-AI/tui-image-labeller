from typing import List, Union

from hledger_preprocessor.TransactionObjects.Receipt import (
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
    app = QuestionnaireApp(
        header=header, questions=questions, labelled_receipts=labelled_receipts
    )
    # write_to_file(filename="eg.txt", content="STARTED", append=False)
    return app
