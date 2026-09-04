import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

import redis
from sqlalchemy import select

from app.core.config import settings
from db.models import AsyncSessionLocal, ReviewRequest

logger = logging.getLogger(__name__)

# Redis client for pub/sub notifications
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

async def create_review_request(
    task_id: str,
    subtask_id: Optional[str],
    trigger_reason: str,
    approval_level: str,
    context_snapshot: Dict[str, Any]
) -> ReviewRequest:
    """
    Create a new ReviewRequest record in PostgreSQL if one is not already pending.
    """
    async with AsyncSessionLocal() as session:
        task_uuid = UUID(task_id) if isinstance(task_id, str) else task_id

        # Deduplicate: check if a pending review already exists for this task and subtask
        existing_res = await session.execute(
            select(ReviewRequest).where(
                ReviewRequest.task_id == task_uuid,
                ReviewRequest.subtask_id == subtask_id,
                ReviewRequest.status == "pending"
            )
        )
        existing = existing_res.scalar_one_or_none()
        if existing:
            logger.info(f"Pending ReviewRequest {existing.id} already exists for task {task_id}")
            return existing

        review_req = ReviewRequest(
            id=uuid4(),
            task_id=task_uuid,
            subtask_id=subtask_id,
            trigger_reason=trigger_reason,
            approval_level=approval_level,
            context_snapshot=context_snapshot,
            status="pending",
            created_at=datetime.utcnow()
        )
        session.add(review_req)
        await session.commit()
        await session.refresh(review_req)
        logger.info(f"Created ReviewRequest {review_req.id} for task {task_id} (reason: {trigger_reason}, level: {approval_level})")

    # Publish notification to Redis pub/sub
    notify_pending_review(str(task_id), str(review_req.id), trigger_reason, approval_level)
    return review_req

def notify_pending_review(task_id: str, review_id: str, trigger_reason: str, approval_level: str):
    """
    Publish a notification event to Redis pub/sub channel 'reviews:pending'.
    """
    try:
        payload = {
            "type": "review_pending",
            "task_id": task_id,
            "review_id": review_id,
            "trigger_reason": trigger_reason,
            "approval_level": approval_level,
            "timestamp": datetime.utcnow().isoformat()
        }
        redis_client.publish("reviews:pending", json.dumps(payload))
        logger.info(f"Published review notification to Redis channel 'reviews:pending' for review {review_id}")
    except Exception as e:
        logger.error(f"Failed to publish review notification to Redis: {e}")
