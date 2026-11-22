# "This receipt is not mine" — design

Date: 2026-11-22. Repos: `hledger-receipt-processing` (branch
`receipt-not-mine`, on top of `receipt-image-windows`) and
`tui-image-labeller` (branch `category-dropdown`).

## Goal

While labelling, a photographed receipt sometimes turns out to belong to
someone else. It has no matching bank transaction, so the user ends up in the
"No matches found" menu with no way out except finishing a label that does
not belong in the bookkeeping. The menu gets a sixth option that takes the
receipt out of the bookkeeping folders and keeps it as AI training data.

## Behaviour

- The labelling menu lists `6. This receipt is not mine (move it to the training dataset)`. The unlisted swap-day-and-month action moves from 6
  to 7. The same menu in the later matching stage is unchanged.
- Choosing 6 lists the files and asks `(y/N)`. Anything but yes returns to
  the menu; the questionnaire and its answers are untouched.
- After yes, every file of the receipt moves to
  `<finance root>/receipt_training_dataset/<name of the first image>/`:
  per image the original, the rotated and cropped copies and the processing
  metadata, plus a finished label file if one exists.
- The folder also gets `partial_label.json` (the answers given so far, by
  question id, marked incomplete) and `moved_from.json` (when, why, and the
  original path of every file).
- The receipt's empty folder in the labels directory is removed, the image
  grouping file forgets the receipt, the image window is closed, and
  labelling continues with the next receipt.

## Safety

- Files are moved, never deleted, and an existing dataset folder is never
  overwritten (the new one gets a number).
- Everything is checked before the first move; a failure during the moves
  puts the moved files back and removes the new folder.
- A failed move is reported and the labelling run goes on; the receipt is
  asked again next time.

## Architecture

| Unit                                                                    | Role                                                                                       |
| ----------------------------------------------------------------------- | ------------------------------------------------------------------------------------------ |
| `hledger_receipt_processing/receipts_to_objects/receipt_not_mine.py`    | file list, confirmation, the move with roll-back, the `ReceiptNotMine` exception           |
| `hledger_receipt_processing/matching/ask_user_action.py`                | `NOT_MINE` action; `get_receipt_action(..., allow_not_mine=False)`                         |
| `hledger_receipt_processing/receipts_to_objects/make_receipt_labels.py` | the labelling loop catches `ReceiptNotMine`, moves the receipt, continues                  |
| `tui_labeller/tuis/urwid/ask_urwid_receipt.py`                          | offers the option in its menu loop, leaves the questionnaire with the screen stopped       |
| `tui_labeller/tuis/urwid/question_app/get_answers.py`                   | `get_answers_so_far`: the answers typed up to now, without failing on unanswered questions |

The labeller checks whether `receipt_not_mine` can be imported; with an older
`hledger-receipt-processing` the option is simply not offered.

## Out of scope

- Offering the option earlier (at the "Can you see" prompt or inside the
  questionnaire) and in the later matching stage.
- Reading the training dataset when training models.
- A configurable dataset location.
