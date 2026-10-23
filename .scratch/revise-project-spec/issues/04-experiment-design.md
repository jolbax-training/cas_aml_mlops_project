# Define the experiment and spending controls

Label: wayfinder:grilling
Type: grilling
Status: resolved
Assignee: jolbax
Parent: [Define the agent-evaluation and MLOps project](../map.md)
Blocked by: 03, 08

## Question

What controlled comparison will answer a useful question about the agreed agent? Define the baseline, intended revision, fixed settings, model/provider selection criteria, repeated-trial plan, quality and efficiency metrics, incomplete-run treatment, and limits on conclusions. Define request/retry/tool limits and how the CHF 10 checkpoint and CHF 15 ceiling will be monitored and enforced, including handling provider billing currency and uncertain cost estimates.

## Comments

### Q25–Q27 — User-confirmed comparison, repetitions, and metrics

- Compare a baseline agent prompt with one revised prompt. Keep model, tools, interaction limits, benchmark, and evaluator fixed. Inspect baseline failures, document one intended prompt change, and produce a reasoned keep/reject decision. Measured improvement is not required. Because the revision uses benchmark feedback, limit performance claims to these tasks.
- Run three independent trials per task per variant: thirty task trials per variant, sixty overall, with 240 hidden acceptance-check outcomes planned overall. Each trial uses a fresh conversation and receives no previous-trial results. Verify projected API cost before committing to the main runs.
- Primary metric: fraction of successful task trials. Include successes by task/category, tasks passing at least one trial and all three trials, hidden-check/edge-case pass rates, failure labels, tool calls, revisions, observed recovery, end-to-end latency, token usage, and reported/estimated API cost. Inspect selected traces to explain gains, regressions, and unchanged results. Do not claim precise reliability estimates or broad generalization from this small sample.

Model/provider settings and cost/retry controls remain open. A research child ticket supplies current OpenRouter facts before model selection.

### Q28 — User-confirmed transport retries

Allow one retry per failed request and at most two transport retries across an entire trial, with bounded backoff for transient transport failures and retryable API errors. These are outside the four logical model-call allowance. Record and budget every physical attempt. Refusals, malformed model responses, failed checks, and poor answers do not trigger transport retries. A timed-out request can still be charged; retain its reserved cost.

### Q29 — User-confirmed project-wide spending enforcement

Use one ledger for every paid call: development, smoke testing, main experiments, and retries. Before a request, reserve a conservative maximum cost from verified prices, request limits, a recorded CHF conversion, and a safety margin. Record a CHF 10 checkpoint and continue automatically. Do not send a request whose reservation would exceed CHF 15. Keep reservations for uncertain charges. Preserve the bundle and mark unfinished work incomplete when the ceiling prevents completion.

### Q30 — User-selected model

The user selected `z-ai/glm-5.3-flash` at https://openrouter.ai/z-ai/glm-5.3-flash, superseding the proposed Qwen model. Model-specific provider routing and documented support are being verified before freezing the configuration. Do not carry the proposed Alibaba provider restriction over to the new model.

### Q31 — User-confirmed request settings

Use a maximum input of 12,000 tokens including conversation history and tool definitions, maximum output of 2,000 tokens per model call, temperature 0.2, top-p 1, and a 60-second API deadline per physical attempt. Reject over-limit requests before sending, retain truncated responses as returned, and apply the agreed failure/retry rules. Freeze these settings after the functional smoke test. An unchanged model identifier does not guarantee immutable upstream weights; document that reproducibility limitation. The settings do not authorize implementation or paid calls during this planning effort.

### Q31 follow-up — Temperature verification and surfaced reasoning choice

The user requested explicit verification that temperature is configurable. OpenRouter's public models API lists `temperature` for `z-ai/glm-5.3-flash`, with defaults temperature 1 / top-p 0.95. The endpoint API lists temperature support for the proposed OpenInference endpoint and alternatives. Z.ai's official model card demonstrates configurable sampling and its API schema documents GLM-5.3-Flash temperature in [0, 1]; 0.2 is therefore within documented support. Functional behavior at the selected routed endpoint remains a smoke-test requirement; metadata support alone is not evidence of a completed live check.

Sources: https://openrouter.ai/api/v1/models ; https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints ; https://huggingface.co/zai-org/GLM-5.3-Flash ; https://docs.z.ai/api-reference/llm/chat-completion.md .

Research also surfaced a setting requiring a decision: the model advertises mandatory reasoning with `low`, `high`, and `max` efforts and default `max`. Provider selection and explicit reasoning effort remain open, particularly because the agreed 2,000-token output allowance must accommodate the provider's reasoning/output accounting.

### Q32–Q33 — Provider explanation requested; reasoning effort confirmed

The user accepted explicit `low` reasoning effort for both variants, retaining temperature 0.2 and top-p 1. The smoke test must verify that the agreed 2,000-token output allowance leaves room for tool calls and final code. This supersedes the open reasoning-effort item above.

For Q32 the user asked what provider pinning is for; no provider has been accepted. Explain the distinction between the selected model and the endpoint hosting it: fixed provider/precision/routing helps avoid confounding the prompt comparison. OpenInference `open-inference/fp4` is a proposed compatible endpoint, not a confirmed requirement.

### Q32 — Provider accepted after explanation

The user accepted pinning OpenInference `open-inference/fp4` for the selected GLM model, subject to a functional smoke test. This supersedes the open-provider statement above. Fix this endpoint across variants, disable fallbacks, and require support for requested parameters.

## Answer

User-confirmed through Q25–Q33, supported by [Verify OpenRouter model choices and budget inputs](08-openrouter-model-research.md):

- Compare one baseline agent prompt with one revised prompt after inspecting baseline failures. Keep the benchmark, evaluator, tools, limits, model/provider, and generation settings fixed. Document one intended prompt change and a keep/reject decision. Improvement is not mandatory; benchmark-informed tuning supports claims only about these tasks.
- Run three independent trials for each of ten tasks for each variant: thirty task trials per variant, sixty total, and 240 hidden acceptance-check outcomes overall. Each trial starts a fresh conversation and receives no earlier-trial results.
- Primary metric: successful task trials / planned task trials. Include task/category results; tasks passing at least once and all three times; check/edge-case rates; failure types; tool calls, revisions, and observed recovery; end-to-end latency, tokens, and reported/estimated cost. Explain selected traces, gains, regressions, and unchanged outcomes without precise reliability or generalization claims.
- Selected model: `z-ai/glm-5.3-flash`; selected endpoint: OpenInference `open-inference/fp4`. Pin routing, disable provider fallbacks, and require parameter support. Record actual provider/canonical-model metadata and disclose upstream changes; a fixed identifier does not guarantee immutable weights. Verify compatibility and projected total cost before freezing the main experiment.
- Request settings: at most 12,000 input tokens including history and tool definitions, 2,000 output tokens per model call, temperature 0.2, top-p 1, explicit low reasoning effort, and a 60-second API deadline per physical attempt. Reject oversized requests before sending; preserve truncated output as returned. Confirm that reasoning and visible output fit the selected provider's token accounting during smoke testing, then freeze settings.
- Permit one retry per failed request and at most two transport retries per trial, outside four logical model calls. Apply bounded backoff to transient/retryable API failures only. Never retry refusals, malformed model responses, bad answers, or failed checks as transport failures. Record every attempt, including timed-out requests that may still be billed.
- Use one persistent project-wide spending ledger for development, smoke tests, main experiments, and retries. Reserve conservative maximum cost before every paid attempt using verified prices, enforced request limits, a recorded CHF conversion, and a safety margin. Keep reservations for uncertain charges. Log a CHF 10 checkpoint and continue automatically; do not send any request whose reservation would exceed CHF 15. Preserve partial evidence and mark unfinished work incomplete if the ceiling blocks completion.
- The mandatory main comparison permits at most 240 logical model calls plus 120 transport retries: 360 physical attempts. Development/smoke usage is additional but shares the same CHF ceiling. Budget preflight must include both, and no unconfirmed research example constitutes an extra allowance.
