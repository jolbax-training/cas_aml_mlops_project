# OpenRouter model choices and budget inputs

Research snapshot: 2026-10-23, approximately 15:30 UTC. Planning evidence only; no paid or authenticated API calls were made. This file belongs to a throwaway research branch and is not an implementation change.

## Selected model and provider recommendation

The user selected **`z-ai/glm-5.3-flash`**, superseding the earlier Qwen recommendation. The selected model is the main experiment model, subject to the required functional smoke test before freezing. Provider selection is still a planning decision. Recommend smoke-testing **`open-inference/fp4`** as the inexpensive endpoint with documented `auto` and `none` tool choice. A more conservatively priced alternative is `cohere`, which also advertises `parallel_tool_calls`. This is a capability/price recommendation, not measured task accuracy or proof of compatibility.

### Verified endpoint snapshot

Unauthenticated requests to the [Models API](https://openrouter.ai/api/v1/models) and [GLM endpoint API](https://openrouter.ai/api/v1/models/z-ai/glm-5.3-flash/endpoints) yielded this 2026-10-23 snapshot. Prices below are USD per million native tokens, converted from API per-token values. The catalog canonical slug is `z-ai/glm-5.3-flash-20260826`; tokenizer family is reported as `Other`.

| Selected model endpoint | Quantization | Input / output | Cached input | Tool choice support |
| --- | --- | --- | --- | --- |
| `open-inference/fp4` (OpenInference) | fp4 | $0.0052 / $0.1985 | $0.0052 | `none`, `auto`, `required`, named function all true |
| `cohere` (Cohere) | unknown | $0.15 / $0.50 | $0.03 | `none`, `auto`, `required`, named function all true |

Both advertise `tools`, `tool_choice`, `temperature`, `top_p`, `max_tokens`, and reasoning controls. The selected endpoint snapshots contain **no price-tier overrides or cache-write rate**; absence is not a guarantee that unadvertised charges can never occur. Requery and retain the exact pricing before paid work. The [model page](https://openrouter.ai/z-ai/glm-5.3-flash) shows many providers, so its headline minimum price is not a price guarantee for every endpoint.

**Important counterexample:** the model's native `z-ai/fp8` endpoint advertises tools and `auto`, but explicitly reports `supports_tool_choice.none: false`. Several other endpoints also lack `none`. Do not select providers solely because `tools` appears: the fourth final-only model call requires a validated way to disable tool choice. Relace is another low-price endpoint with `none`/`auto` true but forced/named choices false; it was observed, not selected.

The previous Qwen/GPT shortlist remains historical evidence in the preceding commits and is not the current experiment plan.

## Routing and reproducibility

For the recommended candidate, propose this provider configuration:

```json
{
  "model": "z-ai/glm-5.3-flash",
  "provider": {
    "order": ["open-inference/fp4"],
    "only": ["open-inference/fp4"],
    "allow_fallbacks": false,
    "require_parameters": true,
    "max_price": {"prompt": 0.01, "completion": 0.25}
  }
}
```

OpenRouter documents `only` as an allowlist, `order` as endpoint preference, `allow_fallbacks: false` as disabling fallback, and `require_parameters: true` as requiring all sent parameters to be supported. Full endpoint tags narrow a base-provider match. `max_price` uses USD per million tokens and filters provider prices; it is not a total experiment-spend cap. [Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)

Record the model ID, catalog canonical slug, endpoint tag, actual returned provider/model, timestamp, pricing snapshot/hash, and all request settings with each run. A routing constraint does not establish immutable model weights; the public slug, undocumented upstream changes, and unreported provider metadata remain reproducibility limitations. Requery the catalog and endpoints before freezing, and treat a detected provider/model change as a comparability issue rather than silently accepting it.

### Temperature is configurable; reasoning needs an explicit policy

The user accepted temperature **0.2**, top_p **1**, 12,000 maximum whole-request input tokens, 2,000 maximum output tokens, and a 60-second API attempt deadline. Endpoint metadata advertises the sampling parameters. More directly, Z.ai's official [Chat Completion OpenAPI](https://docs.z.ai/api-reference/llm/chat-completion.md) defines the GLM-5.3-Flash vision request with temperature range **0–1**, default 1, and top_p range **0.01–1**, default 0.95. It states that `do_sample` defaults true and setting it false makes temperature/top_p ineffective. Thus 0.2 is within the documented configurable range; it is not documented as a fixed-temperature-only model. Do not send unsupported provider parameters merely to mirror the native API.

The official [Flash model guide](https://docs.z.ai/guides/vlm/glm-5.3-flash) recommends temperature 1, top_p 0.95, and maximum reasoning, but describes them as recommended settings, not mandatory fixed values. It states thinking cannot be disabled. The OpenRouter model catalog independently reports reasoning `mandatory: true`, `default_enabled: true`, supported efforts `max`, `high`, `low`, default `max`.

Propose explicitly setting OpenRouter `reasoning.effort: "low"`, holding it fixed for both variants, and validating it in the smoke test. This extra reasoning choice is not yet user-confirmed. OpenRouter documents that reasoning is billed as output and on most providers shares the `max_tokens` budget with the visible answer; a small cap can be exhausted by reasoning alone. Preserve usage/finish reason and verify that the selected endpoint produces tool arguments and final code within the agreed 2,000-token budget. Excluding reasoning from a response does not stop its computation or billing. [Reasoning token controls](https://openrouter.ai/docs/guides/best-practices/reasoning-tokens)

No live sampling test was performed. Documentation and endpoint metadata establish supported configuration, not that a particular deployment honors every parameter in practice or that low temperature makes results deterministic.

## Agent-interface implications and smoke exit evidence

OpenRouter's client-tool protocol returns requested tool calls to the application; the application executes the tool and sends back its result. It documents `tool_choice: "auto"` and `"none"`, the latter matching the final-only fourth call. [Client tools](https://openrouter.ai/docs/guides/features/tool-calling)

The proposed `open-inference/fp4` endpoint does **not** advertise `parallel_tool_calls`; the `cohere` alternative does. Do not blindly send it with `require_parameters: true`; enforce the one-tool/remaining-call policy in the harness unless explicit endpoint support is verified. Do not request strict-schema features merely because tools are supported. Validate every argument against the local tool schema.

Before baseline, retain evidence of: a valid native tool request; candidate plus up to four structured examples; bounded tool-result feedback; a follow-up that uses the result; final-only `tool_choice: "none"`; raw final source accepted/rejected without repair; and usage/cost/provider metadata. Use a tiny functional smoke test, not repeated resampling until a benchmark answer passes. These behaviors are **untested in this research**. A failed interface smoke can justify selecting the alternative before freezing; changing after baseline requires restarting comparable experiments and retaining the abandoned evidence.

## Cost envelope and spending controls

Planning assumptions: 60 task trials × at most 4 logical model calls = 240 main calls; the accepted retry policy permits at most one retry per logical request and two retries per trial, giving at most **360 physical attempts for the main comparison**. A proposed separate allowance of 60 logical smoke/development calls, each conservatively reserving one retry, would raise the total envelope to **480 physical attempts**. Conservatively assume every attempt is charged. Each complete request history, tool schema, and feedback must fit a **12,000 input-token cap**, with 2,000 maximum completion tokens. Bound feedback and check the full accumulated input, not just the latest user message. Input-token accounting needs tokenizer validation; an estimate is not a hard token guarantee.

| Scenario | GLM/OpenInference fp4 | GLM/Cohere |
| --- | ---: | ---: |
| One maximum-size attempt | $0.0004594 | $0.00280 |
| 240 main attempts, no retries | $0.110256 | $0.6720 |
| 360 main attempts, including maximum accepted retries | $0.165384 | $1.0080 |
| 480 attempts including the unconfirmed development allowance | $0.220512 | $1.3440 |

These are arithmetic envelopes under the stated price/token assumptions, not spending guarantees. They omit checkout/payment fees, taxes, currency conversion spreads, unrelated key use, and extra services/plugins. No server-side search/plugin is needed. Recalculate if prices, caps, allowances, or retry counts change. A source-and-arguments byte cap does not enforce the full model-request token cap.

OpenRouter returns native token counts, cache details, and `usage.cost` automatically for non-streaming completions. Preserve the full non-secret usage object and distinguish provider-reported charges from estimates. Generation-ID lookup supplies later cost/provider metadata when an ID is available. [Usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting), [Generation metadata](https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation)

Use one dedicated project key with a provider-side USD spending cap, plus a local ledger/reservation before **every physical attempt**, including retries. Keep concurrency one for this small experiment. The ledger includes all development and smoke spend. On a lost response retain a worst-case charge reservation until reconciled; do not treat missing usage as free. OpenRouter documents per-key limits and an in-flight budget based on input plus allowed completion tokens; settlement occurs after completion and the in-flight estimate does not cover every possible non-token charge. [Credit and rate limits](https://openrouter.ai/docs/api_reference/limits)

CHF/USD conversion is intentionally **not frozen by this research**. Before paid work, record a dated primary-source FX rate (for example, the [Swiss National Bank data portal](https://data.snb.ch/en/topics/ziredev)), conversion direction, and allowance for fees/spreads. Set the provider USD cap conservatively below the CHF 15 ceiling. Treat CHF 10 as a recorded notification/checkpoint, not an automatic stop. The parent planning effort must confirm whether the CHF ceiling means API consumption or total cash paid for credits/fees.

## Proposed retry and timeout policy

Use non-streaming responses and explicit, application-owned retry accounting; disable hidden SDK retries. The user has accepted **one retry maximum per failed request and two retries maximum per trial**, outside the four logical model calls. Suggest a 10-second connect timeout and a 60-second overall attempt deadline, verified against the chosen HTTP client's timeout semantics. The 60-second overall deadline is user-accepted; the connect limit is an implementation suggestion. Neither duration is an OpenRouter guarantee. Keep the same rendered request/settings on a retry and retain attempt/error/cost records; never retry based on refusal, malformed model response, answer quality, source errors, tool mistakes, or truncation.

OpenRouter documents 408 timeouts, 429 rate limits, 502 invalid/down provider responses, and 503 unavailable providers; errors can also appear in a response body after HTTP 200. `Retry-After` may accompany 429/503 and a particular in-flight-budget 402. Empty responses can still incur prompt-processing charges. [Errors and debugging](https://openrouter.ai/docs/api_reference/errors-and-debugging)

Proposed classification: retry one eligible transient 429/5xx/explicit provider timeout within both the per-request and per-trial limits and cost reservation, honoring `Retry-After`; if the delay exceeds the configured run-time allowance, stop incomplete rather than shortening the required wait. Do not automatically retry malformed requests, credentials/permissions problems, or spent-credit/budget failures. For a disconnected/ambiguous request, preserve the potential charge and missing-response evidence; an allowed retry is another physical attempt, not proof that the first attempt did no work. No idempotency or exactly-once guarantee for generation was established by the consulted primary sources. Exhausted API attempts leave the evaluation run incomplete under the agreed scoring policy.

## Decision-ready conclusion

The selected model is `z-ai/glm-5.3-flash`; earlier Qwen/GPT recommendations are superseded. Temperature 0.2 is within Z.ai's documented configurable range and is advertised by the relevant OpenRouter endpoints. The proposed OpenInference fp4 endpoint satisfies the advertised `auto`/`none` requirement at a very low current token price; provider choice and explicit reasoning effort still require planning agreement and functional smoke evidence. The native Z.ai endpoint's lack of `none` is a reason to validate endpoint details rather than infer them from model-level tools support.

The user has accepted the 12k-input/2k-output, temperature/top_p, and 60-second attempt settings, plus one retry per failed request and two per trial. All paid calls share a project ledger, unknown charges retain reservations, the CHF 10 checkpoint continues automatically, and new attempts must stay within the CHF 15 ceiling. The separate development allowance remains unconfirmed. No paid call or behavioral compatibility test occurred during this research.
