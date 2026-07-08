# Architecture

## Overview

CampusGuide AI is a three-tier application: a React/TypeScript frontend, a FastAPI backend, and an offline ingestion pipeline that builds a local vector index from curated public UIUC webpages.

```text
┌─────────────────┐        HTTP/JSON        ┌──────────────────────┐
│  React Frontend  │  ───────────────────▶  │   FastAPI Backend    │
│  (Vite + TS +    │  ◀───────────────────  │  (chat / retrieve /   │
│   Tailwind)      │                         │  checklist / feedback)│
└─────────────────┘                         └──────────┬───────────┘
                                                        │
                                             ┌──────────▼───────────┐
                                             │   RAG Layer          │
                                             │  - retriever.py       │
                                             │  - prompt_builder.py  │
                                             │  - generator.py       │
                                             │  - safety.py (guard)  │
                                             └──────────┬───────────┘
                                                        │
                                             ┌──────────▼───────────┐
                                             │   ChromaDB (local)    │
                                             │   persisted vector    │
                                             │   store of chunks     │
                                             └──────────▲───────────┘
                                                        │
                                             ┌──────────┴───────────┐
                                             │  Ingestion Pipeline   │
                                             │  fetch → clean →      │
                                             │  chunk → embed        │
                                             │  (offline, batch)     │
                                             └───────────────────────┘
                                                        │
                                             ┌──────────▼───────────┐
                                             │ sources.json          │
                                             │ (curated public URLs) │
                                             └───────────────────────┘
```

## Components

### Frontend (`frontend/`)

- **Pages:** Home, Chat, Checklist, Sources, About
- **Components:** ChatBox, MessageBubble, SourceCard, DisclaimerBanner, PrivacyBanner, ConfidenceBadge, FeedbackButtons
- **Services:** `api.ts` — thin wrapper around `fetch`/axios calls to the backend, configured via `VITE_API_BASE_URL`

### Backend (`backend/app/`)

- **`api/`** — FastAPI routers: `chat.py`, `retrieve.py`, `sources.py`, `checklist.py`, `feedback.py`
- **`core/`** — `config.py` (env-driven settings via Pydantic), `safety.py` (guardrail classifier)
- **`llm/`** — provider-agnostic chat generation: `base.py` (the `LLMClient` interface + `LLMProviderError`), `groq_client.py`, `openai_client.py` (also the shared base for the two below), `google_client.py`, `openrouter_client.py`, `provider_factory.py` (the only place that instantiates a specific provider, selected by `LLM_PROVIDER`)
- **`rag/`** — `embeddings.py` (local sentence-transformers, no API key), `vector_store.py`, `retriever.py`, `prompt_builder.py`, `generator.py` (calls `llm/provider_factory.py`, doesn't know which provider it got), `_telemetry.py` (no-op Chroma telemetry client, sidesteps a `posthog` version-skew bug)
- **`models/`** — Pydantic request/response schemas shared across endpoints
- **`prompts/`** — `rag_system_prompt.txt`, the system prompt template used for generation

### Ingestion (`ingestion/`)

Offline, script-driven pipeline (not part of the live request path):

1. `fetch_pages.py` — fetches curated public URLs from `sources.json`, saves raw HTML + metadata
2. `clean_text.py` — strips boilerplate (nav/footer/script/style), extracts readable text
3. `chunk_text.py` — splits cleaned text into ~500–800 token chunks with ~100 token overlap, preserving source metadata
4. `embed_chunks.py` — embeds chunks locally (sentence-transformers, no API key) and writes them into the persistent ChromaDB store
5. `refresh_index.py` — orchestrates the full fetch → clean → chunk → embed pipeline in one command

### Storage

- **ChromaDB** (local persistence, path configured via `CHROMA_DB_PATH`) — the vector index used at query time
- **JSON/JSONL files** (`ingestion/data/{raw,processed,chunks}`) — intermediate artifacts of the ingestion pipeline, useful for debugging and re-embedding without re-fetching
- No SQL database in v1 — deliberately avoided to keep the MVP simple

## Request Flow: `/api/chat`

1. Frontend sends `{ "question": "..." }` to `POST /api/chat`.
2. Backend runs the question through `core/safety.py` to classify it: `private_data` (blocking), one of `health`/`emergency`/`immigration`/`financial_aid` (sensitive-but-allowed), or `normal`.
3. If it's `private_data`, the backend returns a fixed safe fallback immediately — **no embedding or LLM call is made at all**.
4. Otherwise, `rag/retriever.py` embeds the question locally (no API key) and queries ChromaDB for the top-5 chunks (cosine similarity).
5. If retrieval returns zero chunks (empty index or no relevant match), a safe "insufficient context" answer is returned — again, no LLM call.
6. `confidence` (`high`/`medium`/`low`) is computed **deterministically from the retrieval scores**, not asked of the model; `sources` are deduplicated by URL from chunk metadata — the model is never given the opportunity to invent a source URL.
7. `rag/prompt_builder.py` assembles chat-completion messages from `rag_system_prompt.txt` (rules only) + a numbered context block + the question.
8. `rag/generator.py` asks `llm/provider_factory.py` for the client configured by `LLM_PROVIDER` (Groq by default) and calls it in JSON mode, parsing `{answer, next_steps}` (falls back to raw text if the model doesn't return valid JSON). `generator.py` never knows which provider it's talking to.
9. If the safety classifier flagged a sensitive-but-allowed category, its escalation note is prepended to `next_steps` and `requires_official_confirmation` is forced `true`.
10. Response `{ answer, sources, confidence, next_steps, requires_official_confirmation }` returns to the frontend for rendering.

## Configuration

All environment-specific values (API keys, model names, CORS origins, Chroma persistence directory) are read from environment variables via `backend/app/core/config.py`, never hardcoded. See root `.env.example`, `backend/.env.example`, and `frontend/.env.example`.

Switching LLM providers (`LLM_PROVIDER=groq|openai|google|openrouter`) or the vector DB (`VECTOR_DB`) is purely a config change — see `backend/README.md` → "AI Stack: Providers" for how `llm/provider_factory.py` keeps this decoupled from the rest of the app.
