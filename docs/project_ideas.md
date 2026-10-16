# Code Generation Agent — MLOps Project

> Historical brainstorming. The current decisions and open questions are in [the working project spec](project_spec.md). Where the two files differ, follow the spec.

## Goal
Build a Python function generation agent with automated evaluation pipeline and CI/CD integration.

## Agent Specification
- **Type**: Code generation (LLM-based)
- **API**: OpenRouter (OpenAI-compatible)
- **Task**: Generate Python functions from natural language descriptions
- **Scope**: Python functions only (no multi-file, no external dependencies)

## Evaluation Strategy

### Core Eval Criteria
- **Syntactic Correctness**: Generated code is valid Python
- **Functional Correctness**: Code executes and produces expected output
- **Edge Cases**: Handles boundary inputs (empty, None, large values)
- **Code Quality**: Reasonable complexity, follows conventions

### Test Framework
- **PyTest**: Run generated code against test cases, verify output
- **DeepChecks**: Validate code quality (e.g., detect overly complex functions)
- **Metrics tracked**: Pass rate, syntax errors, execution time, test coverage

## MLOps Stack (Labs)

| Lab | Component | Purpose |
|-----|-----------|---------|
| **Lab 04** | PyTest + GitHub Actions | Automated eval on commits, gating |
| **Lab 04** | DeepChecks | Output quality validation |
| **Lab 03** | MLflow | Track eval metrics across agent versions |
| Lab 06 (optional) | DVC | Version test datasets |

## Project Phases

1. **Agent MVP** — Basic prompt + function generation
2. **Eval Suite** — PyTest harness to execute and grade generated code
3. **CI/CD Pipeline** — GitHub Actions to run evals on every commit
4. **Metrics Tracking** — MLflow logging of pass rates, errors
5. **Iteration** — Improve agent prompt/model based on eval failures

## Implementation Patterns (from Labs)

- **Env management**: conda `env.yaml` (Lab 03/04 pattern)
- **Metrics logging**: MLflow tracking API (Lab 03)
- **Test structure**: pytest fixtures for code execution (Lab 04)
- **CI/CD workflow**: GitHub Actions on commits/PRs (Lab 04)

## Open Questions
- Test dataset size? (100, 500, 1000 test cases)
- Agent iteration scope? (tune prompts, swap models, both)
- Success threshold for PR? (e.g., 90% pass rate)
- Which OpenRouter model? (Mistral, CodeLlama, etc.)
