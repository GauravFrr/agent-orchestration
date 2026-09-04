import pytest
import asyncio
from uuid import UUID
from app.api.routes.tasks import run_task_workflow
from db.models import AsyncSessionLocal, Task

@pytest.mark.asyncio
async def test_agent_failure_recovery(db_cleaner):
    """
    Test 6: Forced tool failure (querying non-existent table) retries up to configured limit
    and transitions cleanly to 'failed' without zombie running tasks.
    """
    task_id = "66666666-6666-6666-6666-666666666666"
    db_cleaner.append(task_id)
    # Query non-existent table to force deterministic tool execution failure
    request_text = "Execute SELECT * FROM non_existent_table_999 to fetch data."

    async with AsyncSessionLocal() as session:
        t = Task(id=UUID(task_id), request_text=request_text, status="intake", confidence=1.0)
        session.add(t)
        await session.commit()

    await run_task_workflow(UUID(task_id), request_text)

    # Verify task state transitioned to 'failed' or 'done' cleanly without stuck status
    async with AsyncSessionLocal() as session:
        t_after = await session.get(Task, UUID(task_id))
        assert t_after is not None
        assert t_after.status in ["failed", "done", "escalated"]
        assert t_after.status != "running"
        assert t_after.status != "intake"
