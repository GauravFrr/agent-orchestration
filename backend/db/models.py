import os
from datetime import datetime
from uuid import uuid4

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    ForeignKeyConstraint,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import ARRAY, JSONB, UUID
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base, relationship

from app.core.config import settings

Base = declarative_base()

# Operational DB Connection
engine = create_async_engine(settings.DATABASE_URL, echo=False)
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False, class_=AsyncSession)

async def get_db_session() -> AsyncSession:
    """
    Dependency helper to retrieve database session.
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
        finally:
            await session.close()

# SQLAlchemy Models
class Task(Base):
    __tablename__ = "tasks"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    request_text = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="intake")  # intake, planning, executing, reviewing, escalated, synthesizing, done, failed
    plan = Column(JSONB, nullable=True)  # Current plan json
    confidence = Column(Float, nullable=False, default=1.0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    total_cost_usd = Column(Numeric(10, 6), default=0.0, nullable=False)

    subtasks = relationship("Subtask", back_populates="task", cascade="all, delete-orphan")

class Subtask(Base):
    __tablename__ = "subtasks"

    id = Column(String, primary_key=True)  # custom id e.g. subtask_1
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), primary_key=True)
    specialist = Column(String, nullable=False)  # research, data_analysis, writing, code_exec
    input = Column(JSONB, nullable=False, default=dict)
    depends_on = Column(ARRAY(String), nullable=False, default=list)
    status = Column(String, nullable=False, default="pending")  # pending, running, review_pending, approved, rejected, retried, done, failed
    retry_count = Column(Integer, default=0, nullable=False)
    output = Column(JSONB, nullable=True)
    reviewer_verdict = Column(String, nullable=True)  # approve, reject, escalate
    reviewer_feedback = Column(Text, nullable=True)
    action_tag = Column(String, nullable=True)  # financial, deletion, external_communication

    task = relationship("Task", back_populates="subtasks")
    tool_invocations = relationship("ToolInvocation", back_populates="subsubtask", cascade="all, delete-orphan")

class ToolInvocation(Base):
    __tablename__ = "tool_invocations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    subtask_id = Column(String, nullable=False)
    task_id = Column(UUID(as_uuid=True), nullable=False)
    tool_name = Column(String, nullable=False)
    tool_kind = Column(String, nullable=False, default="custom")  # custom, mcp
    input = Column(JSONB, nullable=False, default=dict)
    output = Column(JSONB, nullable=False, default=dict)
    latency_ms = Column(Integer, nullable=False)
    success = Column(Boolean, nullable=False)
    error = Column(Text, nullable=True)
    cost_usd = Column(Numeric(10, 6), nullable=True, default=0.0)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    # Setup composite foreign key constraint
    __table_args__ = (
        ForeignKeyConstraint(
            ['subtask_id', 'task_id'],
            ['subtasks.id', 'subtasks.task_id'],
            ondelete="CASCADE"
        ),
    )

    subsubtask = relationship(
        "Subtask",
        primaryjoin="and_(ToolInvocation.subtask_id==Subtask.id, ToolInvocation.task_id==Subtask.task_id)",
        back_populates="tool_invocations"
    )

class Memory(Base):
    __tablename__ = "memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    source_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    memory_type = Column(String, nullable=False)  # plan, fact, preference
    summary = Column(Text, nullable=False)
    importance_score = Column(Float, nullable=False, default=1.0)
    retrieval_count = Column(Integer, nullable=False, default=0)
    last_retrieved_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    deleted_at = Column(DateTime(timezone=True), nullable=True)

    task = relationship("Task")

class ReviewRequest(Base):
    __tablename__ = "review_requests"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    subtask_id = Column(String, nullable=True)
    trigger_reason = Column(String, nullable=False)  # low_confidence, sensitive_action, repeated_failure, reviewer_flag, user_requested
    approval_level = Column(String, nullable=False)  # notify, approve_action, approve_plan, take_over
    context_snapshot = Column(JSONB, nullable=False, default=dict)
    status = Column(String, nullable=False, default="pending")  # pending, approved, rejected, modified, taken_over
    decision_payload = Column(JSONB, nullable=True)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)
    decided_at = Column(DateTime(timezone=True), nullable=True)

    task = relationship("Task")

class Checkpoint(Base):
    __tablename__ = "checkpoints"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    node_name = Column(String, nullable=False)
    state_snapshot = Column(JSONB, nullable=False, default=dict)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    task = relationship("Task")

class HITLConfig(Base):
    __tablename__ = "hitl_configs"

    key = Column(String, primary_key=True)
    value = Column(JSONB, nullable=False)
    description = Column(Text, nullable=True)

class TraceSpan(Base):
    __tablename__ = "trace_spans"

    id = Column(String, primary_key=True)  # OTel span ID hex string
    task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    parent_span_id = Column(String, nullable=True)  # OTel parent span ID hex
    span_type = Column(String, nullable=False)  # plan, dispatch, tool_call, review, memory_retrieval, escalation, synthesize, llm_call
    actor = Column(String, nullable=False)  # supervisor, specialist name, reviewer, tool name
    subtask_id = Column(String, nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=False)
    ended_at = Column(DateTime(timezone=True), nullable=False)
    latency_ms = Column(Integer, nullable=False, default=0)
    cost_usd = Column(Numeric(10, 6), nullable=True, default=0.0)
    tokens_in = Column(Integer, nullable=True, default=0)
    tokens_out = Column(Integer, nullable=True, default=0)
    payload = Column(JSONB, nullable=False, default=dict)

    task = relationship("Task")

class Replay(Base):
    __tablename__ = "replays"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid4)
    original_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    from_checkpoint_id = Column(String, nullable=False)
    input_override = Column(JSONB, nullable=True)
    resulting_task_id = Column(UUID(as_uuid=True), ForeignKey("tasks.id", ondelete="CASCADE"), nullable=False)
    created_at = Column(DateTime(timezone=True), default=datetime.utcnow, nullable=False)

    original_task = relationship("Task", foreign_keys=[original_task_id])
    resulting_task = relationship("Task", foreign_keys=[resulting_task_id])


