# Security — Agent Orchestration System

## 1. Code Execution Sandboxing
- The Code Execution specialist NEVER runs arbitrary code in the API/worker host process. Executes inside a restricted subprocess with: no network access, CPU/memory/time limits (resource limits or a dedicated lightweight container), read-only filesystem except a scoped tmp directory that is wiped after each invocation.
- All sandboxed exec inputs/outputs are logged to `tool_invocations` for audit, including truncated stdout/stderr on failure.

## 2. Tool Registry Boundaries
- Specialists only ever see their declared allowlist (enforced in code, not just by convention — the registry rejects a call from a specialist not on a tool's `allowed_specialists` list).
- MCP tool connections are read-only/scoped wherever the MCP server supports scoping (e.g., filesystem server rooted to a specific directory, fetch/browser tool with a domain allowlist if supported) — never grant a specialist broader MCP server permissions than the task requires.
- Rate limits per tool (reusing the Redis token-bucket pattern from LLM Gateway) to prevent a runaway agent loop from hammering an external API or the sandbox.

## 3. Human-in-the-Loop as a Security Control
- Sensitive-action tags (`financial`, `deletion`, `external_communication`) are a hard-coded minimum trigger set — even if confidence is high, these always route to at least `APPROVE_ACTION`. This is not configurable down to `NOTIFY` for these three tags (config table can add more sensitive tags, but cannot downgrade these three).
- `TAKE_OVER` decisions are logged with the human's identity/timestamp distinctly from agent-generated outputs in `review_requests.decision_payload`, so the trace explorer never conflates human and agent authorship.

## 4. Secrets and Credentials
- All provider API keys (Gemini/Claude/Groq), Postgres, Redis, ChromaDB creds via `.env`, never committed — `.env.example` only, mirroring LLM Gateway.
- `scripts/check_secrets.sh` + `gitleaks` CI job reused from LLM Gateway, confirming no `.env` in git history before each release.
- MCP server credentials (if the connected server needs auth) stored the same way — never inlined in tool registry code.

## 5. Data / Memory Privacy
- Long-term memory (ChromaDB + `memories` table) may contain content derived from user requests — the delete endpoint (`DELETE /memory/{id}`) must hard-purge both the Chroma vector and the Postgres row, not soft-delete-only, once the decay/purge job runs. Soft delete (`deleted_at`) is only a grace-period marker, not the final state.
- No PII-specific handling is assumed beyond what the user explicitly puts in a task request — document this assumption plainly in the README rather than over-claiming compliance.

## 6. Review UI Access
- Review UI and its API are assumed single-operator (Gaurav) for this portfolio scope — no multi-user RBAC is in scope (unlike LLM Gateway's team model). This is stated explicitly as a scope boundary, not silently ignored, so it doesn't read as an oversight in review.

## 7. Dependency Hygiene
- Approved-dependency-only policy (same as LLM Gateway's AGENT.md rule) — no ad-hoc `pip install` mid-build; new dependencies require an explicit update to `09_dependencies.md` first.
- CI security-scan job (`security-scan.yml`, gitleaks) required green before any phase is considered closed, same bar as LLM Gateway.
