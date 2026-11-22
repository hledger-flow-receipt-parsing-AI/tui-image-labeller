# Category Dropdown Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** The "Bookkeeping expense category:" question offers the categories of the categories file in a dropdown drawn over the questions below, and new categories can only be created deliberately in a tree screen that saves them to the categories file.

**Architecture:** A urwid-free `CategoryStore` owns the tree (matching, addition preview, verified atomic save). `CategoryQuestion`, a subclass of `InputValidationQuestion`, owns the field state and all keys, and attaches a pop-up to its own canvas. `QuestionnaireApp` wraps its top widget in a display-only pop-up host, so the list is drawn while keys, focus and cursor stay with the field, and swaps `loop.widget` to `CategoryTreeScreen` for creating a category.

**Tech Stack:** Python 3.12 (conda env `hledger_preprocessor`), urwid 4.0.3, PyYAML, pytest, pexpect + pyte for the real-terminal check.

## Global Constraints

- Spec: `docs/superpowers/specs/2026-11-22-category-dropdown-design.md`.
- Repo `tui-image-labeller` only, branch `category-dropdown`.
- Functions: `@typechecked`, keyword-only (`*,`) unless `self` first, return annotations (project convention).
- No real finance data in committed files or tests: examples use `groceries:ekoplaza`, `repairs:bike` and similar.
- Tests never touch a real categories file; file tests use `tmp_path`.
- Question ids and captions do not change (`category`, `"\nBookkeeping expense category:"`): the scenario harness in `hledger-preprocessor` keys on them.
- The question widget stays the direct child of its `AttrMap`: `prefill_receipt` reaches it through `AttrMap._original_widget`.
- Run tests with `PATH=/home/a/miniconda3/envs/hledger_preprocessor/bin:$PATH python -m pytest test -q --ignore=test/urwid/test_receipt_from_urwid.py`. Ten failures predate this work (`test_input_validation.py` x8, `test_receipt_cli.py`, `test_prefill_receipt.py`); no other test may fail.

______________________________________________________________________

### Task 1: category tree store and YAML writer

**Files:** Create `src/tui_labeller/categories/__init__.py`, `categories/category_yaml.py`, `categories/category_store.py`. Test: `test/categories/__init__.py`, `test/categories/test_category_yaml.py`, `test/categories/test_category_store.py`.

**Produces:**

- `category_yaml`: `CategorySaveError(Exception)`; `normalise_hierarchy(*, hierarchy: Dict[Any, Any]) -> Dict[Any, Any]` (every leaf becomes `{}`); `dump_categories(*, hierarchy) -> str`; `load_categories(*, yaml_path: str) -> Dict[Any, Any]`; `save_categories(*, yaml_path: str, hierarchy) -> None`.

- `category_store`: `AdditionPlan` (frozen dataclass: `parent: str`, `full_path: str`, `created: Tuple[str, ...]`, `error: Optional[str]`, `already_exists: bool`, `look_alikes: Tuple[str, ...]`, `same_name_elsewhere: Tuple[str, ...]`); `CategoryStore(*, hierarchy: Dict[Any, Any], yaml_path: Optional[str] = None)` with `paths() -> List[str]`, `exists(*, path: str) -> bool`, `children(*, path: str) -> List[str]` (`""` is the root), `matches(*, text: str) -> List[str]`, `deepest_existing_ancestor(*, path: str) -> Tuple[str, str]`, `plan_addition(*, parent: str, text: str) -> AdditionPlan`, `add(*, path: str) -> List[str]`.

- [ ] Tests, YAML: dump of `{"a": {"b": {}, "c": None}, "d": {}}` is `"a:\n  b: {}\n  c: {}\nd: {}\n"`; keys `no` and `2024` (strings) survive dump then `yaml.safe_load`; key order is kept; `save_categories` on a hand-formatted file (`"a :  {}\n\nb:\n    c: {}\n"`) leaves a file that loads to the same tree and equals `dump_categories`; no temporary file remains; when `os.replace` is patched to raise, the original file is byte-identical and no temporary file remains.

- [ ] Tests, store: `paths()` lists every node including parents; `exists` is case-insensitive and false for `""`; `matches("groc")` orders exact, then path prefix, then segment prefix, then contains (`plumb` finds `repairs:house:kitchen:plumbing`); `*` chunks must occur in order; empty text returns all paths; `deepest_existing_ancestor("repairs:house:kitchen")` is `("repairs", "house:kitchen")` when only `repairs` exists, `("", "x:y")` when nothing exists.

- [ ] Tests, addition: `plan_addition(parent="repairs", text="house:kitchen")` lists both created paths; errors for empty text, empty segment (`a::b`), bad characters (`a-b`), unknown parent; `already_exists` for an existing path; `look_alikes` for `grocries` next to `groceries` and `transport` next to `transportation`, none for `bike` next to `car`; `same_name_elsewhere` reports `groceries:ah` when adding `restaurant:ah`.

- [ ] Tests, add: with `yaml_path=None` the dict passed in is mutated in place; with a file, the file gains the nodes, the dict passed in is updated in place, and a node added to the file by "an editor" after the store was built is still there afterwards; a failing save raises and leaves both file and dict unchanged.

- [ ] Run the tests to see them fail, implement, run to green, commit.

### Task 2: input type, question data, base questions

**Files:** Modify `tuis/urwid/input_validation/InputType.py`, `input_validation/InputValidationQuestion.py`, `tuis/urwid/question_data_classes.py`, `receipts/BaseQuestions.py`, `prefill_receipt/pre_fill_receipt.py`. Test: `test/urwid/test_category_question_data.py`.

**Consumes:** `CategoryStore`.

**Produces:** `InputType.CATEGORY` (letters, digits, `_`, `:`, `*`; a string type in `get_answer` / `set_answer`); `CategoryQuestionData(InputValidationQuestionData)` with one extra keyword `category_store: CategoryStore`; `BaseQuestions(ai_suggestions=None, category_store=None)`, whose `get_category_question()` returns a `CategoryQuestionData` when a store is given and the plain `InputValidationQuestionData` otherwise, both with `InputType.CATEGORY`.

- [ ] Tests: a plain `InputValidationQuestion` with `InputType.CATEGORY` accepts `bicycle_parts`, `a1:b_2` via `set_answer` and keypresses, rejects `-` and space; `BaseQuestions().get_category_question()` is not a `CategoryQuestionData` and keeps id `category` and its caption; `BaseQuestions(category_store=store).get_category_question()` is one and carries the store; `test_question_ids.py` still passes.
- [ ] Implement (also switch the `receipt_category` entry of `set_receipt_details` to `InputType.CATEGORY`), run, commit.

### Task 3: dropdown view and category question

**Files:** Create `tuis/urwid/category_question/__init__.py`, `category_question/dropdown.py`, `category_question/CategoryQuestion.py`. Modify `question_app/palette.py`, `question_app/create_widgets.py`. Test: `test/urwid/test_category_dropdown.py`, `test/urwid/test_category_question.py`.

**Consumes:** `CategoryStore`, `CategoryQuestionData`.

**Produces:**

- `dropdown`: `NEW_ROW_LABEL = "+ new category..."`; `MAX_VISIBLE_ROWS = 8`; `dropdown_size(*, matches: List[str], maxcol: int) -> Tuple[int, int]` (width, height); `dropdown_lines(*, matches: List[str], highlight: int, total: int, width: int, height: int) -> List[Tuple[str, str]]` (attribute and text per row, exactly `height` rows of `width` characters, row 0 pinned, the window of matches follows the highlight); `CategoryDropdown(urwid.Widget)` box widget rendering those lines; `DisplayOnlyPopUpTarget(urwid.PopUpTarget)`.

- `CategoryQuestion(InputValidationQuestion)`: attributes `store`, `matches: List[str]`, `highlight: int` (0 is the new row, `i` is `matches[i - 1]`), `dropdown_open: bool`; `NEW_CATEGORY_KEY = "new_category"`; `is_known_category() -> bool`; `accept_category(*, path: str) -> Optional[str]`; `keypress` returns `None`, `"reconfigurer"` / `"next_question"`, `"previous_question"` or `NEW_CATEGORY_KEY`.

- Palette entries `dropdown`, `dropdown_selected`.

- `create_question_widget` builds `AttrMap(CategoryQuestion)` for `CategoryQuestionData`.

- [ ] Tests, lines: every line has the requested width; row 0 text contains `+ new category...`; the highlighted row carries `dropdown_selected`; with 20 matches and height 11 the highlighted match 15 is visible and row 0 still is; the bottom line contains `3 of 120` for 3 matches of 120; a small height (4) still yields exactly 4 lines.

- [ ] Tests, question (driven by `keypress`, widget built through `create_question_widget`): typing `groc` filters and highlights the first match; Enter returns `"reconfigurer"` and the text is the full path; typing an unknown text leaves only the new row and Enter returns `NEW_CATEGORY_KEY`; Down / Up move the highlight, Up on row 0 returns `"previous_question"`; Tab copies the highlighted path and keeps the list open; Esc closes, a typed character reopens; with the list closed Enter on unknown text returns `None`, paints the owner `error` and reopens; `_`, digits typeable; `*` filters without replacing the text; `set_answer("groceries:ah:zz")` (unknown) keeps the text, `has_answer()` is true, `is_known_category()` is false; an exact match typed in upper case is accepted and stored lower-case.

- [ ] Tests, pop-up host: a `Pile` of edits with a focused `CategoryQuestion` rendered through `DisplayOnlyPopUpTarget` at `(80, 20)` shows the box directly under the field; every row outside the box equals the render with the list closed; `get_cursor_coords` is unchanged; a key sent to the host reaches the field; an unfocused question shows no box; with only 4 rows of space below the field the box is 4 rows high.

- [ ] Implement, run, commit.

### Task 4: new-category screen

**Files:** Create `tuis/urwid/category_question/CategoryTreeScreen.py`. Modify `question_app/palette.py` (entry `tree_cursor`). Test: `test/urwid/test_category_tree_screen.py`.

**Consumes:** `CategoryStore`, `AdditionPlan`.

**Produces:** `TreeRow` (frozen dataclass: `path`, `depth`, `has_children`, `expanded`); `visible_tree_rows(*, store: CategoryStore, expanded: Set[str]) -> List[TreeRow]` (first row is the root, path `""`); `CategoryTreeScreen(*, store, typed_text: str, on_use: Callable[[str], None], on_cancel: Callable[[], None])`, a box widget with attributes `cursor_path: str`, `expanded: Set[str]`, `adding: bool`, `confirm_pending: bool`, `status: str`, `input: urwid.Edit`.

- [ ] Tests, rows: only the root and top-level nodes are visible when nothing is expanded; children are alphabetical; expanding `repairs` shows its children at depth 2.
- [ ] Tests, start: `typed_text=""` gives browsing on the root; `"repairs"` (existing) gives browsing on `repairs`, expanded; `"repairs:house:kitchen"` gives adding on `repairs` with input `house:kitchen`; `"Gro*C"` gives adding on the root with input `groc`.
- [ ] Tests, browsing keys: Down / Up / Home / End move; Right expands then enters the first child; Left collapses then moves to the parent; Enter on a category calls `on_use(path)`, on the root does nothing; Esc calls `on_cancel`; `n` starts adding under the cursor.
- [ ] Tests, adding keys: typing builds the input (upper case is lowered, `-` is ignored); Enter creates, the store has the nodes, `on_use` gets the full path; an existing path calls `on_use` without adding; a look-alike needs a second Enter and editing the text resets the confirmation; an error text does nothing on Enter; Esc returns to browsing; a store whose `add` raises sets `status`, does not call `on_use`, and the screen still renders.
- [ ] Test, render: `screen.render((80, 24), focus=True)` contains the title, the cursor row text, the preview lines `creates` and the legend.
- [ ] Implement, run, commit.

### Task 5: wiring

**Files:** Modify `tuis/urwid/QuestionnaireApp.py`, `tuis/urwid/ask_urwid_receipt.py`, `question_app/reconfiguration/reconfiguration.py`. Test: `test/urwid/test_category_wiring.py`.

**Consumes:** everything above.

**Produces:** `QuestionnaireApp.popup_host`; `QuestionnaireApp._handle_input(NEW_CATEGORY_KEY)` opens the tree screen; `first_unanswered_required` reports an unknown category; `get_configuration(..., base_questions: Optional[BaseQuestions] = None)` and `handle_withdrawal_toggle(..., base_questions: Optional[BaseQuestions] = None)`; `build_category_store(*, config: Any) -> Optional[CategoryStore]` in `ask_urwid_receipt.py`.

- [ ] Tests: an app with a category question whose text is unknown refuses `"terminator"`, focuses the category question and names it in the error panel; `_handle_input(NEW_CATEGORY_KEY)` sets `loop.widget` to a `CategoryTreeScreen`; its `on_cancel` restores `popup_host`; its `on_use("repairs:bike")` restores `popup_host`, sets the field and raises `urwid.ExitMainLoop` (the question is a reconfigurer); `handle_withdrawal_toggle` with answer `n` re-adds a `CategoryQuestionData` carrying the same store; `build_category_store` returns `None` for a config without a namespace and a store sharing the namespace's dict otherwise; rendering the whole app at `(120, 40)` with the category question focused shows the box and leaves the rows of all other questions and the sidebar unchanged.
- [ ] Implement, run the whole suite, commit.

### Task 6: real-terminal verification

**Files:** none in `src`; a throwaway driver in the session scratchpad.

- [ ] Drive the real labeller questionnaire in a pseudo-terminal (pexpect, screen read back with pyte) against a temporary categories file: the list appears under the field after typing, the questions below keep their rows, Enter takes the highlighted row, `+ new category...` opens the tree screen, creating a category writes the temporary file and returns to the questionnaire with the field filled.
- [ ] Run the `hledger-preprocessor` scenario tests that drive the real TUI (`test/scenarios`), which type a category from their own fixture; they must pass as before.
- [ ] Record what was run and what was seen; fix anything found, with a regression test in the task it belongs to.
