from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    app_name: str = "IlliniAssist AI"
    environment: str = "development"
    log_level: str = "INFO"

    cors_origins: str = "http://localhost:3000"

    groq_api_key: str = ""
    groq_model: str = "llama-3.3-70b-versatile"

    embedding_model_name: str = "BAAI/bge-small-en-v1.5"

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

    # Generation backend: explicit opt-in, deliberately independent of
    # groq_api_key's mere presence -- get_answer_generator used to switch
    # to GroqAnswerGenerator on `if groq_api_key:` alone, which meant
    # configuring a key to power agentic retrieval below would *also*
    # silently flip generation off the deterministic extractive default.
    # Requires both this flag and a real key.
    groq_generation_enabled: bool = False

    # Agentic retrieval: an LLM judges whether retrieved context is
    # sufficient to answer the question before generation runs, and if
    # not, reformulates the query and retries retrieval
    # (app/graph/retrieval_agent.py, app/llm/retrieval_agent.py). Off by
    # default -- AlwaysSufficientChecker is used instead, which never
    # calls Groq and never changes today's single-pass behavior. Also
    # independent of groq_generation_enabled above: you can run agentic
    # retrieval with the extractive generator, which is the whole point.
    agentic_retrieval_enabled: bool = False
    # Total retrieve() calls allowed per turn: 1 initial + N reformulated
    # retries. 2 = one retry -- enough to recover from a genuinely bad
    # first retrieval without multiplying per-turn latency/cost
    # unboundedly. The router (app/graph/edges.py) enforces this
    # unconditionally, so the loop always terminates regardless of what
    # the checker reports -- LangGraph's own recursion_limit (default 25
    # supersteps) is a backstop, not the mechanism this depends on.
    agentic_retrieval_max_attempts: int = 2
    agentic_retrieval_temperature: float = 0.0
    agentic_retrieval_max_completion_tokens: int = 512

    # Query decomposition: an LLM splits a genuinely multi-part question
    # into 2-3 focused sub-questions, each retrieved independently and
    # merged before reranking (app/graph/query_decomposition.py,
    # app/llm/query_decomposition.py). Off by default -- NoOpQueryDecomposer
    # is used instead, which never calls Groq and always returns the
    # original question as a single-item list, so retrieve() runs its
    # existing single-query search unchanged. Deliberately independent of
    # agentic_retrieval_enabled: either can run without the other.
    query_decomposition_enabled: bool = False
    query_decomposition_max_subqueries: int = 3
    query_decomposition_temperature: float = 0.0
    query_decomposition_max_completion_tokens: int = 512

    # Source Manifest V2 metadata (see backend/scripts/data/source_manifest_v2.md).
    # Role-aware chunk sizing (app/ingestion/chunking.py::role_chunk_config) is specified in
    # tokens there; the pipeline has no tokenizer dependency, so this is a documented
    # approximation for converting a token target to a character target, not a precise count.
    chars_per_token: int = 4
    # Stamped onto Document.embedding_version by IndexingService whenever a document's chunks
    # are (re-)embedded, so a future embedding-model change can be identified per-document
    # instead of assumed uniform across the whole corpus. Defaults to the embedding model name
    # since that's the actual thing that determines vector compatibility; bump this (or the
    # model name) together if the model ever changes.
    embedding_version: str = "BAAI/bge-small-en-v1.5"
    # retrieval_priority boost applied in HybridRetriever._fuse: normalized priority (0-100) maps
    # linearly onto [1 - retrieval_priority_boost_range, 1 + retrieval_priority_boost_range],
    # multiplying each chunk's fused RRF score. Deliberately small -- a boost/nudge per Source
    # Manifest V2 Part 4 ("do not allow retrieval_priority to completely override semantic
    # relevance"), not a re-ranking mechanism in its own right.
    retrieval_priority_boost_range: float = 0.1

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
