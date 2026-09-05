import pytest
import asyncio
from uuid import UUID
from typing import AsyncGenerator
from sqlalchemy import text
from db.models import AsyncSessionLocal

import pytest_asyncio

@pytest_asyncio.fixture(autouse=True)
async def db_cleaner() -> AsyncGenerator[list, None]:
    """
    Automatic cleanup fixture that tracks and deletes test-created rows
    across tasks, subtasks, review_requests, checkpoints, trace_spans, and replays
    both BEFORE and AFTER test execution for total idempotency.
    """
    test_task_ids = []

    async def cleanup_ids(ids):
        async with AsyncSessionLocal() as session:
            for tid in ids:
                try:
                    task_uuid = UUID(str(tid))
                    await session.execute(text("DELETE FROM public.review_requests WHERE task_id = :tid"), {"tid": task_uuid})
                    await session.execute(text("DELETE FROM public.trace_spans WHERE task_id = :tid"), {"tid": task_uuid})
                    await session.execute(text("DELETE FROM public.replays WHERE original_task_id = :tid OR resulting_task_id = :tid"), {"tid": task_uuid})
                    await session.execute(text("DELETE FROM public.checkpoints WHERE thread_id = :tid"), {"tid": str(tid)})
                    await session.execute(text("DELETE FROM public.task_checkpoints WHERE task_id = :tid"), {"tid": task_uuid})
                    await session.execute(text("DELETE FROM public.subtasks WHERE task_id = :tid"), {"tid": task_uuid})
                    await session.execute(text("DELETE FROM public.tasks WHERE id = :tid"), {"tid": task_uuid})
                    await session.commit()
                except Exception:
                    await session.rollback()

    known_test_uuids = [
        "11111111-1111-1111-1111-111111111111",
        "22222222-2222-2222-2222-222222222222",
        "33333333-3333-3333-3333-333333333333",
        "44444444-4444-4444-4444-444444444441",
        "44444444-4444-4444-4444-444444444442",
        "55555555-5555-5555-5555-555555555555",
        "66666666-6666-6666-6666-666666666666",
    ]
    await cleanup_ids(known_test_uuids)

    yield test_task_ids

    await cleanup_ids(test_task_ids + known_test_uuids)
