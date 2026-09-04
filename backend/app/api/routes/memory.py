import logging
from datetime import datetime
from typing import List, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.memory.long_term import delete_from_collection
from db.models import Memory, get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/memory", tags=["memory"])

class MemoryResponse(BaseModel):
    id: UUID
    source_task_id: UUID
    memory_type: str
    summary: str
    importance_score: float
    retrieval_count: int
    last_retrieved_at: Optional[datetime] = None
    created_at: datetime
    deleted_at: Optional[datetime] = None

    class Config:
        from_attributes = True

@router.get("", response_model=List[MemoryResponse])
async def list_memories(db: AsyncSession = Depends(get_db_session)):
    """
    List all active, non-soft-deleted memories.
    """
    try:
        logger.info("Fetching list of active memories...")
        # Only list non-deleted memories
        query = select(Memory).where(Memory.deleted_at.is_(None)).order_by(Memory.created_at.desc())
        result = await db.execute(query)
        memories = result.scalars().all()
        return memories
    except Exception as e:
        logger.error(f"Error listing memories: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error while listing memories.")

@router.delete("/{memory_id}")
async def delete_memory(memory_id: UUID, db: AsyncSession = Depends(get_db_session)):
    """
    Hard-purge memory from both the vector store (ChromaDB) and the Postgres database.
    """
    try:
        logger.info(f"Received request to hard-purge memory: {memory_id}")
        mem = await db.get(Memory, memory_id)
        if not mem:
            raise HTTPException(status_code=404, detail="Memory not found.")

        # Map type to ChromaDB collection name
        collection_map = {
            "plan": "plans",
            "fact": "facts",
            "preference": "preferences"
        }
        collection_name = collection_map.get(mem.memory_type)

        if collection_name:
            # Delete from ChromaDB
            await delete_from_collection(collection_name, str(memory_id))
            logger.info(f"Deleted vector for memory {memory_id} from collection '{collection_name}'")
        else:
            logger.warning(f"Unknown memory type '{mem.memory_type}' for memory {memory_id}; skipped ChromaDB deletion.")

        # Hard delete from Postgres database
        await db.delete(mem)
        await db.commit()
        logger.info(f"Hard-purged memory row {memory_id} from database.")

        return {"success": True, "detail": f"Memory {memory_id} has been hard-purged."}
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error deleting memory {memory_id}: {str(e)}")
        raise HTTPException(status_code=500, detail="Internal server error while hard-purging memory.")
