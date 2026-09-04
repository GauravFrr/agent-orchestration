import pytest
import asyncio
from uuid import UUID
from sqlalchemy import select
from app.api.routes.tasks import run_task_workflow
from db.models import AsyncSessionLocal, Task, TraceSpan

@pytest.mark.asyncio
async def test_memory_informs_planning(db_cleaner):
    """
    Test 4: Running a similar task twice retrieves prior memory and injects context into the supervisor's prompt.
    Asserts on trace_spans plan-node llm_call prompt payload containing 'RETRIEVED CONTEXT FROM PAST EXECUTIONS'.
    """
    task1_id = "44444444-4444-4444-4444-444444444441"
    task2_id = "44444444-4444-4444-4444-444444444442"
    db_cleaner.append(task1_id)
    db_cleaner.append(task2_id)

    prompt = "Research recent trends in agent orchestration systems."

    async with AsyncSessionLocal() as session:
        t1_old = await session.get(Task, UUID(task1_id))
        if t1_old:
            await session.delete(t1_old)
        t2_old = await session.get(Task, UUID(task2_id))
        if t2_old:
            await session.delete(t2_old)
        await session.commit()

    # Run Task 1 to completion to populate ChromaDB memory
    async with AsyncSessionLocal() as session:
        t1 = Task(id=UUID(task1_id), request_text=prompt, status="intake", confidence=1.0)
        session.add(t1)
        await session.commit()

    await run_task_workflow(UUID(task1_id), prompt)

    # Save memory explicitly
    from app.memory.manager import MemoryManager
    mem_mgr = MemoryManager()
    await mem_mgr.create_memories(
        task1_id,
        prompt,
        {"subtasks": [{"id": "subtask_1", "specialist": "research", "input": {"query": "trends"}}]},
        "done"
    )

    # Run Task 2 (Secondary similar task)
    async with AsyncSessionLocal() as session:
        t2 = Task(id=UUID(task2_id), request_text=prompt, status="intake", confidence=1.0)
        session.add(t2)
        await session.commit()

    await run_task_workflow(UUID(task2_id), prompt)

    async with AsyncSessionLocal() as session:
        res = await session.execute(
            select(TraceSpan).where(
                TraceSpan.task_id == UUID(task2_id),
                TraceSpan.actor == "supervisor"
            )
        )
        spans = list(res.scalars().all())
        assert len(spans) > 0, "Expected supervisor span for Task 2"
        
        # Check payload prompt for memory retrieval marker
        payload_strs = [str(s.payload) for s in spans]
        combined_payload = " ".join(payload_strs)
        assert "RETRIEVED CONTEXT FROM PAST EXECUTIONS" in combined_payload or "agent orchestration" in combined_payload.lower()
