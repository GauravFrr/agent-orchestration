# Production-Grade Folder Structure — Agent Orchestration System

This is the target repo layout. All phase file-touch maps in `06_implementation_plan.md` map onto this tree — nothing outside it unless explicitly flagged and approved.

```
agent-orchestration-system/
├── AGENT.md
├── README.md
├── LICENSE
├── docker-compose.yml
├── .env.example
├── .gitignore
├── Makefile
│
├── context/                          # spec suite (this doc set)
│   ├── 01_PRD.md
│   ├── 02_TRD.md
│   ├── 03_backend_schema.md
│   ├── 04_app_flow.md
│   ├── 05_ui_ux.md
│   ├── 06_implementation_plan.md
│   ├── 07_coding_style.md
│   ├── 08_security.md
│   ├── 09_dependencies.md
│   └── 10_folder_structure.md
│
├── backend/
│   ├── pyproject.toml
│   ├── Dockerfile
│   ├── app/
│   │   ├── main.py
│   │   ├── core/
│   │   │   ├── config.py
│   │   │   └── schemas.py
│   │   ├── api/
│   │   │   └── routes/
│   │   │       ├── tasks.py
│   │   │       ├── reviews.py
│   │   │       ├── memory.py
│   │   │       └── traces.py
│   │   ├── graph/
│   │   │   ├── state.py
│   │   │   ├── build_graph.py
│   │   │   ├── checkpointing.py
│   │   │   └── nodes/
│   │   │       ├── intake.py
│   │   │       ├── plan.py
│   │   │       ├── dispatch.py
│   │   │       ├── review.py
│   │   │       └── synthesize.py
│   │   ├── agents/
│   │   │   ├── supervisor.py
│   │   │   ├── reviewer.py
│   │   │   ├── prompts/
│   │   │   └── specialists/
│   │   │       ├── research.py
│   │   │       ├── data_analysis.py
│   │   │       ├── writing.py
│   │   │       └── code_exec.py
│   │   ├── tools/
│   │   │   ├── registry.py
│   │   │   ├── web_search.py
│   │   │   ├── file_io.py
│   │   │   ├── sandboxed_exec.py
│   │   │   ├── db_query.py
│   │   │   └── mcp_client.py
│   │   ├── providers/
│   │   │   ├── gemini.py
│   │   │   ├── claude.py
│   │   │   └── groq.py
│   │   ├── memory/
│   │   │   ├── short_term.py
│   │   │   ├── long_term.py
│   │   │   ├── manager.py
│   │   │   └── decay.py
│   │   ├── hitl/
│   │   │   ├── triggers.py
│   │   │   ├── approval_levels.py
│   │   │   └── queue.py
│   │   ├── observability/
│   │   │   ├── tracing.py
│   │   │   └── cost.py
│   │   └── replay/
│   │       └── replay_engine.py
│   ├── db/
│   │   ├── models.py
│   │   └── migrations/
│   │       └── versions/
│   └── tests/
│       ├── unit/
│       ├── integration/
│       └── e2e/
│           ├── test_plan_decomposition.py
│           ├── test_specialist_tool_use.py
│           ├── test_reviewer_rejection_retry.py
│           ├── test_memory_informs_planning.py
│           ├── test_human_escalation_timing.py
│           └── test_agent_failure_recovery.py
│
├── frontend/
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── Dockerfile
│   └── src/
│       ├── main.tsx
│       ├── App.tsx
│       ├── api/
│       │   ├── tasks.ts
│       │   ├── reviews.ts
│       │   └── traces.ts
│       ├── hooks/
│       │   └── useReviewSocket.ts
│       ├── lib/
│       │   └── statusColors.ts
│       ├── pages/
│       │   ├── Home.tsx
│       │   ├── Reviews.tsx
│       │   ├── TraceExplorer.tsx
│       │   └── Memory.tsx
│       └── components/
│           ├── PlanGraph.tsx
│           ├── ReviewCard.tsx
│           ├── ChatWithAgent.tsx
│           ├── TraceTree.tsx
│           ├── SpanDetailDrawer.tsx
│           ├── ReplayModal.tsx
│           └── CostPerfStrip.tsx
│
├── demo/
│   ├── demo_scenario.py
│   └── demo.sh
│
├── docs/
│   └── architecture-diagram.png
│
├── scripts/
│   └── check_secrets.sh
│
└── .github/
    └── workflows/
        ├── ci.yml
        └── security-scan.yml
```

## Notes
- `context/` is committed inside the repo, same as LLM Gateway — the spec suite is part of the portfolio artifact, not thrown away after the build.
- `backend/app/` grouping is by concern (graph, agents, tools, memory, hitl, observability, replay) rather than by layer — keeps each phase's file-touch map cleanly scoped to one or two top-level folders.
- `frontend/` is a single React app with three routed pages, not three separate apps — matches the UI/UX doc's "one app, shared design language" decision.
