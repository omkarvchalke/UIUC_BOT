# IlliniGuide AI

An AI-powered onboarding assistant for prospective, admitted, freshman, transfer, graduate,
and international students at the University of Illinois Urbana-Champaign (UIUC). Answers are
grounded exclusively in official, publicly available UIUC resources via Retrieval-Augmented
Generation, and the app never asks for personally identifiable information.

> **Status:** Phase 1 (project architecture, folder structure, environment setup, Docker) complete.
> The system currently exposes a backend health check and a frontend page that verifies
> connectivity to it. RAG, LangGraph orchestration, and the chat UI arrive in later phases.

## Tech Stack

| Layer            | Choice                                              |
|-------------------|------------------------------------------------------|
| Frontend          | Next.js (App Router), TypeScript, TailwindCSS, shadcn/ui |
| Backend           | Python, FastAPI                                     |
| Orchestration     | LangGraph, LangChain (Phase 5+)                     |
| LLM               | Groq (Phase 6+)                                     |
| Embeddings        | Local sentence-transformers (BAAI/bge-small-en-v1.5) (Phase 4+) |
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
│   │   ├── retrieval/          # Hybrid search, re-ranking
│   │   ├── embeddings/         # Local embedding generation
│   │   ├── database/            # DB session/engine setup
│   │   ├── prompts/              # Prompt templates
│   │   └── utils/                 # Shared helpers
│   ├── tests/
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

## Testing

```bash
cd backend && uv run pytest
```

## Environment Variables

See [.env.example](.env.example) (docker-compose), [backend/.env.example](backend/.env.example),
and [frontend/.env.example](frontend/.env.example). Never commit a real `.env` file — secrets
belong only in gitignored `.env` files, not the tracked `.env.example` templates.

## Privacy

This assistant never asks for or stores UIN, NetID, email, password, phone number, or any other
personally identifiable information. Personalization is limited to anonymous session context
(student type, semester, optional college/department).
