from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "IlliniGuide AI"
    environment: str = "development"
    log_level: str = "INFO"

    cors_origins: str = "http://localhost:3000"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    embedding_model_name: str = "BAAI/bge-small-en-v1.5"

    qdrant_url: str = "http://localhost:6333"
    qdrant_collection_name: str = "illiniguide_documents"

    database_url: str = "postgresql+asyncpg://illiniguide:change-me@localhost:5432/illiniguide"
    db_pool_size: int = 5
    db_max_overflow: int = 10

    # Chat calls a paid Groq API per request; retrieve runs embedding +
    # cross-encoder inference. Both are rate-limited per client IP to bound
    # cost and CPU load from a single abusive or looping client.
    chat_rate_limit: str = "20/minute"
    retrieve_rate_limit: str = "30/minute"

    @property
    def cors_origins_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]

    @property
    def test_database_url(self) -> str:
        # Derived, not a separate configured value: always "<dev db>_test" on
        # the same server, so there's no separate setting to forget to set
        # (and no way for it to silently drift to point at the dev database
        # again -- see the incident where the test suite's autouse table
        # cleanup fixture truncated the real ingested document corpus
        # because tests and manual smoke-testing shared one database).
        base_url, _, db_name = self.database_url.rpartition("/")
        return f"{base_url}/{db_name}_test"


@lru_cache
def get_settings() -> Settings:
    return Settings()
