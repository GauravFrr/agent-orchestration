import json
import logging
from typing import Any, Dict

from app.agents.prompts.specialist_prompts import SPECIALIST_SYSTEM_PROMPT
from app.agents.supervisor import clean_json_text
from app.core.config import settings
from app.providers import get_default_provider

logger = logging.getLogger(__name__)

# Bounded tool set constant per coding style
ALLOWED_TOOLS = []
SPECIALIST_NAME = "writing"

class WritingSpecialist:
    """
    Writing Specialist Agent.
    Allowed tools: none (pure LLM synthesis/drafting)
    """

    def __init__(self):
        self.provider = get_default_provider()

    async def execute(
        self,
        subtask_input: Dict[str, Any],
        expected_schema: Dict[str, Any],
        feedback_history: str = "",
        max_steps: int = 1,
        subtask_id: str = "",
        task_id: str = ""
    ) -> tuple[Dict[str, Any], int, int]:
        """
        Execute subtask by calling LLM in a single shot.
        """
        system_instruction = SPECIALIST_SYSTEM_PROMPT.format(
            specialist_name="Writing",
            subtask_input=json.dumps(subtask_input, indent=2),
            feedback_history=feedback_history or "None"
        )

        system_instruction += "\n\nYou do not have access to any external tools. Your job is to compile the response purely from the input context.\n"
        system_instruction += "You MUST return a JSON object that strictly conforms to this expected output schema:\n" + json.dumps(expected_schema, indent=2)

        messages = [
            {"role": "system", "content": system_instruction},
            {"role": "user", "content": "Please write the output matching the requested schema."}
        ]

        model = settings.DEFAULT_MODEL_GEMINI if settings.GEMINI_API_KEY or settings.MOCK_PROVIDERS else settings.DEFAULT_MODEL_CLAUDE

        from app.observability.cost import calculate_span_cost
        from app.observability.tracing import get_tracer
        tracer = get_tracer()

        logger.info("Writing specialist generating output...")
        span_attrs = {
            "span_type": "llm_call",
            "actor": "specialist:writing",
            "model": model
        }
        if task_id:
            span_attrs["task_id"] = str(task_id)
        if subtask_id:
            span_attrs["subtask_id"] = str(subtask_id)

        with tracer.start_as_current_span(
            "llm_call",
            attributes=span_attrs
        ) as span:
            response, in_t, out_t = await self.provider.chat_completion(
                model=model,
                messages=messages
            )
            cost = calculate_span_cost(model, in_t, out_t)
            if span and hasattr(span, "set_attribute"):
                span.set_attribute("tokens_in", in_t)
                span.set_attribute("tokens_out", out_t)
                span.set_attribute("cost_usd", cost)
                span.set_attribute("payload", {"messages": messages, "response": response})

        try:
            cleaned_response = clean_json_text(response)
            parsed = json.loads(cleaned_response)
            return parsed, in_t, out_t
        except Exception as e:
            logger.error(f"Error parsing Writing specialist output: {str(e)}. Raw: {response}")
            # Try to return raw response inside a JSON if expected_schema is simple, or return error dict
            return {"text": response, "error": f"Failed to parse as JSON: {str(e)}"}, in_t, out_t
