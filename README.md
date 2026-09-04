# Agent Orchestration System

A production-grade autonomous agent orchestration system. A supervisor agent decomposes complex natural-language tasks into an execution plan, delegates subtasks to specialized agents, validates their output with a reviewer, saves memory across sessions, escalates to a human operator when confidence is low or an action is sensitive, and makes every decision observable and replayable.

Built as a portfolio project demonstrating multi-agent reasoning architecture, not a chatbot or single-LLM-call toy.

---

## Problem Statement

Most public "AI agent" portfolio projects are single-agent toy demos: one LLM call, one tool, no memory, no oversight. Real production agent systems need task decomposition, specialized delegation, persistent memory, and a human safety valve. This project builds exactly that. See [`context/01_PRD.md`](context/01_PRD.md) for the full spec.

---

## Architecture

```
                         ┌─────────────────────────┐
                         │      Client / Demo        │
                         │  (CLI, curl, React UI)    │
                         └────────────┬─────────────┘
                                      │ REST / WebSocket
                         ┌────────────▼─────────────┐
                         │      Orchestration API     │
                         │   FastAPI · Python 3.12    │
                         └────────────┬─────────────┘
                                      │
                         ┌────────────▼─────────────┐
                         │     LangGraph Runtime      │
                         │  intake→plan→dispatch→     │
                         │  review→synthesize         │
                         │  (AsyncPostgresSaver ckpt) │
                         └──┬──────┬───────┬─────────┘
                            │      │       │
                  ┌──────────▼─┐ ┌─▼──────┐ ┌▼────────────┐
                  │ Specialist  │ │Reviewer│ │   Memory     │
                  │  Agents     │ │ Agent  │ │   Manager    │
                  │ (research,  │ └────────┘ └──────┬───────┘
                  │  analysis,  │                   │
                  │  writing,   │        ┌──────────┴──────────┐
                  │  code_exec) │        │                     │
                  └──────┬──────┘   ┌───▼──────┐     ┌────────▼────┐
                         │          │  Redis    │     │  ChromaDB   │
                  ┌───────▼───────┐ │(short-term│     │(long-term   │
                  │ Tool Registry │ │ per-task) │     │ semantic)   │
                  │ custom + MCP  │ └───────────┘     └─────────────┘
                  └───────────────┘
                         │
                  ┌───────▼────────────┐
                  │ Human Review Queue  │──► React Review UI
                  │  (Postgres + Redis) │     (approve / reject /
                  └──────────┬──────── ┘      modify / take over)
                             │
                  ┌──────────▼─────────┐
                  │  OTel Trace Store   │──► Trace Explorer UI
                  │ (Postgres + OTel    │     (span tree, cost,
                  │  collector)         │      replay modal)
                  └─────────────────────┘
```

See [`context/02_TRD.md`](context/02_TRD.md) for the full component breakdown, state machine definition, and tech stack rationale.

The architecture diagram is also available as a rendered SVG at [`docs/architecture-diagram.svg`](docs/architecture-diagram.svg).

---

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI (Python 3.12) |
| Agent runtime | LangGraph (state machine + AsyncPostgresSaver checkpointing) |
| LLM providers | Gemini (`gemini-3.5-flash-lite` default), Claude, Groq |
| Short-term memory | Redis (per-task state, TTL) |
| Long-term memory | ChromaDB (semantic embeddings, 3 collections) |
| Memory decay | Celery Beat |
| Database | PostgreSQL 15 (tasks, plans, reviews, trace spans, checkpoints, replays, memories) |
| Observability | OpenTelemetry → local OTel collector → Postgres (no SaaS dependency) |
| Frontend | React + TypeScript (Review UI, Trace Explorer, Memory Dashboard) |
| Containerization | Docker + Docker Compose (full stack, one command) |

---

## Quickstart

### Prerequisites
- Docker and Docker Compose installed
- A Gemini API key (free tier works; see Known Limitations for rate-limit note)

### 1. Clone and configure

```bash
git clone https://github.com/your-username/agent-orchestration.git
cd agent-orchestration
cp .env.example .env
# Edit .env and set GEMINI_API_KEY=your_key_here
```

### 2. Start the full stack

```bash
docker-compose up --build
```

This starts: FastAPI API, PostgreSQL, Redis, ChromaDB, OTel Collector, Celery Worker, Celery Beat, and the React frontend.

Services:
- API: `http://localhost:8000`
- React UI: `http://localhost:3000`
- API docs: `http://localhost:8000/docs`

### 3. Run the demo

```bash
bash demo/demo.sh
```

Or run the full scripted scenario directly:

```bash
python demo/demo_scenario.py
```

The demo scenario exercises the full system end-to-end: task decomposition → specialist execution with real tool calls → reviewer rejection-and-retry → human escalation → human approval → task completion → memory-informed second run → trace replay.

---

## What It Does — A Walkthrough

### Task Submission and Decomposition

Submit a natural-language task:

```bash
curl -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"request_text": "Research recent agent orchestration trends, analyze churn in sales data, and write a synthesis report."}'
```

The supervisor LLM decomposes this into a dependency-aware plan:
```json
{
  "subtasks": [
    {"id": "t1", "specialist": "research", "input": "Research recent agent orchestration trends", "depends_on": []},
    {"id": "t2", "specialist": "data_analysis", "input": "Query and analyze churn in sales data", "depends_on": []},
    {"id": "t3", "specialist": "writing", "input": "Write synthesis report from research and analysis", "depends_on": ["t1", "t2"]}
  ],
  "confidence": 0.9
}
```

### Specialist Execution with Real Tool Calls

Each specialist runs with a bounded tool allowlist:
- **Research**: `web_search`, `file_read`
- **Data Analysis**: `db_query`, `sandboxed_code_exec`
- **Writing**: memory read only (no external tools)
- **Code Execution**: `sandboxed_code_exec` only

Every tool call is logged: inputs, outputs, latency, cost.

### Reviewer Catches and Rejects a Bad Output

After each specialist completes, the reviewer evaluates the output against the expected schema and a quality rubric. When a specialist returns low-quality or off-schema output, the reviewer returns `reject(feedback)` and the subtask is retried with the feedback attached — no manual intervention.

### Human Escalation for Sensitive Actions

The demo task includes a `deletion` action tag (`delete from demo_data.sales_data`). This triggers the HITL escalation:

1. LangGraph execution pauses, state checkpointed to Postgres
2. A `ReviewRequest` is written with full context
3. Redis pub/sub pushes a notification to the React UI
4. The operator sees the escalation with full context in the Review UI at `http://localhost:3000/reviews`
5. Operator approves → `POST /reviews/{id}/decision` → execution resumes

Approval levels: `NOTIFY` (log and proceed), `APPROVE_ACTION` (block on next action), `APPROVE_PLAN` (block on full plan), `TAKE_OVER` (operator supplies output directly). All mapped from a config table, not hardcoded conditionals.

### Memory-Informed Second Run

After the first task completes, a structurally similar second request is submitted. The supervisor's planning prompt is augmented with top-k semantically retrieved past memories before the LLM call:

```
=== RETRIEVED CONTEXT FROM PAST EXECUTIONS ===
### Similar Past Plans
- Request: "Research recent agent orchestration trends..."
  Outcome: done
  Plan summary: Executed research + data analysis + writing synthesis.

### Related Domain Facts
- "Agent orchestration is shifting toward decentralized multi-agent networks."

### User Preferences
- Prefers structured and professional report formatting for research summaries.
=============================================
```

The second plan visibly differs — fewer redundant subtasks, better tool choices — because the supervisor can see what worked last time.

### Trace Explorer and Replay

Open the Trace Explorer at `http://localhost:3000/traces`. Every past task shows a full span tree:

```
NODE  intake          12ms
NODE  plan            847ms   $0.000142
  LLM   supervisor/plan    734ms   $0.000142   in=1842 out=312
NODE  dispatch         2ms
NODE  review          623ms   $0.000089
  LLM   reviewer/eval      523ms   $0.000089   in=1104 out=201
NODE  synthesize      912ms   $0.000201
  LLM   supervisor/synth   812ms   $0.000201   in=2341 out=423
```

Click any span to see the full prompt, response payload, token counts, and cost. Click **Replay from here** to re-execute forward from any checkpoint with an optional input override — a new linked run is created for side-by-side comparison.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `POST` | `/tasks` | Submit a new task |
| `GET` | `/tasks/{id}` | Status, plan, progress |
| `GET` | `/tasks/{id}/trace` | Full OTel span tree |
| `POST` | `/tasks/{id}/replay` | Replay from a checkpoint |
| `GET` | `/reviews` | Pending human review queue |
| `POST` | `/reviews/{id}/decision` | Submit approve/reject/modify/takeover |
| `GET` | `/memory` | Memory dashboard |
| `DELETE` | `/memory/{id}` | Hard-delete a memory record |

Full interactive docs at `http://localhost:8000/docs`.

---

## Design Decisions

### Why LangGraph instead of a custom state machine?

LangGraph provides typed graph state, conditional routing, and native Postgres checkpointing (via `AsyncPostgresSaver`) out of the box. The checkpointing is what makes replay and HITL pause/resume reliable — a crashed API process doesn't lose a paused escalation because state is persisted at every node transition, not held in memory.

The alternative (custom state machine in FastAPI) would require reinventing all of that, plus losing the graph visualization and debugging tooling that comes with LangGraph.

### Why real MCP integration, not just a custom tool registry?

The TRD explicitly locks this in as a differentiator. Typical portfolio agent projects implement a custom tool registry and call it "tool use." Real production systems need to compose with the broader tool ecosystem — MCP provides a standard protocol for that. The tool registry here supports both `kind: "custom"` and `kind: "mcp"` tools behind the same interface, so specialists call them identically regardless of kind. The MCP path is what enables connecting real external tool servers (filesystem, browser/fetch, or any MCP-compatible server) without specialist-level code changes.

### Why React instead of Streamlit for the UI?

The review UI and trace explorer have meaningful real-time requirements: WebSocket-pushed review notifications, interactive span trees, expandable payloads, a replay modal with side-by-side comparison. Streamlit's execution model (full reruns on any state change) makes this awkward and produces noticeably degraded UX for anything event-driven. React with proper component decomposition handles the WebSocket connection, the conditional routing through the span tree, and the modal lifecycle cleanly without fighting the framework.

### Why self-hosted OTel instead of a SaaS tracer?

Honeycomb and Datadog are excellent products, but adding an external SaaS dependency means: API keys in CI, potential data-privacy issues for task payloads (which may contain sensitive prompts), ongoing cost, and a demo that breaks when the free tier lapses. The self-hosted approach (OTel collector → Postgres) costs nothing, works offline, and the Postgres backend means the trace explorer uses the same SQLAlchemy stack as the rest of the system — no additional query language to learn or additional service to operate. This mirrors the LLM Gateway's self-hosted Grafana approach for the same reasons.

---

## E2E Test Suite

```bash
docker exec agent_api pytest tests/e2e -v --asyncio-mode=auto
```

| Test | What it verifies |
|---|---|
| `test_plan_decomposition.py` | Supervisor decomposes a multi-part request into 2+ named subtasks |
| `test_specialist_tool_use.py` | Research specialist calls `web_search`; span recorded in trace |
| `test_reviewer_rejection_retry.py` | Deliberately bad specialist input causes real reviewer rejection; retry with feedback |
| `test_memory_informs_planning.py` | Second run's plan-node span payload contains `RETRIEVED CONTEXT FROM PAST EXECUTIONS` |
| `test_human_escalation_timing.py` | Sensitive-action task pauses execution; task remains `escalated` until decision posted |
| `test_agent_failure_recovery.py` | `db_query` against non-existent table raises error; state transitions to `failed` cleanly |

---

## Known Limitations

These are stated plainly. None were silently dropped.

1. **`sandboxed_exec` uses subprocess timeout only, not real resource limits (Phase 1).** On Windows (and in the current Linux container), code execution isolation is `subprocess.run(..., timeout=10)` with a stripped `PATH` environment. There is no `seccomp` profile, no `ulimit` on memory or file descriptors, and no network namespace isolation. A malicious script could consume arbitrary memory or attempt filesystem writes to any path the process can reach. For a production deployment this needs either `gVisor`/`nsjail` or a dedicated container-per-execution model. Flagged and documented, not silently softened.

2. **Supervisor planning uses prompt + manual JSON parsing instead of structured output (Phase 1).** Gemini's `response_schema` parameter does not support `additionalProperties` on nested `Dict[str, Any]` fields, which the `Plan` schema requires. Rather than reduce the schema to fit structured output, the supervisor prompts for JSON in free text and parses it with `json.loads` + `Plan(**plan_dict)`. This is more fragile to prompt drift than native structured output — if the model produces malformed JSON, the fallback is an empty plan with `confidence=0.0`. A production system should either coerce the schema to fit the API's constraints or implement a retry loop with schema-validation feedback.

3. **The in-memory `_SPAN_TASK_MAP` for cost rollups is per-process (Phase 4).** `tracing.py` maintains a `Dict[str, str]` mapping OTel `span_id` → `task_id` to propagate task context to child spans that don't carry the attribute themselves. This map lives in the API process memory. If specialist execution ever moves to separate Celery worker processes (the TRD envisions this for parallelism), child spans emitted from workers would not appear in the API process's map, breaking cost propagation for those spans. This would require switching to a shared external store (Redis) for the span-to-task mapping, or ensuring task_id is always passed explicitly through the LangGraph state to every span attribute.

4. **Gemini free-tier rate limits (500 req/day) slow E2E test runs and demo recording (Phase 5).** Running the full E2E test suite against the real Gemini API triggers 429 (`RESOURCE_EXHAUSTED`) responses after sustained use. Mitigated with exponential backoff in `app/providers/gemini.py` (up to 6 retries, max 80s delay), but this makes the full test suite take 15–30 minutes to run. On the paid tier or with a higher-quota key, this is not an issue. On the free tier, run tests with gaps between suites or use `MOCK_PROVIDERS=true` for rapid iteration.

---

## Project Structure

```
agent-orchestration/
├── backend/
│   ├── app/
│   │   ├── agents/          # Supervisor, Specialists, Reviewer
│   │   ├── api/routes/      # tasks, reviews, memory, traces
│   │   ├── core/            # config, schemas, cost
│   │   ├── graph/           # LangGraph nodes, build_graph, checkpointing
│   │   ├── hitl/            # escalation triggers, approval queue
│   │   ├── memory/          # Redis short-term, ChromaDB long-term, manager, decay
│   │   ├── observability/   # OTel setup, PostgresSpanProcessor
│   │   ├── providers/       # Gemini, Claude, Groq wrappers
│   │   ├── replay/          # replay_engine
│   │   └── tools/           # registry, web_search, db_query, sandboxed_exec, file_io
│   ├── db/
│   │   ├── models.py        # SQLAlchemy models (all tables)
│   │   └── init_db.py
│   └── tests/
│       └── e2e/             # 6 E2E tests (Phase 5)
├── frontend/
│   └── src/
│       ├── pages/           # TaskList, Reviews, TraceExplorer, MemoryDashboard
│       └── components/      # ReviewCard, TraceTree, SpanDetailDrawer, ReplayModal, ...
├── demo/
│   ├── demo_scenario.py     # scripted full-lifecycle demo
│   └── demo.sh              # curl/CLI wrapper
├── context/                 # PRD, TRD, schema, flow, UI spec, implementation plan
├── docs/
│   └── architecture-diagram.svg
├── .github/workflows/
│   ├── ci.yml               # E2E + unit tests against real Postgres/Redis/Chroma
│   └── security-scan.yml    # gitleaks secret scan
├── docker-compose.yml
├── .env.example
└── LICENSE                  # MIT
```

---

## License

MIT — see [`LICENSE`](LICENSE).
