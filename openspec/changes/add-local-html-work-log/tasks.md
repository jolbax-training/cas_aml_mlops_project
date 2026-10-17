# Tasks

All tasks are proposed and unstarted. Implement only after this change is reviewed and the user asks to apply it. The report foundation is independent of the local-loop milestone; CI/MLflow integration remains later work.

## 1. Source selection and local build boundary

- [ ] 1.1 Add `docs/work_log.toml` with the ordered current-source selections, selected journal entries and supersession context, pending benchmark-review/results/CI/MLflow sections, planned change artifacts, and explicit safe text references from the design; verify each registered path/heading exists and no raw/private artifact is selected.
- [ ] 1.2 Add the standalone Python builder entry point and lock its Markdown development dependency through uv; verify the environment can run the entry point without importing the evaluator or requiring service credentials.
- [ ] 1.3 Implement manifest/path validation and privacy exclusions before content reads; test traversal, URL-encoded escapes, symlink escapes, credential files, raw bundles, private sources, and missing registered sources using synthetic fixtures.
- [ ] 1.4 Document source registration, pending sections, private exclusions, and selected journal behavior in editable Markdown; verify a small new approved record is included while an unregistered sibling is not.

## 2. Faithful rendering, evidence, and navigation

- [ ] 2.1 Render selected Markdown with source/hash provenance, generation timestamp, tables, checklists, code blocks, and current/historical/personal labels; test that edits appear once, incomplete/pending evidence is honest, journal prompts remain unanswered, and source files remain unchanged.
- [ ] 2.2 Add stable section/heading IDs, duplicate-heading disambiguation, in-page link rewriting, approved escaped-text appendices, and labeled omitted references; test cross-document fragments, omitted private headings, missing targets, and all current project document links.
- [ ] 2.3 Enforce inert source HTML/code, external-image suppression, safe external evidence schemes, credential-pattern checks with location-only errors, and output CSP; test script/event-handler markup, a candidate sentinel write, remote image URLs, unsafe/credential-bearing links, and synthetic tokens without accessing real credentials.
- [ ] 2.4 Add semantic navigation, skip link, focus styling, readable tables, and unchecked external/local-service evidence labels; verify keyboard destinations and document that external availability is never queried during build/view.

## 3. Opening architecture figure

- [ ] 3.1 Add `docs/architecture.json` with every component and flow listed in the design, local/external/later/report lanes, implementation-status labels, and the sandbox trust boundary; verify required nodes/edges and that expected answers and credentials have no path into generation or sandbox execution.
- [ ] 3.2 Implement constrained inline SVG rendering and a text equivalent from the same graph; test escaping, duplicate IDs, dangling edges, unknown phases/layout values, and propagation of a label/edge change to both representations.
- [ ] 3.3 Place the goal figure before visible narrative/navigation and add accessible title/description, non-color labels, and narrow-screen scrolling; verify DOM order and document how to maintain the graph without editing generated HTML.

## 4. Build/check integration and documentation alignment

- [ ] 4.1 Complete the documented build and `--check` commands with full input/output validation, atomic output replacement, and no writes in check mode; test successful builds, preservation after failure, unchanged sources, and repeatability except the timestamp.
- [ ] 4.2 Update README with setup/build/check/open instructions and `docs/project_spec.md`, `docs/progress.md`, and OpenSpec context with the user-directed report-first foundation, current origin configuration, and this change's status; verify current prose is consistent while historical entries and student reflections remain intact.
- [ ] 4.3 Build and validate the report from the actual repository and run the offline test suite; verify `report/` is ignored and no evaluator/product behavior changed. Record exact commands and observed results in the progress log.
- [ ] 4.4 Open `report/index.html` directly in a browser with network disabled and no required services; inspect the complete architecture at desktop width, 375-pixel width, and 200-percent zoom, check keyboard navigation and accessible text alternatives, verify no clipped labels/unreadable flows or automatic network requests, and record browser/version and evidence of the check.

## Workflow follow-up

- Present the implemented result and validation evidence for review before archiving the completed change.
- Keep the subsequent local agent-loop work as a separate change; do not fold CI, MLflow, or live generation into this report implementation.
