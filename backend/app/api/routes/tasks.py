import logging
from uuid import UUID, uuid4
from fastapi import APIRouter, HTTPException, BackgroundTasks, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.schemas import TaskCreate, TaskResponse
from app.graph.build_graph import build_workflow
from db.models import get_db_session, Task

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/tasks", tags=["tasks"])

async def run_task_workflow(task_id: UUID, request_text: str):
    """
    Background worker task to execute the LangGraph state machine.
    """
    logger.info(f"Starting background LangGraph execution for task: {task_id}")
    workflow = build_workflow()
    from app.graph.checkpointing import get_checkpointer
    cp = get_checkpointer()
    if hasattr(cp, "conn") and hasattr(cp.conn, "_closed") and cp.conn._closed:
        await cp.conn.open()
    elif hasattr(cp, "conn") and hasattr(cp.conn, "open"):
        try:
            await cp.conn.open()
        except Exception:
            pass
    
    initial_state = {
        "task_id": str(task_id),
        "request_text": request_text,
        "plan": None,
        "results": {},
        "errors": {},
        "retries": {},
        "current_subtask_ids": [],
        "synthesis": "",
        "status": "intake"
    }
    
    from app.observability.tracing import get_tracer
    tracer = get_tracer()
    
    try:
        config = {"configurable": {"thread_id": str(task_id)}}
        with tracer.start_as_current_span(
            "task_execution",
            attributes={
                "task_id": str(task_id),
                "span_type": "node",
                "actor": "system"
            }
        ):
            await workflow.ainvoke(initial_state, config=config)
        logger.info(f"Successfully finished LangGraph workflow execution for task: {task_id}")
    except Exception as e:
        logger.exception(f"LangGraph execution crashed for task: {task_id}. Error: {str(e)}")
        # Update database status to failed
        from db.models import AsyncSessionLocal
        async with AsyncSessionLocal() as session:
            task = await session.get(Task, task_id)
            if task:
                task.status = "failed"
                await session.commit()

@router.post("", response_model=TaskResponse)
async def create_task(
    payload: TaskCreate,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Submit a new natural language task request.
    Creates a database record and triggers execution in the background.
    """
    task_id = uuid4()
    logger.info(f"Received request to create task: {task_id}")
    
    # 1. Create a task record in status intake
    task = Task(
        id=task_id,
        request_text=payload.request_text,
        status="intake",
        confidence=1.0,
        total_cost_usd=0.0
    )
    
    db.add(task)
    await db.commit()
    await db.refresh(task)
    
    # 2. Trigger the LangGraph execution in the background
    background_tasks.add_task(run_task_workflow, task_id, payload.request_text)
    
    return task

@router.get("/{task_id}", response_model=TaskResponse)
async def get_task(
    task_id: UUID,
    db: AsyncSession = Depends(get_db_session)
):
    """
    Retrieve status and execution results for a specific task.
    """
    logger.info(f"Fetching task: {task_id}")
    
    # Fetch task and eagerly load subtasks relationship
    query = select(Task).where(Task.id == task_id).options(selectinload(Task.subtasks))
    result = await db.execute(query)
    task = result.scalar_one_or_none()
    
    if not task:
        raise HTTPException(status_code=404, detail="Task not found.")
        
    # Reconstruct the Plan dynamically using the actual subtask states from the DB
    if task.plan and task.subtasks:
        plan_dict = dict(task.plan)
        original_subtasks = {st["id"]: st for st in plan_dict.get("subtasks", []) if isinstance(st, dict)}
        
        subtasks_list = []
        for st in task.subtasks:
            orig = original_subtasks.get(st.id, {})
            subtasks_list.append({
                "id": st.id,
                "specialist": st.specialist,
                "input": st.input,
                "depends_on": st.depends_on,
                "expected_output_schema": orig.get("expected_output_schema", {}),
                "status": st.status,
                "retry_count": st.retry_count,
                "output": st.output,
                "reviewer_verdict": st.reviewer_verdict,
                "reviewer_feedback": st.reviewer_feedback
            })
        plan_dict["subtasks"] = subtasks_list
        task.plan = plan_dict
        
    return task
