# App Flow — Agent Orchestration System

## 1. Happy Path (No Escalation)
1. Client `POST /tasks {request_text}` → task row created, status `intake`.
2. LangGraph enters `plan` node → Memory Manager queries ChromaDB for similar past tasks → Supervisor LLM call produces `Plan` (subtasks + confidence).
3. `dispatch` node: subtasks with no unmet dependencies fan out to Celery workers running the relevant specialist subgraph, in parallel where possible.
4. Each specialist: reads its input, calls allowed tools (custom or MCP) via the Tool Registry, produces output against the `expected_output_schema`. Every tool call logged to `tool_invocations` + an OTel span.
5. `review` node: Reviewer LLM call evaluates specialist output → `approve` → subtask marked `done`, dependent subtasks unblocked.
6. When all subtasks `done` → `synthesize` node: Supervisor (or Writing specialist) combines outputs into final deliverable.
7. `deliver` → task status `done`, final output returned via WebSocket + `GET /tasks/{id}`.
8. Post-completion: Memory Manager embeds and stores a `TaskMemory` in ChromaDB (async, Celery).

## 2. Reviewer Rejection Path
1. Reviewer returns `reject(feedback)` instead of `approve`.
2. Conditional edge routes back to the specialist node with `feedback` appended to its input and `retry_count += 1`.
3. Specialist re-attempts. If `retry_count >= max_retries` (config, e.g. 2) → trigger `repeated_failure` escalation instead of a third retry.

## 3. Human Escalation Path
1. At `plan` or `dispatch`/`review` time, escalation-trigger evaluation runs against the config table (confidence threshold, sensitive-action tags, repeated failure, reviewer low score, explicit user flag).
2. On trigger: LangGraph state is checkpointed (`checkpoints` row), execution pauses, a `review_requests` row is created with `context_snapshot` (task, plan, completed steps so far, the pending decision, the agent's proposed action + its stated reasoning) and the mapped `approval_level`.
3. Redis pub/sub notifies the React review UI; UI polls/subscribes to `/reviews`.
4. Human reviews: sees task context, decision point, proposed action + reasoning, relevant past decisions (pulled from `memories`), and can chat with the agent (a scoped Q&A call, not part of the main execution graph) before deciding.
5. Human submits `POST /reviews/{id}/decision` with one of: `approve` (resume as planned), `modify` (resume with edited action), `reject` (route back to specialist/supervisor with reason), `take_over` (human's own output is injected as the subtask/plan result, execution resumes past that point).
6. LangGraph resumes from the checkpoint with the decision applied.

## 4. Replay Flow
1. From the trace explorer, user selects a past task and a specific checkpoint (node).
2. Optionally supplies an `input_override` for that step.
3. `POST /tasks/{id}/replay` loads the `checkpoints.state_snapshot`, applies the override if present, and re-runs the LangGraph from that node forward as a *new* task row (linked via `replays`).
4. Trace explorer UI shows original run and replay run side by side, diffing plan/outputs from the divergence point onward.

## 5. Memory-Informed Planning Flow (second-run demo case)
1. User submits a task similar to a previously completed one.
2. `plan` node's memory retrieval step finds the matching `plans`/`facts` entries above a similarity threshold.
3. These are injected into the supervisor's planning prompt as "relevant past experience."
4. Resulting plan differs from a cold-start plan (e.g., skips a subtask that failed last time, or reuses a known-good tool sequence) — this diff is what the demo highlights.

## 6. State Diagram (task-level)
```
intake → planning → executing ⇄ reviewing → escalated → executing
                         ↓                        ↑
                    synthesizing ←──────── (resume after human decision)
                         ↓
                        done
      (any state) → failed  [unrecoverable error, all retries/escalations exhausted]
```
