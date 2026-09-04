import json
import logging

from pydantic import BaseModel, Field

from app.agents.prompts.reviewer_prompts import REVIEWER_SYSTEM_PROMPT
from app.agents.supervisor import clean_json_text
from app.core.config import settings
from app.providers import get_default_provider

logger = logging.getLogger(__name__)

class ReviewResult(BaseModel):
    verdict: str = Field(description="One of: 'approve', 'reject', 'escalate'")
    feedback: str = Field(default="", description="Detailed constructive feedback if rejected or escalated")

class ReviewerAgent:
    """
    Reviewer Agent responsible for validating specialist outputs.
    """

    def __init__(self):
        self.provider = get_default_provider()

    async def review(
        self,
        specialist: str,
        subtask_input: dict,
        expected_schema: dict,
        specialist_output: dict,
        task_id: str = "",
        subtask_id: str = ""
    ) -> tuple[ReviewResult, int, int]:
        """
        Validate specialist output.
        Returns:
            Tuple of (ReviewResult, input_tokens, output_tokens)
        """
        system_prompt = REVIEWER_SYSTEM_PROMPT.format(
            specialist=specialist,
            subtask_input=json.dumps(subtask_input),
            expected_schema=json.dumps(expected_schema),
            specialist_output=json.dumps(specialist_output)
        )

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": "Please perform the review."}
        ]

        model = settings.DEFAULT_MODEL_GEMINI if settings.GEMINI_API_KEY or settings.MOCK_PROVIDERS else settings.DEFAULT_MODEL_CLAUDE

        from app.observability.cost import calculate_span_cost
        from app.observability.tracing import get_tracer
        tracer = get_tracer()

        logger.info(f"Reviewer calling LLM ({model}) to review {specialist} output...")
        span_attrs = {
            "span_type": "llm_call",
            "actor": "reviewer",
            "model": model,
            "payload": {"messages": messages}
        }
        if task_id:
            span_attrs["task_id"] = str(task_id)
        if subtask_id:
            span_attrs["subtask_id"] = str(subtask_id)

        with tracer.start_as_current_span(
            "llm_call",
            attributes=span_attrs
        ) as span:
            response, in_tokens, out_tokens = await self.provider.chat_completion(
                model=model,
                messages=messages,
                response_schema=ReviewResult
            )
            cost = calculate_span_cost(model, in_tokens, out_tokens)
            if span and hasattr(span, "set_attribute"):
                span.set_attribute("tokens_in", in_tokens)
                span.set_attribute("tokens_out", out_tokens)
                span.set_attribute("cost_usd", cost)
                span.set_attribute("payload", {"messages": messages, "response": response})

        try:
            cleaned_response = clean_json_text(response)
            result_dict = json.loads(cleaned_response)
            result = ReviewResult(**result_dict)
            return result, in_tokens, out_tokens
        except Exception as e:
            logger.error(f"Failed to parse ReviewResult from LLM output: {response}. Error: {str(e)}")
            # Default to reject if parsing failed to be safe
            fallback_result = ReviewResult(
                verdict="reject",
                feedback=f"Failed to parse reviewer response. Raw output: {response}"
            )
            return fallback_result, in_tokens, out_tokens
