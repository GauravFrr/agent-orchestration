import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from psycopg_pool import AsyncConnectionPool

from app.core.config import settings
from db.models import AsyncSessionLocal, Checkpoint

logger = logging.getLogger(__name__)

_checkpointer_instance: Optional[AsyncPostgresSaver] = None
_checkpointer_loop: Optional[asyncio.AbstractEventLoop] = None

def get_checkpointer() -> AsyncPostgresSaver:
    """
    Returns a LangGraph AsyncPostgresSaver checkpointer instance cached per event loop.
    Raises RuntimeError if initialization fails.
    """
    global _checkpointer_instance, _checkpointer_loop
    try:
        current_loop = asyncio.get_running_loop()
    except RuntimeError:
        current_loop = None

    if _checkpointer_instance is None or _checkpointer_loop != current_loop:
        try:
            if _checkpointer_instance and hasattr(_checkpointer_instance, "conn"):
                try:
                    asyncio.create_task(_checkpointer_instance.conn.close())
                except Exception:
                    pass
            conn_str = settings.DATABASE_URL.replace("postgresql+psycopg://", "postgresql://")
            pool = AsyncConnectionPool(conninfo=conn_str, min_size=1, max_size=2, kwargs={"autocommit": True})
            _checkpointer_instance = AsyncPostgresSaver(pool)
            _checkpointer_loop = current_loop
        except Exception as e:
            error_msg = f"Failed to initialize LangGraph AsyncPostgresSaver checkpointer: {str(e)}"
            logger.error(error_msg)
            raise RuntimeError(error_msg) from e
    return _checkpointer_instance

async def save_checkpoint(task_id: str, node_name: str, state_snapshot: Dict[str, Any]) -> str:
    """
    Persist a state snapshot checkpoint to the database. Returns checkpoint ID string.
    """
    cp_id = str(uuid4())
    async with AsyncSessionLocal() as session:
        cp = Checkpoint(
            id=UUID(cp_id),
            task_id=UUID(task_id),
            node_name=node_name,
            state_snapshot=state_snapshot,
            created_at=datetime.utcnow()
        )
        session.add(cp)
        await session.commit()
    logger.info(f"Saved state checkpoint {cp_id} for task {task_id} at node '{node_name}'.")
    return cp_id

async def load_checkpoint(checkpoint_id: str, thread_id: Optional[str] = None) -> Dict[str, Any]:
    """
    Load state snapshot from LangGraph Postgres checkpointer using native aget_tuple or SQL query.
    Logs explicitly whether native checkpoint replay succeeded, and raises ValueError if no valid checkpoint exists.
    """
    checkpointer = get_checkpointer()
    config = {"configurable": {"thread_id": thread_id or "", "checkpoint_id": checkpoint_id}}
    try:
        tuple_res = await checkpointer.aget_tuple(config)
        if tuple_res and tuple_res.checkpoint:
            channel_values = tuple_res.checkpoint.get("channel_values", {})
            logger.info(f"Loaded checkpoint via native LangGraph aget_tuple for thread '{thread_id}', checkpoint '{checkpoint_id}'. [PATH: NATIVE_LANGGRAPH_CHECKPOINT]")
            return channel_values
    except Exception as e:
        logger.warning(f"LangGraph aget_tuple lookup attempted for thread '{thread_id}', checkpoint '{checkpoint_id}': {str(e)}")

    # Fallback to direct raw query on public.checkpoints table by checkpoint_id & thread_id
    from sqlalchemy import text
    async with AsyncSessionLocal() as session:
        query = text("SELECT checkpoint FROM public.checkpoints WHERE checkpoint_id = :cp_id OR (thread_id = :th_id AND checkpoint_id = :cp_id)")
        res = await session.execute(query, {"cp_id": checkpoint_id, "th_id": thread_id or ""})
        row = res.fetchone()
        if row and row[0]:
            cp_dict = row[0]
            logger.info(f"Loaded checkpoint via direct SQL query on public.checkpoints for checkpoint '{checkpoint_id}'. [PATH: RAW_CHECKPOINT_TABLE_QUERY]")
            return cp_dict.get("channel_values", {})

    error_msg = f"No LangGraph checkpoint available for node/checkpoint '{checkpoint_id}' on task/thread '{thread_id}'."
    logger.error(error_msg)
    raise ValueError(error_msg)
