# Python Repository Template

[![Python 3.12][python_badge]](https://www.python.org/downloads/release/python-3120/)
[![License: AGPL v3][agpl3_badge]](https://www.gnu.org/licenses/agpl-3.0)
[![Code Style: Black][black_badge]](https://github.com/ambv/black)

Example Python repository to quickly fork into new clean environment.

- typechecking
- pre-commit

## Usage

First install this pip package with:

```bash
pip install tui-labeller
```

Then run:

```sh
python -m tui_labeller
```

## Tests

```sh
python -m pytest
```

## UI specification

The user interface (UI) supports 3 types of questions:

- multiple choice questions (mc).
- questions with input validation (iv).
- questions that ask for a date (date).

### Autocomplete

There are two boxes with autocomplete suggestions:

- **AI Suggestions**: Provided as you type, filtered automatically based on input.
- **Past Input/History Suggestions**: Displays previous entries, also filtered by input.
  - Filtering uses patterns like `a*d` to match terms (e.g., `avocad(o)`).

#### date entries

You can apply AI suggestions with:

- `alt+u`: Applies the first remaining AI suggestion (if any).

#### input validation

you can apply AI or history suggestions (if any) with:

- `alt+u`: Applies the first remaining AI suggestion (if any).
- `ctrl+u`: Applies the first remaining past entry/history suggestion (if any).
- `tab`: Applies the only one remaining suggestion (either history or AI if only 1, in total, exists) (but not in date format) For:

#### multiple choice questions

The most probable AI answer is primary selected one. (The confidence probability is and model are displayed below the answer.)

### Navigation

One can navigate within question answer boxes, and amongst question answer boxes.

- Going **beyond the end** of a question moves to the next question.
- Going **before the start** of a question moves to the previous question.
- Going **beyond the last question** wraps to the start of the first question.
- Going **back from the first question** wraps to the end of the last question.

#### Navigation: Tab

To navigate between the types of questions the following keys can be used, which behave context dependent:
`tab`:

- **Input Validation**: Triggers autocomplete (see above) if a single autocomplete suggestion is left, goes to next question if multiple suggestions remain.
- **Date Questions - date only**: Moves to the next segment (`yyyy` → `mm` → `dd`)
  - At `dd`, moves to the next question.
- **Date Questions - date & time**: Moves to the next segment (`yyyy` → `mm` → `dd` → `hh`→ `mm`).
  - At `ss`, moves to the next question.
- **Multiple Choice**: Selects the next option and puts the cursor there.
  - At the last option, moves next question.

#### Navigation: Shift+Tab

## To navigate between the types of questions the following keys can be used, which behave context dependent: `tab`:

- **Input Validation**: `shift+tab` goes to the previous question.
- **Date Questions**: Moves to the previous segment (`yyyy` → `mm` → `dd`). At Y of `Yyyy`, moves to the previous question.
- **Multiple Choice**: Selects the previous option. At the first option, moves to the previous question.

#### Navigation: Enter

- `Enter`: Selects the current answer and moves to the next question. TODO: MC.
- `Shift+Enter`: (Shift is not detected when pressing enter with urwid.) Selects the current answer and moves to the previous question.

#### Navigation: Home, End

- `Home`: Moves the cursor to the start of the current question’s input field. If already at the start, moves to the first question in the form.
  - input validation: Done
  - date_question: Done
  - multiple choice: Done
- `End`: Moves the cursor to the end of the current question’s input field. If already at the end, moves to the last question in the form.
  - input validation: Done
  - date_question: Done
  - multiple choice: Done

#### Navigation: Up, Down

- **Multiple Choice**: `Up` moves to the previous question, `Down` to the next.

# TODO: Wraps from first to last (`Up`) or last to first (`Down`).

- **Input Validation**: `Up` moves to the previous question, `Down` to the next. Wraps similarly.
- For date questions: `Up` rolls the current digit/segment (e.g., `yyyy`, `mm`, `dd`) upward (increments), `Down` rolls it downward (decrements). Wrapping occurs at the segment’s valid range (e.g., 1-12 for `mm`).

#### Navigation: Left, Right

______________________________________________________________________

- **Multiple Choice**: `Left` selects the previous option, `Right` the next. At the first option, `Left` moves to the previous question; at the last, `Right` moves to the next.
- **Input Validation**: `Left` moves cursor left one character, `Right` moves right. At the start, `Left` moves to the previous question; at the end, `Right` moves to the next.
- **Date Questions**: `Left` moves cursor one digit left (e.g., `Yyyy` → `Yyy`), `Right` moves one digit right. At `Y` of `Yyyy`, `Left` moves to the previous question; at `D` of `dD`, `Right` moves to the next.

## Developer

```bash
conda env create --file environment.yml
conda activate tui-labeller

pre-commit install
pre-commit autoupdate
pre-commit run --all
```

## Publish pip package

Install the pip package locally with:

```bash
rm -r build
python -m build
pip install -e .
```

Upload the pip package to the world with:

```bash
rm -r build
python -m build
python3 -m twine upload dist/\*
```

## Sphinx documentation

To generate the documentation ensure the pip package is installed locally, such
that the documentation is able to import its Python files.

```bash
rm -r build
python -m build
pip install -e .
```

Then build the documentation with::

```sh
cd docs
make html
```

You can now see all your auto-generated Sphinx documentation in:
[docs/build/html/index.html](docs/build/html/index.html). This repository
auto-generates the Sphinx documentation for all your Python files using the
[/docs/source/conf.py](/docs/source/conf.py) file.

### Additional manual documentation

- The [docs/source/index.rst](docs/source/index.rst) is autogenerated and
  contains the main page and documentation file-structure.
- You can also add additional manual documentation in Markdown format as files in:

```
docs/source/manual_documenation/your_manual_documentation_filename.md
docs/source/manual_documenation/another_manual_documentation_filename.md
```

and then adding those filepaths into the `docs/source/manual.rst` file like:

```rst
Handwritten Documentation
=========================
.. toctree::
   :maxdepth: 2

   manual_documenation/your_manual_documentation_filename.md
   another_manual_documentation_filename.md
```

<!-- Un-wrapped URL's below (Mostly for Badges) -->

## Urwid colours

### 16 Standard Foreground Colors

'black'
'dark red'
'dark green'
'brown'
'dark blue'
'dark magenta'
'dark cyan'
'light gray'
'dark gray'
'light red'
'light green'
'yellow'
'light blue'
'light magenta'
'light cyan'
'white'

### 8 Standard Background Colors

'black'
'dark red'
'dark green'
'brown'
'dark blue'
'dark magenta'
'dark cyan'
'light gray'

[agpl3_badge]: https://img.shields.io/badge/License-AGPL_v3-blue.svg
[black_badge]: https://img.shields.io/badge/code%20style-black-000000.svg
[python_badge]: https://img.shields.io/badge/python-3.6-blue.svg
