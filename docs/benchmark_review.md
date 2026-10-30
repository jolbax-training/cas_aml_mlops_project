# Benchmark v1 review evidence

This records the review of the ten-task benchmark in [`data/benchmark_v1.json`](../data/benchmark_v1.json) (schema version 1, benchmark version `1`, **not yet frozen**; the content hash is recorded when the benchmark is frozen, change task 4.3).

## Reviewer and limitations

- **Reviewer:** Claude Sonnet 5.5 (the model that authored the new tasks), working in an Orca worker session on 2026-10-30. **No human has reviewed any task, case, or reference.** The review is a derivation-and-execution check by the authoring model, not independent human validation.
- **Method per task:** (1) the instruction and signature were written first; (2) each expected answer was derived by hand from the instruction (derivations below) before any code ran; (3) a reference solution was written afterwards as a separate file, using a different algorithm from the hand derivation where practical, and kept inside the one-function source contract; (4) the reference was run against the four cases (strict type-aware equality and no-mutation check, in-process in `tests/test_benchmark.py::test_reference_satisfies_the_source_contract_and_all_four_cases`, and through the Podman sandbox in `test_references_pass_every_case_in_the_sandbox`).
- **Limitation:** author, derivation, and reference come from the same model, so a shared misreading of an instruction would not be caught. Two safeguards apply: every rule the cases depend on is stated in the instruction (no hidden conventions), and the user can still spot-check before freezing. A model answer that was not derived and executed this way would not count as validation.
- **Reference solutions:** [`data/references_v1/<task_id>.py`](../data/references_v1). They are never shown to generators.

## Result

All ten references pass all forty cases (twenty of them edge cases) with no input mutation. No reference disagreed with a derived expected answer, so no expected answer needed correcting. The only correction is the `strings_01` instruction below.

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

## Scope exclusions checked

No case uses floating point, an expected exception, a non-JSON value, or an input outside its stated type; `tasks.py` rejects floats, booleans in integer positions, and other mismatches against the signature when the benchmark is loaded.

## Still to do before freezing

Section 3 (grading and accounting) and section 4 (fixtures, freeze, hash, progress entry) of `add-reviewed-benchmark-and-graders` are outstanding. This evidence is not frozen until the version and hash are recorded.
