"""Application configuration using pydantic-settings."""

from functools import lru_cache
from decimal import Decimal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    # Application
    app_name: str = "bot_ebooks"
    debug: bool = False
    api_v1_prefix: str = "/api/v1"

    # Database
    database_url: str = "postgresql+asyncpg://bot_ebooks:bot_ebooks@localhost:5432/bot_ebooks"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # LLM Providers
    # Using BOT_EBOOKS_ prefix to avoid conflicts with shell env vars
    bot_ebooks_anthropic_key: str = ""
    bot_ebooks_openai_key: str = ""
    bot_ebooks_google_key: str = ""  # For Gemini

    # Fallback to standard names if prefixed ones not set
    anthropic_api_key: str = ""
    openai_api_key: str = ""
    google_api_key: str = ""

    @property
    def effective_anthropic_key(self) -> str:
        """Get Anthropic key, preferring prefixed version."""
        return self.bot_ebooks_anthropic_key or self.anthropic_api_key

    @property
    def effective_openai_key(self) -> str:
        """Get OpenAI key, preferring prefixed version."""
        return self.bot_ebooks_openai_key or self.openai_api_key

    @property
    def effective_google_key(self) -> str:
        """Get Google key, preferring prefixed version."""
        return self.bot_ebooks_google_key or self.google_api_key

    # Evaluation
    judge_model: str = "claude-sonnet-4-20250514"
    embedding_model: str = "text-embedding-3-small"

    # Multi-evaluator settings
    evaluation_providers: str = "claude,openai"  # Comma-separated list
    evaluation_personas: str = "rigorist,synthesizer,stylist,contrarian,pedagogue"  # All 5 personas

    # Economy
    initial_credits: Decimal = Decimal("100.0")
    ebook_price: Decimal = Decimal("10.0")
    author_share: Decimal = Decimal("1.0")  # 100% to author for Phase 1

    # Rate Limiting
    max_submissions_per_day: int = 5
    max_requests_per_minute: int = 60

    # Evaluation thresholds
    minimum_overall_score: Decimal = Decimal("3.0")


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()
