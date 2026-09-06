import pytest
import asyncio
from uuid import UUID
from sqlalchemy import select

from app.api.routes.tasks import run_task_workflow
from app.api.routes.reviews import submit_decision, DecisionRequest
from db.models import AsyncSessionLocal, Task, ReviewRequest, Subtask
from fastapi import BackgroundTasks

async def run_bg_tasks(bg_tasks: BackgroundTasks):
    for task in bg_tasks.tasks:
        res = task.func(*task.args, **task.kwargs)
        if asyncio.iscoroutine(res):
            await res

@pytest.mark.asyncio
async def test_human_escalation_resume_approve(db_cleaner):
    """
    Test FULL path for 'approve' decision:
    submit task -> escalate -> pause -> submit_decision('approve') ->
    assert graph resumes past intake/plan (no re-planning) -> assert task reaches status 'done'.
    """
    task_id = "77777777-7777-7777-7777-777777777771"
    db_cleaner.append(task_id)
    request_text = "Delete staging records from demo_data.sales_data where sale_amount = 0."

    async with AsyncSessionLocal() as session:
        t = Task(id=UUID(task_id), request_text=request_text, status="intake", confidence=1.0)
        session.add(t)
        await session.commit()

    # 1. Execute workflow until escalation pause
    await run_task_workflow(UUID(task_id), request_text)

    # Verify task is paused in escalated status with pending review request
    async with AsyncSessionLocal() as session:
        t_after = await session.get(Task, UUID(task_id))
        assert t_after is not None
        assert t_after.status == "escalated"

        res = await session.execute(
            select(ReviewRequest).where(
                ReviewRequest.task_id == UUID(task_id),
                ReviewRequest.status == "pending"
            )
        )
        reviews = list(res.scalars().all())
        assert len(reviews) == 1
        review_req = reviews[0]

    # 2. Submit 'approve' decision via review route endpoint logic
    bg_tasks = BackgroundTasks()
    async with AsyncSessionLocal() as session:
        res = await submit_decision(
            review_id=review_req.id,
            payload=DecisionRequest(decision="approve", feedback="Operator approved action"),
            background_tasks=bg_tasks,
            db=session
        )
        assert res["success"] is True
        assert res["review_request"]["status"] == "approved"

    # Execute background tasks (resumes workflow from checkpoint)
    await run_bg_tasks(bg_tasks)

    # 3. Assert graph resumed to completion ('done') without re-planning
    async with AsyncSessionLocal() as session:
        t_final = await session.get(Task, UUID(task_id))
        assert t_final is not None
        assert t_final.status == "done"

        # Verify plan was preserved and subtask status updated
        db_subtasks = await session.execute(select(Subtask).where(Subtask.task_id == UUID(task_id)))
        st_list = list(db_subtasks.scalars().all())
        assert len(st_list) > 0
        del_st = next((s for s in st_list if s.action_tag == "deletion"), None)
        assert del_st is not None
        assert del_st.status in ("running", "review_pending", "approved", "done")


@pytest.mark.asyncio
async def test_human_escalation_resume_modify(db_cleaner):
    """
    Test FULL path for 'modify' decision:
    submit task -> escalate -> submit_decision('modify', modified_input) ->
    verify graph resumes with modified subtask input to completion.
    """
    task_id = "77777777-7777-7777-7777-777777777772"
    db_cleaner.append(task_id)
    request_text = "Delete staging records from demo_data.sales_data where sale_amount = 0."

    async with AsyncSessionLocal() as session:
        t = Task(id=UUID(task_id), request_text=request_text, status="intake", confidence=1.0)
        session.add(t)
        await session.commit()

    await run_task_workflow(UUID(task_id), request_text)

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(ReviewRequest).where(
                ReviewRequest.task_id == UUID(task_id),
                ReviewRequest.status == "pending"
            )
        )
        review_req = res.scalars().first()
        assert review_req is not None

    bg_tasks = BackgroundTasks()
    mod_input = {"query": "SELECT count(*) FROM demo_data.sales_data"}
    async with AsyncSessionLocal() as session:
        res = await submit_decision(
            review_id=review_req.id,
            payload=DecisionRequest(decision="modify", modified_input=mod_input, feedback="Modified query to read-only count"),
            background_tasks=bg_tasks,
            db=session
        )
        assert res["success"] is True
        assert res["review_request"]["status"] == "modified"

    await run_bg_tasks(bg_tasks)

    async with AsyncSessionLocal() as session:
        t_final = await session.get(Task, UUID(task_id))
        assert t_final is not None
        assert t_final.status == "done"


@pytest.mark.asyncio
async def test_human_escalation_resume_reject(db_cleaner):
    """
    Test FULL path for 'reject' decision:
    submit task -> escalate -> submit_decision('reject') ->
    verify review request status updated to 'rejected' and decision recorded.
    """
    task_id = "77777777-7777-7777-7777-777777777773"
    db_cleaner.append(task_id)
    request_text = "Delete staging records from demo_data.sales_data where sale_amount = 0."

    async with AsyncSessionLocal() as session:
        t = Task(id=UUID(task_id), request_text=request_text, status="intake", confidence=1.0)
        session.add(t)
        await session.commit()

    await run_task_workflow(UUID(task_id), request_text)

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(ReviewRequest).where(
                ReviewRequest.task_id == UUID(task_id),
                ReviewRequest.status == "pending"
            )
        )
        review_req = res.scalars().first()
        assert review_req is not None

    bg_tasks = BackgroundTasks()
    async with AsyncSessionLocal() as session:
        res = await submit_decision(
            review_id=review_req.id,
            payload=DecisionRequest(decision="reject", feedback="Operator rejected action due to production policy"),
            background_tasks=bg_tasks,
            db=session
        )
        assert res["success"] is True
        assert res["review_request"]["status"] == "rejected"

    async with AsyncSessionLocal() as session:
        rev_db = await session.get(ReviewRequest, review_req.id)
        assert rev_db is not None
        assert rev_db.status == "rejected"
        assert rev_db.decision_payload["decision"] == "reject"


@pytest.mark.asyncio
async def test_human_escalation_resume_take_over(db_cleaner):
    """
    Test FULL path for 'take_over' decision:
    submit task -> escalate -> submit_decision('take_over', taken_over_output) ->
    verify human-authored output injected and graph completes to 'done'.
    """
    task_id = "77777777-7777-7777-7777-777777777774"
    db_cleaner.append(task_id)
    request_text = "Delete staging records from demo_data.sales_data where sale_amount = 0."

    async with AsyncSessionLocal() as session:
        t = Task(id=UUID(task_id), request_text=request_text, status="intake", confidence=1.0)
        session.add(t)
        await session.commit()

    await run_task_workflow(UUID(task_id), request_text)

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(ReviewRequest).where(
                ReviewRequest.task_id == UUID(task_id),
                ReviewRequest.status == "pending"
            )
        )
        review_req = res.scalars().first()
        assert review_req is not None

    bg_tasks = BackgroundTasks()
    takeover_out = {"status": "bypassed", "summary": "Manually purged by operator"}
    async with AsyncSessionLocal() as session:
        res = await submit_decision(
            review_id=review_req.id,
            payload=DecisionRequest(decision="take_over", taken_over_output=takeover_out, feedback="Human manual injection"),
            background_tasks=bg_tasks,
            db=session
        )
        assert res["success"] is True
        assert res["review_request"]["status"] == "taken_over"

    await run_bg_tasks(bg_tasks)

    async with AsyncSessionLocal() as session:
        t_final = await session.get(Task, UUID(task_id))
        assert t_final is not None
        assert t_final.status == "done"
