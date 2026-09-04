from abc import ABC, abstractmethod
from typing import Any


class GatewayProviderError(Exception):
    """Base exception for all provider failures."""

    def __init__(self, message: str, provider: str, status_code: int | None = None):
        super().__init__(message)
        self.message = message
        self.provider = provider
        self.status_code = status_code
        self.trips_circuit: bool = True

class RetryableProviderError(GatewayProviderError):
    """Exceptions that are safe to retry (e.g., rate limits, network timeouts, transient 5xx)."""
    pass

class ProviderRateLimitError(RetryableProviderError):
    """Provider returned 429 (quota/rate-limit). Retryable but does NOT trip the circuit breaker."""

    def __init__(self, message: str, provider: str, status_code: int = 429):
        super().__init__(message, provider, status_code)
        self.trips_circuit = False

class NonRetryableProviderError(GatewayProviderError):
    """Exceptions that should not be retried (e.g., bad request, invalid API keys, invalid models)."""
    pass

class BaseProvider(ABC):
    """
    Abstract interface for all model providers.
    """

    @abstractmethod
    async def chat_completion(
        self,
        model: str,
        messages: list[dict[str, str]],
        max_tokens: int | None = None,
        response_schema: Any | None = None,
    ) -> tuple[str, int, int]:
        """
        Send a chat completion request to the provider.

        Args:
            model: The exact provider model string.
            messages: List of message dictionaries, each with 'role' and 'content'.
            max_tokens: Optional token limit for generation.
            response_schema: Optional Pydantic model for structured output format.

        Returns:
            A tuple of (generated_content_string, input_tokens_count, output_tokens_count).
        """
        pass
