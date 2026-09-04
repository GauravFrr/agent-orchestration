import logging
from typing import Dict, Any, Optional, List
from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from db.models import get_db_session, Task, Replay
from app.observability.tracing import get_task_trace_tree
from app.replay.replay_engine import execute_replay

logger = logging.getLogger(__name__)

router = APIRouter(prefix="", tags=["traces"])

class ReplayRequest(BaseModel):
    checkpoint_id: str = Field(description="UUID string of checkpoint snapshot to resume from")
    input_override: Optional[Dict[str, Any]] = Field(default=None, description="Optional payload modifications to apply")

@router.get("/tasks/{task_id}/trace")
async def get_task_trace(task_id: str):
    """
    Returns full OpenTelemetry span tree hierarchy and metric rollups for a task.
    """
    try:
        tree = await get_task_trace_tree(task_id)
        return tree
    except Exception as e:
        logger.error(f"Error building trace tree for task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Failed to fetch trace: {str(e)}")

@router.post("/tasks/{task_id}/replay")
async def create_task_replay(task_id: str, payload: ReplayRequest):
    """
    Execute a replay run from a given checkpoint ID with optional input override.
    """
    try:
        resulting_task_id = await execute_replay(
            original_task_id=task_id,
            checkpoint_id=payload.checkpoint_id,
            input_override=payload.input_override
        )
        return {
            "success": True,
            "original_task_id": task_id,
            "checkpoint_id": payload.checkpoint_id,
            "resulting_task_id": resulting_task_id
        }
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as e:
        logger.error(f"Error executing replay for task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Replay failed: {str(e)}")

@router.get("/tasks/{task_id}/replays")
async def get_task_replays(task_id: str, db: AsyncSession = Depends(get_db_session)):
    """
    Fetch all replay runs created from or linked to a task.
    """
    from uuid import UUID
    try:
        task_uuid = UUID(task_id)
        query = select(Replay).where(
            (Replay.original_task_id == task_uuid) | (Replay.resulting_task_id == task_uuid)
        ).order_by(Replay.created_at.desc())
        
        res = await db.execute(query)
        replays = list(res.scalars().all())

        return [
            {
                "id": str(r.id),
                "original_task_id": str(r.original_task_id),
                "from_checkpoint_id": r.from_checkpoint_id,
                "input_override": r.input_override,
                "resulting_task_id": str(r.resulting_task_id),
                "created_at": r.created_at.isoformat()
            }
            for r in replays
        ]
    except Exception as e:
        logger.error(f"Error fetching replays for task {task_id}: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))
