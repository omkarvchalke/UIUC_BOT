from functools import lru_cache

from groq import AsyncGroq

from app.core.config import get_settings


class GroqError(Exception):
    pass


@lru_cache
def get_groq_client() -> AsyncGroq:
    return AsyncGroq(api_key=get_settings().groq_api_key)


class GroqClient:
    """Thin wrapper: JSON-mode chat completion, no retry/streaming logic of
    its own -- the Groq SDK already retries transient failures, and
    streaming is a chat-endpoint concern that doesn't exist until the
    frontend does (Phase 7)."""

    def __init__(self, client: AsyncGroq | None = None) -> None:
        self._client = client or get_groq_client()

    async def complete_json(
        self,
        messages: list[dict[str, str]],
        *,
        model: str | None = None,
        temperature: float = 0.2,
        max_completion_tokens: int = 4096,
    ) -> str:
        settings = get_settings()
        try:
            # The SDK's overloads want precisely-typed per-role message
            # TypedDicts and a model Literal; we intentionally accept any
            # plain dicts and any configured model string here so the model
            # ID stays a runtime setting, not a type-checked constant.
            #
            # max_completion_tokens: without this, Groq falls back to a
            # default too small for the system prompt's "be thorough" rule
            # once a topic has enough real source material to draw on --
            # confirmed via a real failure ("max completion tokens reached
            # before generating a valid document", a 400 from Groq's
            # server-side JSON-mode validator) on a library-hours question
            # after the crawler (app/ingestion/crawler.py) added substantial
            # real library content that hadn't existed before. Raised from
            # an initial 2048 after the *same* error recurred on a housing
            # question that happened to enumerate every residence hall --
            # "be thorough" plus a topic with a lot of enumerable content
            # (dozens of halls) can genuinely need more room than a first
            # guess at "generous" accounts for.
            response = await self._client.chat.completions.create(  # type: ignore[call-overload]
                messages=messages,
                model=model or settings.groq_model,
                temperature=temperature,
                max_completion_tokens=max_completion_tokens,
                response_format={"type": "json_object"},
            )
        except Exception as exc:  # noqa: BLE001 - surfaced as a domain error the caller can degrade on
            raise GroqError(str(exc)) from exc

        content = response.choices[0].message.content
        if not content:
            raise GroqError("Groq returned an empty response")
        return str(content)
