# Pilot benchmark tasks

These three tasks exercise the implemented offline evaluator and will support the first local generation/evaluation milestone. The [working specification](project_spec.md) defines a reviewed minimum of 10 tasks across five categories, with 30 as a stretch target. Each task has two ordinary and two edge cases. The tasks use typed inputs only; behavior for inputs outside the stated types is out of scope.

The pilot is stored as machine-readable [pilot task data](../data/pilot_tasks.json). The evaluator reads that data rather than scraping the tables below. Recheck expected answers independently before including these tasks in a frozen benchmark.

## Task record and visibility

Each JSON task has a unique `id`, `category`, `function_name`, `signature`, `instruction`, and four `cases`. Each case has a unique `id`, a `kind` (`ordinary` or `edge`), positional `args`, and an `expected` return value.

The generator sees only the task's `instruction` and `signature`. The evaluator keeps the case inputs, expected outputs, and case labels private until scoring. This visibility rule also applies to the expanded benchmark. During execution, only the individual case inputs are passed into the container; expected answers remain outside it.

## Pilot evaluation rules

- The generator must return raw Python source with optional standard-library imports and exactly one synchronous function definition matching the requested name and signature. Markdown fences, extra prose, helper functions, decorators, top-level executable statements, and third-party imports fail the output contract.
- Compare return values using strict type-aware recursive equality for these pilot tasks; they use only strings, integers, lists, and dictionaries.
- The list and dictionary inputs must be unchanged after each call. A case fails if the function mutates an input, even when its return value is correct.
- None of the pilot cases expects an exception. Each case is scored independently.
- The same no-mutation rule applies to the minimum expanded benchmark.

## Task 1: Count vowels

- **ID:** `strings_01`
- **Category:** strings
- **Signature:** `count_vowels(text: str) -> int`
- **Instruction to the generator:** Write `count_vowels(text: str) -> int`. Count occurrences of the Latin vowels `a`, `e`, `i`, `o`, and `u`, including accented forms such as `é` and `ü`, without regard to case. A vowel written as a base letter followed by a combining accent counts once. Do not count ligatures such as `æ`, or `y`. The input is always a string; return `0` for an empty string. Python standard-library imports are allowed, but third-party dependencies are not.

| Case | Kind | Input | Expected |
| --- | --- | --- | ---: |
| `strings_01_a` | ordinary | `"hello"` | 2 |
| `strings_01_b` | ordinary | `"café"` | 2 |
| `strings_01_c` | edge | `""` | 0 |
| `strings_01_d` | edge | `"A\u0308Éæ"` (A + combining diaeresis, É, æ) | 2 |

**Agreed boundary:** Ligatures such as `æ` are excluded. The input is a `str`; `None` is outside this task's contract.

## Task 2: Unique integers in first-seen order

- **ID:** `lists_01`
- **Category:** lists
- **Signature:** `unique_in_order(items: list[int]) -> list[int]`
- **Instruction to the generator:** Write `unique_in_order(items: list[int]) -> list[int]`. Return each distinct integer exactly once, in the order it first appears in `items`. Do not modify `items`. The input is always a list of integers. For an empty list, return an empty list.

| Case | Kind | Input | Expected |
| --- | --- | --- | --- |
| `lists_01_a` | ordinary | `[3, 1, 3, 2, 1]` | `[3, 1, 2]` |
| `lists_01_b` | ordinary | `[-2, -2, 0, 4, 0]` | `[-2, 0, 4]` |
| `lists_01_c` | edge | `[]` | `[]` |
| `lists_01_d` | edge | `[5, 5, 5]` | `[5]` |

**Agreed boundary:** Modifying the input list fails a case, even if the return value is correct.

## Task 3: Merge integer maps

- **ID:** `dictionaries_01`
- **Category:** dictionaries
- **Signature:** `merge_integer_maps(left: dict[str, int], right: dict[str, int]) -> dict[str, int]`
- **Instruction to the generator:** Write `merge_integer_maps(left: dict[str, int], right: dict[str, int]) -> dict[str, int]`. Return a dictionary containing every key from either input. If a key appears in both, its result is the sum of the two integer values. If it appears in only one, preserve that value. Keep keys whose result is zero. Do not modify either input dictionary. The inputs are always dictionaries with string keys and integer values.

| Case | Kind | Input (`left`, `right`) | Expected |
| --- | --- | --- | --- |
| `dictionaries_01_a` | ordinary | `{"a": 2}`, `{"b": 3}` | `{"a": 2, "b": 3}` |
| `dictionaries_01_b` | ordinary | `{"a": 2, "b": 1}`, `{"a": 3, "c": 4}` | `{"a": 5, "b": 1, "c": 4}` |
| `dictionaries_01_c` | edge | `{}`, `{}` | `{}` |
| `dictionaries_01_d` | edge | `{"x": 0}`, `{"x": 0}` | `{"x": 0}` |

**Agreed boundary:** Modifying either input dictionary fails a case. Returned dictionary contents are compared without requiring key iteration order.
