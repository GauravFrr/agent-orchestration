import logging
from uuid import UUID

from app.agents.reviewer import ReviewerAgent
from app.core.schemas import SubtaskStatus
from app.graph.state import AgentState
from app.observability.tracing import get_tracer
from db.models import AsyncSessionLocal, Subtask

logger = logging.getLogger(__name__)

async def review_node(state: AgentState) -> dict:
    """
    Review node. Evaluates completed subtasks outputs against expected schemas using the Reviewer Agent.
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
        "review",
        attributes={
            "task_id": str(task_id),
            "span_type": "review",
            "actor": "reviewer"
        }
    ) as span:
        if cp_id:
            span.set_attribute("checkpoint_id", cp_id)
        plan = state.get("plan")
        results = state.get("results", {})
        current_subtask_ids = state.get("current_subtask_ids", [])

        if not current_subtask_ids:
            logger.info("No current subtasks to review in review node.")
            return {}

        reviewer = ReviewerAgent()
        reviewer_verdicts = {}

    async with AsyncSessionLocal() as session:
        task_uuid = UUID(task_id)

        for subtask_id in current_subtask_ids:
            # Find subtask in plan representation
            subtask = next((s for s in plan.subtasks if s.id == subtask_id), None)
            if not subtask:
                continue

            # Skip if subtask failed or has no output
            output = results.get(subtask_id)
            if not output or "error" in output:
                continue

            # Run reviewer LLM check
            review_res, in_t, out_t = await reviewer.review(
                specialist=subtask.specialist.value,
                subtask_input=subtask.input,
                expected_schema=subtask.expected_output_schema,
                specialist_output=output,
                task_id=task_id,
                subtask_id=subtask_id
            )

            from app.core.config import settings
            from app.core.cost import record_llm_cost
            model = settings.DEFAULT_MODEL_GEMINI if (settings.GEMINI_API_KEY or settings.MOCK_PROVIDERS) else settings.DEFAULT_MODEL_CLAUDE
            await record_llm_cost(task_id, model, in_t, out_t)

            logger.info(f"Reviewer verdict for subtask {subtask_id}: {review_res.verdict}. Feedback: {review_res.feedback}")
            reviewer_verdicts[subtask_id] = review_res.verdict

            # Create a mutable copy of results if we need to modify it
            results = dict(results)

            db_subtask = await session.get(Subtask, (subtask_id, task_uuid))
            if db_subtask:
                db_subtask.reviewer_verdict = review_res.verdict
                db_subtask.reviewer_feedback = review_res.feedback

                # In Phase 1, we treat review as either approved or rejected.
                if review_res.verdict == "approve":
                    db_subtask.status = "approved"
                    subtask.status = SubtaskStatus.APPROVED
                else:
                    db_subtask.status = "rejected"
                    db_subtask.retry_count += 1
                    subtask.status = SubtaskStatus.REJECTED
                    # Check if repeated failure threshold triggered escalation

                    from app.hitl.approval_levels import get_approval_level
                    from app.hitl.queue import create_review_request
                    from app.hitl.triggers import evaluate_triggers
                    from db.models import Task as TaskModel

                    triggers = await evaluate_triggers(
                        task_id=task_id,
                        plan=plan,
                        subtask=subtask,
                        reviewer_verdict=review_res.verdict,
                        reviewer_feedback=review_res.feedback
                    )
                    if triggers:
                        trigger = triggers[0]
                        logger.info(f"Escalation triggered in review_node for subtask '{subtask_id}': {trigger['reason']}")
                        approval_level = await get_approval_level(trigger["reason"])

                        db_task = await session.get(TaskModel, task_uuid)
                        if db_task:
                            db_task.status = "escalated"

                        await session.commit()

                        context_snapshot = {
                            "request_text": state.get("request_text"),
                            "plan": plan.model_dump() if plan else None,
                            "subtask": subtask.model_dump() if subtask else None,
                            "completed_outputs": results,
                            "trigger": trigger,
                            "proposed_action": f"Reviewer rejected subtask {subtask_id}. Proposed action: Retry or human intervention."
                        }
                        await create_review_request(
                            task_id=task_id,
                            subtask_id=subtask_id,
                            trigger_reason=trigger["reason"],
                            approval_level=approval_level,
                            context_snapshot=context_snapshot
                        )
                        return {
                            "plan": plan,
                            "results": results,
                            "status": "escalated"
                        }

        await session.commit()
        # Save working state to Redis
        from app.memory.short_term import save_working_state
        errors = state.get("errors", {})
        save_working_state(task_id, plan.model_dump() if plan else None, results, errors)

    return {
        "plan": plan,
        "results": results,
        "status": "executing"
    }
