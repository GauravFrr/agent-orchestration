import asyncio
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID, uuid4

from app.graph.checkpointing import load_checkpoint
from db.models import AsyncSessionLocal, Replay, Task

logger = logging.getLogger(__name__)

async def execute_replay(
    original_task_id: str,
    checkpoint_id: str,
    input_override: Optional[Dict[str, Any]] = None
) -> str:
    """
    Load state snapshot from a checkpoint, apply optional input overrides,
    spawn a new task execution, and link original task to resulting task via replays table.
    """
    logger.info(f"Initiating task replay from checkpoint {checkpoint_id} for original task {original_task_id}")

    async with AsyncSessionLocal() as session:
        orig_uuid = UUID(original_task_id)
        orig_task = await session.get(Task, orig_uuid)
        if not orig_task:
            raise ValueError(f"Original task {original_task_id} not found.")

        # Load checkpoint snapshot
        checkpoint_snapshot = await load_checkpoint(checkpoint_id, original_task_id)
        if not checkpoint_snapshot:
            raise ValueError(f"Checkpoint {checkpoint_id} not found.")

        # Prepare request text and state for replay task
        new_request_text = orig_task.request_text
        if input_override and "request_text" in input_override:
            new_request_text = input_override["request_text"]

        # Create new task row
        resulting_task_id = str(uuid4())
        resulting_uuid = UUID(resulting_task_id)

        new_task = Task(
            id=resulting_uuid,
            request_text=f"[Replay of {original_task_id[:8]}] {new_request_text}",
            status="intake",
            confidence=1.0,
            total_cost_usd=0.0
        )
        session.add(new_task)

        # Create Replay link record
        replay_record = Replay(
            id=uuid4(),
            original_task_id=orig_uuid,
            from_checkpoint_id=checkpoint_id,
            input_override=input_override or {},
            resulting_task_id=resulting_uuid,
            created_at=datetime.utcnow()
        )
        session.add(replay_record)
        await session.commit()

    logger.info(f"Created replay task {resulting_task_id} linked to checkpoint {checkpoint_id}")

    # Prepare restored state with input overrides applied
    restored_state = dict(checkpoint_snapshot)
    restored_state["task_id"] = resulting_task_id
    restored_state["request_text"] = new_request_text

    if input_override:
        if "plan" in input_override and "plan" in restored_state:
            restored_state["plan"] = input_override["plan"]
        if "subtask_input" in input_override and "plan" in restored_state and restored_state["plan"]:
            st_id = input_override.get("subtask_id")
            for st in restored_state["plan"].get("subtasks", []):
                if not st_id or st.get("id") == st_id:
                    st["input"] = input_override["subtask_input"]

    # Trigger background workflow execution for resulting replay task
    from app.api.routes.tasks import run_task_workflow
    asyncio.create_task(run_task_workflow(resulting_task_id, new_request_text))

    return resulting_task_id
