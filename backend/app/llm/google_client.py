"""Google Gemini chat completion client, via Gemini's OpenAI-compatible
endpoint (no separate Google SDK needed — same `openai` package, just a
different base_url/api_key/model).
"""
from app.core.config import get_settings
from app.llm.openai_client import OpenAICompatibleClient


class GoogleClient(OpenAICompatibleClient):
    def __init__(self) -> None:
        settings = get_settings()
        super().__init__(
            api_key=settings.google_api_key,
            base_url=settings.google_base_url,
            model=settings.llm_model,
            key_env_var="GOOGLE_API_KEY",
            provider_label="Google Gemini",
        )
