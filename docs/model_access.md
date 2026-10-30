# Model access and spending ledger (offline-tested; no live result yet)

Code: `openrouter_config.py`, `openrouter_client.py`, `ledger.py`, `openrouter_cli.py`; versioned config `src/codegen_eval/model_configs/openrouter_glm_v1.json` (hash recorded in each bundle's `identity.model`). Everything is tested with a fake transport; no paid call has been made and the smoke test is **not run**.

- **Pinning:** `z-ai/glm-5.3-flash`, provider `open-inference/fp4` (order + only), fallbacks off, require-parameters on, temperature 0.2, top-p 1, reasoning `low`, 2,000 output / 12,000 input tokens, 60 s per attempt. The final-only call sends `tool_choice: none` and resends the tool definitions so history stays valid on the wire (to confirm in the smoke test).
- **Pre-send check:** conservative bound = request bytes (over-counts) + 8 per message; over 12,000 is rejected before reservation or sending (`request_rejected`). The default bound is provable but may reject real trials; `input_bound_bytes_per_token` may only be raised after calibrating against reported `prompt_tokens`.
- **Retries:** timeouts, connection errors, HTTP 408/429/5xx (and such codes inside a 200 body); one per request, two per trial, backoff 1 s doubling to 8 s (Retry-After honoured, capped 10 s). Refusals, malformed or truncated output, 4xx are never retried. No SDK is used.
- **Ledger:** append-only JSON lines outside Git, default `~/.codegen_eval/spend_ledger.jsonl` (override `CODEGEN_EVAL_LEDGER` or `--ledger`). Reservation is fsynced before each send; checkpoint (CHF 10) and ceiling (CHF 15) use committed + reservations. Uncertain charges (timeout, error, missing usage) keep their reservation. Inputs: a pricing file (`docs/openrouter_pricing.example.json`; fx, margin and fees must be filled and rechecked).
- **Attempt records:** each physical attempt is stored in the trial record (`attempts`, `reservation`, `latency_ms`, `errors`) and the incremental call log; missing fields are listed in `missing_fields`; no credential is stored.
- **Reproducibility limit:** a fixed model identifier does not guarantee immutable upstream weights; returned model/provider are recorded per attempt.

Smoke command (spends money; refuses without both):

    export OPENROUTER_API_KEY=...
    .venv/bin/python -m codegen_eval.openrouter_cli smoke --pricing ~/prices.json --i-accept-cost
