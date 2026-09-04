import logging
from datetime import datetime
from uuid import UUID
from app.graph.state import AgentState
from app.agents.supervisor import SupervisorAgent
from db.models import AsyncSessionLocal, Task

from app.observability.tracing import get_tracer

logger = logging.getLogger(__name__)

async def synthesize_node(state: AgentState) -> dict:
    """
    Synthesize node. Combines all subtask outputs using the Supervisor and saves the final response.
    """
    task_id = state.get("task_id")
    request_text = state.get("request_text")
    results = state.get("results", {})
    tracer = get_tracer()

    from sqlalchemy import text
    cp_id = None
    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT checkpoint_id FROM public.checkpoints WHERE thread_id = :th ORDER BY checkpoint_id DESC LIMIT 1"), {"th": str(task_id)})
            row = res.fetchone()
            if row:
                cp_id = row[0]
    except Exception:
        pass

    with tracer.start_as_current_span(
        "synthesize",
        attributes={
            "task_id": str(task_id),
            "span_type": "synthesize",
            "actor": "supervisor"
        }
    ) as span:
        if cp_id:
            span.set_attribute("checkpoint_id", cp_id)
        logger.info(f"Synthesize node started for task: {task_id}")

        supervisor = SupervisorAgent()
        synthesis_output, in_t, out_t = await supervisor.synthesize(request_text, results, task_id=str(task_id))

        from app.core.cost import record_llm_cost
        from app.core.config import settings
        model = settings.DEFAULT_MODEL_GEMINI if (settings.GEMINI_API_KEY or settings.MOCK_PROVIDERS) else settings.DEFAULT_MODEL_CLAUDE
        await record_llm_cost(task_id, model, in_t, out_t)

    # Update database
    async with AsyncSessionLocal() as session:
        task_uuid = UUID(task_id)
        task = await session.get(Task, task_uuid)
        
        if task:
            task.status = "done"
            # In Phase 1 we can save the synthesis response in a custom field or serialize it.
            # Let's save it by wrapping the task plan with a final result or output,
            # or in a new column. Wait! The tasks table schema lists `completed_at` and `total_cost_usd` but no direct final response text column.
            # Let's check `context/03_backend_schema.md` Tasks table:
            # | id | request_text | status | plan | confidence | created_at/updated_at | completed_at | total_cost_usd |
            # Where is the final output stored? In `04_app_flow.md` line 10 it says:
            # "deliver -> task status done, final output returned via WebSocket + GET /tasks/{id}."
            # Since there's no separate output column in the schema, we can store the final synthesis inside the `plan` field (e.g. `task.plan['synthesis'] = synthesis_output`),
            # or update the plan JSONB structure. This is extremely clean because plan is JSONB and can contain any final execution metadata!
            # Let's save the final output inside the task's plan dictionary under "synthesis".
            plan_data = dict(task.plan) if task.plan else {}
            plan_data["synthesis"] = synthesis_output
            task.plan = plan_data
            
            task.completed_at = datetime.utcnow()
            await session.commit()
            logger.info(f"Task {task_id} completed. Final synthesis saved.")
            
            # Save final working state to Redis and set 24h expiration
            from app.memory.short_term import save_working_state, set_working_state_ttl
            errors = state.get("errors", {})
            save_working_state(task_id, task.plan, results, errors)
            set_working_state_ttl(task_id)

            # Extract and store long-term semantic memories
            from app.memory.manager import MemoryManager
            import asyncio
            asyncio.create_task(MemoryManager().create_memories(task_id, request_text, task.plan, "done"))
        else:
            logger.error(f"Task with ID {task_id} not found in database during synthesis.")

    return {
        "synthesis": synthesis_output,
        "status": "done"
    }
