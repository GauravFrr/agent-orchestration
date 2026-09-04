import logging
from typing import Any, Dict, List, Optional
from sqlalchemy import select
from db.models import AsyncSessionLocal, HITLConfig
from app.core.schemas import Plan, Subtask

logger = logging.getLogger(__name__)

# Hardcoded minimum sensitive action tags per security spec (08_security.md)
MANDATORY_SENSITIVE_TAGS = {"financial", "deletion", "external_communication"}

async def get_config_val(key: str, default: Any) -> Any:
    """
    Fetch a configuration value from hitl_configs table with a default fallback.
    """
    try:
        async with AsyncSessionLocal() as session:
            res = await session.execute(select(HITLConfig).where(HITLConfig.key == key))
            cfg = res.scalar_one_or_none()
            if cfg and cfg.value is not None:
                return cfg.value.get("val", default) if isinstance(cfg.value, dict) else cfg.value
    except Exception as e:
        logger.warning(f"Failed to fetch config key '{key}' from DB: {e}. Using default.")
    return default

async def evaluate_triggers(
    task_id: str,
    plan: Optional[Plan] = None,
    subtask: Optional[Subtask] = None,
    reviewer_verdict: Optional[str] = None,
    reviewer_feedback: Optional[str] = None
) -> List[Dict[str, Any]]:
    """
    Evaluates escalation triggers against the hitl_configs table.
    Returns a list of triggered escalation reason dictionaries.
    """
    triggers = []

    # 1. Low Plan Confidence Trigger
    if plan and plan.confidence is not None:
        low_confidence_threshold = await get_config_val("low_confidence_threshold", 0.8)
        if plan.confidence < low_confidence_threshold:
            logger.info(f"Triggered low_confidence: plan confidence {plan.confidence} < threshold {low_confidence_threshold}")
            triggers.append({
                "reason": "low_confidence",
                "details": f"Plan confidence ({plan.confidence:.2f}) is below threshold ({low_confidence_threshold})"
            })

    # 2. Sensitive Action Trigger (STRICTLY checked on structured action_tag field ONLY)
    if subtask and subtask.action_tag:
        action_tag_clean = subtask.action_tag.lower().strip()
        custom_sensitive_tags = await get_config_val("sensitive_action_tags", [])
        all_sensitive_tags = MANDATORY_SENSITIVE_TAGS.union(set(custom_sensitive_tags))

        if action_tag_clean in all_sensitive_tags:
            logger.info(f"Triggered sensitive_action for subtask {subtask.id} with action_tag '{action_tag_clean}'")
            triggers.append({
                "reason": "sensitive_action",
                "action_tag": action_tag_clean,
                "details": f"Subtask '{subtask.id}' involves sensitive action: '{action_tag_clean}'"
            })

    # 3. Repeated Subtask Failure Trigger
    if subtask and subtask.retry_count is not None:
        max_subtask_failures = await get_config_val("max_subtask_failures", 2)
        if subtask.retry_count >= max_subtask_failures:
            logger.info(f"Triggered repeated_failure for subtask {subtask.id}: retry_count {subtask.retry_count} >= max {max_subtask_failures}")
            triggers.append({
                "reason": "repeated_failure",
                "details": f"Subtask '{subtask.id}' reached maximum retry attempts ({subtask.retry_count})"
            })

    # 4. Reviewer Low Score / Flag Trigger
    if reviewer_verdict and reviewer_verdict in ("reject", "escalate"):
        logger.info(f"Triggered reviewer_flag for subtask: verdict={reviewer_verdict}")
        triggers.append({
            "reason": "reviewer_flag",
            "details": f"Reviewer verdict was '{reviewer_verdict}'. Feedback: {reviewer_feedback or 'None'}"
        })

    return triggers
