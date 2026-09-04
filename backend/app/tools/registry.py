import logging
import time
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)

# Central registry store
_registry: Dict[str, Dict[str, Any]] = {}

def register_tool(
    name: str,
    description: str,
    allowed_specialists: List[str],
    func: Callable[..., Any],
    input_schema: Optional[Dict[str, Any]] = None
):
    """
    Register a tool in the global tool registry.
    """
    _registry[name] = {
        "name": name,
        "description": description,
        "allowed_specialists": allowed_specialists,
        "func": func,
        "input_schema": input_schema or {}
    }
    logger.info(f"Registered tool '{name}' allowed for specialists: {allowed_specialists}")

async def invoke_tool(
    tool_name: str,
    specialist_name: str,
    arguments: Dict[str, Any],
    subtask_id: Optional[str] = None,
    task_id: Optional[str] = None
) -> Dict[str, Any]:
    """
    Invoke a tool from the registry. Validates permissions and logs execution.
    """
    if tool_name not in _registry:
        error_msg = f"Tool '{tool_name}' not found in registry."
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

    tool_info = _registry[tool_name]
    allowed = tool_info["allowed_specialists"]

    # Validate permission boundary
    if specialist_name not in allowed:
        error_msg = f"Security Boundary Violation: Specialist '{specialist_name}' is not allowed to run tool '{tool_name}' (allowed: {allowed})."
        logger.error(error_msg)
        return {"success": False, "error": error_msg}

    func = tool_info["func"]
    start_time = time.time()
    success = True
    error_str = None
    output = None

    from app.observability.tracing import get_tracer
    tracer = get_tracer()

    span_attrs = {
        "span_type": "tool_call",
        "actor": tool_name,
        "specialist": specialist_name,
        "payload": {"arguments": arguments}
    }
    if task_id:
        span_attrs["task_id"] = str(task_id)
    if subtask_id:
        span_attrs["subtask_id"] = str(subtask_id)

    with tracer.start_as_current_span(f"tool:{tool_name}", attributes=span_attrs):
        try:
            # Check if function is coroutine or regular function
            import inspect
            if inspect.iscoroutinefunction(func):
                output = await func(**arguments)
            else:
                output = func(**arguments)
        except Exception as e:
            success = False
            error_str = str(e)
            output = {"success": False, "error": error_str}
            logger.exception(f"Error executing tool '{tool_name}': {error_str}")

    latency_ms = int((time.time() - start_time) * 1000)
    logger.info(f"Tool '{tool_name}' executed by '{specialist_name}' in {latency_ms}ms. Success: {success}")

    # Log to database only when both subtask_id and task_id are provided
    if subtask_id and task_id:
        try:
            from uuid import UUID as _UUID

            from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
            from sqlalchemy.orm import sessionmaker

            from app.core.config import settings
            from db.models import ToolInvocation

            def _to_json_safe(obj):
                import json
                from datetime import date, datetime
                from decimal import Decimal
                from uuid import UUID

                def _default(item):
                    if isinstance(item, Decimal):
                        return float(item)
                    if isinstance(item, (datetime, date)):
                        return item.isoformat()
                    if isinstance(item, UUID):
                        return str(item)
                    return str(item)

                return json.loads(json.dumps(obj, default=_default))

            engine = create_async_engine(settings.DATABASE_URL)
            async_session = sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)
            async with async_session() as session:
                invocation = ToolInvocation(
                    subtask_id=subtask_id,
                    task_id=_UUID(task_id),
                    tool_name=tool_name,
                    tool_kind="custom",
                    input=_to_json_safe(arguments),
                    output=_to_json_safe(output if success else {"error": error_str}),
                    latency_ms=latency_ms,
                    success=success,
                    error=error_str,
                    cost_usd=0.0,
                    created_at=datetime.utcnow()
                )
                session.add(invocation)
                await session.commit()
            logger.info(f"Logged tool invocation '{tool_name}' for subtask {subtask_id} to DB.")
        except Exception as db_err:
            logger.warning(f"Could not log tool invocation to DB: {db_err}")
    else:
        logger.debug(f"Skipping DB log for tool '{tool_name}': subtask_id or task_id not provided.")

    return {
        "success": success,
        "output": output,
        "error": error_str,
        "latency_ms": latency_ms
    }

def get_registered_tools() -> List[Dict[str, Any]]:
    """
    Returns list of all registered tools and metadata.
    """
    return list(_registry.values())

# Auto-import tools to register them
try:
    import app.tools.db_query
    import app.tools.file_io
    import app.tools.sandboxed_exec
    import app.tools.web_search
except ImportError as e:
    logger.debug(f"Tool auto-import notice: {e}")

