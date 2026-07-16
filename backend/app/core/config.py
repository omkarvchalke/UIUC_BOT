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

    # Pipeline tuning knobs, centralized here so every one is visible in one
    # place and env-overridable without a code change. Defaults match what
    # was previously hardcoded at each call site -- see that call site's own
    # comment for why the value was chosen; this is just where it now lives.
    chunk_size: int = 1000
    chunk_overlap: int = 150
    # Sections shorter than this (post <link>/nav-tag stripping) get merged
    # into a neighboring section rather than becoming their own tiny,
    # low-value chunk -- see app/ingestion/semantic_chunker.py.
    semantic_chunk_min_section_chars: int = 200
    retrieval_candidate_limit: int = 20
    rerank_top_k: int = 8
    topic_filter_min_results: int = 3
    topic_classification_confidence_threshold: float = 0.55
    # Standard constant from the original RRF paper (Cormack, Clarke &
    # Buettcher 2009) -- large enough that rank differences among top
    # results still matter, small enough that being ranked at all (even
    # far down one retriever's list) counts for something.
    rrf_k: int = 60
    groq_temperature: float = 0.2
    groq_max_completion_tokens: int = 4096
    crawl_default_max_depth: int = 4
    crawl_default_max_pages: int = 60

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
