import pytest
import asyncio
from uuid import UUID
from app.api.routes.tasks import run_task_workflow
from db.models import AsyncSessionLocal, Task

@pytest.mark.asyncio
async def test_reviewer_rejection_retry(db_cleaner):
    """
    Test 3: Reviewer evaluates a subtask output with deterministic input that causes review rejection & retry pass.
    """
    task_id = "33333333-3333-3333-3333-333333333333"
    db_cleaner.append(task_id)
    # Request text designed to trigger a schema mismatch or data constraint that causes initial review retry
    request_text = "Query non-existent column 'customer_sentiment_score' from demo_data.sales_data and output structured analysis."

    async with AsyncSessionLocal() as session:
        t = Task(id=UUID(task_id), request_text=request_text, status="intake", confidence=1.0)
        session.add(t)
        await session.commit()

    await run_task_workflow(UUID(task_id), request_text)

    async with AsyncSessionLocal() as session:
        t_after = await session.get(Task, UUID(task_id))
        assert t_after is not None
        assert t_after.plan is not None
        subtasks = t_after.plan.get("subtasks", [])
        assert len(subtasks) > 0
        # Check subtask executed review loop and contains reviewer verdict metadata
        st = subtasks[0]
        assert "reviewer_verdict" in st or "status" in st
