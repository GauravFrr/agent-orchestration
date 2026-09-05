# Operator User Guide — Agent Orchestration System

Welcome to the Operator User Guide for the **Agent Orchestration System**. This guide provides an operational walkthrough for managing, reviewing, debugging, and inspecting natural language task workflows using the web dashboard and REST APIs.

---

## Table of Contents
1. [Submitting Tasks](#1-submitting-tasks)
2. [Human-in-the-Loop (HITL) Review Interface (`/reviews`)](#2-human-in-the-loop-hitl-review-interface-reviews)
3. [Trace Explorer & Replay System (`/traces`)](#3-trace-explorer--replay-system-traces)
4. [Memory Dashboard (`/memory`)](#4-memory-dashboard-memory)
5. [Architecture & Sequence Diagrams](#5-architecture--sequence-diagrams)

---

## 1. Submitting Tasks

Tasks can be submitted to the Agent Orchestration System using the web interface at `/` or via the REST API.

### Submitting via API (`curl`)

To submit a natural language task request to the backend orchestrator:

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "request_text": "Research market trends in agent orchestration and write a brief summary report."
  }'
```

#### Example HTTP Response (`201 Created`):
```json
{
  "id": "11111111-1111-1111-1111-111111111111",
  "request_text": "Research market trends in agent orchestration and write a brief summary report.",
  "status": "intake",
  "confidence": 1.0,
  "created_at": "2026-09-05T15:00:00Z",
  "updated_at": "2026-09-05T15:00:00Z",
  "completed_at": null,
  "total_cost_usd": 0.0,
  "plan": null
}
```

### What to Expect During Execution

1. **Intake & Planning (`intake` → `planning`)**:
   - The Supervisor agent analyzes the request, queries long-term memory in ChromaDB for similar past tasks, and generates a structured, dependency-aware plan with a confidence score.
2. **Subtask Dispatch (`executing`)**:
   - Subtasks fan out in parallel to specialized workers (`research`, `data_analysis`, `writing`, `code_exec`).
   - Tools are invoked dynamically with every invocation recorded in the OpenTelemetry trace log.
3. **Subtask Verification (`reviewing`)**:
   - Reviewer agents grade specialist outputs against schema requirements. Rejections trigger automated retry cycles with feedback.
4. **Synthesis & Deliverables (`synthesizing` → `done`)**:
   - The Supervisor synthesizes subtask outputs into the final deliverable returned via WebSocket and `GET /tasks/{id}`.
5. **Memory Extraction (Post-Task)**:
   - Extracted plans, domain facts, and user preferences are asynchronously saved to PostgreSQL and embedded into ChromaDB.

---

## 2. Human-in-the-Loop (HITL) Review Interface (`/reviews`)

When an agent action triggers security policies or low-confidence thresholds, execution pauses safely and creates a `review_request` record.

Navigating to **`/reviews`** presents the review queue and decision panel:

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ PENDING REVIEWS                                                                        │
│ ┌──────────────────────────────────────┐ ┌───────────────────────────────────────────┐ │
│ │ Task #55555555-5555                  │ │ Trigger: [ sensitive_action ]             │ │
│ │ Action: Delete sales data            │ │ Level:   [ Approve Action ]               │ │
│ │ Status: PENDING                      │ ├───────────────────────────────────────────┤ │
│ └──────────────────────────────────────┘ │ PROPOSED ACTION:                          │ │
│                                          │ "Execute specialist 'data_analysis' on    │ │
│                                          │  input: Delete temp records"              │ │
│                                          │ ├───────────────────────────────────────────┤ │
│                                          │ │ CHAT WITH PAUSED AGENT                   │ │
│                                          │ │ Operator: "Why delete this table?"       │ │
│                                          │ │ Agent: "Requested by subtask_1 input."    │ │
│                                          │ ├───────────────────────────────────────────┤ │
│                                          │ │ [ Approve ]  [ Modify ]                  │ │
│                                          │ │ [ Reject ]   [ Take Over ]               │ │
│                                          │ └───────────────────────────────────────────┘ │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Trigger & Approval Level Badges

Each pending review displays color-coded metadata badges:

#### Trigger Badges (`trigger_reason`):
- <span style="color:#60a5fa">**`low_confidence`**</span>: Supervisor plan confidence score fell below the configured threshold (e.g. `< 0.8`).
- <span style="color:#f59e0b">**`sensitive_action`**</span>: Subtask contains high-risk action tags (such as `financial`, `deletion`, or `external_communication`).
- <span style="color:#ef4444">**`repeated_failure`**</span>: Subtask failed multiple specialist retries without passing reviewer verification.
- <span style="color:#a855f7">**`reviewer_flag`**</span>: Reviewer agent flagged suspicious or unsafe output data.
- <span style="color:#94a3b8">**`user_requested`**</span>: Manual operator intervention flag.

#### Approval Level Badges (`approval_level`):
- **`Notify`**: Informational alert; no execution pause required.
- **`Approve Action`**: Requires explicit operator authorization before the specific tool call or subtask executes.
- **`Approve Plan`**: Requires operator verification of the entire multi-step plan before execution begins.
- **`Take Over`**: Requires direct human intervention or manual output injection.

### Chat with Paused Agent Panel

The **Chat with Paused Agent** panel allows operators to conduct scoped Q&A queries against the agent's current state before making a decision. 

- Asking questions (e.g., *"What alternative tables did you consider?"*) performs a read-only query against the current context snapshot.
- Chat interactions **do not mutate** graph state or advance execution until a formal decision is submitted.

### The 4 Decision Buttons

| Decision | Operator Action | Execution Result |
| :--- | :--- | :--- |
| <span style="color:#22c55e">**Approve**</span> | Click **Approve** | Resumes graph execution from the Postgres checkpoint exactly as planned. |
| <span style="color:#3b82f6">**Modify**</span> | Edit input parameters in modal & submit | Resumes execution using the operator's modified subtask parameters. |
| <span style="color:#ef4444">**Reject**</span> | Provide rejection reason & submit | Routes execution back to specialist/supervisor for re-planning or retry with operator feedback. |
| <span style="color:#f59e0b">**Take Over**</span> | Enter direct output JSON/text & submit | Injects human-authored output into the subtask result and advances the graph past that step. |

---

## 3. Trace Explorer & Replay System (`/traces`)

The Trace Explorer at **`/traces`** provides deep observability into agent reasoning, tool calls, costs, and execution timing.

### Reading the Span Tree

The central panel displays a nested hierarchy of execution spans mirroring parent-child execution boundaries:

- **Root Task Span** (`span_type: plan`): Overall task lifecycle.
- **Subtask Spans** (`span_type: dispatch`): Individual specialist executions (`research`, `data_analysis`, `writing`, `code_exec`).
- **Tool Spans** (`span_type: tool_call`): Specific tool calls (`db_query`, `web_search`, `sandboxed_code_exec`).
- **Review Spans** (`span_type: review`): Reviewer agent evaluations.

Each tree item displays the actor name, status badge, latency in milliseconds, token counts (`in`/`out`), and cumulative cost in USD.

### SpanDetailDrawer

Clicking any span in the tree opens the **SpanDetailDrawer** on the right side of the screen:

- **Metadata Header**: Displays Span ID, Parent Span ID, Actor, Start Time, and Duration.
- **Payload Inspection**: Formatted JSON views of system prompts, user content inputs, LLM completion responses, and tool arguments.
- **Cost & Token Breakdown**: Exact prompt and candidate token counts with USD cost calculations.

### Cost & Performance Strip

The summary strip at the top of the Trace Explorer displays:
- **Total Task Cost**: Cumulative LLM generation cost across all providers.
- **Total Latency**: Wall-clock duration of the complete workflow.
- **Agent Cost Distribution**: Relative cost breakdown by agent role.
- **Tool Execution Latency**: Performance overhead of invoked tools.

### Replay System (`ReplayModal`)

The Replay feature allows operators to fork execution from any historical checkpoint node and re-run the workflow with optional parameter overrides.

1. Locate the target node in the trace tree or checkpoint history.
2. Click **Replay Step** to launch the `ReplayModal`.
3. Optionally supply a JSON `input_override` (e.g. updating input queries or subtask parameters).
4. Click **Run Replay**.
5. The UI opens a **Split Comparison View**:
   - **Left**: Original execution trace and output.
   - **Right**: Replay execution running in real time from the divergence checkpoint forward.

---

## 4. Memory Dashboard (`/memory`)

The Memory Dashboard at **`/memory`** displays short-term working state and long-term semantic memories extracted across task runs.

```
┌────────────────────────────────────────────────────────────────────────────────────────┐
│ MEMORY DASHBOARD                                                                       │
│ Filter: [ All Types ▼ ]   Sort: [ Importance Score ▼ ]                                  │
├────────────────────────────────────────────────────────────────────────────────────────┤
│ TYPE       SUMMARY                                          SCORE   RETRIEVED   ACTION │
│ ────────────────────────────────────────────────────────────────────────────────────── │
│ [ Plan ]   Executed 2 subtasks for agent orchestration...  1.0     2 times     [Delete]│
│ [ Fact ]   LangGraph v0.2.60 introduced functional...       1.0     1 times     [Delete]│
│ [ Pref ]   Prefers summarized structured details...         0.5     3 times     [Delete]│
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Memory Types Explained

- <span style="color:#3b82f6">**`Plan`**</span>: High-level execution strategies and subtask structures stored from completed tasks.
- <span style="color:#22c55e">**`Fact`**</span>: Specific, verified domain facts discovered by specialist agents (e.g. library versions, dataset metrics).
- <span style="color:#a855f7">**`Preference`**</span>: Inferred user preferences and formatting rules (e.g. preferred output schemas, brevity constraints).

### Deleting a Memory Record

To uphold explicit **privacy-by-design** principles, operators can delete any memory record directly from the UI:

1. Locate the memory item in the Memory Dashboard table.
2. Click the red **Delete** button on the row.
3. The system issues a `DELETE /memory/{id}` request:
   - Removes the memory record from the PostgreSQL `memories` table.
   - Deletes the corresponding document embedding from the ChromaDB vector collection (`plans`, `facts`, or `preferences`).

---

## 5. Architecture & Sequence Diagrams

For visual reference, the following architectural and sequence diagrams are included in the repository documentation:

- **System Architecture**: [`docs/architecture-diagram.svg`](file:///f:/Agent-Orchestration/docs/architecture-diagram.svg)
- **HITL Escalation Sequence**: [`docs/hitl-escalation-flow.svg`](file:///f:/Agent-Orchestration/docs/hitl-escalation-flow.svg)
- **Memory Retrieval Sequence**: [`docs/memory-retrieval-flow.svg`](file:///f:/Agent-Orchestration/docs/memory-retrieval-flow.svg)
