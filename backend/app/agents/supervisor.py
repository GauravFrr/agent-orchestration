import json
import logging
from typing import Any, Dict

from app.agents.prompts.supervisor_prompts import PLANNING_SYSTEM_PROMPT, SYNTHESIS_SYSTEM_PROMPT
from app.core.config import settings
from app.core.schemas import Plan
from app.providers import get_default_provider

logger = logging.getLogger(__name__)

def clean_json_text(text: str) -> str:
    """
    Strips markdown formatting from a JSON string if present.
    """
    text = text.strip()
    if text.startswith("```json"):
        text = text[7:]
    elif text.startswith("```"):
        text = text[3:]
    if text.endswith("```"):
        text = text[:-3]
    return text.strip()

class SupervisorAgent:
    """
    Supervisor Agent responsible for task planning (decomposition) and final response synthesis.
    """

    def __init__(self):
        self.provider = get_default_provider()

    async def plan(self, request_text: str, task_id: str = "") -> tuple[Plan, int, int]:
        """
        Decompose user request into a dependency-aware plan of subtasks.
        Returns:
            Tuple of (Plan object, input_tokens_count, output_tokens_count)
        """
        messages = [
            {"role": "system", "content": PLANNING_SYSTEM_PROMPT},
            {"role": "user", "content": f"Please decompose this request: {request_text}"}
        ]

        # Use Gemini default model for planning since it natively supports Pydantic response_schema
        model = settings.DEFAULT_MODEL_GEMINI if settings.GEMINI_API_KEY or settings.MOCK_PROVIDERS else settings.DEFAULT_MODEL_CLAUDE

        from app.observability.cost import calculate_span_cost
        from app.observability.tracing import get_tracer
        tracer = get_tracer()

        logger.info(f"Supervisor calling LLM ({model}) for planning...")
        span_attrs = {
            "span_type": "llm_call",
            "actor": "supervisor",
            "model": model,
            "payload": {"messages": messages}
        }
        if task_id:
            span_attrs["task_id"] = str(task_id)

        with tracer.start_as_current_span(
            "llm_call",
            attributes=span_attrs
        ) as span:
            response, in_tokens, out_tokens = await self.provider.chat_completion(
                model=model,
                messages=messages,
            )
            cost = calculate_span_cost(model, in_tokens, out_tokens)
            if span and hasattr(span, "set_attribute"):
                span.set_attribute("tokens_in", in_tokens)
                span.set_attribute("tokens_out", out_tokens)
                span.set_attribute("cost_usd", cost)
                span.set_attribute("payload", {"messages": messages, "response": response})

        try:
            cleaned_response = clean_json_text(response)
            plan_dict = json.loads(cleaned_response)
            plan = Plan(**plan_dict)
            return plan, in_tokens, out_tokens
        except Exception as e:
            logger.error(f"Failed to parse plan from LLM output: {response}. Error: {str(e)}")
            # Fallback schema in case of total failure
            fallback_plan = Plan(
                subtasks=[],
                confidence=0.0
            )
            return fallback_plan, in_tokens, out_tokens

    async def synthesize(self, request_text: str, subtask_outputs: Dict[str, Any], task_id: str = "") -> tuple[str, int, int]:
        """
        Combine all subtask outputs into a final synthesized response.
        Returns:
            Tuple of (synthesis_string, input_tokens_count, output_tokens_count)
        """
        outputs_str = json.dumps(subtask_outputs, indent=2)
        system_prompt = SYNTHESIS_SYSTEM_PROMPT.format(
            request_text=request_text,
            subtask_outputs=outputs_str
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Please generate the final output."}
        ]

        model = settings.DEFAULT_MODEL_GEMINI if settings.GEMINI_API_KEY or settings.MOCK_PROVIDERS else settings.DEFAULT_MODEL_CLAUDE

        from app.observability.cost import calculate_span_cost
        from app.observability.tracing import get_tracer
        tracer = get_tracer()

        logger.info(f"Supervisor calling LLM ({model}) for synthesis...")
        span_attrs = {
            "span_type": "llm_call",
            "actor": "supervisor",
            "model": model,
            "payload": {"messages": messages}
        }
        if task_id:
            span_attrs["task_id"] = str(task_id)

        with tracer.start_as_current_span(
            "llm_call",
            attributes=span_attrs
        ) as span:
            response, in_tokens, out_tokens = await self.provider.chat_completion(
                model=model,
                messages=messages
            )
            cost = calculate_span_cost(model, in_tokens, out_tokens)
            if span and hasattr(span, "set_attribute"):
                span.set_attribute("tokens_in", in_tokens)
                span.set_attribute("tokens_out", out_tokens)
                span.set_attribute("cost_usd", cost)
                span.set_attribute("payload", {"messages": messages, "response": response})

        return response, in_tokens, out_tokens
