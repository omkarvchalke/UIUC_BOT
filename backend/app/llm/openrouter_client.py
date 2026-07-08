"""OpenRouter chat completion client — a multi-model aggregator, also
OpenAI-compatible (same `openai` package, different base_url/api_key/model).
"""
from app.core.config import get_settings
from app.llm.openai_client import OpenAICompatibleClient


class OpenRouterClient(OpenAICompatibleClient):
    def __init__(self) -> None:
        settings = get_settings()
        super().__init__(
            api_key=settings.openrouter_api_key,
            base_url=settings.openrouter_base_url,
            model=settings.llm_model,
            key_env_var="OPENROUTER_API_KEY",
            provider_label="OpenRouter",
        )
