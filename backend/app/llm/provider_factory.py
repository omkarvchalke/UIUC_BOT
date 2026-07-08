"""Returns the configured LLM client for LLM_PROVIDER.

This is the ONLY place in the app that knows how to instantiate a specific
provider — app/rag/generator.py just calls get_llm_client() and uses the
returned LLMClient interface. Adding a new provider means adding a branch
here (and a client module); no other code changes.

Each provider module is imported lazily (inside its branch) so that an
unused provider's import-time behavior can never affect startup when a
different provider is configured.
"""
from app.core.config import get_settings
from app.llm.base import LLMClient, LLMProviderError

SUPPORTED_PROVIDERS = ("groq", "openai", "google", "openrouter")


def get_llm_client() -> LLMClient:
    settings = get_settings()
    provider = settings.llm_provider.lower().strip()

    if provider == "groq":
        from app.llm.groq_client import GroqClient

        return GroqClient()

    if provider == "openai":
        from app.llm.openai_client import OpenAIClient

        return OpenAIClient()

    if provider == "google":
        from app.llm.google_client import GoogleClient

        return GoogleClient()

    if provider == "openrouter":
        from app.llm.openrouter_client import OpenRouterClient

        return OpenRouterClient()

    raise LLMProviderError(
        f"Unknown LLM_PROVIDER={provider!r}. Supported providers: {list(SUPPORTED_PROVIDERS)}."
    )
