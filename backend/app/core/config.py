"""
Application configuration.

All settings are loaded from environment variables (with sane local-dev
defaults) via pydantic-settings. Nothing here requires an API key to run --
LLM-dependent settings are optional and simply disable AI-powered features
(handled gracefully in app/services/llm_client.py, added in Phase 2) until
you provide them.
"""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- Core ---
    APP_NAME: str = "AI ResearchOS"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True

    # --- Database ---
    # Defaults to a local SQLite file so the project runs with zero external
    # services. Set DATABASE_URL to a Postgres DSN in production, e.g.:
    # postgresql+asyncpg://user:pass@postgres:5432/researchos
    DATABASE_URL: str = "sqlite+aiosqlite:///./data/researchos.db"

    # --- External research APIs (no key required) ---
    ARXIV_API_BASE: str = "https://export.arxiv.org/api/query"
    ARXIV_TIMEOUT_SECONDS: float = 15.0
    ARXIV_MAX_RESULTS_DEFAULT: int = 20

    SEMANTIC_SCHOLAR_API_BASE: str = "https://api.semanticscholar.org/graph/v1/paper/search"
    SEMANTIC_SCHOLAR_API_KEY: str | None = None  # optional; raises the free rate limit

    # --- Storage ---
    PDF_STORAGE_DIR: str = "./data/pdfs"

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # --- Rate limiting (always on; generous defaults, tune per deployment) ---
    RATE_LIMIT_CAPACITY: int = 120       # burst size, requests
    RATE_LIMIT_REFILL_PER_SECOND: float = 2.0  # sustained rate after burst

    # --- Auth (off by default -- see docs/GAP_ANALYSIS.md for the OAuth
    # roadmap; this HMAC-token scheme is the working auth layer for now).
    # Flip REQUIRE_API_AUTH on and set API_AUTH_SECRET to require a Bearer
    # token (see scripts/issue_token.py) on paper-ingest/research-run calls.
    REQUIRE_API_AUTH: bool = False
    API_AUTH_SECRET: str | None = None

    # --- LLM (optional, added Phase 2) ---
    ANTHROPIC_API_KEY: str | None = None


@lru_cache
def get_settings() -> Settings:
    return Settings()
