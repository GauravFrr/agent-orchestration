from typing import Any
import asyncio
import json
from anthropic import APIError, APIStatusError, AsyncAnthropic

from app.providers.base import BaseProvider, NonRetryableProviderError, RetryableProviderError
from app.core.config import settings

class ClaudeProvider(BaseProvider):
    """
    Provider wrapper for Anthropic Claude API using the anthropic SDK.
    """

    def __init__(self, api_key: str | None = None):
        """
        Initialize Claude client.
        """
        api_key = api_key or settings.ANTHROPIC_API_KEY
        if not api_key and not settings.MOCK_PROVIDERS:
            raise NonRetryableProviderError("Anthropic API key is required but missing.", provider="claude")
        if api_key:
            self.client = AsyncAnthropic(api_key=api_key)
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
        Execute chat completion on Anthropic Claude model.
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
            
            # Check if this is a specialist agent call
            is_specialist = any("Specialist" in msg.get("content", "") or "final_answer" in msg.get("content", "") for msg in messages)
            if is_specialist:
                return '{"thought": "I have completed the subtask.", "final_answer": {"overview": "Trends include LangGraph, supervisor patterns, and sandboxed code execution."}}', 10, 5

            return "This is a mocked Claude response.", 15, 10

        if not self.client:
            raise NonRetryableProviderError("Claude client is not initialized.", provider="claude")

        system_parts = [msg["content"] for msg in messages if msg.get("role") == "system"]
        
        # If response_schema is specified, instruct Claude to return valid JSON matching it
        if response_schema:
            schema_desc = ""
            if hasattr(response_schema, "model_json_schema"):
                schema_desc = json.dumps(response_schema.model_json_schema(), indent=2)
            else:
                schema_desc = str(response_schema)
            json_instruction = (
                f"\n\nYou MUST return output strictly in JSON format. "
                f"The JSON structure must adhere to the following schema:\n{schema_desc}\n"
                f"Do not include any introductory or concluding text, only return the JSON object."
            )
            system_parts.append(json_instruction)

        system_instruction = "\n".join(system_parts) if system_parts else None

        filtered_messages = [
            {"role": msg["role"], "content": msg["content"]} for msg in messages if msg.get("role") != "system"
        ]

        final_max_tokens = max_tokens or 1024

        kwargs = {}
        if system_instruction:
            kwargs["system"] = system_instruction

        try:
            response = await self.client.messages.create(
                model=model, messages=filtered_messages, max_tokens=final_max_tokens, **kwargs
            )
        except APIStatusError as e:
            if e.status_code >= 500 or e.status_code == 429:
                raise RetryableProviderError(
                    f"Claude API status error: {e.message}", provider="claude", status_code=e.status_code
                )
            else:
                raise NonRetryableProviderError(
                    f"Claude API status error: {e.message}", provider="claude", status_code=e.status_code
                )
        except APIError as e:
            raise RetryableProviderError(f"Claude API error: {str(e)}", provider="claude")
        except Exception as e:
            raise NonRetryableProviderError(f"Unexpected Claude error: {str(e)}", provider="claude")

        content_text = ""
        if response.content:
            content_text = response.content[0].text if hasattr(response.content[0], "text") else ""

        input_tokens = response.usage.input_tokens if response.usage else 0
        output_tokens = response.usage.output_tokens if response.usage else 0

        return content_text, input_tokens, output_tokens
