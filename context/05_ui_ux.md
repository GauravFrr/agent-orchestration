# UI/UX — Agent Orchestration System

Two React surfaces, one app (routed), sharing the design language: dense, technical, dark-mode-first — think Grafana/Linear, not consumer chat UI. This mirrors the LLM Gateway's Grafana dashboards as the observability aesthetic reference.

## 1. Task Submission + Live Execution View (`/`)
- Left: task input box (textarea + submit), list of past tasks (status pill: planning/executing/escalated/done/failed).
- Center: **live plan graph** — nodes = subtasks, edges = dependencies, color-coded by status (pending gray, running blue pulsing, review-pending amber, done green, failed/rejected red). Updates via WebSocket.
- Right panel (context-sensitive): click a node → shows its input, live tool calls as they happen, reasoning trace, retry count.
- Top bar: task-level confidence score, running cost counter, elapsed time.

## 2. Human Review Interface (`/reviews`)
Queue list (left) + decision panel (right) for the selected `review_request`:
- **Header**: trigger reason badge (low confidence / sensitive action / repeated failure / reviewer flag / user requested), approval level badge (Notify / Approve Action / Approve Plan / Take Over).
- **Context block**: original request, full plan so far, completed subtask outputs (collapsible), the specific pending decision.
- **Proposed action card**: what the agent wants to do next + its stated reasoning, side-by-side with any relevant past decision pulled from memory ("last time a similar action was approved/rejected because...").
- **Chat panel**: free-text Q&A with the paused agent (scoped read-only query against current context — does not mutate state) so the human can ask "why do you want to do this" before deciding.
- **Action bar**: Approve / Modify (opens an editable JSON/text field for the action) / Reject (reason required) / Take Over (human supplies output directly). Disabled states make the required level's minimum action obvious (e.g. Notify only shows "Acknowledge").

## 3. Trace Explorer (`/traces/:taskId`)
- **Tree view**: expandable hierarchy — Task → Plan → Subtask → Tool Calls / Reviewer verdict, mirroring `trace_spans.parent_span_id` nesting. Each node shows actor, latency, cost, status icon.
- **Node detail drawer**: full prompt/response payload, tokens in/out, cost, timestamps — expand-in-place, no separate page.
- **Cost/perf strip** at top: total cost, total latency, cost-by-agent bar, cost-by-tool bar (small inline charts, not full dashboards — full aggregate dashboards are a stretch item, not core scope).
- **Replay button** on any node → opens a modal to optionally edit that step's input, then "Run Replay" → opens the new run in a split view (original left, replay right) with divergence highlighted from that node onward.

## 4. Memory Dashboard (`/memory`)
- Table of stored memories: type (plan/fact/preference), summary, importance score, retrieval count, source task link, age.
- Filter by type, sort by importance/recency.
- Per-row delete button (calls the hard-delete endpoint) — surfaces the privacy-by-design commitment explicitly in the UI, not just the API.

## 5. Visual/Interaction Notes
- Status colors consistent across all three surfaces (same palette as the plan graph).
- No modal-heavy flows except the replay input-override editor — everything else is inline/drawer to keep the live-execution feel.
- WebSocket reconnect handled gracefully (existing state doesn't flash/reset on reconnect).
