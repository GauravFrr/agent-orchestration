import asyncio
import logging
from typing import Any

from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.core.config import settings
from app.providers.base import BaseProvider, NonRetryableProviderError, ProviderRateLimitError, RetryableProviderError

logger = logging.getLogger(__name__)

class GeminiProvider(BaseProvider):
    """
    Provider wrapper for Google Gemini API using the modern google-genai SDK.
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize Gemini client.
        """
        # If API key is not supplied, try setting it from config.
        api_key = api_key or settings.GEMINI_API_KEY
        if not api_key and not settings.MOCK_PROVIDERS:
            raise NonRetryableProviderError("Gemini API key is required but missing.", provider="gemini")
        # In mock mode, client setup can be skipped or stubbed
        if api_key:
            self.client = genai.Client(api_key=api_key)
        else:
            self.client = None

    async def chat_completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        response_schema: Any | None = None,
    ) -> tuple[str, int, int]:
        """
        Execute chat completion on Google Gemini model.
        """
        model = settings.DEFAULT_MODEL_GEMINI
        if settings.MOCK_PROVIDERS:
            await asyncio.sleep(0.010)
            last_msg = messages[-1].get("content", "").lower() if messages and isinstance(messages[-1].get("content"), str) else ""

            is_supervisor = (response_schema and getattr(response_schema, "__name__", "") == "Plan") or ("supervisor agent" in last_msg or "decompose" in last_msg)
            is_reviewer = (response_schema and getattr(response_schema, "__name__", "") == "ReviewResult") or ("reviewer agent" in last_msg or "evaluate" in last_msg)

            if is_supervisor:
                import json
                if "research market trends" in last_msg or "summary report" in last_msg:
                    subtasks = [
                        {
                            "id": "subtask_1",
                            "specialist": "research",
                            "input": {"query": "agent orchestration trends"},
                            "depends_on": [],
                            "expected_output_schema": {}
                        },
                        {
                            "id": "subtask_2",
                            "specialist": "writing",
                            "input": {"facts_file": "subtask_1"},
                            "depends_on": ["subtask_1"],
                            "expected_output_schema": {}
                        }
                    ]
                elif "delete" in last_msg:
                    subtasks = [
                        {
                            "id": "subtask_1",
                            "specialist": "data_analysis",
                            "input": {"query": "Delete all temp records from demo_data.sales_data."},
                            "action_tag": "deletion",
                            "depends_on": [],
                            "expected_output_schema": {}
                        }
                    ]
                elif "non_existent_table" in last_msg:
                    subtasks = [
                        {
                            "id": "subtask_1",
                            "specialist": "data_analysis",
                            "input": {"query": "SELECT * FROM non_existent_table_999;"},
                            "depends_on": [],
                            "expected_output_schema": {}
                        }
                    ]
                elif "customer_sentiment_score" in last_msg:
                    subtasks = [
                        {
                            "id": "subtask_1",
                            "specialist": "data_analysis",
                            "input": {"query": "Query non-existent column 'customer_sentiment_score' from demo_data.sales_data."},
                            "depends_on": [],
                            "expected_output_schema": {}
                        }
                    ]
                elif "sales_data" in last_msg or "metrics" in last_msg:
                    subtasks = [
                        {
                            "id": "subtask_1",
                            "specialist": "data_analysis",
                            "input": {"query": "SELECT * FROM demo_data.sales_data;"},
                            "depends_on": [],
                            "expected_output_schema": {}
                        }
                    ]
                else:
                    subtasks = [
                        {
                            "id": "subtask_1",
                            "specialist": "research",
                            "input": {"query": "agent orchestration trends"},
                            "depends_on": [],
                            "expected_output_schema": {}
                        },
                        {
                            "id": "subtask_2",
                            "specialist": "writing",
                            "input": {"facts_file": "subtask_1"},
                            "depends_on": ["subtask_1"],
                            "expected_output_schema": {}
                        }
                    ]
                return json.dumps({"subtasks": subtasks, "confidence": 0.95}), 15, 10

            if is_reviewer:
                return '{"verdict": "approve", "feedback": ""}', 10, 5

            # Specialist agent call
            if "returned:" in last_msg or "tool '" in last_msg:
                return '{"thought": "Finished tool execution", "final_answer": {"overview": "Analysis and execution complete."}}', 10, 5

            if "non_existent_table" in last_msg:
                return '{"thought": "Querying table", "tool_call": {"name": "db_query", "arguments": {"query": "SELECT * FROM non_existent_table_999;"}}}', 10, 5
            elif "sales_data" in last_msg or "customer_sentiment_score" in last_msg:
                return '{"thought": "Querying sales data", "tool_call": {"name": "db_query", "arguments": {"query": "SELECT * FROM demo_data.sales_data;"}}}', 10, 5
            elif "research" in last_msg or "trends" in last_msg or "orchestration" in last_msg:
                return '{"thought": "Searching web for trends", "tool_call": {"name": "web_search", "arguments": {"query": "agent orchestration trends"}}}', 10, 5

            return '{"thought": "I have completed the subtask.", "final_answer": {"overview": "Trends include LangGraph, supervisor patterns, and sandboxed code execution."}}', 10, 5

        if not self.client:
            raise NonRetryableProviderError("Gemini client is not initialized (no API key).", provider="gemini")

        contents = []
        system_instruction = None

        for msg in messages:
            role = msg.get("role")
            content = msg.get("content")
            if role == "system":
                system_instruction = content
            elif role == "assistant":
                contents.append(types.Content(role="model", parts=[types.Part.from_text(text=content)]))
            else:
                contents.append(types.Content(role="user", parts=[types.Part.from_text(text=content)]))

        config = types.GenerateContentConfig()
        if max_tokens is not None:
            config.max_output_tokens = max_tokens
        if system_instruction is not None:
            config.system_instruction = system_instruction
        if response_schema is not None:
            config.response_mime_type = "application/json"

            def clean_additional_properties(schema: Any) -> Any:
                if isinstance(schema, dict):
                    return {k: clean_additional_properties(v) for k, v in schema.items() if k != "additionalProperties"}
                elif isinstance(schema, list):
                    return [clean_additional_properties(item) for item in schema]
                return schema

            if hasattr(response_schema, "model_json_schema"):
                schema_dict = response_schema.model_json_schema()
                config.response_schema = clean_additional_properties(schema_dict)
            else:
                config.response_schema = clean_additional_properties(response_schema)

        response = None
        max_retries = 10
        delay = 10
        for attempt in range(max_retries):
            try:
                # We must use self.client.aio for async calls
                response = await self.client.aio.models.generate_content(
                    model=model,
                    contents=contents,
                    config=config,
                )
                break
            except APIError as e:
                code = e.code
                if (code in (429, 503) or (code is not None and code >= 500)) and attempt < max_retries - 1:
                    logger.warning(f"Gemini API returned retryable status {code} (attempt {attempt+1}/{max_retries}). Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 120)
                    continue
                if code == 429:
                    raise ProviderRateLimitError(f"Gemini API error: {e.message}", provider="gemini")
                elif code is not None and code >= 500:
                    raise RetryableProviderError(f"Gemini API error: {e.message}", provider="gemini", status_code=code)
                else:
                    raise NonRetryableProviderError(f"Gemini API error: {e.message}", provider="gemini", status_code=code)
            except Exception as e:
                if attempt < max_retries - 1 and ("503" in str(e) or "UNAVAILABLE" in str(e) or "429" in str(e) or "RESOURCE_EXHAUSTED" in str(e)):
                    logger.warning(f"Gemini API retryable exception '{str(e)}' (attempt {attempt+1}/{max_retries}). Retrying in {delay}s...")
                    await asyncio.sleep(delay)
                    delay = min(delay * 2, 120)
                    continue
                raise NonRetryableProviderError(f"Unexpected Gemini error: {str(e)}", provider="gemini")

        if response is None:
            raise RetryableProviderError("Gemini API error: maximum retries exceeded without response", provider="gemini")

        content_text = response.text or ""
        usage = response.usage_metadata
        input_tokens = (usage.prompt_token_count or 0) if usage else 0
        output_tokens = (usage.candidates_token_count or 0) if usage else 0

        return content_text, input_tokens, output_tokens
