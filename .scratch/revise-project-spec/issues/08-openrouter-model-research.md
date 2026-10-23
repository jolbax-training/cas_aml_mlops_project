# Verify OpenRouter model choices and budget inputs

Label: wayfinder:research
Type: research
Status: resolved
Assignee: jolbax
Parent: [Define the agent-evaluation and MLOps project](../map.md)
Blocked by: none

## Question

Which currently documented inexpensive OpenRouter models and provider configurations support native tool calling for the proposed bounded Python-function agent, and which pricing, request-limit, retry, routing, and cost-reporting facts are needed to freeze a comparable experiment within CHF 15? Use primary sources, shortlist at most two models, recommend a candidate subject to a later functional smoke test, and distinguish documented support from behavior not yet tested. Verify current CHF/USD conversion from a primary source if practical, or explicitly leave the conversion as a preflight input. The main comparison has sixty task trials, at most four logical model calls per trial, with pilot/development and transport retries also charged to the project budget. Make no paid API calls.

Research findings must be retained as one cited Markdown file on a throwaway `research/` branch, pushed without a PR and never merged. Record the branch, commit, and findings path here on resolution.

## Answer

Research completed against first-party OpenRouter endpoint/catalog/routing/usage documentation and Z.ai documentation. No paid API calls were made.

- The user-selected model is `z-ai/glm-5.3-flash`; OpenRouter currently reports canonical slug `z-ai/glm-5.3-flash-20260826`.
- The `open-inference/fp4` endpoint advertises the agreed sampling parameters, tool calling, and `tool_choice` values `auto` and `none`, including the final-submission-only requirement. Disable fallbacks, restrict the exact endpoint, and require parameter support. Metadata support is not a completed functional smoke test.
- Endpoint pricing snapshot: USD 0.0052/M input and USD 0.1985/M output; no tier or cache-write price was advertised. At enforced 12k-input / 2k-output caps, 360 main physical attempts have a USD 0.165384 token-price envelope, excluding development calls, fees, FX, and safety margin. Recheck prices and conversion before running; the ledger remains authoritative for total project reservations.
- Z.ai documents configurable temperature in [0, 1] and top-p in [0.01, 1], with sampling enabled by default. Temperature 0.2 is documented as valid. Provider-level request acceptance/behavior still needs a smoke check.
- GLM reasoning is mandatory; the catalog reports efforts `low`, `high`, `max` with default `max`. Explicit low effort and a smoke test of the combined reasoning/visible-output allowance are appropriate for the agreed small tasks and 2k output cap.
- The native `z-ai/fp8` endpoint advertises `tool_choice.none:false`, illustrating why model-level tools support alone is insufficient for provider selection. Do not silently substitute it.
- CHF conversion remains a recorded preflight input. The research's illustrative development allowance was not a user-confirmed quota.

Retained evidence: branch `research/openrouter-model-choice`, pushed commit `44d1fff8e7d5c947c56c50e4fec355f47991f08a`, single findings file [docs/research/openrouter-model-choice.md](https://github.com/jolbax-training/cas_aml_mlops_project/blob/44d1fff8e7d5c947c56c50e4fec355f47991f08a/docs/research/openrouter-model-choice.md). The research branch is not merged and has no PR. Initial Qwen recommendations in earlier research revisions were superseded by the user's GLM selection.
