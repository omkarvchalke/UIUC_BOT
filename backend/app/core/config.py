from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-driven settings. See backend/.env.example for defaults.

    Provider-agnostic by design: LLM_PROVIDER selects the chat-generation
    provider (see app/llm/provider_factory.py) and EMBEDDING_PROVIDER
    selects the embeddings provider (currently only "local" is
    implemented — see app/rag/embeddings.py). Each provider reads its own
    API key/base URL; switching providers is an env var change only, no
    code change.
    """

    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # --- Chat generation ---
    llm_provider: str = "groq"
    llm_model: str = "llama-3.3-70b-versatile"

    groq_api_key: str = ""

    openai_api_key: str = ""
    openai_base_url: str = "https://api.openai.com/v1"

    google_api_key: str = ""
    google_base_url: str = "https://generativelanguage.googleapis.com/v1beta/openai/"

    openrouter_api_key: str = ""
    openrouter_base_url: str = "https://openrouter.ai/api/v1"

    # --- Embeddings ---
    embedding_provider: str = "local"
    embedding_model: str = "BAAI/bge-base-en-v1.5"

    # --- Vector store ---
    vector_db: str = "chromadb"
    chroma_db_path: str = "../ingestion/data/chroma"

    # --- API ---
    cors_origins: str = "http://localhost:5173"

    @property
    def cors_origin_list(self) -> list[str]:
        return [origin.strip() for origin in self.cors_origins.split(",") if origin.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
