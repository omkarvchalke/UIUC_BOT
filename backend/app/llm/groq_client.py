"""Groq chat completion client — the default LLM_PROVIDER.

Uses the official `groq` SDK (its interface mirrors the `openai` SDK
closely — same exception hierarchy, same chat.completions.create shape —
since Groq's API is OpenAI-compatible). See README "AI Stack" for why Groq
is the default: fast, has a genuinely free tier (no credit card), and the
app only needs it for chat generation — embeddings run locally.
"""
from typing import Iterator

import groq

from app.core.config import get_settings
from app.llm.base import ChatMessage, LLMClient, LLMProviderError


class GroqClient(LLMClient):
    def __init__(self) -> None:
        settings = get_settings()
        if not settings.groq_api_key:
            raise LLMProviderError(
                "GROQ_API_KEY is not set. Copy backend/.env.example to backend/.env "
                "and set a real Groq API key — free at https://console.groq.com/keys."
            )
        self._client = groq.Groq(api_key=settings.groq_api_key)
        self._model = settings.llm_model

    def generate(self, messages: list[ChatMessage], *, json_mode: bool = False) -> str:
        kwargs: dict = {"model": self._model, "messages": messages, "temperature": 0.2}
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            response = self._client.chat.completions.create(**kwargs)
        except groq.AuthenticationError as exc:
            raise LLMProviderError(f"Groq rejected the configured GROQ_API_KEY: {exc}") from exc
        except groq.RateLimitError as exc:
            raise LLMProviderError(f"Groq rate limit hit: {exc}") from exc
        except (groq.APITimeoutError, groq.APIConnectionError) as exc:
            raise LLMProviderError(f"Groq request timed out or failed to connect: {exc}") from exc
        except groq.APIError as exc:
            if json_mode:
                # Not every Groq model supports JSON mode — retry once without it
                # rather than failing outright.
                return self.generate(messages, json_mode=False)
            raise LLMProviderError(f"Groq API request failed: {exc}") from exc

        content = response.choices[0].message.content if response.choices else None
        if not content:
            raise LLMProviderError("Groq returned an empty response.")
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
        except groq.AuthenticationError as exc:
            raise LLMProviderError(f"Groq rejected the configured GROQ_API_KEY: {exc}") from exc
        except groq.RateLimitError as exc:
            raise LLMProviderError(f"Groq rate limit hit: {exc}") from exc
        except (groq.APITimeoutError, groq.APIConnectionError) as exc:
            raise LLMProviderError(f"Groq request timed out or failed to connect: {exc}") from exc
        except groq.APIError as exc:
            raise LLMProviderError(f"Groq API request failed: {exc}") from exc
