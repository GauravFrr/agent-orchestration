import json
import logging
from typing import Any, Dict

import redis

from app.core.config import settings

logger = logging.getLogger(__name__)

# Initialize redis connection
redis_client = redis.from_url(settings.REDIS_URL, decode_responses=True)

def save_working_state(task_id: str, plan: Dict[str, Any] | None, completed_outputs: Dict[str, Any], errors: Dict[str, Any]):
    """
    Save current execution state to Redis working memory.
    """
    try:
        key = f"task:{task_id}:state"
        state_data = {
            "plan": plan,
            "completed_outputs": completed_outputs,
            "errors": errors
        }
        redis_client.set(key, json.dumps(state_data))
        logger.info(f"Successfully saved working state to Redis for task {task_id}")
    except Exception as e:
        logger.error(f"Error saving working state to Redis: {str(e)}")

def get_working_state(task_id: str) -> Dict[str, Any] | None:
    """
    Retrieve execution state from Redis working memory.
    """
    try:
        key = f"task:{task_id}:state"
        data = redis_client.get(key)
        if data:
            return json.loads(data)
    except Exception as e:
        logger.error(f"Error retrieving working state from Redis: {str(e)}")
    return None

def set_working_state_ttl(task_id: str, ttl_seconds: int = 86400):
    """
    Set expiration TTL on task working memory (e.g. post-completion).
    """
    try:
        key = f"task:{task_id}:state"
        redis_client.expire(key, ttl_seconds)
        logger.info(f"Set TTL of {ttl_seconds}s on working state for task {task_id}")
    except Exception as e:
        logger.error(f"Error setting TTL on working state: {str(e)}")
