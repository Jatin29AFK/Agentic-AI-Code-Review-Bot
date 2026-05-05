from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    app_name: str = "Agentic AI Code Review Bot"
    github_token: str | None = None
    github_webhook_secret: str | None = None
    llm_provider: str = "openai"
    llm_api_key: str | None = None
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str | None = None
    database_url: str = "sqlite:///./reviews.db"
    backend_cors_origins: str = (
        "http://localhost:3000,"
        "http://127.0.0.1:3000,"
        "http://localhost:5173,"
        "http://127.0.0.1:5173,"
        "http://localhost:5174,"
        "http://127.0.0.1:5174,"
        "http://localhost:5175,"
        "http://127.0.0.1:5175"
    )
    backend_cors_origin_regex: str = r"https?://(localhost|127\.0\.0\.1)(:\d+)?"
    max_files_reviewed: int = 25
    max_patch_chars_per_file: int = 12000
    max_total_patch_chars: int = 60000
    github_timeout_seconds: float = 20.0
    llm_timeout_seconds: float = 60.0
    post_webhook_comments: bool = False
    autofix_enabled: bool = True
    autofix_max_issues_per_review: int = 3
    autofix_min_confidence: float = 0.85
    autofix_max_patch_chars: int = 8000
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    @property
    def backend_cors_origins_list(self) -> list[str]:
        return [item.strip() for item in self.backend_cors_origins.split(",") if item.strip()]

    @property
    def resolved_llm_base_url(self) -> str:
        if self.llm_base_url:
            return self.llm_base_url.rstrip("/")

        provider_defaults = {
            "openai": "https://api.openai.com/v1",
            "groq": "https://api.groq.com/openai/v1",
            "openrouter": "https://openrouter.ai/api/v1",
            "openai_compatible": "https://api.openai.com/v1",
        }
        return provider_defaults.get(self.llm_provider.lower(), "https://api.openai.com/v1")


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
