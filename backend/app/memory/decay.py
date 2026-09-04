import asyncio
import logging
from datetime import datetime
from uuid import UUID

from celery import Celery
from sqlalchemy import delete, select

from app.core.config import settings
from app.memory.long_term import delete_from_collection
from db.models import AsyncSessionLocal, Memory

logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery(
    "agent_orchestration_tasks",
    broker=settings.REDIS_URL,
    backend=settings.REDIS_URL
)

celery_app.conf.beat_schedule = {
    "decay-memories-every-hour": {
        "task": "app.memory.decay.decay_and_prune_memories",
        "schedule": 3600.0,  # Every hour
    }
}
celery_app.conf.timezone = "UTC"

async def run_decay_and_pruning():
    """
    Decay importance scores of all active memories by 0.95.
    If importance score falls below 0.3, hard-purge from Postgres and ChromaDB.
    """
    logger.info("Starting memory decay and pruning job...")
    DECAY_FACTOR = 0.95
    PRUNE_THRESHOLD = 0.3

    try:
        async with AsyncSessionLocal() as session:
            # Get all active, non-soft-deleted memories
            query = select(Memory).where(Memory.deleted_at.is_(None))
            res = await session.execute(query)
            memories = res.scalars().all()

            for mem in memories:
                # Lower the importance score
                new_score = round(mem.importance_score * DECAY_FACTOR, 4)

                if new_score < PRUNE_THRESHOLD:
                    logger.info(f"Memory {mem.id} score ({new_score}) is below threshold ({PRUNE_THRESHOLD}). Hard-purging.")

                    # 1. Hard delete from ChromaDB
                    collection_map = {
                        "plan": "plans",
                        "fact": "facts",
                        "preference": "preferences"
                    }
                    collection_name = collection_map.get(mem.memory_type)
                    if collection_name:
                        await delete_from_collection(collection_name, str(mem.id))

                    # 2. Hard delete from Postgres
                    await session.delete(mem)
                else:
                    # Update the score
                    mem.importance_score = new_score
                    logger.debug(f"Decayed memory {mem.id} score to {new_score}")

            await session.commit()
            logger.info("Finished memory decay and pruning job successfully.")
    except Exception as e:
        logger.error(f"Error in run_decay_and_pruning: {str(e)}")

@celery_app.task
def decay_and_prune_memories():
    """
    Celery task wrapper to execute async decay logic.
    """
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    loop.run_until_complete(run_decay_and_pruning())
