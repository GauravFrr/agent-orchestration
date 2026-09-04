import logging
from typing import Any
import asyncio
from google import genai
from google.genai import types
from google.genai.errors import APIError

from app.providers.base import BaseProvider, NonRetryableProviderError, ProviderRateLimitError, RetryableProviderError
from app.core.config import settings

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
            if response_schema:
                # If a structured schema is requested (like Plan), return a mock JSON
                if hasattr(response_schema, "__name__") and response_schema.__name__ == "Plan":
                    mock_json = """{
                      "subtasks": [
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
                      ],
                      "confidence": 0.95
                    }"""
                    return mock_json, 15, 10
                elif hasattr(response_schema, "__name__") and response_schema.__name__ == "ReviewResult":
                    return '{"verdict": "approve", "feedback": ""}', 10, 5
            
            # Check if this is a specialist agent call
            is_specialist = any("Specialist" in msg.get("content", "") or "final_answer" in msg.get("content", "") for msg in messages)
            if is_specialist:
                return '{"thought": "I have completed the subtask.", "final_answer": {"overview": "Trends include LangGraph, supervisor patterns, and sandboxed code execution."}}', 10, 5
            
            return "This is a mocked Gemini response.", 15, 10

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
