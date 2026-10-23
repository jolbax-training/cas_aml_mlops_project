# Agent Evaluation

Terms for coding tasks, agent attempts, and evaluation checks.

## Language

**Coding task**:
A request for one Python function, with an instruction, a typed function signature, and acceptance criteria.

**Trial**:
One attempt by the agent to solve a coding task, including any development checks and internal revisions until submission or a stopping limit is reached.
_Avoid_: Calling each internal revision a separate trial.

**Evaluation run**:
A scheduled collection of task trials evaluated under one agent configuration against one benchmark version. Its planned task/trial records define the scoring denominators.
_Avoid_: Calling a single development check a run.

**Incomplete evaluation run**:
An evaluation run missing required task/trial evidence or affected by an infrastructure or exhausted API-transport failure. Its partial evidence is retained, but it is excluded from headline comparisons.
_Avoid_: Treating incompleteness as a lower agent-success score or shrinking denominators to hide it.

**Candidate**:
A proposed function implementation produced during a trial. A trial can contain multiple candidates before final submission.

**Development check**:
A check the agent creates and can inspect while developing its candidate.
_Avoid_: Acceptance check, hidden test.

**Acceptance check**:
A check kept hidden from the agent and used to grade its final submission.
_Avoid_: Development check.

**Grading replay**:
A new evaluation of saved final candidates against a retained benchmark, without new model generation. It produces fresh grading evidence and does not constitute a new agent trial.
_Avoid_: Calling regrading a reproduction of the agent's interaction or a fresh model run.

**Trace inspection**:
Reading the retained requests, responses, tool interactions, and outcomes of an existing trial without executing it again.
_Avoid_: Replay, when no execution occurs.

### Workflow-orchestrator example

**Coordinator**:
The agent responsible for splitting a research request into work items and coordinating their completion.

**Work item**:
A part of the coordinator's request assigned to one worker and assessed by its own verifier.

**Worker**:
The agent assigned to produce the result for one work item.

**Independent verifier**:
A separate agent assigned to assess one work item's result rather than produce that result as its worker.

**Final check**:
A check of the combined results across all work items after item-level verification.
