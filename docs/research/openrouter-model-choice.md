# OpenRouter model choices and budget inputs

Research snapshot: 2026-10-23, approximately 15:30 UTC. Planning evidence only; no paid or authenticated API calls were made. This file belongs to a throwaway research branch and is not an implementation change.

## Recommendation

Start the functional smoke test with **`qwen/qwen3-coder-flash` through the `alibaba` endpoint**. Keep **`openai/gpt-4.1-mini` through `openai`** as a pre-baseline alternative if the first candidate fails the tool-interface smoke test. Choose one before the main baseline and use it for both prompt variants; do not switch automatically during a comparison. This recommendation is an inference from documented capabilities and price, not measured task accuracy or a claim that either model has passed this project's tests.

### Verified shortlist

Unauthenticated `GET` requests to OpenRouter's [Models API](https://openrouter.ai/api/v1/models) and each model's endpoint API produced the following snapshot. Endpoint prices are USD per million native tokens, converted here from the API's per-token values.

| Candidate | Fixed endpoint tag | Input / output | Advertised tool support | Snapshot detail |
| --- | --- | --- | --- | --- |
| `qwen/qwen3-coder-flash` | `alibaba` | $0.195 / $0.975 | `tools`, `tool_choice`; `none`, `auto`, `required`, named function | 1,000,000 context; 65,536 maximum completion; tokenizer family Qwen3 |
| `openai/gpt-4.1-mini` | `openai` | $0.40 / $1.60 | `tools`, `tool_choice`; `none`, `auto`, `required`, named function | 1,047,576 context; 32,768 maximum completion; catalog canonical slug `openai/gpt-4.1-mini-2025-04-14` |

Sources: [Qwen endpoint response](https://openrouter.ai/api/v1/models/qwen/qwen3-coder-flash/endpoints), [GPT endpoint response](https://openrouter.ai/api/v1/models/openai/gpt-4.1-mini/endpoints). The [Qwen model page](https://openrouter.ai/qwen/qwen3-coder-flash) and [GPT model page](https://openrouter.ai/openai/gpt-4.1-mini) independently show these base prices. Qwen's endpoint additionally advertises cache-write pricing of $0.24375/M and higher token-price tiers beginning at 32,000 and 128,000 prompt tokens. The small-input proposal below stays below those tiers.

## Routing and reproducibility

For the recommended candidate, propose this provider configuration:

```json
{
  "model": "qwen/qwen3-coder-flash",
  "provider": {
    "order": ["alibaba"],
    "only": ["alibaba"],
    "allow_fallbacks": false,
    "require_parameters": true,
    "max_price": {"prompt": 0.25, "completion": 1.0}
  }
}
```

OpenRouter documents `only` as an allowlist, `order` as endpoint preference, `allow_fallbacks: false` as disabling fallback, and `require_parameters: true` as requiring all sent parameters to be supported. Full endpoint tags narrow a base-provider match. `max_price` uses USD per million tokens and filters provider prices; it is not a total experiment-spend cap. [Provider routing](https://openrouter.ai/docs/guides/routing/provider-selection)

Record the model ID, catalog canonical slug, endpoint tag, actual returned provider/model, timestamp, pricing snapshot/hash, and all request settings with each run. A routing constraint does not establish immutable model weights; the public slug, undocumented upstream changes, and unreported provider metadata remain reproducibility limitations. Requery the catalog and endpoints before freezing, and treat a detected provider/model change as a comparability issue rather than silently accepting it.

Both candidates advertise `temperature`, `top_p`, and `max_tokens`. Proposed fixed settings are temperature 0.2, top_p 1, maximum 2,000 output tokens, and no seed. These are planning defaults to validate in the smoke test, not quality-optimal settings. Low temperature does not establish determinism.

## Agent-interface implications and smoke exit evidence

OpenRouter's client-tool protocol returns requested tool calls to the application; the application executes the tool and sends back its result. It documents `tool_choice: "auto"` and `"none"`, the latter matching the final-only fourth call. [Client tools](https://openrouter.ai/docs/guides/features/tool-calling)

The endpoint snapshots do **not** advertise `parallel_tool_calls`. Do not blindly send it with `require_parameters: true`; enforce the one-tool/remaining-call policy in the harness unless explicit endpoint support is verified. Do not request strict-schema features merely because tools are supported. Validate every argument against the local tool schema.

Before baseline, retain evidence of: a valid native tool request; candidate plus up to four structured examples; bounded tool-result feedback; a follow-up that uses the result; final-only `tool_choice: "none"`; raw final source accepted/rejected without repair; and usage/cost/provider metadata. Use a tiny functional smoke test, not repeated resampling until a benchmark answer passes. These behaviors are **untested in this research**. A failed interface smoke can justify selecting the alternative before freezing; changing after baseline requires restarting comparable experiments and retaining the abandoned evidence.

## Cost envelope and spending controls

Planning assumptions: 60 task trials × at most 4 logical model calls = 240 main calls; allow a separate maximum of 60 logical calls for smoke/development; at most one transport retry per logical call. This yields at most **600 physical attempts**, conservatively assuming every attempt is charged. Each complete request history, tool schema, and feedback must fit an **8,000 input-token planning cap**, with 2,000 maximum completion tokens. Bound feedback and check the full accumulated input, not just the latest user message. Input-token accounting needs tokenizer validation; an estimate is not a hard token guarantee.

| Scenario | Qwen, base input price | Qwen, conservative cache-write input price | GPT/OpenAI |
| --- | ---: | ---: | ---: |
| One maximum-size attempt | $0.00351 | $0.00390 | $0.00640 |
| 240 main attempts, no retries | $0.8424 | $0.9360 | $1.5360 |
| 600 attempts including the proposed allowance/retries | $2.1060 | $2.3400 | $3.8400 |

These are arithmetic envelopes under the stated price/token assumptions, not spending guarantees. They omit checkout/payment fees, taxes, currency conversion spreads, unrelated key use, and extra services/plugins. No server-side search/plugin is needed. Recalculate if prices, caps, allowances, or retry counts change. A source-and-arguments byte cap does not enforce the full model-request token cap.

OpenRouter returns native token counts, cache details, and `usage.cost` automatically for non-streaming completions. Preserve the full non-secret usage object and distinguish provider-reported charges from estimates. Generation-ID lookup supplies later cost/provider metadata when an ID is available. [Usage accounting](https://openrouter.ai/docs/cookbook/administration/usage-accounting), [Generation metadata](https://openrouter.ai/docs/api/api-reference/generations/get-request-&-usage-metadata-for-a-generation)

Use one dedicated project key with a provider-side USD spending cap, plus a local ledger/reservation before **every physical attempt**, including retries. Keep concurrency one for this small experiment. The ledger includes all development and smoke spend. On a lost response retain a worst-case charge reservation until reconciled; do not treat missing usage as free. OpenRouter documents per-key limits and an in-flight budget based on input plus allowed completion tokens; settlement occurs after completion and the in-flight estimate does not cover every possible non-token charge. [Credit and rate limits](https://openrouter.ai/docs/api_reference/limits)

CHF/USD conversion is intentionally **not frozen by this research**. Before paid work, record a dated primary-source FX rate (for example, the [Swiss National Bank data portal](https://data.snb.ch/en/topics/ziredev)), conversion direction, and allowance for fees/spreads. Set the provider USD cap conservatively below the CHF 15 ceiling. Treat CHF 10 as a recorded notification/checkpoint, not an automatic stop. The parent planning effort must confirm whether the CHF ceiling means API consumption or total cash paid for credits/fees.

## Proposed retry and timeout policy

Use non-streaming responses and explicit, application-owned retry accounting; disable hidden SDK retries. Suggest **one retry maximum per logical call**, a 10-second connect timeout and a 60-second overall attempt deadline, verified against the chosen HTTP client's timeout semantics. Those durations are project recommendations, not OpenRouter guarantees. Keep the same rendered request/settings on a retry and retain attempt/error/cost records; never retry based on answer quality, source errors, tool mistakes, or truncation.

OpenRouter documents 408 timeouts, 429 rate limits, 502 invalid/down provider responses, and 503 unavailable providers; errors can also appear in a response body after HTTP 200. `Retry-After` may accompany 429/503 and a particular in-flight-budget 402. Empty responses can still incur prompt-processing charges. [Errors and debugging](https://openrouter.ai/docs/api_reference/errors-and-debugging)

Proposed classification: retry one eligible transient 429/5xx/explicit provider timeout within the cost reservation, honoring `Retry-After`; if the delay exceeds the configured run-time allowance, stop incomplete rather than shortening the required wait. Do not automatically retry malformed requests, credentials/permissions problems, or spent-credit/budget failures. For a disconnected/ambiguous request, preserve the potential charge and missing-response evidence; an allowed retry is another physical attempt, not proof that the first attempt did no work. No idempotency or exactly-once guarantee for generation was established by the consulted primary sources. Exhausted API attempts leave the evaluation run incomplete under the agreed scoring policy.

## Decision-ready conclusion

The documented token costs leave room within the proposed CHF budget for this small experiment, conditional on enforcing token/attempt caps and converting the cap before paid work. Qwen/Alibaba is the recommended first smoke candidate. The model choice, exact settings, retry/timeout policy, cost-accounting interpretation, and development-call allowance remain user decisions; researched API facts do not settle them automatically.
