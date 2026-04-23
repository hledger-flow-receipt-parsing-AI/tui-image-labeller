from enum import Enum


class InputType(Enum):
    LETTERS = "letters"
    LETTERS_SEMICOLON = "letters_semicolon"
    LETTERS_AND_SPACE = "letters_and_space"
    LETTERS_AND_NRS = "letters_and_numbers"
    FLOAT = "float"
    INTEGER = "integer"
