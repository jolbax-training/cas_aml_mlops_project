# Paid smoke evidence (`add-openrouter-client-and-budget-ledger`)

Reviewed 2026-11-03 from the coordinator's own commands (Mac arm64, primary checkout). Bundles are under `run_bundles/` (Git-ignored, retained); pricing inputs, the settings freeze and the spending ledger are outside Git. This is a smoke of the client, ledger and calibration, not a model-quality result and not a comparison run.

## Price and endpoint rechecks (task 4.1, no spend)

| Date | Input USD/M | Output USD/M | FX (ECB) | EUR/USD x EUR/CHF | USD to CHF recorded |
| --- | --- | --- | --- | --- | --- |
| 2026-11-01 | 0.03 | 0.16 | 2026-10-30: 1.1172, 0.9194 | 0.82295 | 0.8230 |
| 2026-11-03 (before the passing smoke) | 0.03 | 0.22 (raised) | 2026-11-02: 1.1216, 0.9193 | 0.81964 | 0.8197 |

- Endpoint: `https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints`, `open-inference/fp4` ("OpenInference | z-ai/glm-5.3-flash-20260826", quantization fp4). The issue-08 snapshot was 0.0052 / 0.1985 USD per M tokens. It supports tools, `tool_choice` none/auto/required/function, temperature, top_p, reasoning_effort, max_tokens, seed and response_format; status 0.
- Pricing inputs kept outside Git: `~/.codegen_eval/pricing_2026-11-01.json` and `~/.codegen_eval/pricing_2026-11-03.json`. Safety margin 0.25; fixed fee CHF 0 (OpenRouter charges no per-request fee; its fee applies when credits are bought).
- Worst-case reservation per attempt with the 2026-11-03 prices: CHF 0.0008197.

## Paid smokes (task 4.2)

All went through the ledger, all ended `submitted`, the provider was OpenInference on every attempt (`provider_matches_pin` true), and `missing_fields` was `['precision']` on every attempt: the provider returns no precision or quantization field, so precision is pinned by the provider tag only and is not confirmed per response.

| Date | Bundle | Task | Mode | Calls | Result |
| --- | --- | --- | --- | --- | --- |
| 2026-11-01 | `20261101T112513Z-d7765e` | strings_01 | unforced | 2 | no final-only call |
| 2026-11-01 | `20261101T112846Z-dd035f` | parsing_formatting_02 | unforced | 2 | no final-only call |
| 2026-11-01 | `20261101T112853Z-8c85c0` | numeric_logic_02 | unforced | 2 | no final-only call |
| 2026-11-01 | `20261101T112901Z-c2a99d` | parsing_formatting_01 | unforced | 3 | no final-only call |
| 2026-11-01 | `20261101T112910Z-b5a4bb` | dictionaries_02 | unforced | 2 | no final-only call |
| 2026-11-01 | `20261101T112917Z-ab29a9` | lists_02 | unforced | 2 | no final-only call |
| 2026-11-03 | `20261103T013902Z-46c5c0` | strings_01 | forced, first wording | 3 (2 tool attempts) | submitted at call 3, no final-only call |
| 2026-11-03 | `20261103T050806Z-30949f` | strings_01 | forced, explicit wording (task 5.5) | 4 (3 tool attempts) | reached the final-only call |

Passing smoke `20261103T050806Z-30949f`: requests 1-3 sent `tool_choice` auto with the tool; request 4 sent `tool_choice` none (final-only); final submission of 305 characters; call 4 HTTP 200, `finish_reason` stop. Completion tokens per call 164 / 145 / 145 / 84 (all within 2,000); `reasoning_tokens` 0 on call 4. Accepted settings: model `z-ai/glm-5.3-flash`, provider `open-inference/fp4`, `allow_fallbacks` false, `require_parameters` true, temperature 0.2, top_p 1.0, `reasoning_effort` low, `max_tokens` 2000, timeout 60 s. `returned_model` was `z-ai/glm-5.3-flash` on all four calls, equal to the requested model.

Tool definitions on the final-only call: `OpenRouterClient._payload` resends them when `tool_choice` is none and raises if a tool-call history has none; the call succeeded with `require_parameters` on. This is a statement about the code plus a successful call; the wire payload itself is not stored in the bundle.

Task 5.5: the explicit wording reached the final-only call on the first forced try (bundle above).

## Ledger and projection (task 4.3)

After all smokes: committed CHF 0.001123954886, reserved 0; the CHF 10 checkpoint was not reached; ceiling CHF 15. Projection: 0.001124 + 360 x 0.0008197 = CHF 0.2962 worst case, which fits the CHF 15 ceiling (no escalation).

## Calibration and settings freeze (task 4.4)

`experiment_cli calibrate` on `20261103T050806Z-30949f`: ok true; 4 sent attempts; bound / `prompt_tokens` ratios 2.102, 2.075, 2.058, 2.047 (minimum 2.047, required at least 1.1); maximum bound 2937 (limit 12,000); `fourth_call_observed` true; `input_bound_ascii_chars_per_token` 2.0. **Decision: keep 2.0**; the bound stays about 2x over the reported count and did not reject the fourth call. All earlier smokes failed calibration only for the missing final-only call; their ratios were 1.923-2.100.

Settings freeze written by `experiment_cli freeze-settings` at 2026-11-03T05:08:32Z to `experiments/evidence/settings_freeze.json` (Git-ignored): decision pass; `model_config_hash` `4fe5bf3e6d9840e2ae7fdac2add3867698ac64022f962d56c30e49206e9e9908`; `settings_hash` `4c3b3b351075142e9db945a7eacb64fe47fef689e83f212957dec72efe0d1c9e`; `config_sha256` `ceec6d991427dc8b375422e8caa1fcf534295aecbae33af7e22216fd6c576233`; smoke mode `exercise_final_only`; smoke `manifest_sha256` `e09cb5b047a22048d25649170da81562b27a45e20250d83b1b7654ff83a5283c`.

- Pre-freeze adjustment: none to model settings; the smoke-only instruction (5.5) is not an experiment setting.
- Reproducibility limit: a fixed model identifier does not guarantee immutable upstream weights. `returned_model` and provider are recorded per attempt; precision is not returned.

## Limits of this evidence

- The traced fourth call is a prompted one (smoke only); the main experiment does not add that instruction.
- Precision is not confirmed per response (provider tag only).
- Eight single-trial smokes on a few tasks say nothing about model quality or the main-run call mix; the prices changed between the two rechecks, so the projection uses the later ones.
