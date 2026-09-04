# PRD — Agent Orchestration System

## 1. Problem Statement
Most public "AI agent" portfolio projects are single-agent toy demos: one LLM call, one tool, no memory, no oversight. Real production agent systems need task decomposition, specialized delegation, persistent memory, and a human safety valve. This project builds that — a supervisor agent that plans, delegates to tool-using specialist agents, validates their work, remembers across sessions, and escalates to a human when confidence is low or the action is sensitive.

## 2. Goals
- Decompose a complex natural-language task into an ordered, dependency-aware subtask plan.
- Execute subtasks via specialized agents (research, data analysis, writing, code execution), each with a bounded tool set.
- Validate specialist output with a reviewer agent before it flows back to the supervisor.
- Maintain short-term (per-task) and long-term (cross-task, semantic) memory that measurably improves planning on repeat/similar tasks.
- Pause and escalate to a human operator on low confidence, repeated failure, sensitive operations, or explicit request — with a real approval UI, not a stub.
- Provide full trace-level observability (who did what, with what tool, at what cost) and the ability to replay any past execution.

## 3. Non-Goals
- Not a general-purpose AI chat product — no consumer-facing chat UI beyond the review interface.
- Not building custom LLM providers — reuses existing Gemini/Claude/Groq wrapper pattern from LLM Gateway.
- Not optimizing for massive concurrent load (LLM Gateway already proved that skill) — this project's proof point is *reasoning/orchestration quality*, not throughput.
- No multi-tenant billing/teams system (LLM Gateway already covers that skill).

## 4. Target Users (portfolio framing)
- Primary: technical interviewers/hiring managers evaluating agentic-systems ability.
- Secondary (real use): Gaurav himself, pointing the system at multi-step research/ops tasks (e.g., market research reports, codebase audits) and at future projects (Atlas Agent, JobPilot) as a reusable orchestration core.

## 5. Core User Stories
1. As an operator, I submit a complex task in natural language and see it decomposed into a visible plan before execution starts (or after, per approval level).
2. As an operator, I can watch specialists execute in real time, see tool calls and reasoning, and see the reviewer catch and reject a bad output at least once in the demo.
3. As an operator, I get interrupted with full context and a clear decision point when the system hits a sensitive action or a low-confidence plan, and I can approve, modify, reject, or take over.
4. As an operator, I can ask the system to do a similar task again later and see that it retrieves and uses a relevant past memory in its new plan.
5. As an operator, I can open the trace explorer for any past run, expand every node, and replay it with a modified input to compare outcomes.

## 6. Success Metrics
- End-to-end demo scenario runs reliably (research → analysis → writing task) with real decomposition, real tool calls, one reviewer rejection-and-retry, one human escalation, and one memory-informed decision — all visible in the trace explorer.
- Memory retrieval demonstrably changes a second run's plan on a repeated/similar task (shown side-by-side in the demo).
- Human review UI: approval decision reaches the paused agent and execution resumes correctly, for all 4 approval levels (Notify, Approve action, Approve plan, Take over).
- Full observability: every supervisor/specialist/reviewer decision, tool call, and escalation has a trace span with latency and cost.
- All 6 phases shipped, containerized, with automated demo script and honest README (including any known limitations, per the LLM Gateway precedent).

## 7. Scope Summary (see TRD for detail)
Full guide scope, no trimming: agent hierarchy + LangGraph state machine, tool registry with real MCP integration, Redis short-term + ChromaDB long-term memory, human-in-the-loop with 4 approval levels, OpenTelemetry tracing + trace explorer + replay, Docker Compose full-system containerization, E2E tests, demo video + narrative.

## 8. Key Decisions Locked
- LLM providers: Gemini + Claude + Groq (reusing proven multi-provider stack from Scoutr / LLM Gateway), not OpenAI+Anthropic as the guide suggests.
- Tool framework: real MCP server integration (not custom-registry-only) — differentiator vs. typical portfolio projects.
- Review UI: React (portfolio polish over Streamlit).
- Build philosophy: full scope, no trimming, same as LLM Gateway.
