import logging

from app.hitl.triggers import MANDATORY_SENSITIVE_TAGS, get_config_val

logger = logging.getLogger(__name__)

# Default mapping of trigger reason to approval level
DEFAULT_APPROVAL_LEVELS = {
    "low_confidence": "approve_plan",
    "sensitive_action": "approve_action",
    "repeated_failure": "take_over",
    "reviewer_flag": "notify",
    "user_requested": "approve_plan"
}

# Approval hierarchy for level comparison
LEVEL_HIERARCHY = {
    "notify": 1,
    "approve_action": 2,
    "approve_plan": 3,
    "take_over": 4
}

async def get_approval_level(trigger_reason: str, action_tag: str | None = None) -> str:
    """
    Resolve trigger reason to an approval level based on database configuration.
    Enforces security overrides for mandatory sensitive action tags.
    """
    custom_mapping = await get_config_val("trigger_to_level_mapping", {})
    resolved_level = custom_mapping.get(trigger_reason, DEFAULT_APPROVAL_LEVELS.get(trigger_reason, "approve_action"))
    resolved_level = resolved_level.lower().strip()

    # HARD SECURITY OVERRIDE (08_security.md):
    # Sensitive-action tags (financial, deletion, external_communication) ALWAYS route to at least APPROVE_ACTION
    if trigger_reason == "sensitive_action" or (action_tag and action_tag.lower().strip() in MANDATORY_SENSITIVE_TAGS):
        current_rank = LEVEL_HIERARCHY.get(resolved_level, 0)
        min_required_rank = LEVEL_HIERARCHY["approve_action"]
        if current_rank < min_required_rank:
            logger.warning(
                f"Security Override: Attempted to resolve sensitive action '{action_tag}' to '{resolved_level}'. "
                f"Downgrade prohibited. Escalating to 'approve_action'."
            )
            return "approve_action"

    return resolved_level
