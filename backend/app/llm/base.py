"""Provider-agnostic LLM client interface.

The rest of the app (app/rag/generator.py) only ever talks to this
interface — never to a specific provider's SDK directly. New providers are
added by implementing LLMClient and registering them in
provider_factory.py; no other code needs to change.
"""
from abc import ABC, abstractmethod
from typing import Iterator, TypedDict


class ChatMessage(TypedDict):
    role: str  # "system" | "user" | "assistant"
    content: str


class LLMProviderError(RuntimeError):
    """Raised for any provider failure: missing/invalid API key, rate
    limit, timeout, or a request-level API error. Callers (generator.py)
    don't need to know which provider raised it or why beyond the message —
    this is what makes the generator provider-agnostic."""


class LLMClient(ABC):
    @abstractmethod
    def generate(self, messages: list[ChatMessage], *, json_mode: bool = False) -> str:
        """Send a chat-style conversation, return the raw text response.

        Implementations must translate provider-specific errors (missing
        API key, rate limits, timeouts, invalid model, empty response) into
        LLMProviderError with a clear, actionable message — never let a
        provider SDK exception escape this method.
        """
        raise NotImplementedError

    @abstractmethod
    def generate_stream(self, messages: list[ChatMessage]) -> Iterator[str]:
        """Send a chat-style conversation, yield raw text chunks as they
        arrive. Always plain text — streaming and JSON mode don't mix well
        (a client can't usefully render partial JSON), so this is only
        ever used for the natural-language-answer call; see
        app/rag/generator.py.

        Implementations must translate provider-specific errors the same
        way as generate() — never let a provider SDK exception escape.
        """
        raise NotImplementedError
