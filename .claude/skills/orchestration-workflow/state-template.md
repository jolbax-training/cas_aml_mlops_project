# STATE.md template

Copy to `STATE.md` at the primary checkout root. The file is Git-ignored and never committed. Put no secrets, API keys, or email addresses in it; run, dispatch, branch, commit, and CI run ids are fine. Update it after every merge, review, or restart. With two coordinators, each change has one owner and run id, and each coordinator edits only its own rows ([handover.md](handover.md)).

```markdown
# Orchestration state (<date>) — Orca run <run_id>

## Merged and archived
- <change> (<commit on main>)

## Merged, not archived
- <change>: owner <coordinator name or session>; run <run_id>; <what is open and why>

## In flight
- <change>: owner <coordinator name or session>; run <run_id>; branch <branch> <commit>; worker <terminal handle or task id>; review <report path or "pending">; next step <step>

## Remaining
- <change or user step>: owner <coordinator name or session>; run <run_id> (<reason it waits: paid phase, user action, queue>)

## CI
- main <commit>: run <run_id> <success|failure> <url>
- Branches left on origin: <ci/** branches>

## Notes for the next session
- <decisions and approvals the user gave, such as a reviewer-model exception>
```
