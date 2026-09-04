from typing import Any
import asyncio
import json
from groq import APIStatusError, AsyncGroq, GroqError

from app.providers.base import BaseProvider, NonRetryableProviderError, ProviderRateLimitError, RetryableProviderError
from app.core.config import settings

class GroqProvider(BaseProvider):
    """
    Provider wrapper for Groq API using the groq SDK.
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize Groq client.
        """
        api_key = api_key or settings.GROQ_API_KEY
        if not api_key and not settings.MOCK_PROVIDERS:
            raise NonRetryableProviderError("Groq API key is required but missing.", provider="groq")
        if api_key:
            self.client = AsyncGroq(api_key=api_key)
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
        Execute chat completion on Groq model.
        """
        if settings.MOCK_PROVIDERS:
            await asyncio.sleep(0.010)
            if response_schema:
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
            
            # Check if this is a specialist call
            is_specialist = any("Specialist" in msg.get("content", "") or "final_answer" in msg.get("content", "") for msg in messages)
            if is_specialist:
                return '{"thought": "I have completed the subtask.", "final_answer": {"overview": "Trends include LangGraph, supervisor patterns, and sandboxed code execution."}}', 10, 5

            return "This is a mocked Groq response.", 15, 10

        if not self.client:
            raise NonRetryableProviderError("Groq client is not initialized.", provider="groq")

        # Format messages for openai-compatible API
        formatted_messages = []
        for msg in messages:
            formatted_messages.append({"role": msg["role"], "content": msg["content"]})

        kwargs = {}
        if max_tokens is not None:
            kwargs["max_tokens"] = max_tokens

        if response_schema is not None:
            kwargs["response_format"] = {"type": "json_object"}
            schema_desc = ""
            if hasattr(response_schema, "model_json_schema"):
                schema_desc = json.dumps(response_schema.model_json_schema(), indent=2)
            else:
                schema_desc = str(response_schema)
            # Inject JSON schema instructions into the first system message if present
            inserted = False
            for msg in formatted_messages:
                if msg["role"] == "system":
                    msg["content"] += (
                        f"\n\nYou MUST return output strictly in JSON format matching the schema:\n{schema_desc}"
                    )
                    inserted = True
                    break
            if not inserted:
                formatted_messages.insert(
                    0,
                    {
                        "role": "system",
                        "content": f"You MUST return output strictly in JSON format matching the schema:\n{schema_desc}",
                    },
                )

        try:
            response = await self.client.chat.completions.create(model=model, messages=formatted_messages, **kwargs)
        except APIStatusError as e:
            if e.status_code == 429:
                raise ProviderRateLimitError(f"Groq API status error: {e.message}", provider="groq")
            elif e.status_code >= 500:
                raise RetryableProviderError(
                    f"Groq API status error: {e.message}", provider="groq", status_code=e.status_code
                )
            else:
                raise NonRetryableProviderError(
                    f"Groq API status error: {e.message}", provider="groq", status_code=e.status_code
                )
        except GroqError as e:
            raise RetryableProviderError(f"Groq error: {str(e)}", provider="groq")
        except Exception as e:
            raise NonRetryableProviderError(f"Unexpected Groq error: {str(e)}", provider="groq")

        content_text = ""
        if response.choices:
            content_text = response.choices[0].message.content or ""

        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        return content_text, input_tokens, output_tokens
