from pathlib import Path

import pytest

from codegen_eval.contract import validate_source
from codegen_eval.tasks import load_tasks


PILOT = Path(__file__).resolve().parents[1] / "data" / "pilot_tasks.json"
TASK = load_tasks(PILOT, {"strings": 1, "lists": 1, "dictionaries": 1})[0]


def test_standard_library_import_and_one_matching_function_are_accepted():
    source = "import unicodedata\n\ndef count_vowels(text: str) -> int:\n    return 0\n"
    assert validate_source(source, TASK) is None


@pytest.mark.parametrize(
    ("source", "expected_code"),
    [
        ("```python\ndef count_vowels(text: str) -> int:\n    return 0\n```", "contract_error"),
        ("def count_vowels(text: str) -> int\n    return 0", "syntax_error"),
        ("import pandas\ndef count_vowels(text: str) -> int:\n    return 0", "contract_error"),
        ("print(1)\ndef count_vowels(text: str) -> int:\n    return 0", "contract_error"),
        ("def count_vowels(text: str) -> int:\n    return 0\ndef helper():\n    pass", "contract_error"),
        ("def count_vowels(text: str) -> int:\n    def helper():\n        return 0\n    return helper()", "contract_error"),
        ("def count_vowels(text) -> int:\n    return 0", "contract_error"),
        ("@staticmethod\ndef count_vowels(text: str) -> int:\n    return 0", "contract_error"),
        ("def count_vowels(text: str):\n    return 0", "contract_error"),
    ],
)
def test_invalid_generated_code_is_classified(source, expected_code):
    issue = validate_source(source, TASK)
    assert issue is not None
    assert issue.code == expected_code
