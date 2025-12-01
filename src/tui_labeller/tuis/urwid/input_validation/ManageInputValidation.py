import urwid

from tui_labeller.tuis.urwid.input_validation.InputValidationQuestion import (
    InputValidationQuestion,
)


class QuestionApp:
    def __init__(self):
        self.questions = [
            ("Question 1: ", ["apple", "apricot", "avocado"]),
            ("Question 2: ", ["banana", "blueberry", "blackberry"]),
            ("Question 3: ", ["cat", "caterpillar", "cactus"]),
        ]

        self.palette = [
            ("normal", "white", "black"),
            ("highlight", "white", "dark red"),
            ("autocomplete", "yellow", "dark blue"),
        ]

        self.autocomplete_box = urwid.AttrMap(
            urwid.Text("", align="left"), "autocomplete"
        )

        self.pile = urwid.Pile([])
        self.inputs = []
        for question, suggestions in self.questions:
            edit = InputValidationQuestion(
                # input_type=question.input_type,
                ans_required=question.ans_required,
                ai_suggestions=suggestions,
                # history_suggestions
                # question=question, self.autocomplete_box, self.pile
            )
            attr_edit = urwid.AttrMap(edit, "normal")
            edit.owner = attr_edit
            self.inputs.append(attr_edit)

        self.pile.contents = [
            (self.inputs[0], ("pack", None)),
            (self.inputs[1], ("pack", None)),
            (self.inputs[2], ("pack", None)),
            (urwid.Divider(), ("pack", None)),
            (
                urwid.Columns(
                    [(30, urwid.Text("Autocomplete: ")), self.autocomplete_box]
                ),
                ("pack", None),
            ),
        ]

        self.fill = urwid.Filler(self.pile, valign="top")
        self.loop = urwid.MainLoop(
            self.fill, self.palette, unhandled_input=self.handle_unhandled_input
        )

    def handle_unhandled_input(self, key):
        raise ValueError(f"Unhandled STOPPED at:{key}")

    def run(self):
        def update_autocomplete(widget, new_text):
            widget.update_autocomplete()

        for input_widget in self.inputs:
            urwid.connect_signal(
                input_widget.base_widget, "change", update_autocomplete
            )

        if self.inputs:
            self.pile.focus_position = 0
            self.inputs[0].base_widget.update_autocomplete()

        self.loop.run()
