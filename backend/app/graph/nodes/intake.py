import logging
from uuid import UUID

from app.graph.state import AgentState
from app.observability.tracing import get_tracer
from db.models import AsyncSessionLocal, Task

logger = logging.getLogger(__name__)

async def intake_node(state: AgentState) -> dict:
    """
    Intake node. Creates/updates the task in the database and transitions status to planning.
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
        "intake",
        attributes={
            "task_id": str(task_id),
            "span_type": "node",
            "actor": "system",
            "payload": {"request_text": request_text}
        }
    ) as span:
        if cp_id:
            span.set_attribute("checkpoint_id", cp_id)
        logger.info(f"Intake node started for task: {task_id}")

        async with AsyncSessionLocal() as session:
            # Check if task already exists
            task_uuid = UUID(task_id)
            task = await session.get(Task, task_uuid)

            if not task:
                # Create a new task record in case it wasn't pre-created
                task = Task(
                    id=task_uuid,
                    request_text=request_text,
                    status="planning",
                    confidence=1.0
                )
                session.add(task)
                logger.info(f"Created new database task record: {task_id}")
            else:
                task.status = "planning"
                logger.info(f"Updated existing database task status to planning: {task_id}")

            await session.commit()

        return {"status": "planning"}
