from __future__ import annotations

import contextlib
import logging
from copy import deepcopy
from datetime import datetime
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from hledger_receipt_processing.matching.ask_user_action import (
        ActionDataset,
    )

from hledger_config.config.AccountConfig import AccountConfig
from hledger_config.config.load_config import Config
from hledger_core.Currency import Currency
from hledger_core.generics.Transaction import Transaction
from hledger_core.TransactionObjects.Account import Account
from hledger_core.TransactionObjects.AccountTransaction import (
    AccountTransaction,
)
from hledger_core.TransactionObjects.Receipt import Receipt
from hledger_receipt_processing.receipt_transaction_matching.get_bank_data_from_transactions import (  # noqa: E501
    HledgerFlowAccountInfo,
)
from typeguard import typechecked
from urwid import AttrMap

from tui_labeller.categories.category_store import CategoryStore
from tui_labeller.tuis.urwid.ai_session import AiSession
from tui_labeller.tuis.urwid.date_question.DateTimeQuestion import (
    DateTimeQuestion,
)
from tui_labeller.tuis.urwid.input_validation.InputValidationQuestion import (
    InputValidationQuestion,
)
from tui_labeller.tuis.urwid.multiple_choice_question.HorizontalMultipleChoiceWidget import (  # noqa: E501
    HorizontalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.multiple_choice_question.VerticalMultipleChoiceWidget import (  # noqa: E501
    VerticalMultipleChoiceWidget,
)
from tui_labeller.tuis.urwid.prefill_receipt.pre_fill_receipt import (
    apply_prefilled_receipt,
)
from tui_labeller.tuis.urwid.question_app.generator import create_questionnaire
from tui_labeller.tuis.urwid.question_app.get_answers import (
    get_answers,
    get_answers_so_far,
    is_terminated,
)
from tui_labeller.tuis.urwid.question_app.reconfiguration.reconfiguration import (  # noqa: E501
    AMOUNT_PAID_QUESTION,
    BELONGS_TO_QUESTION,
    CHANGE_RETURNED_QUESTION,
    MATCH_CHOICE_QUESTION,
    get_configuration,
)
from tui_labeller.tuis.urwid.question_data_classes import AISuggestion
from tui_labeller.tuis.urwid.QuestionnaireApp import QuestionnaireApp
from tui_labeller.tuis.urwid.receipt_tags import ReceiptTags
from tui_labeller.tuis.urwid.receipts.AccountQuestions import AccountQuestions
from tui_labeller.tuis.urwid.receipts.BaseQuestions import (
    BaseQuestions,
)
from tui_labeller.tuis.urwid.receipts.create_receipt import (
    build_receipt_from_answers,
)
from tui_labeller.tuis.urwid.receipts.OptionalQuestions import OptionalQuestions
from tui_labeller.tuis.urwid.receipts.WithdrawalQuestions import (
    WithdrawalQuestions,
)
from tui_labeller.tuis.urwid.screen_session import (
    resume_screen,
    shared_screen,
    suspend_screen,
)
from tui_labeller.tuis.urwid.skip_receipt import (
    ReceiptSkipped,
    receipt_skipping,
)

logger = logging.getLogger(__name__)


def _wants_matching_cli(tui: QuestionnaireApp) -> bool:
    """Check if the user selected 'Enter matching CLI'."""
    for inp in tui.inputs:
        w = inp if not isinstance(inp, AttrMap) else inp.base_widget
        if (
            hasattr(w, "question_data")
            and w.question_data.question == MATCH_CHOICE_QUESTION
            and hasattr(w, "has_answer")
            and w.has_answer()
            and str(w.get_answer()) == "Enter matching CLI"
        ):
            return True
    return False


def _build_action_dataset(
    *,
    tui: QuestionnaireApp,
    config: Config,
    csv_transactions_per_account: dict[
        AccountConfig, dict[int, list[Transaction]]
    ],
    labelled_receipts: list[Receipt],
) -> ActionDataset:
    """Build an ActionDataset from the current TUI answers."""
    from hledger_receipt_processing.matching.ask_user_action import (
        ActionDataset,
    )

    receipt_date: datetime | None = None
    account_str: str | None = None
    amount_paid: float = 0.0
    change_returned: float = 0.0

    for inp in tui.inputs:
        w = inp.base_widget if isinstance(inp, AttrMap) else inp
        if not hasattr(w, "question_data"):
            continue
        q = w.question_data.question
        if q == "Receipt date and time:\n" and w.has_answer():
            receipt_date = w.get_answer()
        elif q == BELONGS_TO_QUESTION and w.has_answer():
            account_str = str(w.get_answer())
        elif q == AMOUNT_PAID_QUESTION and w.has_answer():
            try:
                amount_paid = float(w.get_answer())
            except (ValueError, TypeError):
                pass
        elif q == CHANGE_RETURNED_QUESTION and w.has_answer():
            try:
                change_returned = float(w.get_answer())
            except (ValueError, TypeError):
                pass

    if receipt_date is None:
        receipt_date = datetime.now()

    # Find matching Account from csv_transactions_per_account.
    account: Account | None = None
    for ac in csv_transactions_per_account:
        if ac.account.to_string() == account_str:
            account = ac.account
            break

    if account is None:
        # Fallback: build a minimal account.
        account = Account(
            base_currency=Currency.EUR,
            account_holder="unknown",
            bank="unknown",
            account_type="unknown",
        )

    search_txn = AccountTransaction(
        account=account,
        the_date=receipt_date,
        tendered_amount_out=amount_paid,
        change_returned=change_returned,
    )

    from hledger_core.TransactionObjects.ExchangedItem import ExchangedItem

    exchanged_item = ExchangedItem(
        quantity=1.0,
        description="stub",
        the_date=receipt_date,
        account_transactions=[search_txn],
    )

    stub_receipt = Receipt.__new__(Receipt)
    stub_receipt.the_date = receipt_date
    stub_receipt.net_bought_items = [exchanged_item]
    stub_receipt.net_returned_items = []
    return ActionDataset(
        receipt=stub_receipt,
        account=account,
        labelled_receipts=labelled_receipts,
        search_receipt_account_transaction=search_txn,
        config=deepcopy(config),
        csv_transactions_per_account=csv_transactions_per_account,
        ai_models_tnx_classification=[],
        rule_based_models_tnx_classification=[],
    )


class _ReceiptAbandoned(Exception):
    """The user confirmed "This receipt is not mine" in the matching CLI."""


def _not_mine_support() -> Any:
    """Hledger-receipt-processing's receipt_not_mine module, or None when an
    older hledger-receipt-processing without it is installed (the matching menu
    then stays as it was).

    That package owns the option: it shows it in the menu, moves the
    receipt's files to the training dataset and continues with the next
    receipt.  This TUI only asks, and hands over the answers typed so far.
    """
    try:
        from hledger_receipt_processing.receipts_to_objects import (
            receipt_not_mine,
        )
    except ImportError:
        return None
    return receipt_not_mine


def _run_matching_cli_loop(
    action_dataset: ActionDataset,
    *,
    raw_receipt_img_filepaths: list[str] | None = None,
) -> Config | None:
    """Run the matching CLI loop. Returns the (potentially widened) config, or
    None if the user chose to return to the TUI.

    With *raw_receipt_img_filepaths* the menu also offers "This receipt
    is not mine"; after an explicit yes it raises _ReceiptAbandoned.

    This function uses input() and print() — the urwid screen must be
    stopped before calling it.
    """
    from hledger_receipt_processing.matching.ask_user_action import (
        ActionValuePair,
        AlternateCurrencyWithdrawl,
        ReceiptMatchingAction,
        apply_action,
        get_receipt_action,
    )
    from hledger_receipt_processing.matching.manual_actions.alternate_currency_withdrawl import (  # noqa: E501
        add_estimated_conversion_ratio,
    )
    from hledger_receipt_processing.matching.manual_actions.widen_amount_range import (  # noqa: E501
        asked_widen_amount_range,
    )
    from hledger_receipt_processing.matching.manual_actions.widen_date_range import (  # noqa: E501
        asked_widen_date_range,
    )
    from hledger_receipt_processing.matching.searching.helper import (
        get_receipt_transaction_matches_in_csv_accounts,
    )

    not_mine = _not_mine_support() if raw_receipt_img_filepaths else None
    menu_options: dict[str, Any] = (
        {"allow_not_mine": True} if not_mine is not None else {}
    )

    while True:
        action: ReceiptMatchingAction = get_receipt_action(
            account=action_dataset.account,
            search_receipt_account_transaction=(
                action_dataset.search_receipt_account_transaction
            ),
            receipt=action_dataset.receipt,
            **menu_options,
        )

        if not_mine is not None and action == ReceiptMatchingAction.NOT_MINE:
            # Files are only moved after an explicit yes; a no keeps the
            # questionnaire and its answers.
            if not_mine.confirm_receipt_not_mine(
                config=action_dataset.config,
                raw_receipt_img_filepaths=raw_receipt_img_filepaths,
            ):
                raise _ReceiptAbandoned()
            print("\nNothing was moved.\n")
            continue

        if action == ReceiptMatchingAction.CHECK_RECEIPT:
            print(
                "\nReturning to receipt editor. Fix the receipt"
                " and try again.\n"
            )
            return None

        if action == ReceiptMatchingAction.CHECK_TRANSACTIONS:
            print("\nNot yet implemented. Returning to TUI.\n")
            return None

        # Build the action value.
        action_values: AlternateCurrencyWithdrawl | float | bool
        if action == ReceiptMatchingAction.ALTERNATE_CURRENCY_WITHDRAWL:
            from_currency, _, ratio = add_estimated_conversion_ratio(
                search_receipt_account_transaction=(
                    action_dataset.search_receipt_account_transaction
                ),
            )
            action_values = AlternateCurrencyWithdrawl(
                from_currency=from_currency,
                conversion_ratio_1_from_to=ratio,
            )
        elif action == ReceiptMatchingAction.WIDEN_DATE:
            action_values = asked_widen_date_range(
                config=action_dataset.config,
            )
        elif action == ReceiptMatchingAction.WIDEN_AMOUNT:
            action_values = asked_widen_amount_range()
        elif action == ReceiptMatchingAction.SWAP_DAY_AND_MONTH:
            from hledger_core.date_extractor import (  # noqa: E501
                can_swap_day_and_month,
                swap_month_day,
            )

            if can_swap_day_and_month(
                some_date=action_dataset.receipt.the_date
            ):
                action_values = swap_month_day(
                    some_date=action_dataset.receipt.the_date,
                )
            else:
                print("\nCannot swap day and month for this date.\n")
                continue
        else:
            print(f"\nUnsupported action: {action}\n")
            continue

        action_value_pair = ActionValuePair(
            action=action,
            values=action_values,
        )
        action_dataset = apply_action(
            action_dataset=action_dataset,
            action_value=action_value_pair,
        )

        # Re-check if we now have a match.
        try:
            matches = get_receipt_transaction_matches_in_csv_accounts(
                csv_transactions_per_account=(
                    action_dataset.csv_transactions_per_account
                ),
                action_dataset=action_dataset,
            )
        except Exception as exc:
            logger.warning("Re-match failed: %s", exc)
            matches = []

        if len(matches) == 1:
            print("\nFound unique match! Returning to TUI.\n")
            return action_dataset.config
        elif len(matches) == 0:
            print(
                f"\nStill no matches ({len(matches)} candidates)."
                " Try another action.\n"
            )
        else:
            print(
                f"\nFound {len(matches)} candidates"
                " (ambiguous). Try narrowing.\n"
            )


def _clear_matching_cli_answer(tui: QuestionnaireApp) -> None:
    """Reset the match choice widget answer so it doesn't re-trigger."""
    for inp in tui.inputs:
        w = inp if not isinstance(inp, AttrMap) else inp.base_widget
        if (
            hasattr(w, "question_data")
            and w.question_data.question == MATCH_CHOICE_QUESTION
            and hasattr(w, "clear_answer")
        ):
            w.clear_answer()


def _log_ai_corrections(
    config: Config,
    ai_suggestions: dict[str, list[AISuggestion]],
    final_answers: list,
    image_path: str | None = None,
) -> None:
    """Log user corrections to AI suggestions for feedback learning."""
    if not ai_suggestions:
        return
    try:
        from hledger_ai.feedback.correction_logger import CorrectionLogger

        feedback_dir = (
            config.ai.feedback_dir if config.ai else "~/.hledger-ai/feedback"
        )
        cl = CorrectionLogger(feedback_dir=feedback_dir)
        user_answers: dict[str, str] = {}
        for widget, answer in final_answers:
            qid = getattr(
                getattr(widget, "question_data", None),
                "question_id",
                None,
            )
            if qid is None:
                # Fallback: use the question text as key.
                qid = getattr(
                    getattr(widget, "question_data", None),
                    "question",
                    None,
                )
            if qid is not None:
                user_answers[qid] = str(answer)

        cl.log_receipt_corrections(
            ai_suggestions=ai_suggestions,
            user_answers=user_answers,
            image_path=image_path,
        )
    except ImportError:
        pass
    except Exception:
        logger.debug("Failed to log AI corrections", exc_info=True)


def _flatten_category_hierarchy(d: dict, prefix: str = "") -> list[str]:
    """Flatten a nested category dict into colon-separated paths."""
    paths: list[str] = []
    for k, v in d.items():
        path = f"{prefix}:{k}" if prefix else k
        paths.append(path)
        if isinstance(v, dict) and v:
            paths.extend(_flatten_category_hierarchy(v, path))
    return paths


@typechecked
def build_category_store(*, config: Any) -> CategoryStore | None:
    """The categories the category question offers, or None when the config
    carries no category tree (the question then stays a free-text field).

    The store shares the tree held by ``config.category_namespace`` (the
    ``_hierarchy`` of hledger-core's CategoryNamespace), so a category
    created while labelling is known to the rest of the run at once, and it
    saves to the configured categories file.
    """
    namespace = getattr(config, "category_namespace", None)
    hierarchy = getattr(namespace, "_hierarchy", None)
    if not isinstance(hierarchy, dict):
        return None
    yaml_path: str | None = None
    file_names = getattr(config, "file_names", None)
    dir_paths = getattr(config, "dir_paths", None)
    if file_names is not None and dir_paths is not None:
        yaml_path = file_names.get_filepath(
            dir_path_config=dir_paths, filename="categories_filename"
        )
    return CategoryStore(hierarchy=hierarchy, yaml_path=yaml_path)


@typechecked
def _open_ai_session(
    *, config: Config, image_paths: list[str], highlighter: Any = None
) -> AiSession | None:
    """Suggestions from the locally trained models of hledger-ai for this
    receipt (``hledger_ai.labeller``); *highlighter* draws their evidence on
    the receipt photo (see ai_session).

    None when hledger-ai is not installed, nothing is trained yet
    (``--train``), or ``--skip-ai`` was given.
    """
    if getattr(config, "_skip_ai", False):
        logger.info("AI suggestions skipped (--skip-ai)")
        return None
    try:
        from hledger_ai.labeller import LabellerSuggester
    except ImportError:
        logger.debug("hledger-ai not installed; skipping AI suggestions")
        return None
    try:
        suggester = LabellerSuggester.open(
            config=config, raw_image_paths=image_paths
        )
    except Exception:
        logger.exception("Opening the AI suggester failed")
        return None
    if suggester is None:
        return None
    return AiSession(suggester=suggester, highlighter=highlighter)


def _get_ai_suggestions(
    config: Config,
    image_path: str,
) -> dict[str, list[AISuggestion]]:
    """Run the Ollama extraction pipeline and return suggestions for the TUI
    (used while no locally trained model exists, see _open_ai_session).

    Returns an empty dict if hledger-ai is not installed or Ollama is
    unavailable.  Works with or without an explicit ``ai:`` section in
    the config (uses defaults when absent).
    """
    if getattr(config, "_skip_ai", False):
        logger.info("AI suggestions skipped (--skip-ai)")
        return {}

    try:
        from hledger_ai.ai_receipt_suggester import AIReceiptSuggester
        from hledger_ai.get_models import build_extraction_pipeline
        from hledger_ai.ollama_client import OllamaClient

        ai = config.ai
        if not OllamaClient(
            base_url=ai.ollama_url if ai else "http://localhost:11434"
        ).is_available():
            logger.debug("Ollama is not running; skipping its suggestions")
            return {}

        # Extract flat category list from config for the LLM classifier.
        category_tree: list[str] = []
        ns = getattr(config, "category_namespace", None)
        if ns is not None:
            hierarchy = getattr(ns, "_hierarchy", None)
            if isinstance(hierarchy, dict):
                category_tree = _flatten_category_hierarchy(hierarchy)

        pipeline = build_extraction_pipeline(
            ollama_url=ai.ollama_url if ai else "http://localhost:11434",
            vlm_model=ai.vlm_model if ai else "qwen3-vl:2b",
            text_model=ai.text_model if ai else "qwen3:0.6b",
            category_tree=category_tree,
        )
        suggester = AIReceiptSuggester(pipeline=pipeline)
        return suggester.suggest(image_path=image_path)
    except ImportError:
        logger.debug("hledger-ai not installed; skipping AI suggestions")
        return {}
    except Exception:
        logger.exception("AI suggestion pipeline failed")
        return {}


@typechecked
def build_receipt_from_urwid(
    *,
    config: Config,
    raw_receipt_img_filepaths: list[str],
    hledger_account_infos: set[HledgerFlowAccountInfo],
    accounts_without_csv: set[str],
    labelled_receipts: list[Receipt],
    prefilled_receipt: Receipt | None,
    csv_transactions_per_account: None | (
        dict[AccountConfig, dict[int, list[Transaction]]]
    ) = None,
    # Draws the evidence of the AI suggestions on the receipt photo (the
    # receipt window of hledger-receipt-processing); None: no boxes.
    highlighter: Any = None,
    # Offer to skip this receipt for now (Alt+s, the button at the top
    # right): the labelling loop, which then goes on with the next one.
    allow_skip: bool = False,
) -> Receipt:
    """Label one receipt in the TUI.

    Its questionnaires (one per reconfiguration) share one terminal
    screen, so the TUI stays on screen between questions.

    Raises skip_receipt.ReceiptSkipped when the user skipped the receipt
    (only with *allow_skip*).
    """
    skipping = receipt_skipping() if allow_skip else contextlib.nullcontext()
    with shared_screen(), skipping:
        return _build_receipt_from_urwid(
            config=config,
            raw_receipt_img_filepaths=raw_receipt_img_filepaths,
            hledger_account_infos=hledger_account_infos,
            accounts_without_csv=accounts_without_csv,
            labelled_receipts=labelled_receipts,
            prefilled_receipt=prefilled_receipt,
            csv_transactions_per_account=csv_transactions_per_account,
            highlighter=highlighter,
        )


@typechecked
def _build_receipt_from_urwid(
    *,
    config: Config,
    raw_receipt_img_filepaths: list[str],
    hledger_account_infos: set[HledgerFlowAccountInfo],
    accounts_without_csv: set[str],
    labelled_receipts: list[Receipt],
    prefilled_receipt: Receipt | None,
    csv_transactions_per_account: None | (
        dict[AccountConfig, dict[int, list[Transaction]]]
    ) = None,
    highlighter: Any = None,
) -> Receipt:
    import time as _time

    _t0 = _time.monotonic()

    # Suggestions from the locally trained models; the Ollama pipeline is
    # the fallback while nothing is trained yet.
    ai_suggestions: dict[str, list[AISuggestion]] = {}
    ai_session: AiSession | None = None
    if raw_receipt_img_filepaths:
        ai_session = _open_ai_session(
            config=config,
            image_paths=raw_receipt_img_filepaths,
            highlighter=highlighter,
        )
        if ai_session is not None:
            ai_suggestions = ai_session.initial()
        else:
            ai_suggestions = _get_ai_suggestions(
                config=config,
                image_path=raw_receipt_img_filepaths[0],
            )

    _t1 = _time.monotonic()
    print(f"  [timing] AI suggestions: {_t1 - _t0:.1f}s")

    account_infos_str: list[str] = list(
        {x.to_colon_separated_string() for x in hledger_account_infos}
    )
    account_questions = AccountQuestions(
        account_infos_str=account_infos_str,
        accounts_without_csv=accounts_without_csv,
        ai_suggestions=ai_suggestions,
    )
    withdrawal_questions = WithdrawalQuestions(
        account_infos_str=account_infos_str,
        accounts_without_csv=accounts_without_csv,
    )
    base_questions = BaseQuestions(
        ai_suggestions=ai_suggestions,
        category_store=build_category_store(config=config),
    )
    optional_questions = OptionalQuestions(
        labelled_receipts=labelled_receipts,
        ai_suggestions=ai_suggestions,
    )

    tui: QuestionnaireApp = create_questionnaire(
        questions=base_questions.base_questions
        + account_questions.account_questions
        + optional_questions.optional_questions,
        header="Answer the receipt questions.",
        labelled_receipts=labelled_receipts,
    )

    tui: QuestionnaireApp = apply_prefilled_receipt(
        config=config,
        tui=tui,
        prefilled_receipt=prefilled_receipt,
        account_infos_str=account_infos_str,
        accounts_without_csv=accounts_without_csv,
    )

    # Events and projects of this receipt (Alt+t); kept over rebuilds.
    receipt_tags = ReceiptTags.for_receipt(
        config=config,
        labelled_receipts=labelled_receipts,
        prefilled_receipt=prefilled_receipt,
    )

    _t2 = _time.monotonic()
    print(f"  [timing] question setup: {_t2 - _t1:.1f}s")

    # Run reconfiguration before the first render so prefilled answers
    # (e.g. withdrawal toggle = "y") inject their dependent questions.
    tui = get_configuration(
        tui=tui,
        account_questions=account_questions,
        optional_questions=optional_questions,
        labelled_receipts=labelled_receipts,
        withdrawal_questions=withdrawal_questions,
        config=config,
        csv_transactions_per_account=csv_transactions_per_account,
        prefilled_receipt=prefilled_receipt,
        base_questions=base_questions,
    )

    _t3 = _time.monotonic()
    print(f"  [timing] get_configuration: {_t3 - _t2:.1f}s")
    print(f"  [timing] total before tui.run(): {_t3 - _t0:.1f}s")

    if ai_session is not None:
        ai_session.attach(tui=tui)
    receipt_tags.attach(tui=tui)
    tui.run()  # Start the first run.
    while True:
        if tui.skip_requested:
            # Alt+s (or the Skip button) and a yes in the red dialog: no
            # label for this receipt; the labelling loop goes on with the
            # next one.
            raise ReceiptSkipped()
        if is_terminated(inputs=tui.inputs):
            final_answers: list[
                tuple[
                    (
                        DateTimeQuestion
                        | InputValidationQuestion
                        | VerticalMultipleChoiceWidget
                        | HorizontalMultipleChoiceWidget
                    ),
                    str | float | int | datetime,
                ]
            ] = get_answers(inputs=tui.inputs)

            # Log corrections where user overrode AI suggestions.
            if ai_session is not None:
                ai_session.finish(tui=tui)
            else:
                _log_ai_corrections(
                    config=config,
                    ai_suggestions=ai_suggestions,
                    final_answers=final_answers,
                    image_path=(
                        raw_receipt_img_filepaths[0]
                        if raw_receipt_img_filepaths
                        else None
                    ),
                )

            return build_receipt_from_answers(
                config=config,
                raw_receipt_img_filepaths=raw_receipt_img_filepaths,
                final_answers=final_answers,
                verbose=True,
                hledger_account_infos=hledger_account_infos,
                accounts_without_csv=accounts_without_csv,
                tags=receipt_tags.tags,
            )

        elif csv_transactions_per_account is not None and _wants_matching_cli(
            tui
        ):
            # Suspend urwid to run the matching CLI via input().
            suspend_screen(screen=tui.loop.screen)

            abandoned = False
            try:
                action_dataset = _build_action_dataset(
                    tui=tui,
                    config=config,
                    csv_transactions_per_account=(csv_transactions_per_account),
                    labelled_receipts=labelled_receipts,
                )
                updated_config = _run_matching_cli_loop(
                    action_dataset,
                    raw_receipt_img_filepaths=raw_receipt_img_filepaths,
                )
                if updated_config is not None:
                    config = updated_config
            except _ReceiptAbandoned:
                abandoned = True
            except KeyboardInterrupt:
                print("\nMatching CLI interrupted. Returning to TUI.")
            finally:
                if not abandoned:
                    # Resume urwid.
                    resume_screen(screen=tui.loop.screen)

            if abandoned:
                # "This receipt is not mine": leave the questionnaire for
                # good (the screen stays stopped) and hand the answers typed
                # so far to the labelling loop in hledger-receipt-processing,
                # which moves the receipt to the training dataset.
                raise _not_mine_support().ReceiptNotMine(
                    partial_answers=get_answers_so_far(inputs=tui.inputs)
                )

            # Clear the choice answer so it does not re-trigger.
            _clear_matching_cli_answer(tui)

            current_position: int = tui.get_focus()
            if ai_session is not None:
                ai_session.confirm_focused(tui=tui)
            tui = get_configuration(
                tui=tui,
                account_questions=account_questions,
                optional_questions=optional_questions,
                labelled_receipts=labelled_receipts,
                withdrawal_questions=withdrawal_questions,
                config=config,
                csv_transactions_per_account=csv_transactions_per_account,
                prefilled_receipt=prefilled_receipt,
                base_questions=base_questions,
            )

            # Update the pile based on the reconfiguration.
            pile_contents = [(tui.header_widget, ("pack", None))]
            for some_widget in tui.inputs:
                pile_contents.append((some_widget, ("pack", None)))
            tui.pile.contents = pile_contents
            if ai_session is not None:
                ai_session.attach(tui=tui)
            receipt_tags.attach(tui=tui)

            # Resume at the first unanswered required question (normally the
            # address selector).  "current position + 1" skipped it, which
            # left it unanswered and crashed get_answers() on termination.
            tui.run_from_question(
                question_index=tui.first_unanswered_required(
                    default=current_position
                )
            )

        else:
            current_position: int = tui.get_focus()
            if ai_session is not None:
                # The answer that triggered this reconfiguration (category,
                # account, ...) re-ranks the suggestions further down.
                ai_session.confirm_focused(tui=tui)
            tui = get_configuration(
                tui=tui,
                account_questions=account_questions,
                optional_questions=optional_questions,
                labelled_receipts=labelled_receipts,
                withdrawal_questions=withdrawal_questions,
                config=config,
                csv_transactions_per_account=csv_transactions_per_account,
                prefilled_receipt=prefilled_receipt,
                base_questions=base_questions,
            )

            # Update the pile based on the reconfiguration.
            pile_contents = [(tui.header_widget, ("pack", None))]
            for some_widget in tui.inputs:
                pile_contents.append((some_widget, ("pack", None)))
            tui.pile.contents = pile_contents
            if ai_session is not None:
                ai_session.attach(tui=tui)
            receipt_tags.attach(tui=tui)

            tui.run(alternative_start_pos=current_position + tui.nr_of_headers)
