import json
import logging
from datetime import datetime
from typing import Any, Dict, Optional
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.graph.build_graph import build_workflow
from app.providers import get_default_provider
from db.models import Checkpoint, ReviewRequest, Subtask, Task, get_db_session

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/reviews", tags=["reviews"])

class DecisionRequest(BaseModel):
    decision: str = Field(..., description="Decision type: 'approve', 'modify', 'reject', or 'take_over'")
    feedback: Optional[str] = Field(default=None, description="Human feedback or rejection reason")
    modified_input: Optional[Dict[str, Any]] = Field(default=None, description="Updated input dict for 'modify'")
    taken_over_output: Optional[Dict[str, Any]] = Field(default=None, description="Human authored output dict for 'take_over'")

class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, description="Question for the paused agent")

async def resume_workflow_from_checkpoint(task_id: str, restored_state: dict):
    """
    Background worker task to resume LangGraph execution from a saved checkpoint state snapshot.
    """
    logger.info(f"Resuming LangGraph execution for task: {task_id}")
    from app.graph.checkpointing import get_checkpointer
    cp = get_checkpointer()
    if hasattr(cp, "conn") and hasattr(cp.conn, "_closed") and cp.conn._closed:
        await cp.conn.open()
    elif hasattr(cp, "conn") and hasattr(cp.conn, "open"):
        try:
            await cp.conn.open()
        except Exception:
            pass

    workflow = build_workflow()
    try:
        config = {"configurable": {"thread_id": task_id}}
        await workflow.ainvoke(restored_state, config=config)
        logger.info(f"Finished resumed LangGraph workflow execution for task: {task_id}")
    except Exception as e:
        logger.exception(f"Resumed LangGraph execution crashed for task: {task_id}. Error: {str(e)}")
        from db.models import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            task = await session.get(Task, UUID(task_id))
            if task:
                task.status = "failed"
                await session.commit()

@router.get("")
async def list_reviews(
    task_id: Optional[UUID] = None,
    status: Optional[str] = None,
    db: AsyncSession = Depends(get_db_session)
):
    """
    List review requests, optionally filtered by task_id or status.
    """
    query = select(ReviewRequest).order_by(ReviewRequest.created_at.desc())
    if task_id:
        query = query.where(ReviewRequest.task_id == task_id)
    if status:
        query = query.where(ReviewRequest.status == status)

    res = await db.execute(query)
    review_reqs = res.scalars().all()
    return review_reqs

@router.get("/{review_id}")
async def get_review(review_id: UUID, db: AsyncSession = Depends(get_db_session)):
    """
    Retrieve details for a specific review request.
    """
    review_req = await db.get(ReviewRequest, review_id)
    if not review_req:
        raise HTTPException(status_code=404, detail="Review request not found.")
    return review_req

@router.post("/{review_id}/decision")
async def submit_decision(
    review_id: UUID,
    payload: DecisionRequest,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Submit a human decision for a paused review request.
    Supports: 'approve', 'modify', 'reject', 'take_over'.
    Applies the decision, records human authorship metadata, and resumes graph execution.
    """
    decision = payload.decision.lower().strip()
    if decision not in ("approve", "modify", "reject", "take_over"):
        raise HTTPException(status_code=400, detail="Invalid decision type. Must be 'approve', 'modify', 'reject', or 'take_over'.")

    # Look up ReviewRequest by review_id OR task_id
    query = select(ReviewRequest).where(
        (ReviewRequest.id == review_id) |
        ((ReviewRequest.task_id == review_id) & (ReviewRequest.status == "pending"))
    ).order_by(ReviewRequest.created_at.desc())

    res = await db.execute(query)
    review_req = res.scalars().first()

    if not review_req:
        raise HTTPException(status_code=404, detail="Review request not found.")
    if review_req.status != "pending":
        raise HTTPException(status_code=400, detail=f"Review request is already processed with status '{review_req.status}'.")

    # Record decision payload with explicit human authorship metadata
    author_metadata = {
        "author": {
            "type": "human",
            "user_id": "operator",
            "role": "human_reviewer"
        },
        "decision": decision,
        "feedback": payload.feedback,
        "modified_input": payload.modified_input,
        "taken_over_output": payload.taken_over_output,
        "timestamp": datetime.utcnow().isoformat()
    }

    status_map = {
        "approve": "approved",
        "modify": "modified",
        "reject": "rejected",
        "take_over": "taken_over"
    }

    review_req.status = status_map[decision]
    review_req.decision_payload = author_metadata
    review_req.decided_at = datetime.utcnow()

    # Load latest checkpoint for task
    cp_query = select(Checkpoint).where(Checkpoint.task_id == review_req.task_id).order_by(Checkpoint.created_at.desc())
    cp_res = await db.execute(cp_query)
    checkpoint = cp_res.scalars().first()

    restored_state = None
    if checkpoint and checkpoint.state_snapshot:
        restored_state = dict(checkpoint.state_snapshot)
    else:
        # Fallback 1: load working state from Redis
        from app.memory.short_term import get_working_state
        ws = get_working_state(str(review_req.task_id))
        if ws:
            restored_state = {
                "task_id": str(review_req.task_id),
                "request_text": review_req.context_snapshot.get("request_text", "") if review_req.context_snapshot else "",
                "plan": ws.get("plan"),
                "results": ws.get("completed_outputs", {}),
                "errors": ws.get("errors", {}),
                "retries": {},
                "current_subtask_ids": [],
                "synthesis": "",
                "status": "executing"
            }
        elif review_req.context_snapshot:
            # Fallback 2: build from context_snapshot
            ctx = review_req.context_snapshot
            restored_state = {
                "task_id": str(review_req.task_id),
                "request_text": ctx.get("request_text", ""),
                "plan": ctx.get("plan"),
                "results": ctx.get("completed_outputs", {}),
                "errors": {},
                "retries": {},
                "current_subtask_ids": [],
                "synthesis": "",
                "status": "executing"
            }

    if not restored_state:
        raise HTTPException(status_code=500, detail="Checkpoint state snapshot not found for task resumption.")

    subtask_id = review_req.subtask_id

    # Apply decision payload to restored state & database models
    task_uuid = review_req.task_id
    task = await db.get(Task, task_uuid)
    if task:
        task.status = "executing"

    if subtask_id:
        db_subtask = await db.get(Subtask, (subtask_id, task_uuid))

        if decision == "approve":
            logger.info(f"Decision 'approve' for subtask {subtask_id}. Resuming execution.")
            if db_subtask:
                db_subtask.status = "running"
            if "plan" in restored_state and restored_state["plan"] and "subtasks" in restored_state["plan"]:
                for st in restored_state["plan"]["subtasks"]:
                    if st.get("id") == subtask_id:
                        st["status"] = "running"

        elif decision == "modify":
            logger.info(f"Decision 'modify' for subtask {subtask_id}. Applying modified input.")
            mod_input = payload.modified_input or {}
            if db_subtask:
                db_subtask.input = mod_input
                db_subtask.status = "running"

            # Update plan representation in state
            if "plan" in restored_state and restored_state["plan"] and "subtasks" in restored_state["plan"]:
                for st in restored_state["plan"]["subtasks"]:
                    if st.get("id") == subtask_id:
                        st["input"] = mod_input
                        st["status"] = "running"

        elif decision == "reject":
            logger.info(f"Decision 'reject' for subtask {subtask_id}. Routing back with feedback.")
            feedback_str = payload.feedback or "Human reviewer rejected proposed action."
            if db_subtask:
                db_subtask.status = "rejected"
                db_subtask.reviewer_feedback = feedback_str
                db_subtask.reviewer_verdict = "reject"
                db_subtask.retry_count += 1

            # Update state results and retries
            results = dict(restored_state.get("results", {}))
            results.pop(subtask_id, None)
            restored_state["results"] = results

            retries = dict(restored_state.get("retries", {}))
            retries[subtask_id] = retries.get(subtask_id, 0) + 1
            restored_state["retries"] = retries

        elif decision == "take_over":
            logger.info(f"Decision 'take_over' for subtask {subtask_id}. Injecting human output.")
            human_output = payload.taken_over_output or {"human_synthesis": payload.feedback or "Human output takeover"}
            if db_subtask:
                db_subtask.status = "approved"
                db_subtask.output = human_output
                db_subtask.reviewer_verdict = "approve"
                db_subtask.reviewer_feedback = "Human take_over replacement"

            # Inject human output directly into state results and plan
            results = dict(restored_state.get("results", {}))
            results[subtask_id] = human_output
            restored_state["results"] = results
            if "plan" in restored_state and restored_state["plan"] and "subtasks" in restored_state["plan"]:
                for st in restored_state["plan"]["subtasks"]:
                    if st.get("id") == subtask_id:
                        st["status"] = "approved"
                        st["output"] = human_output

    await db.commit()

    # Trigger background workflow resumption
    background_tasks.add_task(resume_workflow_from_checkpoint, str(review_req.task_id), restored_state)

    return {
        "success": True,
        "detail": f"Decision '{decision}' recorded successfully.",
        "review_request": {
            "id": str(review_req.id),
            "status": review_req.status,
            "decision_payload": author_metadata
        }
    }

@router.post("/{review_id}/chat")
async def chat_with_agent(
    review_id: UUID,
    payload: ChatRequest,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Perform a lightweight Q&A query with the paused agent context.
    Does NOT mutate graph state.
    """
    review_req = await db.get(ReviewRequest, review_id)
    if not review_req:
        raise HTTPException(status_code=404, detail="Review request not found.")

    provider = get_default_provider()
    from app.core.config import settings
    model = settings.DEFAULT_MODEL_GEMINI if settings.GEMINI_API_KEY or settings.MOCK_PROVIDERS else settings.DEFAULT_MODEL_CLAUDE

    system_prompt = (
        "You are an AI Agent explaining your current execution state to a human supervisor during a pause. "
        "Use the provided context snapshot to answer the user's question clearly, concisely, and accurately. "
        "Do not invent facts not present in the context."
    )

    context_str = json.dumps(review_req.context_snapshot, indent=2)
    user_prompt = f"Context Snapshot:\n{context_str}\n\nHuman Question: {payload.message}"

    messages = [
        {"role": "system", "content": system_prompt},
        {"role": "user", "content": user_prompt}
    ]

    try:
        reply, _, _ = await provider.chat_completion(model=model, messages=messages)
        return {"response": reply}
    except Exception as e:
        logger.error(f"Error in chat_with_agent: {e}")
        return {"response": f"The agent is currently paused. Context overview: Task {review_req.task_id} triggered review due to '{review_req.trigger_reason}'."}
