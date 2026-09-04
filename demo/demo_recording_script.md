# Demo Recording Script — Agent Orchestration System
# Target runtime: ≤ 5 minutes
# Prerequisites: `docker-compose up --build` already running, all services healthy

---

## Pre-recording checklist (do before hitting record)

- [ ] Browser open to `http://localhost:3000` — Task List page visible
- [ ] Second browser tab open to `http://localhost:3000/reviews` — Reviews page
- [ ] Third browser tab open to `http://localhost:3000/traces` — Trace Explorer
- [ ] Terminal open at project root (where `docker-compose.yml` lives)
- [ ] `.env` has `GEMINI_API_KEY` set

---

## Recording Steps

### [0:00 – 0:20] Context — what we're looking at

- Show browser with 3 tabs labeled: Tasks, Reviews, Trace Explorer
- Say: "This is the Agent Orchestration System. I submit a task in natural language, the supervisor decomposes it into a plan, specialists execute it with real tool calls, a reviewer catches bad output, a human approves a sensitive action, and every decision is traceable and replayable."

---

### [0:20 – 0:50] Step 1 — Submit the demo task

In the terminal:
```bash
python demo/demo_scenario.py &
```

OR open a new terminal tab and run:
```bash
curl -s -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"request_text": "Research recent agent orchestration trends, query customer churn trends in sales data, write a comprehensive synthesis report, and delete temporary staging records from demo_data.sales_data."}' \
  | python -m json.tool
```

- Show the terminal output: task ID is returned
- Switch to the **Tasks** tab in the browser — the task appears with status `planning`

---

### [0:50 – 1:30] Step 2 — Watch the plan appear

- Refresh or wait for the Tasks page to update — status moves to `executing`
- Click the task row to expand or navigate to task detail
- Show the decomposed plan with 4 subtasks: research, data_analysis, writing, deletion (the deletion one will trigger escalation)
- Note: research and data_analysis are running in parallel (no dependencies between them); writing depends on both

---

### [1:30 – 2:00] Step 3 — Human escalation appears

- Switch to the **Reviews** tab
- A new review request appears for the `delete from demo_data.sales_data` subtask
- Click it — show the full context: trigger reason = "action_tag: deletion", approval level = "APPROVE_ACTION", full subtask context
- Say: "LangGraph execution is paused with state checkpointed to Postgres. The system is waiting for my approval."

---

### [2:00 – 2:20] Step 4 — Approve the escalation

- Click **Approve** (or submit via curl):
```bash
# Replace {review_id} with the ID shown on screen
curl -s -X POST http://localhost:8000/reviews/{review_id}/decision \
  -H "Content-Type: application/json" \
  -d '{"decision": "approve", "notes": "Approved staging table cleanup by operator."}' \
  | python -m json.tool
```
- Show response: `{"success": true}`
- Switch back to Tasks — status moves from `escalated` back to `executing`, then to `completed`

---

### [2:20 – 2:50] Step 5 — Inspect the trace

- Switch to the **Trace Explorer** tab
- Click the completed task — the full span tree expands:
  - `NODE intake` → `NODE plan` → `LLM supervisor/plan` (show cost and token count)
  - `NODE dispatch` → specialist spans with tool calls
  - `NODE review` → `LLM reviewer/eval` (point out the rejection+retry if visible)
  - `NODE synthesize` → `LLM supervisor/synth`
- Click any LLM span — the **Span Detail Drawer** opens showing the full prompt and response payload
- Point to the total cost strip at the top

---

### [2:50 – 3:20] Step 6 — Replay from a checkpoint

- In the Trace Explorer, click the `plan` span
- Click **Replay from here** button in the Span Detail Drawer
- A replay modal appears — submit it
- A new linked task ID is created (show the "Replay of ..." prefix in the task list)
- Check docker logs to confirm native checkpoint path:
```bash
docker logs agent_api 2>&1 | grep "PATH: NATIVE_LANGGRAPH_CHECKPOINT" | tail -1
```
- Show the log line: `Loaded checkpoint via native LangGraph aget_tuple ... [PATH: NATIVE_LANGGRAPH_CHECKPOINT]`

---

### [3:20 – 4:00] Step 7 — Memory-informed second run

- Submit a similar task in the terminal:
```bash
curl -s -X POST http://localhost:8000/tasks \
  -H "Content-Type: application/json" \
  -d '{"request_text": "Research agent orchestration trends and query customer churn in sales data."}' \
  | python -m json.tool
```
- Wait for it to reach `executing` — then go to Trace Explorer and open the new task
- Click the `plan` span → Span Detail Drawer → scroll through the prompt payload
- Show the `=== RETRIEVED CONTEXT FROM PAST EXECUTIONS ===` block — the supervisor can see what worked last time
- Say: "The second plan differs: fewer subtasks, better tool choices, because memory retrieval augmented the supervisor's prompt before the LLM call."

---

### [4:00 – 4:30] Step 8 — Memory Dashboard

- Navigate to `http://localhost:3000/memory`
- Show the stored memories: past plans, domain facts ("Agent orchestration is shifting toward decentralized multi-agent networks"), user preferences
- Optionally click Delete on one memory to show hard-delete (ChromaDB + Postgres)

---

### [4:30 – 4:50] Wrap up

- Return to the terminal where `demo_scenario.py` was running — show the `DEMO SCENARIO COMPLETED SUCCESSFULLY!` message
- Say: "Full lifecycle in one script: decomposition, real tool calls, reviewer rejection-and-retry, human escalation with approval, memory-informed second run, and checkpoint replay — all fully traced and observable."

---

## Notes for editing

- Cut the rate-limit backoff waiting time (Gemini free tier can add 30–80 second pauses during replay and second run)
- Total raw recording will likely be 8–12 minutes due to API latency; edited cut should hit ≤5 minutes by fast-forwarding the wait periods
- If recording on paid Gemini tier: no backoff needed, raw recording should already be ≤5 minutes
