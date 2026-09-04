from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore"
    )

    # Database URLs
    DATABASE_URL: str = Field(
        default="postgresql+psycopg://orchestrator:orchestrator_pass@localhost:5432/orchestration"
    )
    ANALYST_DATABASE_URL: str = Field(
        default="postgresql+psycopg://analyst:analyst_pass@localhost:5432/orchestration"
    )

    # Provider API Keys
    GEMINI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    GROQ_API_KEY: str | None = None

    # Memory Store Configuration
    REDIS_URL: str = Field(default="redis://localhost:6379/0")
    CHROMA_HOST: str = Field(default="localhost")
    CHROMA_PORT: int = Field(default=8000)

    # Model Defaults
    DEFAULT_MODEL_GEMINI: str = "gemini-3.5-flash-lite"
    DEFAULT_MODEL_CLAUDE: str = "claude-3-5-sonnet-latest"
    DEFAULT_MODEL_GROQ: str = "llama-3.3-70b-versatile"

    # Testing & Development
    MOCK_PROVIDERS: bool = False

settings = Settings()
