# Design

## Context

See proposal.md. The specification defines a four-day, 32-hour plan with day exit evidence and an eleven-item completion checklist. Upstream changes deliver the actual capabilities; this change verifies, documents, and demonstrates them. All tasks remain unstarted.

## Goals / Non-Goals

**Goals:** Exact tested commands, a rehearsed demo path, checklist-to-evidence mapping, explicit buffer use and cut order, honest incomplete labels.

**Non-Goals:** Hosting, recording a video, adding features, rerunning paid experiments for the demo, or completing personal reflections on the student's behalf.

## Decisions

### 1. Commands are documented only after re-execution

README/setup documentation lists commands for environment setup, image restoration, MLflow service start, trace inspection, grading replay, report build/open, and CI reproduction. Each is re-executed from a clean-ish environment before being recorded; exact names come from the implementing changes.

### 2. Demo path without new paid generation

The demo inspects retained traces (no API/Podman), runs grading replay of saved final candidates (Podman, no API), navigates recorded MLflow runs, opens the offline report, and walks through the comparison and the transfer guide. Live generation is not required; if shown, it is charged to the shared ledger under the CHF 15 ceiling.

### 3. Checklist accounting

A progress entry maps each completion-checklist item to retained evidence (paths, run IDs, CI identifiers) or labels it incomplete with the reason. Day exit evidence from the plan is reviewed the same way.

### 4. Buffer and cut order

Use the 2h buffer where required work overran. When time is short, simplify presentation polish first (report styling, diagram refinement, demo narration). Never reduce the ten-task benchmark, sixty trials, fixed denominators, required probes, CI, or MLflow records to claim completion.

## Risks / Trade-offs

- Commands drifting from documentation → re-execute before recording and record dates/versions.
- Services unavailable at demo time → the inspection and offline report path need no services; replay needs only Podman.
- Pressure to declare completion → checklist mapping requires evidence per item.

## Migration Plan

Collect commands from upstream changes, re-execute them, write the demo path, rehearse it, update progress and work-log sources, and rebuild the report. Rollback is documentation-only.
