from typing import Any, Dict, List, Optional, TypedDict

from app.core.schemas import Plan


class AgentState(TypedDict):
    """
    State carried through the LangGraph workflow.
    """
    task_id: str
    request_text: str
    plan: Optional[Plan]
    results: Dict[str, Any]
    errors: Dict[str, str]
    retries: Dict[str, int]
    current_subtask_ids: List[str]
    synthesis: str
    status: str
