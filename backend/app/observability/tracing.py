import asyncio
import logging
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional
from uuid import UUID

from opentelemetry import trace
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, SpanProcessor, TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from sqlalchemy import select

from db.models import AsyncSessionLocal, Task, TraceSpan

logger = logging.getLogger(__name__)

# Global Tracer Setup Flag
_TRACER_INITIALIZED = False

_SPAN_TASK_MAP: Dict[str, str] = {}

class PostgresSpanProcessor(SpanProcessor):
    """
    Custom OpenTelemetry SpanProcessor that intercepts completed spans
    and persists span data directly into the PostgreSQL trace_spans table.
    """
    def on_start(self, span: trace.Span, parent_context: Optional[Any] = None) -> None:
        try:
            span_context = span.get_span_context()
            span_id = f"{span_context.span_id:016x}"
            attributes = dict(span.attributes or {})
            task_id = attributes.get("task_id")
            if not task_id and span.parent and span.parent.span_id:
                parent_id = f"{span.parent.span_id:016x}"
                task_id = _SPAN_TASK_MAP.get(parent_id)
                if task_id:
                    span.set_attribute("task_id", task_id)
            if task_id:
                _SPAN_TASK_MAP[span_id] = str(task_id)
        except Exception as e:
            logger.error(f"Error in PostgresSpanProcessor.on_start: {str(e)}")

    def on_end(self, span: ReadableSpan) -> None:
        try:
            # Extract span properties
            span_context = span.get_span_context()
            span_id = f"{span_context.span_id:016x}"

            parent_span_id = None
            if span.parent and span.parent.span_id:
                parent_span_id = f"{span.parent.span_id:016x}"

            attributes = dict(span.attributes or {})
            task_id_str = attributes.get("task_id")
            if not task_id_str and parent_span_id:
                task_id_str = _SPAN_TASK_MAP.get(parent_span_id)

            if not task_id_str:
                return

            span_type = attributes.get("span_type", "node")
            actor = attributes.get("actor", "system")
            subtask_id = attributes.get("subtask_id")
            tokens_in = attributes.get("tokens_in", 0)
            tokens_out = attributes.get("tokens_out", 0)
            cost_usd = attributes.get("cost_usd", 0.0)
            checkpoint_id = attributes.get("checkpoint_id")
            payload = attributes.get("payload", {})
            if isinstance(payload, str):
                import json
                try:
                    payload = json.loads(payload)
                except Exception:
                    payload = {"raw": payload}
            if not isinstance(payload, dict):
                payload = {"value": payload}
            if checkpoint_id and "checkpoint_id" not in payload:
                payload["checkpoint_id"] = str(checkpoint_id)

            # Timestamps
            start_ns = span.start_time or 0
            end_ns = span.end_time or start_ns
            started_at = datetime.fromtimestamp(start_ns / 1e9, tz=timezone.utc)
            ended_at = datetime.fromtimestamp(end_ns / 1e9, tz=timezone.utc)
            latency_ms = int((end_ns - start_ns) / 1e6)

            span_record = {
                "id": span_id,
                "task_id": UUID(task_id_str),
                "parent_span_id": parent_span_id,
                "span_type": span_type,
                "actor": actor,
                "subtask_id": subtask_id,
                "started_at": started_at,
                "ended_at": ended_at,
                "latency_ms": latency_ms,
                "cost_usd": cost_usd,
                "tokens_in": tokens_in,
                "tokens_out": tokens_out,
                "payload": payload
            }

            # Fire async DB insertion task safely
            asyncio.create_task(self._persist_span(span_record))
        except Exception as e:
            logger.error(f"Error in PostgresSpanProcessor.on_end: {str(e)}")

    async def _persist_span(self, record: Dict[str, Any]) -> None:
        try:
            async with AsyncSessionLocal() as session:
                db_span = TraceSpan(
                    id=record["id"],
                    task_id=record["task_id"],
                    parent_span_id=record["parent_span_id"],
                    span_type=record["span_type"],
                    actor=record["actor"],
                    subtask_id=record["subtask_id"],
                    started_at=record["started_at"],
                    ended_at=record["ended_at"],
                    latency_ms=record["latency_ms"],
                    cost_usd=record["cost_usd"],
                    tokens_in=record["tokens_in"],
                    tokens_out=record["tokens_out"],
                    payload=record["payload"]
                )
                await session.merge(db_span)
                await session.commit()
        except Exception as e:
            logger.error(f"Failed to persist TraceSpan to database: {str(e)}")

    def shutdown(self) -> None:
        pass

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return True


def init_tracer() -> trace.Tracer:
    global _TRACER_INITIALIZED
    if not _TRACER_INITIALIZED:
        resource = Resource.create({"service.name": "agent-orchestration-system"})
        provider = TracerProvider(resource=resource)

        # 1. Custom Postgres SpanProcessor for relational querying
        provider.add_span_processor(PostgresSpanProcessor())

        # 2. OTLP Exporter for OTel Collector (if configured)
        otlp_endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")
        try:
            exporter = OTLPSpanExporter(endpoint=otlp_endpoint, insecure=True)
            provider.add_span_processor(BatchSpanProcessor(exporter))
        except Exception as e:
            logger.warning(f"Could not connect OTLP exporter to {otlp_endpoint}: {str(e)}")

        trace.set_tracer_provider(provider)
        _TRACER_INITIALIZED = True
        logger.info("OpenTelemetry TracerProvider initialized with PostgresSpanProcessor & OTLP Exporter.")

    return trace.get_tracer("agent-orchestration")


def get_tracer(name: str = "agent-orchestration") -> trace.Tracer:
    if not _TRACER_INITIALIZED:
        init_tracer()
    return trace.get_tracer(name)


async def get_task_trace_tree(task_id: str) -> Dict[str, Any]:
    """
    Fetch all trace_spans for a task_id and construct a nested hierarchy tree.
    """
    task_uuid = UUID(task_id)
    async with AsyncSessionLocal() as session:
        # Fetch task details
        task = await session.get(Task, task_uuid)
        if not task:
            return {"task_id": task_id, "spans": [], "metrics": {}}

        # Fetch spans ordered by start time
        query = select(TraceSpan).where(TraceSpan.task_id == task_uuid).order_by(TraceSpan.started_at.asc())
        res = await session.execute(query)
        spans = list(res.scalars().all())

    # Build metric rollups
    total_cost = 0.0
    total_latency_ms = 0
    cost_by_agent: Dict[str, float] = {}
    cost_by_tool: Dict[str, float] = {}

    span_dicts = []
    span_map = {}

    for s in spans:
        cost = float(s.cost_usd or 0.0)
        total_cost += cost

        actor = s.actor or "unknown"
        if s.span_type == "tool_call":
            cost_by_tool[actor] = cost_by_tool.get(actor, 0.0) + cost
        else:
            cost_by_agent[actor] = cost_by_agent.get(actor, 0.0) + cost

        sd = {
            "id": s.id,
            "task_id": str(s.task_id),
            "parent_span_id": s.parent_span_id,
            "span_type": s.span_type,
            "actor": s.actor,
            "subtask_id": s.subtask_id,
            "started_at": s.started_at.isoformat() if s.started_at else None,
            "ended_at": s.ended_at.isoformat() if s.ended_at else None,
            "latency_ms": s.latency_ms,
            "cost_usd": float(s.cost_usd or 0.0),
            "tokens_in": s.tokens_in,
            "tokens_out": s.tokens_out,
            "payload": s.payload or {},
            "children": []
        }
        span_dicts.append(sd)
        span_map[s.id] = sd

    # Tree assembly
    root_spans = []
    for sd in span_dicts:
        parent_id = sd["parent_span_id"]
        if parent_id and parent_id in span_map:
            span_map[parent_id]["children"].append(sd)
        else:
            root_spans.append(sd)

    if root_spans:
        total_latency_ms = sum(s["latency_ms"] for s in root_spans)

    return {
        "task_id": task_id,
        "request_text": task.request_text,
        "status": task.status,
        "total_cost_usd": round(total_cost, 6),
        "total_latency_ms": total_latency_ms,
        "cost_by_agent": {k: round(v, 6) for k, v in cost_by_agent.items()},
        "cost_by_tool": {k: round(v, 6) for k, v in cost_by_tool.items()},
        "trace_tree": root_spans
    }
