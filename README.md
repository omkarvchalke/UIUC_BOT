# IlliniAssist AI

An AI-powered onboarding assistant for prospective, admitted, freshman, transfer, graduate,
and international students at the University of Illinois Urbana-Champaign (UIUC). Answers are
grounded exclusively in official, publicly available UIUC resources via Retrieval-Augmented
Generation, and the app never asks for personally identifiable information.

**Live repo:** https://github.com/omkarvchalke/UIUC_BOT

> **Status:** Full RAG pipeline, LangGraph orchestration, hybrid retrieval, a live analytics
> dashboard, an automated RAG evaluation harness, and a polished Next.js chat UI — all
> implemented, tested, and verified against the real running app (not just unit tests). See
> [docs/production-readiness.md](docs/production-readiness.md) for the honest, evidence-based
> readiness assessment: 257/257 backend tests and 70/70 frontend tests pass, a live 20-question
> end-to-end run against the running app answered 20/20 with zero crashes/errors, and the report
> documents exactly which topics the corpus doesn't yet cover well rather than claiming the
> content is complete.

## Tech Stack

| Layer            | Choice                                              |
|-------------------|------------------------------------------------------|
| Frontend          | Next.js 16 (App Router), React 19, TypeScript, TailwindCSS 4, shadcn/ui (Base UI primitives) |
| Backend           | Python, FastAPI                                     |
| Orchestration     | LangGraph, LangChain-core                           |
| LLM               | Groq (`llama-4-scout-17b-16e-instruct`, JSON mode)  |
| Embeddings        | Local sentence-transformers (BAAI/bge-small-en-v1.5), CPU-only |
| Vector database   | Qdrant                                              |
| Relational database | PostgreSQL                                        |
| Package manager   | uv (backend), npm (frontend)                        |
| Containerization  | Docker / docker-compose                             |
| Testing           | pytest + pytest-cov (backend), Vitest + React Testing Library (frontend), Playwright (manual live E2E) |
| CI                | GitHub Actions (`.github/workflows/ci.yml`)         |
| Rate limiting     | slowapi (per-IP, `/chat` and `/retrieve`)           |

## Folder Structure

```
.
├── backend/
│   ├── app/
│   │   ├── api/              # FastAPI routers: chat, sessions, retrieve, feedback, analytics, checklist
│   │   ├── services/          # Business logic (chat, analytics, ingestion, indexing, feedback, session)
│   │   ├── repositories/      # Data access (Postgres, Qdrant) -- includes chat_turn_event_repository
│   │   ├── models/             # ORM / domain models -- includes chat_turn_event.py (analytics)
│   │   ├── schemas/             # Pydantic request/response schemas -- includes analytics.py
│   │   ├── core/                 # Config, logging, rate limiting, cross-cutting concerns
│   │   ├── graph/                  # LangGraph state, nodes, edges, graph assembly, checkpointer
│   │   ├── retrieval/               # BM25, hybrid (RRF) search, cross-encoder reranker, topic classifier
│   │   ├── embeddings/                # Local embedding generation (sentence-transformers)
│   │   ├── database/                    # DB session/engine setup
│   │   ├── llm/                           # Groq client, prompt builder, GroqAnswerGenerator
│   │   ├── ingestion/                       # HTML/PDF loaders, cleaning, semantic chunking, source manifest
│   │   │   ├── domains/                       # 14 Knowledge Domain modules (source URLs + crawl seeds)
│   │   │   └── metadata/                        # audience/document_type/keyword extraction
│   │   ├── prompts/                              # Prompt templates (rag_system_prompt.txt)
│   │   ├── evaluation/                             # RAG eval harness: golden set, retrieval metrics,
│   │   │                                             faithfulness (heuristic + optional LLM judge), runners
│   │   └── utils/                                    # Shared helpers
│   ├── migrations/            # Alembic migrations (async env.py)
│   ├── scripts/                # run_ingestion / run_indexing / run_crawl / discover_sources /
│   │                              eval_answers / eval_rag / load_test / backfill_semantic_chunks
│   ├── tests/
│   ├── alembic.ini
│   ├── pyproject.toml (uv)
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/               # Next.js App Router routes: page.tsx (chat), analytics/page.tsx
│   │   ├── components/         # UI components (shadcn/ui in components/ui, chat UI in components/chat)
│   │   │                         (co-located *.test.tsx next to the components they cover)
│   │   ├── hooks/                # useSession, useChat, useDebugMode (co-located *.test.ts)
│   │   ├── services/               # API client (chatApi.ts, analyticsApi.ts, api.ts)
│   │   ├── types/                    # Shared TS types matching backend schemas
│   │   └── lib/                        # cn() and other shared utilities
│   ├── vitest.config.ts
│   ├── vitest.setup.ts        # jsdom polyfills (matchMedia, scrollIntoView)
│   └── Dockerfile
├── .github/workflows/ci.yml   # Backend + frontend jobs: lint, typecheck, test, build
├── docs/
│   └── production-readiness.md  # Evidence-based readiness report (test results, live E2E findings, gaps)
├── docker-compose.yml          # Base: Postgres, Qdrant, backend, frontend
├── docker-compose.override.yml # Auto-loaded for local dev: publishes DB/vector-store ports
└── docker-compose.prod.yml     # Explicit -f overlay: resource limits, log rotation, no DB ports
```

## Quick Start

### Prerequisites
- [uv](https://docs.astral.sh/uv/) (Python package manager)
- Node.js 20+
- Docker Desktop
- A [Groq API key](https://console.groq.com/keys) (free tier works; see [Groq Integration](#groq-integration-and-prompt-engineering) for why it's needed and what runs without one)

### Run everything with Docker (recommended)

```bash
git clone https://github.com/omkarvchalke/UIUC_BOT.git
cd UIUC_BOT
cp .env.example .env
cp backend/.env.example backend/.env      # then fill in GROQ_API_KEY
cp frontend/.env.example frontend/.env.local
docker compose up --build
```

- Frontend (chat UI): http://localhost:3000
- Analytics dashboard: http://localhost:3000/analytics
- Backend health check: http://localhost:8000/api/v1/health
- Qdrant dashboard: http://localhost:6333/dashboard
- Postgres: localhost:5433 (mapped to avoid clashing with other local Postgres instances)

Migrations run automatically on container start (see [Database Migrations](#database-migrations)),
but the corpus does **not** ingest itself — run the ingestion + indexing steps below once the
containers are up, or the chat will have nothing to retrieve from.

```bash
cd backend
uv run python -m scripts.run_crawl      # crawl + auto-ingest UIUC pages (few minutes)
uv run python -m scripts.run_indexing   # embed what was ingested into Qdrant
```

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
and PDF pages, organized across 14 Knowledge Domain modules), cleans the text, splits it via
heading-aware **semantic chunking** (not fixed-size — see below), and persists documents + chunks
in PostgreSQL:

```bash
cd backend
uv run python -m scripts.run_ingestion
```

Re-running is cheap: each source's cleaned text is hashed, and unchanged sources are skipped
(no re-chunk, no DB write). Inspect what's been ingested via `GET /api/v1/documents` and
`GET /api/v1/documents/{id}`. Add a new source by appending a `SourceConfig`/`CrawlSeed` entry to
the relevant domain module in `app/ingestion/domains/` — no other code changes needed.

### Semantic chunking

`app/ingestion/semantic_chunker.py::SemanticChunker` splits each document along its actual HTML
heading structure (`app/ingestion/html_loader.py::_extract_sections`) instead of a fixed
character window — a chunk boundary lands at a real topic boundary (a new `<h2>`/`<h3>`), not
mid-paragraph. Small sections are merged forward (or backward, for a too-small trailing section)
so a chunk never ends up as a lone one-line heading with no content. Each chunk carries its
`subtopic` (the joined heading path, e.g. `"Applying > Freshman > Required Documents"`), surfaced
in the API response and in the frontend's debug mode.

### Content coverage

38 sources/crawl seeds across 14 Knowledge Domains, expanding via the crawler (below) into
**1,301 indexed documents** as of the last real ingestion run (`GET /api/v1/analytics/summary` —
also visible live on the `/analytics` dashboard). A live 20-question end-to-end test this session
found real, honest coverage gaps rather than claiming completeness — see
[docs/production-readiness.md](docs/production-readiness.md) for exactly which topics (OPT, CPT,
career services, academic advising, student orgs, out-of-state tuition) currently return zero
citations. The app's honesty guardrail (the `grounded` self-report, below) correctly says "I don't
have enough information" for these rather than fabricating an answer — the gap is in content
coverage, not in the app's willingness to admit what it doesn't know.

Two categories of gap found and fixed during earlier content-quality passes, now guarded by
`tests/ingestion/test_sources.py` so they can't silently regress:

- **A real retrieval bug, not just missing content**: `student_type` is a hard filter in
  `VectorRepository._build_filter` (`app/repositories/vector_repository.py`) — a document scoped
  to one `StudentType` never surfaces for a different one, and only a document with
  `student_types=()` (applies to everyone) is exempt. The two original admissions sources were
  both `FRESHMAN`-only, so a transfer or graduate student asking *any* admissions question got
  zero results — confirmed live via `GET /api/v1/retrieve?student_type=transfer`. Fixed by adding
  transfer, graduate, and international-specific admissions sources.
  `test_every_student_type_has_admissions_coverage` asserts every `StudentType` has at least one
  applicable admissions source.
- **"Gateway" pages producing vague answers**: the admissions site structures each application
  type as a landing page that's mostly navigation links, with the actual step-by-step process
  living on separate subpages the original manifest didn't include. Fixed by adding the dedicated
  process/requirements subpages, each verified beforehand to contain real numbered steps, not
  another nav page.

**A known, accepted limitation**: the library hours page renders its actual hours table
client-side via JavaScript — the static HTML the ingestion pipeline fetches contains only
navigation links, never the hours themselves. Not fixable by picking a different URL; would need
a JS-rendering fetch step, out of scope. The system degrades correctly here: `grounded: false`
for hours questions instead of confidently inventing an answer.

### Automated discovery crawler

Hand-curating individual URLs doesn't scale and goes stale as UIUC restructures its sites.
`app/ingestion/crawl_seeds.py` lists the approved UIUC/UI-System domains (one `CrawlSeed` each, no
`path_prefixes`) and `Crawler` (`app/ingestion/crawler.py`) does bounded BFS crawls of each,
`max_depth=4` / `max_pages=60` per seed by default — this is what actually produces the 1,301
indexed documents from 38 starting seeds:

```bash
cd backend
uv run python -m scripts.run_crawl      # crawl + auto-ingest new pages from all seeds
uv run python -m scripts.run_indexing   # embed whatever run_crawl added
uv run python -m scripts.eval_answers   # confirm answer quality didn't regress
```

Per-page quality control happens inside `Crawler`, not by curating which URLs to visit:

- **robots.txt** compliance and a politeness delay between requests.
- **Login-wall detection**: checks the *post-redirect* URL against known SSO/login markers.
- **Non-HTML rejection by Content-Type**, not file extension.
- **Soft-404 and thinness filtering**, same as manual sources.
- **Duplicate-content detection** via a SHA-256 hash of extracted text, tracked across the whole
  crawl.

`scripts/discover_sources.py --full` runs the same seeds at a much higher, unbounded budget with
no ingestion, and writes every page found — including rejected ones and the reason — to a CSV,
for reviewing crawl coverage before trusting a candidate new domain to auto-ingest.

## Embeddings, Qdrant, and Hybrid Retrieval

Embeds every ingested chunk (local, CPU-only `BAAI/bge-small-en-v1.5` — no paid embedding API)
and upserts into Qdrant:

```bash
cd backend
uv run python -m scripts.run_indexing
```

Idempotent the same way ingestion is: a `documents.embedded_content_hash` column is compared
against `content_hash`, so re-running only embeds documents that actually changed. Query the
result with `GET /api/v1/retrieve?query=...&topic=...&student_type=...&audience=...&document_type=...`
— it fuses Qdrant semantic search with an in-process BM25 index via Reciprocal Rank Fusion and
returns each result's per-ranker rank, fused score, subtopic, and rerank score, for inspecting
retrieval quality directly (also surfaced in the frontend's debug mode).

## Conversation Graph (LangGraph)

`app/graph/graph.py::build_graph()` assembles a LangGraph `StateGraph` with conditional routing
for intent detection, profile-aware clarification, ambiguous-topic clarification, hybrid
retrieval, cross-encoder reranking, and citation generation. State (`app/graph/state.py::GraphState`)
is a typed `TypedDict`; conversation history persists across turns via a Postgres-backed
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

Every turn also persists a `chat_turn_events` row (intent, topic, `needs_clarification`,
`grounded`, citation count, latency) — this is what powers the `/analytics` dashboard, recorded
fire-and-forget so a logging failure never breaks the chat response itself.

## Groq Integration and Prompt Engineering

`app/api/dependencies.py::get_answer_generator()` picks the real `GroqAnswerGenerator`
(`app/llm/groq_answer_generator.py`) when `GROQ_API_KEY` is set, and falls back to an
`ExtractiveAnswerGenerator` when it isn't — local dev and most tests work without a key; only
`POST /api/v1/chat` giving a real generated answer needs one.

- **Model choice** (`Settings.groq_model`, `backend/.env` `GROQ_MODEL`): `llama-4-scout-17b-16e-instruct`,
  not the more obvious `llama-3.3-70b-versatile` or `llama-3.1-8b-instant`. Picked by comparing
  real per-minute rate-limit headers across candidates on this account, not published numbers --
  what actually matters for RAG is *tokens*-per-minute, since our prompts carry several retrieved
  chunks of context. `llama-3.1-8b-instant` looked like the obvious "more quota" choice from its
  14,400 req/min limit, but its 6,000 TPM is actually *lower* than `llama-3.3-70b-versatile`'s
  12,000, and it hit real `429`s plus 18-21s SDK retry backoffs running the golden-set eval
  against it. Llama 4 Scout's 30,000 TPM (2.5x `llama-3.3-70b-versatile`) has real headroom for
  context-heavy prompts. **Known operational risk**: this account has hit its daily token quota
  repeatedly during development — see [docs/production-readiness.md](docs/production-readiness.md)
  for why a paid tier matters before any real traffic volume.
- **Prompt** (`app/prompts/rag_system_prompt.txt`): instructs the model to answer only from the
  numbered context sections, cite inline with `[n]`, never ask for PII, and respond in a strict
  JSON envelope (`answer`, `grounded`, `citations_used`). The instruction is to be *thorough* --
  walk through every relevant step/requirement/option in the cited context rather than
  compressing a multi-part answer into one terse sentence.
- **Groundedness self-report**: the model reports whether its own answer is actually supported
  by the cited context — this is what catches a "high confidence but the model doesn't actually
  know" failure mode. A parse failure (invalid JSON) is treated as ungrounded rather than trusted.
  Surfaced directly in the UI (an inline "this answer may be incomplete" notice) and aggregated
  live on `/analytics` as a grounded rate.
- **Citation filtering**: `citation_generator` only cites the context sections the model's
  `citations_used` actually references — this is what "no hallucinated citations" means in
  practice here.
- **Verified against a real Groq call**: set `GROQ_API_KEY` in `backend/.env` (never in
  `.env.example`) to enable it; a handful of tests (`tests/llm/test_groq_client.py`,
  `tests/llm/test_groq_answer_generator_live.py`) are gated on a real key and skip themselves
  otherwise.

### A real retrieval bug this caught

Manual end-to-end testing surfaced a genuine bug: the embedding-based `TopicClassifier`
confidently misclassified "How do I apply for OPT?" as `admissions`, and `retrieve` was passing
that classification to Qdrant as a **hard filter**, so a wrong classification returned zero
results even though hybrid search with no topic filter correctly ranked the real OPT page #1.
Fixed by no longer using topic as a retrieval filter at all (`student_type` still is, since it
comes from the verified session profile, not a noisy classifier guess) — topic classification now
only drives the clarification decision. `tests/test_graph.py::test_retrieval_is_not_broken_by_wrong_topic_classification`
regression-tests this with a stub classifier that's always wrong.

## Analytics Dashboard

`GET /api/v1/analytics/summary?days=N` (default 30, max 365) aggregates `chat_turn_events` +
`feedback` + `conversation_sessions` into: total conversations/questions, grounded rate,
clarification rate, topic distribution, feedback helpful/not-helpful ratio, and latency
percentiles (`avg`/`p50`/`p95` via Postgres `percentile_cont`). Surfaced live at
`frontend/src/app/analytics/page.tsx` (`/analytics` route) with a 7/30/90-day preset selector and
a recharts bar chart for topic distribution, styled to match the rest of the app's design system.

```bash
curl "http://localhost:8000/api/v1/analytics/summary?days=30"
```

## RAG Evaluation Harness

`pytest`/CI verify the app doesn't crash or regress its control flow; they don't verify answers
are actually good or well-retrieved, since that needs a real Groq call and the real ingested
corpus. Two complementary tools cover that gap:

**Answer quality** (`app/evaluation/golden_set.py` — 19 hand-curated cases across every student
type plus edge cases): checks *properties* of the answer (grounded, cited, no hedging) rather than
exact wording, tolerating Groq's normal phrasing variance while catching real failure modes.

**Full RAG report** (`scripts/eval_rag.py`): answer-quality + retrieval metrics
(Precision@5/Recall@5/MRR/Context Precision against `expected_relevant_urls` in the golden set) +
faithfulness/groundedness (a zero-cost lexical-overlap heuristic by default, an opt-in LLM-judge
for occasional higher-fidelity runs) + latency percentiles, all from one run against the same
golden set:

```bash
cd backend
uv run python -m scripts.eval_answers            # answer-quality only, faster
uv run python -m scripts.eval_rag                 # full report, heuristic faithfulness
uv run python -m scripts.eval_rag --llm-judge      # full report, spends Groq quota on the judge
```

Both require a running backend and a real `GROQ_API_KEY`; neither runs in `pytest`/CI (expensive,
non-deterministic). `tests/evaluation/` covers the parts that don't need a network call: the
metric math (hand-computed small examples), the golden set's own well-formedness, and the
faithfulness heuristic's sentence-scoring logic.

## Feedback

`POST /api/v1/feedback` records a thumbs up/down (plus an optional comment) against a specific
answer:

```bash
curl -X POST localhost:8000/api/v1/feedback \
  -H 'Content-Type: application/json' \
  -d '{"session_id": "<uuid>", "message_id": "<client-generated id>", "question": "...", "answer": "...", "rating": "helpful"}'
```

Feedback rows denormalize the question and answer text rather than referencing a persisted
message id: conversation turns live in the LangGraph checkpointer, not a separate queryable
messages table. `session_id` *is* validated against `conversation_sessions` (404 on an unknown
session) before the row is written.

## Frontend (Chat UI)

A Next.js (App Router) chat interface built directly against the real backend endpoints, styled
with a "neo-brutalist" design system (`brutal-border`/`brutal-shadow` Tailwind utilities in
`globals.css`) — a bold ink border plus a hard offset shadow on interactive surfaces, deliberately
**not** applied to chat message bubbles (which stay plain for readability in a scrolling
conversation).

- **Onboarding** (`components/chat/StudentTypeSelector.tsx`): a structured picker
  (freshman/transfer/graduate/international/skip) before the first message, rather than relying
  on the backend's text-based clarification, since there's no NLU yet to parse a free-text answer
  back into `student_type`.
- **Markdown-rendered answers** (`react-markdown` + `remark-gfm`): lists, bold, links, and tables
  in assistant answers render properly instead of showing raw `**`/`-`/`[]()` syntax; links open
  safely in a new tab (`rel="noopener noreferrer"`).
- **Copy-to-clipboard**: a copy button on every answer that also highlights the copied text in the
  page (native browser selection) as visual confirmation of exactly what was copied.
- **No lost messages on failure**: if sending fails, the typed text is restored to the composer
  instead of being silently discarded — the previous behavior actually lost your question on a
  network hiccup.
- **Composer auto-focus**, skipped on touch devices specifically so it doesn't pop the mobile
  keyboard unexpectedly after every answer.
- **Confirmation before wiping a conversation** ("New conversation" button), only when there's
  actually something to lose.
- **Accessibility**: an `aria-live` region announces a plain-text excerpt of each new answer for
  screen readers (silent while a request is in flight, silent on initial page load so existing
  history doesn't spuriously announce); a "still thinking" hint appears after 5s on a slow answer
  so a long wait doesn't read as "stuck."
- **Retry on session-start failure**: remembers the last-attempted student type and offers a
  retry button instead of requiring a full page reload.
- **Conversation memory** is client-side (`hooks/useChat.ts`, localStorage keyed by
  `session_id`), not fetched from the backend checkpointer, since the checkpointer stores message
  history but not per-message citations.
- **Source panel** (`components/chat/SourcePanel.tsx`): a slide-over sheet per assistant message
  with citation cards (title, department, topic, link to the official page).
- **Groundedness surfaced in the UI**: `grounded: false` shows an inline "this answer may be
  incomplete" notice; `needs_clarification: true` shows a "Clarifying question" label.
- **Debug mode** (`hooks/useDebugMode.ts`, toggled via the header bug icon, persisted): shows
  topic/classification-confidence per answer and subtopic/fused-score/rerank-score per citation.
- **Dark mode** via `next-themes`, system preference by default, manually toggleable, persisted.
- **Feedback** (`components/chat/FeedbackButtons.tsx`): thumbs up/down under each assistant
  answer, optimistic (updates immediately, reverts only on a real failure).
- **Responsive**: verified with zero horizontal overflow across 320px–1440px viewports (phone
  through desktop), including the source-citation sheet and confirmation dialogs.
- Browser-tested end-to-end with Playwright against the real running app (not mocks) — onboarding,
  suggested questions, a real multi-turn chat conversation, source panel, dark mode, mobile
  viewport, the clarification flow, and a 20-question live soak test — zero console errors,
  zero failed requests, zero crashes across all of it.

## Testing

```bash
cd backend && uv run pytest      # runs with coverage by default (see pyproject.toml addopts)
```

Tests run against real PostgreSQL and Qdrant instances (no mocking the database or vector
store) — but a **dedicated test database**, never the dev database: the table-cleanup fixtures
between tests are destructive (`TRUNCATE ... CASCADE`). Create it once per Postgres instance
(name is `<dev db>_test`, derived automatically by `Settings.test_database_url`):

```bash
docker exec uiuc_bot-postgres-1 psql -U illiniguide -d postgres -c "CREATE DATABASE illiniguide_test OWNER illiniguide;"
DATABASE_URL="postgresql+asyncpg://illiniguide:change-me@localhost:5433/illiniguide_test" uv run alembic upgrade head
```

Qdrant tests run against a separate `illiniguide_documents_test` collection, created and torn
down automatically per test. **257/257 tests pass, 88% line coverage.** The handful of tests
gated on a real Groq call skip themselves when `GROQ_API_KEY` isn't set, so the suite (and CI)
stays green either way.

```bash
cd frontend && npm run test      # Vitest + React Testing Library, jsdom environment
```

**70/70 tests pass.** Covers the stateful hooks (`useSession`, `useChat`, `useDebugMode` —
localStorage persistence, hydration timing, error handling, retry logic) and components with real
conditional rendering logic (`StudentTypeSelector`, `MessageBubble`'s markdown/copy/groundedness/
clarification behavior, `ChatInput`'s validation and focus behavior, `ChatWindow`'s slow-answer
hint and aria-live announcements) — not the purely presentational shadcn primitives.

`vitest.setup.ts` polyfills `window.matchMedia` and `Element.prototype.scrollIntoView`, since
jsdom implements neither and several components now depend on both.

### CI

`.github/workflows/ci.yml` runs on every push/PR: a `backend` job (real Postgres + Qdrant service
containers, `ruff check`, `mypy`, `pytest`) and a `frontend` job (`eslint`, `tsc --noEmit`,
`vitest run`, `next build`) — the same commands you'd run locally, not a separate CI-only path.

## Performance

- **Rate limiting** (`app/core/rate_limit.py`, slowapi): `/chat` (20/min per IP) and `/retrieve`
  (30/min) are throttled — `/chat` calls a paid Groq API per request and `/retrieve` runs
  embedding + cross-encoder inference.
- **Model loading**: the embedding model and cross-encoder reranker are loaded once per process
  (`@lru_cache`-wrapped singletons), not per-request.
- **DB connection pooling**: `Settings.db_pool_size` (default 5) and `Settings.db_max_overflow`
  (default 10) are explicit, configurable settings.
- **Live latency** (from the real analytics dashboard, real traffic): avg ~3.7s, p50 ~2.6s, p95
  ~10.3s for a full `/chat` round trip (profile check, retrieval, reranking, Groq generation).

### Load testing

```bash
cd backend && uv run python -m scripts.load_test          # full run, needs a real GROQ_API_KEY
uv run python -m scripts.load_test --skip-chat              # skip the Groq-backed /chat benchmark
```

Not part of pytest/CI — needs a live backend and a real ingested corpus. Measures a sequential
per-endpoint latency profile (mean/p50/p95/p99) and a genuine concurrent burst
(`asyncio.gather`, not a loop) against `/retrieve`'s rate limiter.

## Deployment

```bash
cp .env.example .env   # fill in FRONTEND_PUBLIC_URL and BACKEND_PUBLIC_URL too
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

`docker-compose.prod.yml` is an explicit overlay (only applied when named with `-f`), so it does
**not** stack with `docker-compose.override.yml` the way plain `docker compose up` does for local
dev. Relative to the base file, it:

- Doesn't publish Postgres/Qdrant ports to the host.
- Sets CPU/memory limits per service (`deploy.resources.limits`).
- Caps container log file size (`json-file`, 10MB × 3 files).
- Sets `ENVIRONMENT=production` and a real `CORS_ORIGINS` instead of `localhost`.

This assumes a single host behind a reverse proxy (nginx, Caddy, Traefik) that terminates TLS and
forwards to the `backend`/`frontend` containers' published ports. Both Dockerfiles declare a
`HEALTHCHECK` (backend: `GET /api/v1/health`; frontend: `GET /`). Postgres data lives in the named
`postgres_data` volume (survives container recreation) — back it up with `pg_dump` or a volume
snapshot before any migration that isn't purely additive.

**Before deploying for real traffic**, read [docs/production-readiness.md](docs/production-readiness.md)
— it lists concrete, evidence-based gaps (content coverage for specific topics, the Groq quota
risk, two topic misclassifications) rather than just "it works on my machine."

### A real Docker networking bug this caught

Adding the frontend `HEALTHCHECK` surfaced a real bug: Docker sets the `HOSTNAME` env var to the
container ID automatically, and Next.js's standalone `server.js` binds to `process.env.HOSTNAME`
when it's set — so the server was listening only on the container's internal Docker-network IP,
never on `127.0.0.1` or `0.0.0.0`. Fixed with `ENV HOSTNAME=0.0.0.0` in `frontend/Dockerfile`,
forcing the standalone server to bind all interfaces.

## Environment Variables

See [.env.example](.env.example) (docker-compose), [backend/.env.example](backend/.env.example),
and [frontend/.env.example](frontend/.env.example). Never commit a real `.env` file — secrets
belong only in gitignored `.env` files, not the tracked `.env.example` templates.

## Privacy

This assistant never asks for or stores UIN, NetID, email, password, phone number, or any other
personally identifiable information. Personalization is limited to anonymous session context
(student type, semester, optional college/department).
