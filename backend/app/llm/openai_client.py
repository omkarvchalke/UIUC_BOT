"""OpenAI chat completion client — and the shared base implementation for
every other OpenAI-compatible provider (google_client.py,
openrouter_client.py). They're mechanically identical REST APIs; only the
API key, base URL, and model differ.
"""
from typing import Iterator

from openai import (
    APIConnectionError,
    APIError,
    APITimeoutError,
    AuthenticationError,
    OpenAI as OpenAISDK,
    RateLimitError,
)

from app.llm.base import ChatMessage, LLMClient, LLMProviderError


class OpenAICompatibleClient(LLMClient):
    """Base for any provider that speaks the OpenAI chat-completions API
    shape. Subclasses just supply api_key/base_url/model/provider_label —
    see google_client.py and openrouter_client.py."""

    def __init__(self, *, api_key: str, base_url: str, model: str, key_env_var: str, provider_label: str) -> None:
        if not api_key:
            raise LLMProviderError(
                f"{key_env_var} is not set. Copy backend/.env.example to backend/.env "
                f"and set a real {provider_label} API key."
            )
        self._client = OpenAISDK(api_key=api_key, base_url=base_url)
        self._model = model
        self._provider_label = provider_label

    def generate(self, messages: list[ChatMessage], *, json_mode: bool = False) -> str:
        kwargs: dict = {"model": self._model, "messages": messages, "temperature": 0.2}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self._client.chat.completions.create(**kwargs)
        except AuthenticationError as exc:
            raise LLMProviderError(
                f"{self._provider_label} rejected the configured API key: {exc}"
            ) from exc
        except RateLimitError as exc:
            raise LLMProviderError(f"{self._provider_label} rate limit hit: {exc}") from exc
        except (APITimeoutError, APIConnectionError) as exc:
            raise LLMProviderError(
                f"{self._provider_label} request timed out or failed to connect: {exc}"
            ) from exc
        except APIError as exc:
            if json_mode:
                return self.generate(messages, json_mode=False)
            raise LLMProviderError(f"{self._provider_label} API request failed: {exc}") from exc

        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise LLMProviderError(f"{self._provider_label} returned an empty response.")
        return content

    def generate_stream(self, messages: list[ChatMessage]) -> Iterator[str]:
        try:
            stream = self._client.chat.completions.create(
                model=self._model, messages=messages, temperature=0.2, stream=True
            )
            for chunk in stream:
                delta = chunk.choices[0].delta.content if chunk.choices else None
                if delta:
                    yield delta
        except AuthenticationError as exc:
            raise LLMProviderError(
                f"{self._provider_label} rejected the configured API key: {exc}"
            ) from exc
        except RateLimitError as exc:
            raise LLMProviderError(f"{self._provider_label} rate limit hit: {exc}") from exc
        except (APITimeoutError, APIConnectionError) as exc:
            raise LLMProviderError(
                f"{self._provider_label} request timed out or failed to connect: {exc}"
            ) from exc
        except APIError as exc:
            raise LLMProviderError(f"{self._provider_label} API request failed: {exc}") from exc


class OpenAIClient(OpenAICompatibleClient):
    def __init__(self) -> None:
        from app.core.config import get_settings

        settings = get_settings()
        super().__init__(
            api_key=settings.openai_api_key,
            base_url=settings.openai_base_url,
            model=settings.llm_model,
            key_env_var="OPENAI_API_KEY",
            provider_label="OpenAI",
        )
