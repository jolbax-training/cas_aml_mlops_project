# Design

## Context

See proposal.md for motivation and the user-directed sequencing adjustment. The repository uses Python 3.12, uv, and pytest; it has six project Markdown documents, an offline evaluator, and no reporting implementation. `report/`, local runs, and MLflow storage are already ignored. The documentation still says no remote is configured although `origin` was subsequently set; implementation must reconcile that factual status without claiming any push or CI run occurred.

This change builds a view over documentation and evidence, not an execution interface. It can precede the local-loop milestone because generation and viewing need none of the depicted services. CI and MLflow implementation remain later work.

## Goals / Non-Goals

**Goals:** A single portable HTML document, architecture visible first, understandable local/later boundaries, accessible navigation, faithful rendering, explicit provenance, and deterministic validation of content and privacy boundaries.

**Non-Goals:** Calling model APIs, executing candidate code, running Podman, querying MLflow/GitHub, implementing the evaluator loop, automatic publishing, live dashboards, editor features, search, or benchmark expansion. The report does not independently establish that a Markdown claim is true.

## Decisions

### 1. Build once with Python; view a self-contained HTML file

Add a standalone `scripts/build_work_log.py`, invoked from the repository root as `.venv/bin/python scripts/build_work_log.py`. This generates `report/index.html` and validates it before replacing the previous output. Add `--check` to render and validate in memory without writing output; malformed inputs or links return nonzero with source locations. This mode validates current sources, not the freshness of a previously generated file. Writes are limited to generated output; failed builds leave the last successful report unchanged.

Use a maintained Markdown parser such as markdown-it-py with raw HTML disabled, table support, and explicit link handling; pin the chosen dependency through uv in the dev group. Use standard-library TOML/JSON parsing and SVG generation. Initial dependency installation may need network access, but builds and checks after environment setup must not. No JavaScript, CDN, web fonts, fetch calls, network checks, or local HTTP server. Embed CSS and SVG. Display build time, source paths, and source hashes. Unchanged sources produce identical content except the explicit build timestamp.

A site framework or client-rendered Markdown would add deployment or browser/runtime dependencies; a hand-written Markdown parser would make correct rendering and link handling harder. One HTML file supports offline opening and copying; it is a generated snapshot, so sources must be rebuilt after edits.

### 2. Explicit source manifest; no recursive repository harvesting

Add `docs/work_log.toml` with ordered section IDs/titles, exact source paths, optional selected heading ranges, section roles (current/historical/personal), and explicit pending sections. Keep content in its existing Markdown file. The manifest contains structure and labels, not duplicate narrative or hand-maintained metrics.

Initial source selection:

| Section | Source and treatment |
| --- | --- |
| Status and dated decisions | `docs/progress.md`, current status first after diagram/navigation |
| Goal, scope, plan, and acceptance | `docs/project_spec.md` |
| Setup and reproduction | `README.md` |
| Pilot and benchmark context | `docs/pilot_tasks.md` |
| Benchmark independent review | Pending until a real review record is registered |
| Experiment results and comparison | Pending until real result records are registered |
| Learning notes | Explicitly selected September journal entries, retaining their supersession context and unfinished prompts; additional entries require manifest selection |
| Historical ideas | `docs/project_ideas.md`, visibly labeled historical |
| Change planning | Explicitly registered proposal/design/spec/tasks Markdown for this change, labeled planned work |

Render sources as sections in the same HTML; users do not have to open raw Markdown to read them. Preserve tables, code blocks, checklists, dates, and historical labels. Journal selections reference existing headings/ranges, never copied passages. Missing selected headings are errors. The initial journal contains no completed personal reflections; show its prompts as unfinished and never fill them automatically. Include its supersession notice alongside selected entries.

New review/result documents are registered explicitly. Empty evidence sections display “Pending — no record registered”; a registered file that disappears is a build error, not silently pending. CI URLs and MLflow run IDs appear only when recorded in approved sources. The report's renderer neither synthesizes scores nor queries services to fill gaps.

### 3. Diagram source is a small declarative graph rendered to inline SVG

Add checked-in `docs/architecture.json` defining node IDs, labels, phase/status labels, lane/row positions, and typed labeled edges. The builder uses a constrained grid/lane renderer with explicit line routing to produce SVG shapes and escaped text; no arbitrary SVG fragments, HTML, scripts, or executable expressions are accepted. Changes to this architecture source update the SVG and its textual equivalent together. Reject duplicate IDs, dangling edges, unknown phases, and invalid layout values.

The first visible main content is the architecture figure with its integrated goal title: “Reproducible MLOps evaluation and evidence”. No status table, prose introduction, or large navigation block precedes it. A keyboard skip link may appear on focus. Keep diagram labels legible rather than shrinking everything to fit; provide responsive horizontal scrolling on narrow screens and a complete text equivalent immediately beneath the figure.

Use labeled lanes and borders, not color alone:

- **Local milestone — laptop:** benchmark/versioned prompt; generation orchestration; contract validation/trusted evaluator; isolated Podman execution; trusted scoring; saved local bundles and replay; baseline/revised comparison.
- **External model service:** OpenRouter, explicitly contacted only by generation; no sandbox-to-service edge.
- **Later integration — after local loop works:** GitHub Actions deterministic checks and MLflow experiment tracking.
- **Project understanding and evidence:** editable Markdown and local work log/report, available independently of the other components.

Required graph relationships:

| From | To | Meaning |
| --- | --- | --- |
| Versioned benchmark instruction/signature + versioned prompt | Generation agent ↔ OpenRouter | Request and candidate response; expected answers excluded |
| Candidate | Contract validation / trusted evaluator | Static acceptance or labeled rejection |
| Trusted evaluator | Podman sandbox | Accepted source and one case's inputs |
| Podman sandbox | Trusted scoring | Returned value, post-call arguments, execution status |
| Benchmark expected answers | Trusted scoring | Trusted comparison outside sandbox |
| Contract rejection | Saved local bundle | Failure recorded without execution |
| Generation + trusted scoring | Saved local requests/responses/results | Inspectable run evidence |
| Saved candidate/response bundle | Replay → trusted evaluator | Re-evaluate without API generation; Podman still needed for execution replay |
| Baseline + revised results | Comparison | Gains, regressions, unchanged outcomes, limitations |
| Versioned fixtures, benchmark, evaluator | Later GitHub Actions | Deterministic checks, not automatic paid generation |
| Saved local bundles | Later MLflow | Parameters, metrics, artifacts after local persistence |
| Comparison, CI/MLflow references, dated progress | Editable Markdown | Reviewed summaries and evidence references |
| Approved Markdown + architecture source | Work log/report | Offline generated view |

Show the Podman trust boundary explicitly: expected answers, scoring, repository files, and credentials stay outside. Distinguish “implemented pilot”, “planned local”, and “planned later” in the initial graph; the diagram describes an intended system, not a claim that every component works. Include a legend and update diagram status as part of future architecture changes.

Accessibility: SVG `role="img"`, title and description, adequate contrast, scalable labels, and an HTML node/flow summary derived from the same source. Semantic headings, visible focus, skip link, and document navigation support keyboard use; no interactive diagram controls are necessary.

### 4. Rewrite and validate links against approved inputs

Give document sections stable IDs from the manifest and prefix heading IDs with the section ID. Apply deterministic duplicate-heading suffixes. Resolve each relative Markdown link from its source file, decode/normalize it, then rewrite links to included documents/headings into in-page anchors. A link to a selected-out private journal section is shown as omitted plain text rather than exposing that source.

For referenced non-Markdown project files (such as pilot JSON, evaluator tests, or OpenSpec YAML), require an explicit text-reference allowlist in the manifest; render escaped text appendices within the same HTML and rewrite links to those appendices. No automatic copying or traversal of linked files. Require all local references to be either selected sources, allowlisted appendices, or explicitly omitted references with a reason; other missing/unapproved references fail the build. Future raw run bundles remain excluded; authors add reviewed summaries rather than link directly into private artifacts.

Permit external `https` and explicit loopback `http` links for locally served MLflow evidence. They are clickable references labeled “external” or “local service; availability not checked”, never loaded automatically. Reject credential-bearing URLs, dangerous schemes, absolute filesystem paths, and paths/symlinks escaping the repository. Validate internal fragment targets and all approved local paths without fetching external URLs.

### 5. Treat rendered input as data and constrain inclusion

Only the manifest's reviewed Markdown/text sources and architecture definition are read. Deny `.git/`, `.env*`, credential/key files, secrets directories, virtual environments, machine/editor state, raw run/artifact directories, and MLflow stores even if accidentally selected; explicitly marked private sources are also denied. Enforce path checks after normalization and symlink resolution, including link destinations. Do not read environment variables or logging configuration into the report.

Render candidate snippets and raw HTML as escaped text. Suppress external images/resources; show alt text instead. The architecture renderer is the only SVG source. Use a restrictive HTML content-security policy with scripts/connect/object/frame/media disabled, inline styles allowed, and no automatic remote resource loading. Deny credentials embedded in URLs and detect recognizable token/private-key patterns in selected content; fail with file/line diagnostics that never echo the secret. Scanning is defense in depth, not a guarantee: allowlisting and author review remain necessary for prose that may contain private information.

The generated snapshot can contain benchmark answers for the local author; it must never be sent to the generation agent or mounted into its sandbox. Building/viewing does not execute candidates or read credential stores.

## Risks / Trade-offs

- **Stale or contradictory Markdown claims** → retain provenance and historical labels; reconcile known status/sequencing text during implementation; generation does not certify factual correctness.
- **Graph grows beyond a legible diagram** → use coarse components and constrained lanes, a single graph source, and visual acceptance checks; defer interactive features.
- **Allowlist needs updates as evidence grows** → document registering source files; failures identify the missing selection rather than silently collecting new files.
- **Private prose can evade token patterns** → explicit selection, private-path rejection, author review, and no automatic publishing; never claim perfect secret detection.
- **Single-file snapshots can grow** → include curated summaries and small text references, exclude raw bundles; pagination is outside this change.
- **External CI/MLflow links unavailable offline** → keep descriptions/run identifiers in Markdown and render them locally; label link availability as unchecked.

## Migration Plan

Implement the builder, manifest, diagram source, and focused tests; register current approved documents and pending evidence sections. Update README instructions and the current plan/progress/OpenSpec context to record the report-first foundation as the latest user-directed sequencing decision. Reconcile the now-configured origin and the existence of this proposal; preserve historical entries rather than rewriting their dates or decisions. Keep generated output ignored and review selections before the first build.

Verify build/check, offline browser rendering, navigation, and privacy fixtures. Rollback removes the reporting additions and generated HTML; the authoritative source documents and evaluator continue to work independently. No live service migrations are involved.
