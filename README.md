# IlliniGuide AI

An AI-powered onboarding assistant for prospective, admitted, freshman, transfer, graduate,
and international students at the University of Illinois Urbana-Champaign (UIUC). Answers are
grounded exclusively in official, publicly available UIUC resources via Retrieval-Augmented
Generation, and the app never asks for personally identifiable information.

> **Status:** Phases 1-4 complete (architecture/Docker, backend database layer, document
> ingestion, embeddings + Qdrant + hybrid retrieval). Local CPU-only embeddings
> (BAAI/bge-small-en-v1.5) are generated for every chunk and upserted into Qdrant; queries are
> answered by fusing Qdrant semantic search with in-process BM25 keyword search via Reciprocal
> Rank Fusion, with topic/student-type metadata filtering. LangGraph orchestration, Groq
> generation, and the chat UI are next.

## Tech Stack

| Layer            | Choice                                              |
|-------------------|------------------------------------------------------|
| Frontend          | Next.js (App Router), TypeScript, TailwindCSS, shadcn/ui |
| Backend           | Python, FastAPI                                     |
| Orchestration     | LangGraph, LangChain (Phase 5+)                     |
| LLM               | Groq (Phase 6+)                                     |
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
│   │   ├── agents/            # LangGraph node implementations
│   │   ├── graph/              # LangGraph graph definition & state
│   │   ├── retrieval/          # BM25 + hybrid (RRF) search
│   │   ├── embeddings/         # Local embedding generation (sentence-transformers)
│   │   ├── database/            # DB session/engine setup
│   │   ├── ingestion/             # HTML/PDF loaders, cleaning, chunking, source manifest
│   │   ├── prompts/              # Prompt templates
│   │   └── utils/                 # Shared helpers
│   ├── migrations/            # Alembic migrations (async env.py)
│   ├── scripts/                # run_ingestion.py / run_indexing.py CLI entrypoints
│   ├── tests/
│   ├── alembic.ini
│   ├── pyproject.toml (uv)
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router routes
│   │   ├── components/        # UI components (shadcn/ui in components/ui)
│   │   ├── hooks/               # React hooks
│   │   ├── services/             # API client
│   │   ├── types/                 # Shared TS types
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
