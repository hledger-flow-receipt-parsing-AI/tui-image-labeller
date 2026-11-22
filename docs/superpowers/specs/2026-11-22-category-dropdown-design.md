# Category dropdown and new-category screen — design

Date: 2026-11-22. Branch: `category-dropdown` (on top of `visualisation-fix`).
Repo: `tui-image-labeller` only.

## Goal

Someone who has not labelled receipts for a while no longer remembers the
exact category names. Today the "Bookkeeping expense category:" question is a
free-text field that knows nothing about the categories file, so a typo or a
half-remembered name silently becomes a new category. A check of existing
labels confirmed this: a sizeable share of receipts carry a category that is
not in the categories file, often a near-duplicate of one that is.

After this change the user picks from the categories that exist, sees them
while typing, and can only create a new one deliberately, in a screen that
shows the whole tree.

## Current state

- `BaseQuestions.get_category_question()` builds a plain
  `InputValidationQuestionData`; `validate_category` accepts anything.
- Suggestions come only from the AI and the session history; the categories
  file (`config.category_namespace`) is not used by the question.
- The field's input type (`LETTERS_SEMICOLON`) rejects `_` and digits, which
  existing category names contain. Those categories cannot be typed, and
  restoring one after a questionnaire rebuild raises in `set_answer`.
- Categories with children are used as receipt categories too, so every node
  of the tree is a valid answer, not only leaves.

## Behaviour

### Dropdown on the category question

The list opens under the field whenever the field has focus. It is drawn over
the questions below; no question changes position.

```
Bookkeeping expense category: groc|
+--------------------------------------+
|   + new category...                  |
| > groceries                          |
|   groceries:ah                       |
|   groceries:ekoplaza                 |
+-- Up/Down Enter Tab Esc -- 3 of 120 -+
```

- Row 0 is always `+ new category...`. Below it: the matching categories.
- At most 8 rows are visible, row 0 included; the list scrolls with the
  highlight. If fewer rows fit between the field and the bottom of the
  screen, the list shrinks to what fits. The bottom border shows a key hint
  and `matches of total`.
- Matching is case-insensitive "contains". `*` splits the text into chunks
  that must occur in that order. Empty text matches everything.
- Order: exact match, then paths starting with the text, then paths with a
  segment starting with the text, then other matches; alphabetical within
  each group. `plumb` therefore finds `repairs:house:kitchen:plumbing`.
- The first match is highlighted after every text change. With no match,
  `+ new category...` is the only row and is highlighted.

Keys while the list is open:

| Key                 | Effect                                                           |
| ------------------- | ---------------------------------------------------------------- |
| typing, Backspace   | edit the text and refilter; `_` and digits are accepted          |
| Down / Up           | move the highlight; Up on row 0 goes to the previous question    |
| Enter               | category row: take it and continue. Row 0: open the new screen   |
| Tab                 | copy the highlighted category into the field, keep the list open |
| Esc                 | close the list; typing reopens it                                |
| Shift+Tab, Home/End | unchanged                                                        |

Rules:

- The field never accepts text that is not an existing category. With the
  list closed, Enter or Down on unknown text turns the field red and reopens
  the list.
- `meta u` / `ctrl u` (apply AI / history suggestion) still work, under the
  same rule.
- Leaving upward is always allowed. Finishing is not: "Done with this
  receipt?" is refused while the category is not in the categories file, with
  the existing "Answer required" mechanism. This also covers an old receipt
  that is reopened with an unknown category: the text stays visible, and the
  user picks or creates a category before finishing.
- The text cursor stays in the field, and the sidebar is unchanged.

### New-category screen

Opened by Enter on `+ new category...`. It replaces the questionnaire until
the user finishes or cancels; the questionnaire and its answers are untouched.

```
New category                 categories.yaml
--------------------------------------------
  + groceries
> - repairs
      + bike
      + car
  + restaurant
--------------------------------------------
Add under repairs: house:kitchen:plumbing|
  creates  repairs:house
           repairs:house:kitchen
           repairs:house:kitchen:plumbing
--------------------------------------------
Up/Down move   Right/Left open/close
n new child    Enter use this one   Esc back
```

Browsing:

- Collapsible tree of the categories file, children in alphabetical order,
  under a top-level row that stands for the root. All branches start closed
  except the path to the starting node.
- Up/Down, PageUp/PageDown, Home/End move. Right opens a branch, Left closes
  it or moves to the parent.
- Enter uses the highlighted category for the receipt (not on the root row).
- `n` starts adding a child under the highlighted node; on the root row it
  adds a top-level category.
- Esc returns to the questionnaire without changes, focus on the field.

Adding:

- The input accepts letters (lower-cased), digits, `_` and `:`. A `:` creates
  several levels at once.
- A live preview lists every node that will be created. Problems are shown
  instead: an empty segment, or "already exists" (Enter then uses it).
- Duplicate guard: if a new segment resembles a sibling, the screen says so
  and Enter must be pressed a second time to create it. "Resembles" means a
  `difflib` similarity ratio of at least 0.8 (`grocries` next to
  `groceries`), or one name being a prefix of the other (`transport` next to
  `transportation`). If the same name exists elsewhere in the tree, its path
  is shown as information only.
- Enter creates the nodes, saves the categories file, returns to the
  questionnaire with the new full path in the field, and continues to the
  next question. Esc leaves the input and returns to browsing.

Starting position: the deepest existing ancestor of the text typed in the
field (the root row if there is none). If the text is empty or an existing
category, the screen opens in browsing mode. Otherwise it opens in adding
mode with the remainder prefilled, lower-cased and without `*`, so typing
`repairs:house:kitchen:plumbing` when only `repairs` exists opens on
`repairs` with `house:kitchen:plumbing` ready.

### Saving the categories file

- Before writing, the file is read again and the new nodes are added to that
  fresh content, so edits made in an editor meanwhile are kept.
- The file is written in one canonical style: 2-space indent, `{}` for
  leaves, existing key order kept, new keys appended to their parent, keys
  that YAML would misread (`no`, `2024`) quoted. Hand formatting is
  normalised the first time; content does not change.
- The dump is parsed back and compared with the intended tree before
  anything is replaced. It is written to a temporary file in the same
  directory and moved over the original in one step.
- The in-memory `config.category_namespace` tree is updated in place, so the
  rest of the session (later receipts, AI category list) sees the new nodes.
- On any failure nothing is written, the in-memory tree is unchanged, and
  the new-category screen shows the error and stays open.

## Architecture

New code, all under `src/tui_labeller/`:

| Unit                                                 | Role                                                                                                                                               |
| ---------------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------- |
| `categories/category_store.py`                       | `CategoryStore`, no urwid. Paths, `exists`, `children`, `matches(text)`, `plan_addition(parent, text)` (preview, errors, look-alikes), `add(path)` |
| `categories/category_yaml.py`                        | canonical dump, verified atomic save                                                                                                               |
| `tuis/urwid/category_question/CategoryQuestion.py`   | `CategoryQuestion(InputValidationQuestion)`: text, matches, highlight, open/closed, all key handling                                               |
| `tuis/urwid/category_question/dropdown.py`           | the list view, its `PopUpLauncher`, and a display-only pop-up host                                                                                 |
| `tuis/urwid/category_question/CategoryTreeScreen.py` | the new-category screen, built on urwid's tree widgets; reports `use(path)` or `cancel`                                                            |

Changes to existing code:

- `InputType.CATEGORY`: letters, digits, `_`, `:`, `*`.
- `CategoryQuestionData(InputValidationQuestionData)` carries the
  `CategoryStore`. Question data objects survive questionnaire rebuilds, so
  the store does too.
- `BaseQuestions(ai_suggestions, category_store)`. Without a store (callers
  that only count questions or read captions, `eg.py`, mocks) the question
  stays the free-text field it is today.
- `build_receipt_from_urwid` builds the store from
  `config.category_namespace` and the configured categories path, and passes
  `base_questions` to `get_configuration`, so the withdrawal toggle re-adds
  the same category question instead of a bare `BaseQuestions()` one.
- `create_question_widget` builds the launcher-wrapped `CategoryQuestion`
  for `CategoryQuestionData`. `base_widget` still resolves to the question,
  so existing `isinstance(..., InputValidationQuestion)` checks keep working.
- `QuestionnaireApp`: wraps its top widget in the pop-up host; handles a new
  `"new_category"` key by swapping `loop.widget` to the tree screen and back;
  `first_unanswered_required` treats an unknown category as unanswered.

Why a display-only pop-up host: urwid's stock `PopUpTarget` sends every key
to the pop-up and renders the widgets beneath it without focus. The dropdown
is a view of the field's state, so the host only draws the pop-up; keys,
focus and cursor stay with the questionnaire. All logic then lives in
`CategoryQuestion.keypress`, which tests can drive without a main loop.

Data flow: keys reach `CategoryQuestion`, which updates its state from
`CategoryStore.matches` and returns a navigation key (`reconfigurer`,
`previous_question`, `new_category`) exactly like the other questions. The
launcher renders the list from that state. The tree screen talks only to
`CategoryStore` and reports back through two callbacks.

## Testing

- `CategoryStore` and the YAML writer: matching and ranking, addition
  preview, look-alike detection, canonical output, key quoting, merge with an
  external edit, a failed save leaving the file intact.
- `CategoryQuestion`, driven by `keypress` as in `test_default_replace.py`:
  filtering, default highlight, Enter on a match and on unknown text, Tab,
  Esc, Up on row 0, `_` and digits, `set_answer` with such a value.
- `CategoryTreeScreen`: add under a node, multi-level add, look-alike needing
  a second Enter, use an existing node, cancel, starting position and
  prefill.
- `QuestionnaireApp`: unknown category blocks termination; `new_category`
  swaps to the tree screen and back with the answer set.
- Rendering: render the app to a canvas at a fixed size with and without the
  list and assert that the list is drawn under the field, that every other
  question stays on the same row, and that the cursor is in the field.
- One real headless run of the labeller in a pseudo-terminal, and the
  existing `hledger-preprocessor` scenario runs for the receipt stories,
  which type a category from their own fixture and must still complete.

## Out of scope

- The per-item "Category (empty is: ...)" field and the CLI questionnaire.
- Correcting existing receipts whose category is not in the categories file.
- Changes to `hledger-core`; the store reads and updates the tree that
  `config.category_namespace` already holds.
- New demo GIFs. Receipt-labelling GIFs will show the dropdown the next time
  they are regenerated.
