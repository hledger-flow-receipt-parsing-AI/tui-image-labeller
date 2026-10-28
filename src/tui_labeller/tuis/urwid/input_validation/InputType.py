from enum import Enum


class InputType(Enum):
    LETTERS = "letters"
    LETTERS_SEMICOLON = "letters_semicolon"
    LETTERS_AND_SPACE = "letters_and_space"
    LETTERS_AND_NRS = "letters_and_numbers"
    # Letters, digits, space and &'-./ : shop names like "H&M", "Koffie Leute".
    NAME = "name"
    FLOAT = "float"
    INTEGER = "integer"
