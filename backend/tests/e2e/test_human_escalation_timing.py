import pytest
import asyncio
from uuid import UUID
from sqlalchemy import select
from app.api.routes.tasks import run_task_workflow
from db.models import AsyncSessionLocal, Task, ReviewRequest

@pytest.mark.asyncio
async def test_human_escalation_timing(db_cleaner):
    """
    Test 5: Sensitive action_tag='deletion' pauses execution and creates EXACTLY ONE pending review_request.
    Validates Phase 3 dedup guarantee.
    """
    task_id = "55555555-5555-5555-5555-555555555555"
    db_cleaner.append(task_id)
    request_text = "Delete all temp records from demo_data.sales_data."

    async with AsyncSessionLocal() as session:
        t = Task(id=UUID(task_id), request_text=request_text, status="intake", confidence=1.0)
        session.add(t)
        await session.commit()

    await run_task_workflow(UUID(task_id), request_text)

    # Verify task state paused in 'escalated' status
    async with AsyncSessionLocal() as session:
        t_after = await session.get(Task, UUID(task_id))
        assert t_after is not None
        assert t_after.status == "escalated"

        # Assert EXACTLY ONE pending review_request row exists in DB
        res = await session.execute(
            select(ReviewRequest).where(
                ReviewRequest.task_id == UUID(task_id),
                ReviewRequest.status == "pending"
            )
        )
        reviews = list(res.scalars().all())
        assert len(reviews) == 1, f"Expected EXACTLY 1 pending review_request, found {len(reviews)}"
        assert reviews[0].approval_level in ["approve_action", "L2_HUMAN_APPROVAL", "L3_EXECUTIVE_SIGN_OFF"]
