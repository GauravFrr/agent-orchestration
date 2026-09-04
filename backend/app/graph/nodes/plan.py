import logging
from uuid import UUID

from app.agents.supervisor import SupervisorAgent
from app.graph.state import AgentState
from app.observability.tracing import get_tracer
from db.models import AsyncSessionLocal, Subtask, Task

logger = logging.getLogger(__name__)

async def plan_node(state: AgentState) -> dict:
    """
    Plan node. Decomposes the task into subtasks using the Supervisor and saves it to the database.
    """
    task_id = state.get("task_id")
    request_text = state.get("request_text")
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
        "plan",
        attributes={
            "task_id": str(task_id),
            "span_type": "plan",
            "actor": "supervisor"
        }
    ) as span:
        if cp_id:
            span.set_attribute("checkpoint_id", cp_id)
        logger.info(f"Plan node started for task: {task_id}")

        from app.memory.manager import MemoryManager
        mem_manager = MemoryManager()
        memories_text = await mem_manager.retrieve_context(request_text)

        request_for_plan = request_text
        if memories_text:
            request_for_plan = f"{request_text}\n\n{memories_text}"
            logger.info(f"Injected retrieved context into request for planning task {task_id}")

        import json
        span.set_attribute("payload", json.dumps({"request_text": request_for_plan}))
        logger.info(f"Final prompt text sent to supervisor for task {task_id}:\n{request_for_plan}")

        supervisor = SupervisorAgent()
        # Call Supervisor planning logic
        plan, in_tokens, out_tokens = await supervisor.plan(request_for_plan, task_id=str(task_id))

        from app.core.config import settings
        from app.core.cost import record_llm_cost
        model = settings.DEFAULT_MODEL_GEMINI if (settings.GEMINI_API_KEY or settings.MOCK_PROVIDERS) else settings.DEFAULT_MODEL_CLAUDE
        await record_llm_cost(task_id, model, in_tokens, out_tokens)

        # Save to database
        async with AsyncSessionLocal() as session:
            task_uuid = UUID(task_id)
            task = await session.get(Task, task_uuid)

            if not task:
                task = Task(
                    id=task_uuid,
                    request_text=request_text,
                    status="executing",
                    confidence=plan.confidence,
                    plan=plan.model_dump()
                )
                await session.merge(task)
            else:
                task.plan = plan.model_dump()
                task.confidence = plan.confidence
                task.status = "executing"

            # Create subtask records in database
            for subtask_schema in plan.subtasks:
                db_subtask = Subtask(
                    id=subtask_schema.id,
                    task_id=task_uuid,
                    specialist=subtask_schema.specialist.value,
                    input=subtask_schema.input,
                    depends_on=subtask_schema.depends_on,
                    status="pending",
                    action_tag=subtask_schema.action_tag
                )
                await session.merge(db_subtask)

            await session.commit()
            logger.info(f"Generated plan with {len(plan.subtasks)} subtasks. Saved to DB.")

            # Save initial working state to Redis
            from app.memory.short_term import save_working_state
            save_working_state(task_id, plan.model_dump(), {}, {})

        return {
            "plan": plan,
            "status": "executing"
        }
