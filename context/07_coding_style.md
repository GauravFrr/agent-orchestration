# Coding Style — Agent Orchestration System

Same conventions as LLM Gateway, extended for the agent/graph-specific parts.

## Python
- Python 3.11+, type hints everywhere, `ruff` for lint+format, `pyproject.toml` config (reuse LLM Gateway's baseline config).
- Pydantic v2 models for every LangGraph node's input/output and every API request/response — no raw dicts crossing a node boundary.
- No bare `except:` — catch specific exceptions; agent/tool failures must be typed (`SpecialistError`, `ToolInvocationError`, `ReviewerRejection`, `EscalationRequired`) so the graph's conditional edges can route on exception type, not string matching.
- Async-first for I/O (DB, Redis, HTTP tool calls); Celery tasks are the sync boundary for long-running specialist work.

## LangGraph-Specific Conventions
- One file per node under `graph/nodes/`; nodes are pure functions of `(state) -> state_update`, no hidden side effects outside logging/tracing.
- State object (`graph/state.py`) is the single source of truth — don't smuggle data through globals or module-level caches.
- Conditional edge functions live next to the node that produces the branching decision, not centralized in `build_graph.py` — `build_graph.py` only wires, never decides.
- Every node wrapped in an OTel span from Phase 4 onward; span name = node name, attributes = actor + key state fields (task_id, subtask_id).

## Agents
- Each specialist's tool allowlist is declared as a constant at the top of its module — never resolved dynamically from the full registry, to keep the "bounded tool set" security property auditable at a glance.
- Prompts live in `agents/prompts/` as separate `.py` or `.jinja` files, not inlined as long strings in agent logic — mirrors keeping config out of code.
- Reviewer verdicts are a closed enum (`approve`, `reject`, `escalate`) — no free-form string parsing of LLM output for control flow; use structured output (function calling / JSON mode) for every decision that drives a conditional edge.

## API
- REST resources match Postgres tables where possible (`/tasks`, `/reviews`, `/memory`).
- WebSocket events are typed (`TaskEvent` union type), versioned in a single `events.py`, so the React client and backend never drift silently.

## Frontend (React)
- TypeScript strict mode, functional components + hooks only.
- API calls isolated in `src/api/*.ts`, components never call `fetch` directly.
- Shared status-color mapping in one `src/lib/statusColors.ts` — used by plan graph, review queue, and trace tree so the palette can't drift between the three surfaces (per UI/UX doc).

## Testing
- Unit tests for every node's pure logic (mock the LLM call), integration tests for graph execution against real Postgres/Redis/Chroma test containers (same pattern as LLM Gateway's CI — no SQLite substitution), E2E tests for full scenarios (Phase 5 list).
- Golden-file tests for prompt templates where feasible, so prompt-format regressions are caught in CI.

## Commits / Docs
- Conventional commits, one phase = one or more PRs, phase tracker updated in AGENT.md as phases close (same pattern as LLM Gateway).
- Every honestly-observed limitation or unresolved bug gets written into the README's "Known Limitations" section, never silently dropped — this was a real credibility win in the LLM Gateway README and repeats here.
