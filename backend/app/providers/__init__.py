from app.core.config import settings
from app.providers.base import (
    BaseProvider,
    GatewayProviderError,
    NonRetryableProviderError,
    ProviderRateLimitError,
    RetryableProviderError,
)
from app.providers.claude import ClaudeProvider
from app.providers.gemini import GeminiProvider
from app.providers.groq import GroqProvider


def get_provider(name: str) -> BaseProvider:
    if name == "gemini":
        return GeminiProvider()
    elif name == "claude":
        return ClaudeProvider()
    elif name == "groq":
        return GroqProvider()
    else:
        raise ValueError(f"Unknown provider: {name}")

def get_default_provider() -> BaseProvider:
    """
    Returns the default available provider based on API keys config.
    """
    if settings.MOCK_PROVIDERS:
        return GeminiProvider()  # Returns mock Gemini provider
    if settings.GEMINI_API_KEY:
        return GeminiProvider()
    if settings.ANTHROPIC_API_KEY:
        return ClaudeProvider()
    if settings.GROQ_API_KEY:
        return GroqProvider()

    # Fallback/Default
    return GeminiProvider()

__all__ = [
    "BaseProvider",
    "GatewayProviderError",
    "RetryableProviderError",
    "NonRetryableProviderError",
    "ProviderRateLimitError",
    "GeminiProvider",
    "ClaudeProvider",
    "GroqProvider",
    "get_provider",
    "get_default_provider"
]
