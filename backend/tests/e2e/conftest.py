import pytest
import asyncio
from uuid import UUID
from typing import AsyncGenerator
from sqlalchemy import text
from db.models import AsyncSessionLocal

import pytest_asyncio

@pytest_asyncio.fixture(autouse=True)
async def db_cleaner() -> AsyncGenerator[None, None]:
    """
    Automatic cleanup fixture that tracks and deletes test-created rows
    across tasks, subtasks, review_requests, checkpoints, trace_spans, and replays
    after every test execution.
    """
    test_task_ids = []
    yield test_task_ids

    # Teardown logic
    async with AsyncSessionLocal() as session:
        for tid in test_task_ids:
            try:
                task_uuid = UUID(str(tid))
                await session.execute(text("DELETE FROM public.review_requests WHERE task_id = :tid"), {"tid": task_uuid})
                await session.execute(text("DELETE FROM public.trace_spans WHERE task_id = :tid"), {"tid": task_uuid})
                await session.execute(text("DELETE FROM public.replays WHERE original_task_id = :tid OR resulting_task_id = :tid"), {"tid": task_uuid})
                await session.execute(text("DELETE FROM public.checkpoints WHERE thread_id = :tid"), {"tid": str(tid)})
                await session.execute(text("DELETE FROM public.subtasks WHERE task_id = :tid"), {"tid": task_uuid})
                await session.execute(text("DELETE FROM public.tasks WHERE id = :tid"), {"tid": task_uuid})
                await session.commit()
            except Exception:
                await session.rollback()
