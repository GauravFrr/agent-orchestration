import asyncio
import logging
from uuid import UUID

from sqlalchemy import update

from app.agents.specialists.code_exec import CodeExecSpecialist
from app.agents.specialists.data_analysis import DataAnalysisSpecialist
from app.agents.specialists.research import ResearchSpecialist
from app.agents.specialists.writing import WritingSpecialist
from app.core.schemas import SpecialistType, SubtaskStatus
from app.graph.state import AgentState
from app.observability.tracing import get_tracer
from db.models import AsyncSessionLocal, Subtask

logger = logging.getLogger(__name__)

async def execute_specialist(
    specialist_type: SpecialistType,
    subtask_input: dict,
    expected_schema: dict,
    feedback: str = "",
    subtask_id: str = "",
    task_id: str = ""
) -> tuple[dict, int, int]:
    """
    Helper to run the appropriate specialist agent.
    """
    if specialist_type == SpecialistType.RESEARCH:
        agent = ResearchSpecialist()
        return await agent.execute(subtask_input, expected_schema, feedback, subtask_id=subtask_id, task_id=task_id)
    elif specialist_type == SpecialistType.DATA_ANALYSIS:
        agent = DataAnalysisSpecialist()
        return await agent.execute(subtask_input, expected_schema, feedback, subtask_id=subtask_id, task_id=task_id)
    elif specialist_type == SpecialistType.WRITING:
        agent = WritingSpecialist()
        return await agent.execute(subtask_input, expected_schema, feedback, subtask_id=subtask_id, task_id=task_id)
    elif specialist_type == SpecialistType.CODE_EXEC:
        agent = CodeExecSpecialist()
        return await agent.execute(subtask_input, expected_schema, feedback, subtask_id=subtask_id, task_id=task_id)
    else:
        raise ValueError(f"Unknown specialist type: {specialist_type}")

async def dispatch_node(state: AgentState) -> dict:
    """
    Dispatch node. Determines ready subtasks, runs their specialists in parallel, and gathers results.
    """
    task_id = state.get("task_id")
    tracer = get_tracer()

    from sqlalchemy import text
    cp_id = None
    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(text("SELECT checkpoint_id FROM public.checkpoints WHERE thread_id = :th ORDER BY checkpoint_id DESC LIMIT 1"), {"th": str(task_id)})
            row = res.fetchone()
            if row:
                cp_id = row[0]
    except Exception:
        pass

    with tracer.start_as_current_span(
        "dispatch",
        attributes={
            "task_id": str(task_id),
            "span_type": "dispatch",
            "actor": "supervisor"
        }
    ) as span:
        if cp_id:
            span.set_attribute("checkpoint_id", cp_id)
        plan = state.get("plan")
        results = dict(state.get("results", {}))
        errors = dict(state.get("errors", {}))

        if not plan or not plan.subtasks:
            logger.warning(f"No plan found for task {task_id} in dispatch node.")
            return {}

    # 1. Identify which subtasks are ready to run
    ready_subtasks = []
    for subtask in plan.subtasks:
        # If it's already done, skip
        if subtask.id in results:
            continue

        # Check dependencies
        all_deps_met = True
        for dep_id in subtask.depends_on:
            if dep_id not in results:
                all_deps_met = False
                break

        if all_deps_met:
            ready_subtasks.append(subtask)

    if not ready_subtasks:
        logger.info("No subtasks are currently ready to dispatch.")
        return {"current_subtask_ids": []}

    # 1.5 Check HITL Escalation Triggers before execution

    from app.hitl.approval_levels import get_approval_level
    from app.hitl.queue import create_review_request
    from app.hitl.triggers import evaluate_triggers
    from db.models import Task as TaskModel

    for subtask in ready_subtasks:
        # Skip re-triggering escalation if the subtask has already been approved or set to running post-human decision
        if subtask.status in (SubtaskStatus.APPROVED, SubtaskStatus.RUNNING):
            continue

        triggers = await evaluate_triggers(
            task_id=task_id,
            plan=plan,
            subtask=subtask
        )
        if triggers:
            trigger = triggers[0]
            logger.info(f"Escalation triggered for subtask '{subtask.id}': {trigger['reason']}")

            approval_level = await get_approval_level(trigger["reason"], action_tag=subtask.action_tag)

            async with AsyncSessionLocal() as session:
                task_uuid = UUID(task_id)
                # Update Task status to escalated
                db_task = await session.get(TaskModel, task_uuid)
                if db_task:
                    db_task.status = "escalated"

                await session.commit()

            req_text = state.get("request_text", "")
            # Create Review Request record and push Redis notification
            context_snapshot = {
                "request_text": req_text,
                "plan": plan.model_dump() if plan else None,
                "subtask": subtask.model_dump() if subtask else None,
                "completed_outputs": results,
                "trigger": trigger,
                "proposed_action": f"Execute specialist '{subtask.specialist.value}' on input: {subtask.input}"
            }
            await create_review_request(
                task_id=task_id,
                subtask_id=subtask.id,
                trigger_reason=trigger["reason"],
                approval_level=approval_level,
                context_snapshot=context_snapshot
            )

            # Pause execution by returning escalated status
            return {
                "status": "escalated",
                "current_subtask_ids": []
            }

    # Update database status for ready subtasks to running
    async with AsyncSessionLocal() as session:
        for subtask in ready_subtasks:
            task_uuid = UUID(task_id)
            await session.execute(
                update(Subtask)
                .where(Subtask.id == subtask.id, Subtask.task_id == task_uuid)
                .values(status="running")
            )
        await session.commit()
        # Save working state to Redis
        from app.memory.short_term import save_working_state
        save_working_state(task_id, plan.model_dump() if plan else None, results, errors)

    # 2. Run specialist execution concurrently
    tasks = []
    for subtask in ready_subtasks:
        # Retrieve feedback history if this subtask was previously rejected
        feedback = subtask.reviewer_feedback or ""
        tasks.append(execute_specialist(
            specialist_type=subtask.specialist,
            subtask_input=subtask.input,
            expected_schema=subtask.expected_output_schema,
            feedback=feedback,
            subtask_id=subtask.id,
            task_id=task_id
        ))

    execution_results = await asyncio.gather(*tasks)

    # 3. Process outputs and update state/DB
    current_subtask_ids = []
    async with AsyncSessionLocal() as session:
        task_uuid = UUID(task_id)

        for subtask, (output, in_t, out_t) in zip(ready_subtasks, execution_results):
            current_subtask_ids.append(subtask.id)

            from app.core.config import settings
            from app.core.cost import record_llm_cost
            model = settings.DEFAULT_MODEL_GEMINI if (settings.GEMINI_API_KEY or settings.MOCK_PROVIDERS) else settings.DEFAULT_MODEL_CLAUDE
            await record_llm_cost(task_id, model, in_t, out_t)

            # Always record output in results so build_graph knows subtask finished
            results[subtask.id] = output

            # Check for error or output
            if "error" in output and len(output) == 1:
                errors[subtask.id] = output["error"]
                logger.error(f"Subtask {subtask.id} failed with error: {output['error']}")
                subtask.status = SubtaskStatus.FAILED
                db_status = "failed"
            else:
                logger.info(f"Subtask {subtask.id} completed successfully.")
                subtask.status = SubtaskStatus.REVIEW_PENDING
                db_status = "review_pending"

            # Update DB subtask row status
            await session.execute(
                update(Subtask)
                .where(Subtask.id == subtask.id, Subtask.task_id == task_uuid)
                .values(status=db_status, output=output)
            )

            # Sync plan status in state object representation
            subtask.output = output

        await session.commit()
        # Save working state to Redis
        from app.memory.short_term import save_working_state
        save_working_state(task_id, plan.model_dump() if plan else None, results, errors)

    return {
        "results": results,
        "errors": errors,
        "current_subtask_ids": current_subtask_ids,
        "plan": plan
    }
