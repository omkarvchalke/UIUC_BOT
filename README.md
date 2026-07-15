# IlliniGuide AI

An AI-powered onboarding assistant for prospective, admitted, freshman, transfer, graduate,
and international students at the University of Illinois Urbana-Champaign (UIUC). Answers are
grounded exclusively in official, publicly available UIUC resources via Retrieval-Augmented
Generation, and the app never asks for personally identifiable information.

> **Status:** Phases 1-7 complete (architecture/Docker, backend database layer, document
> ingestion, embeddings + Qdrant + hybrid retrieval, LangGraph orchestration, Groq generation,
> Next.js chat UI). `POST /api/v1/chat` runs the full graph — profile checks, intent detection,
> topic classification, hybrid retrieval, cross-encoder reranking, real Groq-generated answers
> with self-reported groundedness, and citations built only from sections the model actually
> cited. The chat UI (onboarding, suggested questions, source panel, dark mode) is live and
> browser-tested end-to-end against the real backend. **Not yet verified against a real Groq API
> key** — falls back to the deterministic Phase 5 generator until `GROQ_API_KEY` is set (see
> Groq Integration below); answer text is noticeably rougher until then (verbatim extracted
> chunk text rather than synthesized prose). Testing (Phase 8) is next.

## Tech Stack

| Layer            | Choice                                              |
|-------------------|------------------------------------------------------|
| Frontend          | Next.js (App Router), TypeScript, TailwindCSS, shadcn/ui |
| Backend           | Python, FastAPI                                     |
| Orchestration     | LangGraph, LangChain-core                           |
| LLM               | Groq (`llama-3.3-70b-versatile`, JSON mode)         |
| Embeddings        | Local sentence-transformers (BAAI/bge-small-en-v1.5), CPU-only |
| Vector database   | Qdrant                                              |
| Relational database | PostgreSQL                                        |
| Package manager   | uv (backend), npm (frontend)                        |
| Containerization  | Docker / docker-compose                             |
| Testing           | pytest (backend), Vitest (frontend, Phase 8)        |

## Folder Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/            # FastAPI routers (HTTP layer only, no business logic)
│   │   ├── services/        # Business logic
│   │   ├── repositories/    # Data access (Postgres, Qdrant)
│   │   ├── models/           # ORM / domain models
│   │   ├── schemas/          # Pydantic request/response schemas
│   │   ├── core/              # Config, logging, cross-cutting concerns
│   │   ├── graph/              # LangGraph state, nodes, edges, graph assembly, checkpointer
│   │   ├── retrieval/          # BM25, hybrid (RRF) search, cross-encoder reranker, topic classifier
│   │   ├── embeddings/         # Local embedding generation (sentence-transformers)
│   │   ├── database/            # DB session/engine setup
│   │   ├── llm/                   # Groq client, prompt builder, GroqAnswerGenerator
│   │   ├── ingestion/             # HTML/PDF loaders, cleaning, chunking, source manifest
│   │   ├── prompts/              # Prompt templates (rag_system_prompt.txt)
│   │   └── utils/                 # Shared helpers
│   ├── migrations/            # Alembic migrations (async env.py)
│   ├── scripts/                # run_ingestion.py / run_indexing.py CLI entrypoints
│   ├── tests/
│   ├── alembic.ini
│   ├── pyproject.toml (uv)
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router routes (page.tsx is the chat page)
│   │   ├── components/        # UI components (shadcn/ui in components/ui, chat UI in components/chat)
│   │   ├── hooks/               # useSession, useChat
│   │   ├── services/             # API client (chatApi.ts, api.ts)
│   │   ├── types/                 # Shared TS types matching backend schemas
│   │   └── styles/                 # Global/shared styles
│   └── Dockerfile
├── docs/
└── docker-compose.yml
```

## Local Development

### Prerequisites
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 20+
- Docker Desktop

### Run everything with Docker

```bash
cp .env.example .env
docker compose up --build
```

- Frontend: http://localhost:3000
- Backend health check: http://localhost:8000/api/v1/health
- Qdrant dashboard: http://localhost:6333/dashboard
- Postgres: localhost:5433 (mapped to avoid clashing with other local Postgres instances)

### Run the backend without Docker

```bash
cd backend
cp .env.example .env
uv sync
uv run uvicorn app.main:app --reload
```

### Run the frontend without Docker

```bash
cd frontend
cp .env.example .env.local
npm install
npm run dev
```

## Database Migrations

Migrations run automatically on container start (`docker-entrypoint.sh` runs `alembic upgrade
head` before launching uvicorn). To manage them manually against a running Postgres:

```bash
cd backend
uv run alembic upgrade head                                  # apply all migrations
uv run alembic revision --autogenerate -m "add some_table"   # generate a new migration
```

## Document Ingestion

Fetches every source in `app/ingestion/sources.py` (a manifest of official, verified UIUC HTML
and PDF pages), cleans and chunks the text, and persists documents + chunks in PostgreSQL:

```bash
cd backend
uv run python -m scripts.run_ingestion
```

Re-running is cheap: each source's cleaned text is hashed, and unchanged sources are skipped
(no re-chunk, no DB write). Inspect what's been ingested via `GET /api/v1/documents` and
`GET /api/v1/documents/{id}`. Add a new source by appending a `SourceConfig` entry to the
manifest — no other code changes needed.

## Embeddings, Qdrant, and Hybrid Retrieval

Embeds every ingested chunk (local, CPU-only `BAAI/bge-small-en-v1.5` — no paid embedding API)
and upserts into Qdrant:

```bash
cd backend
uv run python -m scripts.run_indexing
```

Idempotent the same way ingestion is: a `documents.embedded_content_hash` column is compared
against `content_hash`, so re-running only embeds documents that actually changed. Query the
result with `GET /api/v1/retrieve?query=...&topic=...&student_type=...` — it fuses Qdrant
semantic search with an in-process BM25 index via Reciprocal Rank Fusion and returns each
result's per-ranker rank and fused score, for inspecting retrieval quality directly.

## Conversation Graph (LangGraph)

`app/graph/graph.py::build_graph()` assembles a 12-node LangGraph `StateGraph` with conditional
routing for intent detection, profile-aware clarification, hybrid retrieval, cross-encoder
reranking, and citation generation. State (`app/graph/state.py::GraphState`) is a typed
`TypedDict`; conversation history persists across turns via a Postgres-backed
`AsyncPostgresSaver` checkpointer (`app/graph/checkpointer.py`), keyed by `thread_id` (the
session ID) — not an in-memory `MemorySaver`, so it survives process restarts.

Generation (`app/graph/generation.py::AnswerGenerator`) is a Protocol; the graph doesn't care
which implementation sits behind it. Try the graph directly:

```python
from app.graph.graph import build_graph, turn_input, config_for
from app.graph.checkpointer import build_checkpointer
# ... construct GraphDependencies (see tests/test_graph.py for a full example)
async with build_checkpointer() as checkpointer:
    graph = build_graph(deps, checkpointer=checkpointer)
    result = await graph.ainvoke(turn_input(session_id, "..."), config=config_for(session_id))
```

Or via HTTP once a session exists (`POST /api/v1/sessions`):

```bash
curl -X POST localhost:8000/api/v1/chat \
  -H 'Content-Type: application/json' \
  -d '{"session_id": "<uuid>", "message": "How do I apply for OPT?"}'
```

## Groq Integration and Prompt Engineering

`app/api/dependencies.py::get_answer_generator()` picks the real `GroqAnswerGenerator`
(`app/llm/groq_answer_generator.py`) when `GROQ_API_KEY` is set, and falls back to Phase 5's
`ExtractiveAnswerGenerator` when it isn't — local dev and most tests work without a key; only
`POST /api/v1/chat` giving a real generated answer needs one.

- **Prompt** (`app/prompts/rag_system_prompt.txt`): instructs the model to answer only from the
  numbered context sections, cite inline with `[n]`, never ask for PII, and respond in a strict
  JSON envelope (`answer`, `grounded`, `citations_used`).
- **Groundedness self-report**: the model reports whether its own answer is actually supported
  by the cited context — the same pattern used in an earlier version of this project to catch a
  real "high confidence but the model doesn't actually know" failure mode. A parse failure (the
  model didn't return valid JSON) is treated as ungrounded rather than trusted.
- **Citation filtering**: `citation_generator` only cites the context sections the model's
  `citations_used` actually references (falls back to "cite everything it was given" only for
  generators, like the Phase 5 placeholder, that can't report which sections they used) — this
  is what "no hallucinated citations" means in practice here.
- **Not yet verified against a real Groq call** — set `GROQ_API_KEY` in `backend/.env` (never in
  `.env.example`) to enable it; 4 tests (`tests/llm/test_groq_client.py`,
  `tests/llm/test_groq_answer_generator_live.py`) are gated on a real key and skip otherwise.
  End-to-end smoke testing so far used the Phase 5 `ExtractiveAnswerGenerator` fallback, which
  always reports `grounded: true` whenever any chunk was retrieved (it can't judge relevance,
  only extract the top-ranked chunk verbatim) — occasionally citing content that doesn't
  actually answer the question. This is exactly the failure mode the real groundedness
  self-report exists to catch; expect noticeably better accuracy once a real key is set.

### A real retrieval bug this caught

Manual end-to-end testing surfaced a genuine bug, not just a Phase 5 quality gap: the
embedding-based `TopicClassifier` confidently (0.65) misclassified "How do I apply for OPT?" as
`admissions`, purely from "apply"/"application" overlapping with the admissions topic
description — and `retrieve` was passing that classification to Qdrant as a **hard filter**, so
a wrong classification returned zero results even though hybrid search with no topic filter
correctly ranked the real OPT page #1. Fixed by no longer using topic as a retrieval filter at
all (`student_type` still is, since it comes from the verified session profile, not a noisy
classifier guess) — topic classification now only drives the clarification decision, where a
wrong guess just means an occasional unnecessary clarifying question instead of a silent wrong
answer. Also tightened the admissions topic description to reduce future collisions, and added
`tests/test_graph.py::test_retrieval_is_not_broken_by_wrong_topic_classification` as a
regression test using a stub classifier that's always wrong, so retrieval correctness doesn't
depend on the embedding model's classification behavior staying the same.

## Frontend (Chat UI)

A Next.js (App Router) single-page chat interface at `frontend/src/app/page.tsx`, built directly
against the real `POST /api/v1/chat` and `POST /api/v1/sessions` endpoints:

- **Onboarding** (`components/chat/StudentTypeSelector.tsx`): asks student type via a
  *structured* picker (freshman/transfer/graduate/international/skip) before the first message,
  rather than relying on the backend's text-based clarification. This is a deliberate choice:
  the backend's clarification asks the question in natural language but has no way to parse a
  free-text answer back into `student_type` (that needs real NLU, not yet built) — a structured
  picker sidesteps that dead end for the common case entirely, while the backend's own
  clarification flow still fires correctly for genuinely ambiguous questions later in the
  conversation.
- **Conversation memory** is client-side (`hooks/useChat.ts`, localStorage keyed by
  `session_id`), not fetched from the backend checkpointer: the checkpointer stores message
  history but not per-message citations, so a naive history-fetch endpoint would lose citation
  data on page reload that client-side storage keeps intact.
- **Source panel** (`components/chat/SourcePanel.tsx`): a slide-over sheet per assistant message
  showing citation cards (title, department, topic, link to the official page) — not a single
  persistent side panel, so each answer's sources stay attached to that specific answer as the
  conversation grows.
- **Groundedness surfaced in the UI**: a message with `grounded: false` shows an inline "this
  answer may be incomplete" notice; a `needs_clarification: true` message shows a "Clarifying
  question" label instead of being presented as a normal answer.
- **Dark mode** via `next-themes` (`components/ThemeProvider.tsx`, `ThemeToggle.tsx`), system
  preference by default, manually toggleable, persisted.
- Browser-tested end-to-end with Playwright against both the dev server and the production
  Docker build (onboarding, suggested questions, a real chat round-trip, source panel, dark
  mode, mobile viewport, the clarification flow) — zero console errors across all of it. Answer
  *text quality* in those screenshots reflects the Phase 5 fallback generator (see Groq
  Integration above), not a frontend issue.

## Testing

```bash
cd backend && uv run pytest
```

Tests run against real PostgreSQL and Qdrant instances (no mocking the database or vector
store) — but a **dedicated test database**, never the dev database: the table-cleanup fixtures
between tests are destructive (`TRUNCATE ... CASCADE`), and once wiped the real ingested UIUC
corpus when tests and manual smoke-testing shared one database. Create it once per Postgres
instance (name is `<dev db>_test`, derived automatically by `Settings.test_database_url`):

```bash
docker exec uiuc_bot-postgres-1 psql -U illiniguide -d postgres -c "CREATE DATABASE illiniguide_test OWNER illiniguide;"
DATABASE_URL="postgresql+asyncpg://illiniguide:change-me@localhost:5433/illiniguide_test" uv run alembic upgrade head
```

Qdrant tests run against a separate `illiniguide_documents_test` collection, created and torn
down automatically per test.

## Environment Variables

See [.env.example](.env.example) (docker-compose), [backend/.env.example](backend/.env.example),
and [frontend/.env.example](frontend/.env.example). Never commit a real `.env` file — secrets
belong only in gitignored `.env` files, not the tracked `.env.example` templates.

## Privacy

This assistant never asks for or stores UIN, NetID, email, password, phone number, or any other
personally identifiable information. Personalization is limited to anonymous session context
(student type, semester, optional college/department).
