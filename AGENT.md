# AGENT.md — Agent Orchestration System

You are building this project inside the Antigravity IDE. Full spec lives in `context/`. Read the relevant doc(s) before writing code for any phase — do not rely on memory of this file alone.

## Context Documents (read in this order as needed)
1. `context/01_PRD.md` — what and why
2. `context/02_TRD.md` — architecture, components, tech stack
3. `context/03_backend_schema.md` — Postgres tables, ChromaDB collections, Redis keyspace
4. `context/04_app_flow.md` — end-to-end flows, state diagram
5. `context/05_ui_ux.md` — React UI specs (review interface, trace explorer, memory dashboard)
6. `context/06_implementation_plan.md` — phase-by-phase scope + exact file-touch map
7. `context/07_coding_style.md` — conventions
8. `context/08_security.md` — sandboxing, tool boundaries, secrets, privacy
9. `context/09_dependencies.md` — approved dependency list (closed list)

## Hard Rules
1. **Approved dependencies only.** Never `pip install` or `npm install` anything not listed in `context/09_dependencies.md`. If a task seems to need something new, stop and flag it instead of installing.
2. **Fixed provider list.** Only Gemini, Claude, Groq. Never add OpenAI or any other provider even if a library example uses it.
3. **File-touch map is binding.** For the phase in progress, only create/modify files listed in that phase's map in `06_implementation_plan.md`. If something outside the map seems necessary, stop and flag it rather than silently expanding scope.
4. **No hardcoding.** Escalation triggers, approval-level mappings, tool allowlists, and rate limits are config-driven (DB table or config file), never hardcoded conditionals scattered through business logic — see `03_backend_schema.md` and `08_security.md`.
5. **Migrations are additive-only.** Never edit a past migration file; always add a new one.
6. **Every tool call is sandboxed and logged.** No exceptions for the code-execution specialist, per `08_security.md`.
7. **Structured output for control-flow decisions.** Reviewer verdicts and escalation triggers must come from structured/function-call output, never regex/string-matched from free-text LLM output.
8. **Full scope, no silent trimming.** All 6 phases are in scope. If something in the guide scope turns out to be infeasible (like LLM Gateway's Prometheus scrape-interval limitation), document it honestly in the README's Known Limitations — do not quietly drop it without a note.
9. **Real MCP integration is required**, not just a custom tool registry — this is a locked differentiator, not optional polish.

## Phase Tracker
- [x] Phase 1 — Agent Architecture
- [x] Phase 2 — Memory System
- [x] Phase 3 — Human-in-the-Loop
- [x] Phase 4 — Observability
- [x] Phase 5 — Integration + E2E Testing
- [x] Phase 6 — Portfolio Polish

Update this tracker (check the box) only when a phase's exit criteria (stated in `06_implementation_plan.md`) are actually verified, not just implemented.

## When Blocked or Uncertain
Stop and surface the question rather than guessing — especially for: anything touching the security rules above, any new dependency, any deviation from the file-touch map, or any escalation/approval-level default not explicitly specified in the docs.
