import pytest
import asyncio
from uuid import UUID
from app.api.routes.tasks import run_task_workflow
from db.models import AsyncSessionLocal, Task

@pytest.mark.asyncio
async def test_plan_decomposition(db_cleaner):
    """
    Test 1: Valid plan decomposition into a dependency-aware subtask list.
    """
    task_id = "11111111-1111-1111-1111-111111111111"
    db_cleaner.append(task_id)
    request_text = "Research market trends in agent orchestration and write a brief summary report."

    # Create task record in DB
    async with AsyncSessionLocal() as session:
        t = Task(id=UUID(task_id), request_text=request_text, status="intake", confidence=1.0)
        session.add(t)
        await session.commit()

    # Run task workflow
    await run_task_workflow(UUID(task_id), request_text)

    # Verify task decomposition in DB
    async with AsyncSessionLocal() as session:
        t_after = await session.get(Task, UUID(task_id))
        assert t_after is not None
        assert t_after.plan is not None
        subtasks = t_after.plan.get("subtasks", [])
        assert len(subtasks) >= 2
        # Check subtasks have IDs and specialist assignments
        for st in subtasks:
            assert "id" in st
            assert "specialist" in st
            assert "input" in st
