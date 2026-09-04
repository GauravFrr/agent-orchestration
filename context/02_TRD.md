# TRD — Agent Orchestration System

## 1. Architecture Overview

```
                         ┌─────────────────────────┐
                         │      Client / Demo       │
                         │  (CLI, curl, React UI)   │
                         └────────────┬─────────────┘
                                      │ REST/WebSocket
                         ┌────────────▼─────────────┐
                         │      Orchestration API     │
                         │        (FastAPI)           │
                         └────────────┬─────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │     LangGraph Runtime       │
                         │  (Supervisor state machine) │
                         └──┬───────┬───────┬────────┘
                            │       │       │
                  ┌─────────▼─┐ ┌───▼────┐ ┌▼──────────┐
                  │ Specialist │ │Reviewer│ │  Memory    │
                  │  Agents    │ │ Agent  │ │  Manager   │
                  │ (Celery    │ └────────┘ └─────┬──────┘
                  │  workers)  │                   │
                  └─────┬──────┘         ┌─────────┴─────────┐
                        │                 │                   │
                  ┌─────▼──────┐   ┌──────▼─────┐     ┌──────▼─────┐
                  │Tool Registry│   │   Redis    │     │  ChromaDB   │
                  │ (custom+MCP)│   │(short-term)│     │(long-term)  │
                  └─────────────┘   └────────────┘     └─────────────┘
                            │
                  ┌─────────▼──────────┐
                  │  Human Review Queue │──► React Review UI
                  │   (Postgres+Redis)  │
                  └─────────────────────┘
                            │
                  ┌─────────▼──────────┐
                  │  OTel Trace Store   │──► Trace Explorer UI
                  │ (Postgres + OTel    │
                  │  collector)          │
                  └─────────────────────┘
```

## 2. Component Breakdown

### 2.1 Orchestration API (FastAPI)
- `POST /tasks` — submit a new task, returns task_id
- `GET /tasks/{id}` — status, current plan, progress
- `GET /tasks/{id}/trace` — full trace tree
- `POST /tasks/{id}/replay` — replay from a given step, optional input override
- `GET /reviews` / `POST /reviews/{id}/decision` — human review queue and decisions
- `GET /memory` / `DELETE /memory/{id}` — memory dashboard + user-data deletion
- WebSocket `/tasks/{id}/stream` — live execution events for the UI

### 2.2 LangGraph State Machine
Nodes: `intake` → `plan` → `dispatch` (fan-out to specialists, parallel or sequential per dependency graph) → `review` (per subtask) → conditional edge: `retry_specialist` (reviewer rejected, feedback attached) | `escalate_human` (low confidence / sensitive / repeated failure) | `continue` → `synthesize` → `deliver`.
Each node is a typed LangGraph node with a Pydantic input/output schema. State object carries: task, plan, subtask results so far, retry counts, escalation flags, memory context.

### 2.3 Agent Roles
- **Supervisor**: owns planning + re-planning. Produces structured `Plan` (list of `Subtask{id, specialist, input, depends_on, expected_output_schema, complexity_estimate}`). Confidence score attached to plan and to each dispatch decision.
- **Specialists**: Research (web search + fetch), Data Analysis (sandboxed code execution + pandas/duckdb), Writing (synthesis, no tools beyond memory read), Code Execution (sandboxed Python runner). Each specialist is a LangGraph subgraph with its own bounded tool allowlist.
- **Reviewer**: validates a specialist's output against the `expected_output_schema` and a quality rubric; returns `approve | reject(feedback) | escalate`.

### 2.4 Tool Registry
Central registry: `{name, description, input_schema, output_schema, allowed_specialists[], rate_limit, kind: "custom"|"mcp"}`. Custom tools: web_search, file_read, file_write, sandboxed_code_exec, db_query. MCP tools: connect real MCP servers (e.g., filesystem, fetch/browser, or any available server) via the same registry interface so specialists call them identically — this is the differentiator over a custom-only registry. Every invocation logged: inputs, outputs, latency, success/failure, cost if applicable.

### 2.5 Memory System
- **Short-term (Redis)**: per-task key `task:{id}:state` — current plan, completed subtask outputs, intermediate results, error log. TTL cleared on task completion (kept briefly for replay, then archived to Postgres).
- **Long-term (ChromaDB)**: on task completion, embed and store a `TaskMemory` document: original request, final plan, what worked/didn't per subtask, tools used, discovered domain facts, inferred user preferences. Collection per memory type (`plans`, `facts`, `preferences`).
- **Retrieval**: supervisor's planning prompt is augmented with top-k semantically similar past `TaskMemory` records before generating a new plan.
- **Management**: importance score (recency + retrieval frequency + explicit positive/negative outcome), decay job (Celery beat) that lowers importance over time and prunes below-threshold memories, a `/memory` dashboard endpoint, and a hard delete endpoint per memory id or per originating task.

### 2.6 Human-in-the-Loop
Escalation triggers evaluated at plan-time and at each dispatch: `plan_confidence < threshold`, `same_subtask_failed >= N times`, `action_tag in {financial, deletion, external_communication}`, `reviewer_quality_score < threshold`, `user_requested_review=true`.
Approval levels: `NOTIFY` (proceed, log only), `APPROVE_ACTION` (block until next-step confirmed), `APPROVE_PLAN` (block until full plan confirmed before any dispatch), `TAKE_OVER` (human supplies the output directly, bypassing the specialist). Trigger→level mapping is a config table, not hardcoded.
Mechanism: on trigger, LangGraph execution pauses (checkpointed state), a `ReviewRequest` row is written (Postgres) with full context snapshot, Redis pub/sub notifies the React UI, execution resumes on `POST /reviews/{id}/decision`.

### 2.7 Observability
OpenTelemetry spans around: supervisor planning, each specialist tool call and reasoning step, reviewer evaluation, memory retrieval (with which memories were used and their similarity score), escalation events. Exported to a local OTel collector → Postgres (for the trace explorer) — no external SaaS dependency, mirroring the LLM Gateway's self-hosted Grafana approach. Cost/token tracking per span, aggregated into per-task, per-agent, per-tool-usage rollups.

### 2.8 Replay System
Every LangGraph run is checkpointed at each node (LangGraph's built-in checkpointing, backed by Postgres). Replay API loads a checkpoint, optionally overrides one step's input, and re-executes forward from there, producing a new `run_id` linked to the original for side-by-side diff in the UI.

## 3. Tech Stack (locked)
Python 3.11+, FastAPI, LangGraph, Gemini + Claude + Groq (via existing provider-wrapper pattern from LLM Gateway/Scoutr), Redis + Celery (async specialist execution + memory decay jobs), PostgreSQL (tasks, reviews, traces, checkpoints), ChromaDB (long-term semantic memory), MCP client integration for at least one real MCP server class (filesystem/fetch), React (review UI + trace explorer), Docker + docker-compose, OpenTelemetry.

## 4. Non-Functional Requirements
- Every escalation must be recoverable — a crashed API process must not lose a paused task (state is Postgres-checkpointed, not in-memory only).
- All tool calls sandboxed; code execution specialist runs in a restricted subprocess/container, never the host process.
- Memory deletion endpoint must actually purge ChromaDB + Postgres references (privacy-by-design, same principle applied to MemoryOS).
- Demo must run fully via `docker-compose up` + one demo script, no manual steps, matching the LLM Gateway precedent.
