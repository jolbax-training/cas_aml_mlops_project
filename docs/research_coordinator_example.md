# Worked example: evaluating a research coordinator

> **Status: design only.** This orchestrator was **not built and not executed**. No worker ran, **no independent verification occurred**, and **no LLM judge is calibrated**. Every trace below is **ILLUSTRATIVE** (invented to show the format), and every grader or rubric is a **PROPOSED** design. The only real material is the cited research, used as a labelled evidence fixture (see [Evidence fixtures](#evidence-fixtures-and-provenance)). It applies the [evaluation design guide](evaluation_design_guide.md); terms follow [GLOSSARY.md](../GLOSSARY.md).

## The system under evaluation

```text
Coordinator splits the research request into work items
  Item A (model controls):          worker --> independent verifier
  Item B (provider compatibility):  worker --> independent verifier
  Item C (pricing/budget):          worker --> independent verifier
Final check across all items
```

**Request (illustrative framing):** "Recommend how to configure a low-cost OpenRouter model for a bounded coding agent within a fixed budget."

| Part | Input | Output |
| --- | --- | --- |
| **Coordinator** | The research request | Three work items, each with a requirement; later the combined recommendation |
| **Work item A: model controls** | Requirement: which sampling/reasoning controls the model documents and their ranges | Worker findings with citations |
| **Work item B: provider compatibility** | Requirement: which routed providers support the needed controls and tool calling | Worker findings with citations |
| **Work item C: pricing/budget accounting** | Requirement: documented prices, limits, and how cost would be reserved and counted | Worker findings with citations |
| **Worker** (one per item) | Its item's requirement and allowed search/read capabilities | Result plus citations |
| **Independent verifier** (one per item) | **Fresh context**: only the item's requirement and the worker's output/citations | Verdict `pass`, `needs revision`, or `unverifiable`, with the evidence it checked |
| **Final check** | All item results and verdicts | Report on coverage, unresolved verification failures, and cross-item contradictions |

### Verifier independence (design rules)

- The verifier starts with a fresh context and **never sees the worker's conversation**.
- It **independently inspects the cited sources** (fetching them itself) rather than trusting quotes in the worker output.
- Worker confidence or fluent prose is **not proof**; only evidence the verifier found counts.
- A different model is **not required**; independence comes from the clean context and its own source inspection.
- Verdicts: `pass` (claims supported), `needs revision` (claim contradicted or insufficiently supported, with what was wrong), `unverifiable` (sources unavailable, paywalled, or claim not checkable, with what was tried).

### Final check (design rules)

Assess (1) **coverage**: all items have a result and a recorded verdict; (2) **unresolved verification failures**: no `needs revision` or `unverifiable` remains hidden in the recommendation; (3) **contradictions across items**: the combined recommendation does not rely on mutually incompatible item results.

## Scenario template

Each scenario gives five things: **inputs**, **capabilities**, **expected outcome and failure handling**, **graders**, **trace evidence**. Graders are tagged **[observable]** (deterministic, checks recorded facts) or **[rubric]** (subjective quality, PROPOSED, needs validation).

**Validation approach for any rubric (PROPOSED, not performed):** have a person label a small held-out set of outputs; compare the judge or second reviewer against those labels; record agreement and disagreements; keep it advisory until agreement is acceptable. Until then it is **uncalibrated**.

**Shared capabilities:** the coordinator can create items and read results; a worker can search and read web sources; a verifier can fetch sources but cannot see the worker conversation; a ledger records every call's reserved cost.

## Scenario 1: Normal completion

- **Inputs:** The request above; three well-defined items; reachable sources.
- **Capabilities:** Shared capabilities; budget sufficient.
- **Expected outcome:** Each item gets a worker result with citations and a `pass`; the final check reports full coverage, no unresolved failures, no contradictions; the coordinator emits a combined recommendation.
- **Graders:**
  - [observable] Three items exist; each has a result, at least one citation, and a recorded verdict.
  - [observable] Each verifier record shows its inputs contained only the requirement and worker output/citations.
  - [observable] Final-check report present with all three assessments filled.
  - [rubric, PROPOSED] Recommendation is clear and uses all item results (validate as above).
- **Trace evidence required:** Item list; per-item worker output and citations; per-item verifier input and verdict with sources inspected; final-check report; ledger totals.

**Illustrative trace (ILLUSTRATIVE, not executed):**

```text
coordinator: items=[A,B,C]
A worker -> result+2 citations ; A verifier(fresh) fetched 2 sources -> pass
B worker -> result+2 citations ; B verifier(fresh) fetched 2 sources -> pass
C worker -> result+3 citations ; C verifier(fresh) fetched 3 sources -> pass
final check: coverage 3/3, unresolved 0, contradictions 0 -> recommendation emitted
```

## Scenario 2: Missing work item

- **Inputs:** The coordinator's split omits item C (pricing/budget) though the request needs it.
- **Capabilities:** Shared capabilities.
- **Expected outcome:** The final check flags coverage 2/3 and names the uncovered requirement; the coordinator either creates the missing item or reports the gap; the recommendation must not present itself as complete.
- **Graders:**
  - [observable] Final-check coverage count is below the number of requirement areas and the missing area is named.
  - [observable] No final recommendation is marked complete while coverage is incomplete.
  - [rubric, PROPOSED] The stated gap is accurate and actionable.
- **Trace evidence required:** Original requirement areas; the item list; final-check coverage section; whether the item was added afterwards.

**Illustrative trace (ILLUSTRATIVE):** `items=[A,B]; A pass; B pass; final check: coverage 2/3 (missing: pricing/budget accounting) -> incomplete`.

## Scenario 3: Unsupported worker claim

- **Inputs:** Worker A states a control is supported with a given range, citing a page that does not say so.
- **Capabilities:** Shared capabilities; the verifier can fetch the cited page.
- **Expected outcome:** The verifier, working from fresh context and its own fetch, returns `needs revision` (page contradicts or lacks the claim) or `unverifiable` (page cannot be read), with the evidence it checked. The claim is not carried into the final result unflagged.
- **Graders:**
  - [observable] Verdict is not `pass`; evidence field lists the source inspected and what it showed.
  - [observable] The unsupported claim is absent from the recommendation or marked unresolved.
  - [observable] Verifier input lacked the worker conversation and worker confidence statements.
  - [rubric, PROPOSED] The verifier's explanation is accurate (validate against human labels).
- **Trace evidence required:** Worker claim and citation; verifier input; fetched source excerpt/identifier; verdict and reasoning.

**Illustrative trace (ILLUSTRATIVE):** `A worker: "temperature range 0-2 [cite X]"; A verifier fetched X: states 0-1 -> needs revision (claim contradicted by X)`.

## Scenario 4: Conflicting item results (items pass individually but combine inconsistently)

- **Inputs:** Item A passes with "use temperature 0.2". Item B passes with "the only compatible provider ignores sampling controls". Each is individually supported by its own sources.
- **Capabilities:** Shared capabilities.
- **Expected outcome:** Both verifiers return `pass`, because each item is correct in isolation. Only the **final check** detects that the combined recommendation (set temperature 0.2 *and* use that provider) is inconsistent, reports the contradiction naming both items, and prevents a clean recommendation.
- **Graders:**
  - [observable] Per-item verdicts are both `pass` (confirms the case is constructed correctly).
  - [observable] Final-check contradiction list names items A and B; recommendation is flagged unresolved.
  - [rubric, PROPOSED] The described contradiction is genuine and not spurious (validate as above; also test on combinations with no real conflict to measure false alarms).
- **Trace evidence required:** Both item results and verdicts; final-check contradiction section; the combined statement being checked.

**Illustrative trace (ILLUSTRATIVE):** `A pass; B pass; final check: contradiction(A: set temperature 0.2, B: provider ignores sampling controls) -> not consistent`.

## Scenario 5: Worker or verifier failure

- **Inputs:** Worker B times out on its search, or verifier C errors before returning a verdict.
- **Capabilities:** Shared capabilities; a bounded retry policy (PROPOSED: one retry per failed call and a small per-run retry cap, mirroring the coding-agent project's rule of one retry per request and at most two per trial, where exhausted retries make the run incomplete).
- **Expected outcome:** A transient failure is retried within the bound; if it still fails the item is recorded as **incomplete (infrastructure)** rather than as a quality failure or a pass. The final check reports the unresolved item and the recommendation is not presented as verified.
- **Graders:**
  - [observable] The failed call, retry count, and final status are recorded.
  - [observable] Retries do not exceed the bound.
  - [observable] An item without a verdict is never counted as `pass`; denominator remains three with the incomplete item listed.
- **Trace evidence required:** Error type and attempt log; retry decisions; item status; final-check unresolved list.

**Illustrative trace (ILLUSTRATIVE):** `B worker: timeout; retry 1: timeout -> B incomplete(infrastructure); final check: unresolved=[B] -> not verified`.

## Scenario 6: Budget exhaustion

- **Inputs:** A small shared budget that is exhausted partway through (after items A and B).
- **Capabilities:** Shared ledger with reserve-before-call and a hard ceiling.
- **Expected outcome:** Calls that would exceed the ceiling are not made; remaining items are marked **not run (budget)**; the final check reports reduced coverage and the coordinator says the result is partial. Spending never exceeds the ceiling.
- **Graders:**
  - [observable] Ledger total at or below the ceiling; no call recorded after the stop.
  - [observable] Unfinished items listed as not run with reason; coverage below 3/3 is reported.
  - [observable] No claim about unfinished items appears in the recommendation.
- **Trace evidence required:** Ledger entries with reservations; the stop event; item statuses; final-check coverage.

**Illustrative trace (ILLUSTRATIVE):** `ledger: A 40%, B 45%; reserve for C would exceed ceiling -> C not run(budget); final check: coverage 2/3 -> partial`.

## Applying the guide's seven steps

| Step | In this example |
| --- | --- |
| 1. Success | Complete, verified, mutually consistent recommendation, or an honest statement of what is incomplete |
| 2. Scenarios | The six above, fixed in advance; scenario 4 is the deliberate cross-item case |
| 3. Graders | Observable checks first; rubrics PROPOSED for subjective quality only |
| 4. Validate | Known-good and known-bad fixtures per grader (e.g. scenario 3's contradicted claim must not `pass`); rubrics need a human-labelled set |
| 5. Trace evidence | Items, verifier inputs/verdicts with sources inspected, final-check report, ledger |
| 6. Denominators | Three items per run; incomplete and not-run items listed, never dropped or counted as pass |
| 7. Variability | If ever built: repeat each scenario, report counts, and decide keep/reject against step 1 |

## Evidence fixtures and provenance

Existing research can supply **evidence fixtures** (real source material a worker's claims could be compared against). It was **not** produced by this coordinator workflow, and no verification by independent verifiers has happened on it.

- **Fixture:** OpenRouter model-choice research, retained on throwaway branch `research/openrouter-model-choice`, commit `44d1fff8e7d5c947c56c50e4fec355f47991f08a` ([findings file](https://github.com/jolbax-training/cas_aml_mlops_project/blob/44d1fff8e7d5c947c56c50e4fec355f47991f08a/docs/research/openrouter-model-choice.md)). Provenance and limits are recorded in [progress](progress.md) and the [specification](project_spec.md): it verifies *documented* temperature/tool controls and provider differences and is a **dated snapshot**, not a live smoke result or a permanent price guarantee.
- **Use:** Item A, B and C ground-truth material for judging whether a worker claim is supported (for example, the documented temperature range or provider differences). Example claims it could support (qualitative, from [the specification](project_spec.md)): item A, temperature is configurable and GLM reasoning is mandatory, defaulting to max when not explicitly controlled; item B, providers differ in documented support, with behaviour at the routed endpoint untested; item C, prices are a dated snapshot. No numbers from it are reproduced here to avoid presenting a stale snapshot as current.

## Not claimed

The orchestrator was not implemented or run; no verifier executed; no judge is calibrated; the traces are invented; building a second system is out of scope ([specification](project_spec.md#transferable-evaluation-design-guide-and-example)).
