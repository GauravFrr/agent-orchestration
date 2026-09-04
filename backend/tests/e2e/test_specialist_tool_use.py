import pytest
import asyncio
from uuid import UUID
from sqlalchemy import select
from app.api.routes.tasks import run_task_workflow
from db.models import AsyncSessionLocal, Task, ToolInvocation

@pytest.mark.asyncio
async def test_specialist_tool_use(db_cleaner):
    """
    Test 2: Specialist actually invokes a real tool (assert tool_invocations row exists).
    """
    task_id = "22222222-2222-2222-2222-222222222222"
    db_cleaner.append(task_id)
    request_text = "Query the sales_data table to get summary metrics."

    # Create task record in DB
    async with AsyncSessionLocal() as session:
        t = Task(id=UUID(task_id), request_text=request_text, status="intake", confidence=1.0)
        session.add(t)
        await session.commit()

    # Run task workflow
    await run_task_workflow(UUID(task_id), request_text)

    # Verify tool_invocations row in DB
    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(ToolInvocation).where(ToolInvocation.task_id == UUID(task_id))
        )
        invocations = list(res.scalars().all())
        assert len(invocations) > 0, "Expected at least one tool_invocations row in DB"
        inv = invocations[0]
        assert inv.tool_name in ["db_query", "file_read", "web_search", "sandboxed_code_exec"]
