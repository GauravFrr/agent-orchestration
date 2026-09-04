from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID

from pydantic import BaseModel, Field


class TaskStatus(str, Enum):
    INTAKE = "intake"
    PLANNING = "planning"
    EXECUTING = "executing"
    REVIEWING = "reviewing"
    ESCALATED = "escalated"
    SYNTHESIZING = "synthesizing"
    DONE = "done"
    FAILED = "failed"

class SubtaskStatus(str, Enum):
    PENDING = "pending"
    RUNNING = "running"
    REVIEW_PENDING = "review_pending"
    APPROVED = "approved"
    REJECTED = "rejected"
    RETRIED = "retried"
    DONE = "done"
    FAILED = "failed"

class SpecialistType(str, Enum):
    RESEARCH = "research"
    DATA_ANALYSIS = "data_analysis"
    WRITING = "writing"
    CODE_EXEC = "code_exec"

class ReviewerVerdict(str, Enum):
    APPROVE = "approve"
    REJECT = "reject"
    ESCALATE = "escalate"

class Subtask(BaseModel):
    id: str = Field(description="Unique identifier for the subtask, e.g., 'subtask_1'")
    specialist: SpecialistType = Field(description="The specialist agent responsible for this subtask")
    input: Dict[str, Any] = Field(default_factory=dict, description="Input parameters and context for the specialist")
    depends_on: List[str] = Field(default_factory=list, description="IDs of subtasks that must complete before this one starts")
    expected_output_schema: Dict[str, Any] = Field(default_factory=dict, description="JSON Schema for the expected output")
    status: SubtaskStatus = Field(default=SubtaskStatus.PENDING)
    retry_count: int = Field(default=0)
    output: Optional[Dict[str, Any]] = None
    reviewer_verdict: Optional[ReviewerVerdict] = None
    reviewer_feedback: Optional[str] = None
    action_tag: Optional[str] = Field(default=None, description="Optional sensitive action tag: 'financial', 'deletion', or 'external_communication'")

class Plan(BaseModel):
    subtasks: List[Subtask] = Field(default_factory=list)
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)

class TaskCreate(BaseModel):
    request_text: str = Field(..., min_length=1, description="Natural language task description")

class TaskResponse(BaseModel):
    id: UUID
    request_text: str
    status: TaskStatus
    plan: Optional[Plan] = None
    confidence: float
    created_at: datetime
    updated_at: datetime
    completed_at: Optional[datetime] = None
    total_cost_usd: float

    class Config:
        from_attributes = True
