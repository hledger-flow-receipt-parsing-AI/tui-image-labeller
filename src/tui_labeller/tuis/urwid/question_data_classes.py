from typing import Dict, List, Optional, Union

from hledger_core.AISuggestion import AISuggestion  # noqa: F401
from urwid import AttrMap

from tui_labeller.categories.category_store import CategoryStore
from tui_labeller.tuis.urwid.input_validation.InputType import InputType


class HistorySuggestion:
    def __init__(self, question: str, frequency: int):
        self.question: str = question
        self.frequency: int = frequency


class DateQuestionData:
    def __init__(
        self,
        question: str,
        date_only: bool,
        ai_suggestions: List[AISuggestion],
        ans_required: bool,
        reconfigurer: bool,
        terminator: bool,
        question_id: Optional[str] = None,
    ):
        self.question = question
        self.date_only = date_only
        self.ai_suggestions: List[AISuggestion] = ai_suggestions
        self.ans_required: bool = ans_required
        self.reconfigurer: bool = reconfigurer
        self.terminator: bool = terminator
        self.question_id: Union[None, str] = question_id


class InputValidationQuestionData:
    def __init__(
        self,
        question: str,
        input_type: InputType,
        ans_required: bool,
        reconfigurer: bool,
        terminator: bool,
        ai_suggestions: List[AISuggestion],
        history_suggestions: List[HistorySuggestion],
        default: Optional[str] = None,
        question_id: Optional[str] = None,
        custom_validator: Optional[callable] = None,
    ):
        self.question: str = question
        self.input_type = input_type
        self.ans_required: bool = ans_required
        self.reconfigurer: bool = reconfigurer
        self.terminator: bool = terminator
        self.ai_suggestions = ai_suggestions
        self.history_suggestions = history_suggestions
        self.default: str = default
        self.question_id: Union[None, str] = question_id
        self.custom_validator: Optional[callable] = custom_validator
        # Set once the user edits the field.  Lives on the question data (not
        # the widget) because the questionnaire is rebuilt on every
        # reconfiguration; a restored, never-edited default must stay
        # replaceable by the first keystroke.
        self.user_edited: bool = False


class CategoryQuestionData(InputValidationQuestionData):
    """The category question when the categories file is known: answers
    are picked from *category_store* instead of typed freely.

    The store rides on the question data because the questionnaire (and
    every widget) is rebuilt on each reconfiguration, while the question
    data objects are carried over.
    """

    def __init__(self, *, category_store: CategoryStore, **kwargs):
        super().__init__(**kwargs)
        self.category_store: CategoryStore = category_store


class VerticalMultipleChoiceQuestionData:
    def __init__(
        self,
        question: str,
        choices: List[str],
        nr_of_ans_per_batch: int,
        ans_required: bool,
        reconfigurer: bool,
        terminator: bool,
        ai_suggestions: List[AISuggestion],
        question_id: Optional[str] = None,
        navigation_display: Optional[AttrMap] = None,
        extra_data: Optional[Dict] = None,
    ):
        self.ans_required: bool = ans_required
        self.nr_of_ans_per_batch: int = nr_of_ans_per_batch
        self.reconfigurer: bool = reconfigurer
        self.terminator: bool = terminator
        self.question = question
        self.choices = choices
        self.ai_suggestions = ai_suggestions
        self.question_id: Union[None, str] = question_id
        self.navigation_display: Union[None, AttrMap] = navigation_display
        self.extra_data: Optional[Dict] = extra_data


class HorizontalMultipleChoiceQuestionData:
    def __init__(
        self,
        question: str,
        choices: List[str],
        ai_suggestions: List[AISuggestion],
        ans_required: bool,
        reconfigurer: bool,
        terminator: bool,
        question_id: Optional[str] = None,
    ):
        self.ans_required: bool = ans_required
        self.reconfigurer: bool = reconfigurer
        self.terminator: bool = terminator
        self.question = question
        self.choices = choices
        self.ai_suggestions = ai_suggestions
        self.question_id: Union[None, str] = question_id
