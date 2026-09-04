# Implementation Plan — Agent Orchestration System

Phases mirror the guide's 6-phase breakdown. Each phase lists scope, exit criteria, and the file-touch map so the coding agent (Antigravity) always knows exactly what it may create/modify in that phase.

## Phase 1 — Agent Architecture (Day 1–4)
**Scope**: Agent hierarchy (Supervisor/Specialist/Reviewer) as LangGraph nodes, task decomposition engine, tool registry (custom tools first), core LangGraph state machine, Orchestration API skeleton.
**Exit criteria**: `POST /tasks` runs a full happy-path task end-to-end against at least 2 specialists with real tool calls, no memory/HITL/observability yet.
**File-touch map**:
```
backend/
  app/
    main.py                      # FastAPI app entrypoint
    api/routes/tasks.py           # POST /tasks, GET /tasks/{id}
    core/config.py                 # settings, env loading
    core/schemas.py                # Plan, Subtask, pydantic I/O schemas
    graph/state.py                  # LangGraph state definition
    graph/nodes/intake.py
    graph/nodes/plan.py
    graph/nodes/dispatch.py
    graph/nodes/review.py
    graph/nodes/synthesize.py
    graph/build_graph.py            # wires nodes + conditional edges
    agents/supervisor.py
    agents/specialists/research.py
    agents/specialists/data_analysis.py
    agents/specialists/writing.py
    agents/specialists/code_exec.py
    agents/reviewer.py
    tools/registry.py                # tool registration + lookup
    tools/web_search.py
    tools/file_io.py
    tools/sandboxed_exec.py
    tools/db_query.py
    providers/                        # reused/adapted from LLM Gateway
      gemini.py
      claude.py
      groq.py
  db/models.py                        # tasks, subtasks, tool_invocations (SQLAlchemy)
  db/migrations/xxxx_initial.py
  docker/Dockerfile
  docker-compose.yml                  # api + postgres, no redis/chroma yet
  .env.example
```

## Phase 2 — Memory System (Day 4–7)
**Scope**: Redis short-term working memory, ChromaDB long-term memory, retrieval injection into planning, memory management (importance scoring, decay job, dashboard endpoint, delete endpoint).
**Exit criteria**: running the same/similar task twice shows a measurably different (memory-informed) second plan; `/memory` list + delete endpoints work.
**File-touch map**:
```
backend/app/
  memory/short_term.py               # Redis read/write for task:{id}:state
  memory/long_term.py                 # ChromaDB client, embed + upsert + query
  memory/manager.py                    # orchestrates retrieval for planning, importance scoring
  memory/decay.py                      # Celery beat task
  api/routes/memory.py                 # GET /memory, DELETE /memory/{id}
  graph/nodes/plan.py                  # MODIFY: inject retrieved memory into prompt
db/models.py                           # MODIFY: add memories table
db/migrations/xxxx_memory.py
docker-compose.yml                     # MODIFY: add redis, chromadb, celery worker, celery beat
```

## Phase 3 — Human-in-the-Loop (Day 7–10)
**Scope**: escalation trigger config + evaluation, approval queue, 4 approval levels, review REST + WebSocket notification, React review UI.
**Exit criteria**: a forced sensitive-action task pauses correctly, appears in the review UI with full context, and each of the 4 decision types correctly resumes/alters execution.
**File-touch map**:
```
backend/app/
  hitl/triggers.py                     # trigger evaluation against config table
  hitl/approval_levels.py               # trigger → level mapping
  hitl/queue.py                          # create/read review_requests, pub/sub notify
  api/routes/reviews.py                  # GET /reviews, POST /reviews/{id}/decision
  graph/nodes/dispatch.py                # MODIFY: check triggers before dispatch
  graph/nodes/review.py                  # MODIFY: check triggers on reviewer verdict
db/models.py                             # MODIFY: add review_requests, checkpoints tables
db/migrations/xxxx_hitl.py
frontend/
  src/pages/Reviews.tsx
  src/components/ReviewCard.tsx
  src/components/ChatWithAgent.tsx
  src/api/reviews.ts
  src/hooks/useReviewSocket.ts
```

## Phase 4 — Observability (Day 10–12)
**Scope**: OpenTelemetry tracing across all node types, trace explorer UI, cost/perf tracking, replay system.
**Exit criteria**: any past task's full execution tree is inspectable node-by-node with prompt/response payloads; replay produces a linked new run visible side-by-side.
**File-touch map**:
```
backend/app/
  observability/tracing.py             # OTel setup, span helpers
  observability/cost.py                 # per-span cost/token rollups
  graph/*.py                            # MODIFY (all nodes): wrap in OTel spans
  agents/*.py                           # MODIFY: wrap LLM calls in spans
  tools/registry.py                     # MODIFY: wrap tool calls in spans
  graph/checkpointing.py                 # LangGraph Postgres checkpointer wiring
  api/routes/traces.py                   # GET /tasks/{id}/trace, POST /tasks/{id}/replay
  replay/replay_engine.py
db/models.py                             # MODIFY: add trace_spans, checkpoints, replays tables
db/migrations/xxxx_observability.py
frontend/
  src/pages/TraceExplorer.tsx
  src/components/TraceTree.tsx
  src/components/SpanDetailDrawer.tsx
  src/components/ReplayModal.tsx
  src/components/CostPerfStrip.tsx
```

## Phase 5 — Integration + E2E Testing (Day 12–13)
**Scope**: demo scenario wiring, full docker-compose (all services), E2E test suite.
**Exit criteria**: `docker-compose up` + one demo script runs the full demo scenario unattended except for the one scripted human-approval step; E2E suite green.
**File-touch map**:
```
backend/tests/e2e/test_plan_decomposition.py
backend/tests/e2e/test_specialist_tool_use.py
backend/tests/e2e/test_reviewer_rejection_retry.py
backend/tests/e2e/test_memory_informs_planning.py
backend/tests/e2e/test_human_escalation_timing.py
backend/tests/e2e/test_agent_failure_recovery.py
demo/demo_scenario.py                    # scripted research→analysis→writing task
demo/demo.sh                              # curl/CLI walkthrough
docker-compose.yml                        # MODIFY: full stack, frontend service added
frontend/Dockerfile
```

## Phase 6 — Portfolio Polish (Day 13–14)
**Scope**: demo recording, README narrative, architecture diagram, honest known-limitations section (per LLM Gateway precedent), MIT license, CI.
**File-touch map**:
```
README.md
docs/architecture-diagram.png (or .svg, generated from TRD diagram)
LICENSE
.github/workflows/ci.yml
.github/workflows/security-scan.yml
demo/demo_video.mp4 (external link if too large for repo)
```
