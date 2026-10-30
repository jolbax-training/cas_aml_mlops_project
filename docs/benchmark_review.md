# Benchmark v1 review evidence

This records the review of the ten-task benchmark in [`data/benchmark_v1.json`](../data/benchmark_v1.json) (schema version 1, benchmark version `1`, **not yet frozen**; the content hash is recorded when the benchmark is frozen, change task 4.3).

## Reviewer and limitations

- **Reviewer:** Claude Sonnet 5.5 (the model that authored the new tasks), working in an Orca worker session on 2026-10-30. **No human has reviewed any task, case, or reference.** The review is a derivation-and-execution check by the authoring model, not independent human validation.
- **Method per task:** (1) the instruction and signature were written first; (2) each expected answer was derived by hand from the instruction (derivations below) before any code ran; (3) a reference solution was written afterwards as a separate file, using a different algorithm from the hand derivation where practical, and kept inside the one-function source contract; (4) the reference was run against the four cases (strict type-aware equality and no-mutation check, in-process in `tests/test_benchmark.py::test_reference_satisfies_the_source_contract_and_all_four_cases`, and through the Podman sandbox in `test_references_pass_every_case_in_the_sandbox`).
- **Limitation:** author, derivation, and reference come from the same model, so a shared misreading of an instruction would not be caught. Two safeguards apply: every rule the cases depend on is stated in the instruction (no hidden conventions), and the user can still spot-check before freezing. A model answer that was not derived and executed this way would not count as validation.
- **Reference solutions:** [`data/references_v1/<task_id>.py`](../data/references_v1). They are never shown to generators.

## Result

All ten references pass all forty cases (twenty of them edge cases) with no input mutation. No reference disagreed with a derived expected answer, so no expected answer needed correcting. Corrections to instructions (no case or expected answer changed): `strings_01` (below), and after the second review `lists_02` and `parsing_formatting_02` (see Second review).

## Pilot task re-review

The pilot file `data/pilot_tasks.json` is unchanged and kept for history. The three pilot tasks are reused in benchmark v1 with identical cases.

| Task | Finding | Action |
| --- | --- | --- |
| `strings_01` | Cases re-derived: `hello` has e, o (2); `café` has a, é (2); empty is 0; `A` + U+0308 counts once, `É` once, `æ` is excluded (2). Expected answers are correct. The instruction was ambiguous about letters such as `ø`, which look like an accented `o` but do not decompose into a base vowel and a combining mark. | **Instruction corrected** in v1: "Do not count y. Do not count letters that are not a vowel letter with combining marks, such as the ligature æ or the letter ø." Cases unchanged. |
| `lists_01` | `[3,1,3,2,1]` gives `[3,1,2]`; `[-2,-2,0,4,0]` gives `[-2,0,4]`; `[]` gives `[]`; `[5,5,5]` gives `[5]`. Instruction is unambiguous. | Reused unchanged. |
| `dictionaries_01` | `{a:2}+{b:3}`; `{a:2,b:1}+{a:3,c:4}` gives a:5, b:1, c:4; `{}+{}`; `{x:0}+{x:0}` keeps `x: 0`. Instruction is unambiguous. | Reused unchanged. |

## Per-task review records

Reviewer for every row: Claude Sonnet 5.5, 2026-10-30, no human review. Case IDs are `<task_id>_a` to `_d` (a, b ordinary; c, d edge).

| Task | Derivation of expected answers | Corrections |
| --- | --- | --- |
| `strings_01` `count_vowels` | See the pilot table above. Reference: NFD normalisation, count base letters in `aeiou`. | Instruction clarified (above). |
| `strings_02` `run_length_encode` | a: `aaabcc` is a×3, b×1, c×2 so `a3b1c2`. b: `aAbb` is a, A, b×2 so `a1A1b2` (case-sensitive). c: empty gives empty. d: twelve `z` give `z12` (multi-digit count). Reference: scan runs with an index. | None. |
| `lists_01` `unique_in_order` | See the pilot table. Reference: membership test while appending. | None. |
| `lists_02` `rotate_left` | a: `[1,2,3,4,5]`, k=2 gives `[3,4,5,1,2]`. b: k=0 gives the same list. c: empty list gives `[]`. d: k=7 on three items is k=1 after wrapping, so `[2,3,1]`. Reference: index arithmetic with modulo, building a new list. | None. |
| `dictionaries_01` `merge_integer_maps` | See the pilot table. Reference: copy left, add right with `get`. | None. |
| `dictionaries_02` `group_keys_by_value` | a: values x (keys a, c) and y (key b). b: both keys have value `k`, listed sorted as `["a","b"]` although `b` was inserted first. c: empty gives `{}`. d: the empty-string value is a valid key, `{"": ["only"]}`. Reference: iterate keys in sorted order. | None. |
| `numeric_logic_01` `digital_root` | a: 38 → 11 → 2. b: 999 → 27 → 9. c: 0 is single-digit so stays 0. d: 10^30 (a 1 followed by thirty zeros, larger than 64 bits as the instruction allows) has digit sum 1. Reference: repeated `divmod` digit sums. | None. |
| `numeric_logic_02` `collatz_steps` | a: 6 → 3 → 10 → 5 → 16 → 8 → 4 → 2 → 1 is 8 steps. b: 7 → 22 → 11 → 34 → 17 → 52 → 26 → 13 → 40 → 20 → 10 → 5 → 16 → 8 → 4 → 2 → 1 is 16 steps. c: 1 is 0 steps. d: 27 takes 111 steps; this value was not derived by hand, it comes from the well-known published Collatz count for 27 and is confirmed only by the reference run. | None. |
| `parsing_formatting_01` `format_duration` | a: 3661 s = 1 h + 1 min + 1 s so `1:01:01`. b: 59 s is `0:00:59`. c: 0 is `0:00:00`. d: 360000 s is exactly 100 h, so `100:00:00` (hours not wrapped). Reference: nested `divmod` and `%d:%02d:%02d`. | None. |
| `parsing_formatting_02` `parse_settings` | a: `a=1;b=2` gives a→1, b→2. b: ` name = Ann ` gives name→Ann; ` city=Bern=CH` splits at the first `=` giving city→`Bern=CH`. c: empty string gives `{}`. d: `k=1;k=2;;z=` gives k→2 (last wins), the empty segment is skipped, and `z=` gives z→empty value. Reference: `partition("=")` per segment. | None. |

## Second review

- **Reviewer:** Claude Fable 5.1, independent derivation, 2026-10-30. **No human review.** The reviewer read only each task's instruction, signature, and case IDs, kinds, and arguments (expected values and references hidden), wrote an expected answer for all 40 cases, then compared with strict type-aware equality. It also ran the references with a mutation check and confirmed the sandbox run. This is a second model reviewer, not human validation, and the same-model-family limitation above still applies.
- **Result:** agreement 40/40; no expected answer needed correction. `numeric_logic_02_d` (111) now has a second derivation (published value plus executing the step rule independently).

| Case | Kind | Args | My derived answer | Benchmark `expected` | Agree |
| --- | --- | --- | --- | --- | --- |
| strings_01_a | ordinary | `"hello"` | 2 (e, o) | 2 | yes |
| strings_01_b | ordinary | `"café"` | 2 (a, é) | 2 | yes |
| strings_01_c | edge | `""` | 0 | 0 | yes |
| strings_01_d | edge | `"ÄÉæ"` | 2 (A+combining diaeresis once, É once, æ excluded) | 2 | yes |
| strings_02_a | ordinary | `"aaabcc"` | `"a3b1c2"` | `"a3b1c2"` | yes |
| strings_02_b | ordinary | `"aAbb"` | `"a1A1b2"` | `"a1A1b2"` | yes |
| strings_02_c | edge | `""` | `""` | `""` | yes |
| strings_02_d | edge | 12 × `z` | `"z12"` | `"z12"` | yes |
| lists_01_a | ordinary | `[3,1,3,2,1]` | `[3,1,2]` | `[3,1,2]` | yes |
| lists_01_b | ordinary | `[-2,-2,0,4,0]` | `[-2,0,4]` | `[-2,0,4]` | yes |
| lists_01_c | edge | `[]` | `[]` | `[]` | yes |
| lists_01_d | edge | `[5,5,5]` | `[5]` | `[5]` | yes |
| lists_02_a | ordinary | `[1,2,3,4,5], 2` | `[3,4,5,1,2]` | `[3,4,5,1,2]` | yes |
| lists_02_b | ordinary | `[7,8,9], 0` | `[7,8,9]` | `[7,8,9]` | yes |
| lists_02_c | edge | `[], 3` | `[]` | `[]` | yes |
| lists_02_d | edge | `[1,2,3], 7` | `[2,3,1]` (7 mod 3 = 1) | `[2,3,1]` | yes |
| dictionaries_01_a | ordinary | `{a:2}, {b:3}` | `{a:2, b:3}` | same | yes |
| dictionaries_01_b | ordinary | `{a:2,b:1}, {a:3,c:4}` | `{a:5, b:1, c:4}` | same | yes |
| dictionaries_01_c | edge | `{}, {}` | `{}` | `{}` | yes |
| dictionaries_01_d | edge | `{x:0}, {x:0}` | `{x:0}` | `{x:0}` | yes |
| dictionaries_02_a | ordinary | `{a:x, b:y, c:x}` | `{x:[a,c], y:[b]}` | same | yes |
| dictionaries_02_b | ordinary | `{b:k, a:k}` | `{k:[a,b]}` (sorted) | same | yes |
| dictionaries_02_c | edge | `{}` | `{}` | `{}` | yes |
| dictionaries_02_d | edge | `{only:""}` | `{"":[only]}` | same | yes |
| numeric_logic_01_a | ordinary | 38 | 2 (38→11→2) | 2 | yes |
| numeric_logic_01_b | ordinary | 999 | 9 (999→27→9) | 9 | yes |
| numeric_logic_01_c | edge | 0 | 0 | 0 | yes |
| numeric_logic_01_d | edge | 10^30 | 1 | 1 | yes |
| numeric_logic_02_a | ordinary | 6 | 8 (6,3,10,5,16,8,4,2,1) | 8 | yes |
| numeric_logic_02_b | ordinary | 7 | 16 (7,22,11,34,17,52,26,13,40,20,10,5,16,8,4,2,1) | 16 | yes |
| numeric_logic_02_c | edge | 1 | 0 | 0 | yes |
| numeric_logic_02_d | edge | 27 | 111 (known Collatz count for 27; confirmed by executing the step rule myself) | 111 | yes |
| parsing_formatting_01_a | ordinary | 3661 | `"1:01:01"` | same | yes |
| parsing_formatting_01_b | ordinary | 59 | `"0:00:59"` | same | yes |
| parsing_formatting_01_c | edge | 0 | `"0:00:00"` | same | yes |
| parsing_formatting_01_d | edge | 360000 | `"100:00:00"` | same | yes |
| parsing_formatting_02_a | ordinary | `"a=1;b=2"` | `{a:"1", b:"2"}` | same | yes |
| parsing_formatting_02_b | ordinary | `" name = Ann ; city=Bern=CH"` | `{name:"Ann", city:"Bern=CH"}` | same | yes |
| parsing_formatting_02_c | edge | `""` | `{}` | `{}` | yes |
| parsing_formatting_02_d | edge | `"k=1;k=2;;z="` | `{k:"2", z:""}` | same | yes |

### Changes made after the second review

Instructions only; no case, argument, or expected answer changed, so references and the 40/40 result are unaffected (rerun after the change).

- `lists_02`: added "Rotation wraps, so rotating by k is the same as rotating by k modulo the length of items." (the wrap for k beyond the length was implied, not stated).
- `parsing_formatting_02`: "spaces" became "space characters (U+0020)" in both places, so the whitespace reading cannot become ambiguous in a later edge case.
- Validator (`tasks.py`): positional-only parameters and missing parameter or return annotations are now rejected with their own diagnostics; benchmark v1 is unaffected.

### Known limitation: empty-input edge cases

Seven of the twenty edge cases are empty inputs (`strings_01_c`, `strings_02_c`, `lists_01_c`, `lists_02_c`, `dictionaries_01_c`, `dictionaries_02_c`, `parsing_formatting_02_c`). This satisfies the specification and empty input is a legitimate edge, so the cases were kept rather than rewritten, to avoid more unreviewed content late in review. It does lower edge-case diversity; later benchmark versions should prefer non-empty edges for those tasks.

## Scope exclusions checked

No case uses floating point, an expected exception, a non-JSON value, or an input outside its stated type; `tasks.py` rejects floats, booleans in integer positions, and other mismatches against the signature when the benchmark is loaded.

## Still to do before freezing

Section 3 (grading and accounting) and section 4 (fixtures, freeze, hash, progress entry) of `add-reviewed-benchmark-and-graders` are outstanding. This evidence is not frozen until the version and hash are recorded.
