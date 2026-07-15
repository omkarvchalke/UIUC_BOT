# IlliniGuide AI

An AI-powered onboarding assistant for prospective, admitted, freshman, transfer, graduate,
and international students at the University of Illinois Urbana-Champaign (UIUC). Answers are
grounded exclusively in official, publicly available UIUC resources via Retrieval-Augmented
Generation, and the app never asks for personally identifiable information.

> **Status:** Phases 1-8 complete (architecture/Docker, backend database layer, document
> ingestion, embeddings + Qdrant + hybrid retrieval, LangGraph orchestration, Groq generation,
> Next.js chat UI, testing/performance/deployment). `POST /api/v1/chat` runs the full graph —
> profile checks, intent detection, topic classification, hybrid retrieval, cross-encoder
> reranking, real Groq-generated answers with self-reported groundedness, and citations built
> only from sections the model actually cited. The chat UI (onboarding, suggested questions,
> source panel, dark mode) is live and browser-tested end-to-end against the real backend.
> **Verified against a real Groq API key** — synthesized prose with correct inline citations, and
> the groundedness self-report correctly flags answers the retrieved context doesn't actually
> support (see Groq Integration below). Backend tests run with coverage (~93%), the frontend has a
> real Vitest/RTL suite, CI runs both on every push, and there's a production Docker Compose
> overlay with per-request rate limiting, resource limits, and log rotation (see Testing and
> Deployment below). Content corpus expanded from 19 to 33 sources after two content-quality
> passes — one found and fixed a real gap where transfer/graduate/international students got zero
> admissions results because the only admissions sources were freshman-scoped, plus coverage for
> three previously-sourceless topics; the other replaced "gateway" admissions pages (mostly nav
> links) with the actual step-by-step process pages after live answers came back vague instead of
> wrong (see Content coverage below).

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
| Testing           | pytest + pytest-cov (backend), Vitest + React Testing Library (frontend) |
| CI                | GitHub Actions (`.github/workflows/ci.yml`)         |
| Rate limiting     | slowapi (per-IP, `/chat` and `/retrieve`)           |

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
│   │   ├── evaluation/           # Golden-set answer-quality eval (cases + runner)
│   │   └── utils/                 # Shared helpers
│   ├── migrations/            # Alembic migrations (async env.py)
│   ├── scripts/                # run_ingestion.py / run_indexing.py / run_crawl.py /
│   │                              discover_sources.py / eval_answers.py / load_test.py entrypoints
│   ├── tests/
│   ├── alembic.ini
│   ├── pyproject.toml (uv)
│   └── Dockerfile
├── frontend/
│   ├── src/
│   │   ├── app/              # Next.js App Router routes (page.tsx is the chat page)
│   │   ├── components/        # UI components (shadcn/ui in components/ui, chat UI in components/chat)
│   │   │                        (co-located *.test.tsx next to the components they cover)
│   │   ├── hooks/               # useSession, useChat (co-located *.test.ts)
│   │   ├── services/             # API client (chatApi.ts, api.ts)
│   │   ├── types/                 # Shared TS types matching backend schemas
│   │   └── styles/                 # Global/shared styles
│   ├── vitest.config.ts
│   └── Dockerfile
├── .github/workflows/ci.yml   # Backend + frontend jobs: lint, typecheck, test, build
├── docs/
├── docker-compose.yml          # Base: Postgres, Qdrant, backend, frontend
├── docker-compose.override.yml # Auto-loaded for local dev: publishes DB/vector-store ports
└── docker-compose.prod.yml     # Explicit -f overlay: resource limits, log rotation, no DB ports
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

### Content coverage

33 sources across 20 topics (up from an initial 19). Several categories of gap surfaced during
content-quality passes; two are now covered by `tests/ingestion/test_sources.py`:

- **A real retrieval bug, not just missing content**: `student_type` is a hard filter in
  `VectorRepository._build_filter` (`app/repositories/vector_repository.py`) — a document scoped
  to one `StudentType` never surfaces for a different one, and only a document with
  `student_types=()` (applies to everyone) is exempt. The two original admissions sources were
  both `FRESHMAN`-only, so a transfer or graduate student asking *any* admissions question got
  zero results — confirmed live via `GET /api/v1/retrieve?student_type=transfer`. Fixed by adding
  transfer, graduate, and international-specific admissions sources.
  `test_every_student_type_has_admissions_coverage` asserts every `StudentType` has at least one
  applicable admissions source, so this can't silently regress as sources are added or reworded.
- **Uncovered topics**: `REGISTRATION`, `COURSE_REGISTRATION`, and
  `INTERNATIONAL_STUDENT_SERVICES` had zero sources at all — retrieval for those topics would
  always come back empty no matter how good the retriever is, and nothing about the retrieval
  code itself would ever flag it. `test_every_topic_has_at_least_one_source` guards this.
- **"Gateway" pages producing vague answers**: the admissions site structures each application
  type as a landing page that's mostly navigation links (`/apply/freshman`, `/apply/transfer`,
  `grad.illinois.edu/admissions/application-instructions`), with the actual step-by-step process
  living on separate subpages the original manifest didn't include. Retrieval was surfacing
  nav-menu text as the top-ranked chunks for "how do I apply" questions, so the model could only
  answer with "follow the process on the website" instead of real steps — grounded, but
  unhelpfully vague, not a hallucination. Confirmed by inspecting the actual chunks
  `GET /api/v1/retrieve` returned. Fixed by adding the dedicated process/requirements subpages
  (`.../Apply/Freshman/process`, `.../apply/freshman/requirements`, `.../apply/transfer/process`,
  `.../application-instructions/completing-your-graduate-application`) — each verified via
  WebFetch beforehand to contain real numbered steps, not another nav page, before being added to
  the manifest. There's no automated regression test for this category (thin vs. substantive
  content isn't a property `test_sources.py` can check without fetching every URL); it was found
  by spot-checking real answers.

**A known, accepted limitation**: the library hours page (`library.illinois.edu/library-hours/`)
renders its actual hours table client-side via JavaScript — the static HTML the ingestion
pipeline fetches contains only navigation links, never the hours themselves (confirmed by
inspecting the scraped chunks directly, and by checking an alternate library page, which has the
same issue). This isn't fixable by picking a different URL; it would need a JS-rendering fetch
step, which is out of scope. The system already degrades correctly here rather than silently:
the groundedness self-report (see Groq Integration below) reports `grounded: false` for hours
questions instead of confidently inventing an answer.

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
  JSON envelope (`answer`, `grounded`, `citations_used`). The instruction is to be *thorough* --
  walk through every relevant step/requirement/option in the cited context rather than
  compressing a multi-part answer into one terse sentence -- not concise; a student asking
  instead of reading the source page wants the full picture, not a summary that still requires
  clicking through. Paired with raising the reranker's `top_k` from 5 to 8
  (`app/graph/nodes.py::make_reranker_node`) so the model actually has enough retrieved material
  to be thorough with, rather than being told to elaborate on 5 short chunks.
- **Groundedness self-report**: the model reports whether its own answer is actually supported
  by the cited context — the same pattern used in an earlier version of this project to catch a
  real "high confidence but the model doesn't actually know" failure mode. A parse failure (the
  model didn't return valid JSON) is treated as ungrounded rather than trusted.
- **Citation filtering**: `citation_generator` only cites the context sections the model's
  `citations_used` actually references (falls back to "cite everything it was given" only for
  generators, like the Phase 5 placeholder, that can't report which sections they used) — this
  is what "no hallucinated citations" means in practice here.
- **Verified against a real Groq call**: set `GROQ_API_KEY` in `backend/.env` (never in
  `.env.example`) to enable it; 4 tests (`tests/llm/test_groq_client.py`,
  `tests/llm/test_groq_answer_generator_live.py`) are gated on a real key and skip themselves
  otherwise. Live end-to-end testing confirmed real synthesized prose with correct `[1][2][3]`
  inline citations (vs. the Phase 5 `ExtractiveAnswerGenerator` fallback's verbatim chunk text,
  which always reports `grounded: true` whenever any chunk was retrieved since it can't judge
  relevance) — and the groundedness self-report correctly caught a real case where the retrieved
  chunk didn't actually answer the question (an OPT application question, where the top match
  only mentioned OPT in passing), returning `grounded: false` instead of a confident wrong answer.

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
cd backend && uv run pytest      # runs with coverage by default (see pyproject.toml addopts)
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
down automatically per test. `pytest-cov` is configured in `pyproject.toml`
(`[tool.coverage.*]`) and reports branch coverage; current backend coverage is ~93%. The 4 tests
gated on a real Groq call (`tests/llm/test_groq_client.py`,
`tests/llm/test_groq_answer_generator_live.py`) skip themselves when `GROQ_API_KEY` isn't set,
so the suite (and CI) stays green either way.

```bash
cd frontend && npm run test      # Vitest + React Testing Library, jsdom environment
```

Frontend tests cover the two stateful hooks (`useSession`, `useChat` — localStorage
persistence, hydration timing, error handling) and the components with real conditional
rendering logic (`StudentTypeSelector`, `MessageBubble`'s groundedness/clarification
indicators, `ChatInput`'s validation) — not the purely presentational shadcn primitives, which
would just be re-testing the library.

### CI

`.github/workflows/ci.yml` runs on every push/PR: a `backend` job (real Postgres + Qdrant service
containers, `ruff check`, `mypy`, `pytest`) and a `frontend` job (`eslint`, `tsc --noEmit`,
`vitest run`, `next build`) — the same commands you'd run locally, not a separate CI-only path.

### Golden-set answer-quality eval

`pytest` (and CI) verify the app doesn't *crash* or regress its control flow; they don't verify
answers are actually good, since that needs a real Groq call against the real ingested corpus,
which is expensive and non-deterministic to run on every push. `app/evaluation/golden_set.py` is
a separate, small suite of real questions for that gap — 19 cases across every student type plus
edge cases (greeting, an ambiguous question with no profile set, an off-topic question), each
checking *properties* of the answer (grounded, cited, no hedging) rather than exact wording, so
it tolerates Groq's normal phrasing variance while still catching the failure modes that have
actually happened in this project: a student-type filter scoped so narrowly it silently returns
nothing, a "gateway" source so thin the model can only point back at the website, or a topic
classifier confidence miss that asks an unnecessary clarifying question instead of answering.

```bash
cd backend && uv run python -m scripts.eval_answers   # requires GROQ_API_KEY + the real corpus
```

Run it manually against a running backend (not part of `pytest`/CI, and not gated on a key --
it needs one to be useful at all). Exits non-zero if any case fails, so it can gate a release
manually. `tests/evaluation/test_golden_set.py` is a small structural check on the golden set
itself (unique names, every case asserts *something*, every `StudentType` covered) that *does*
run in the regular suite, since that part needs no network call.

**What it caught on first use**: two real regressions in one run.
- `international_opt` ("What is OPT and how does it work?") got an unnecessary clarifying
  question instead of an answer. Root cause: `TopicClassifier`'s OPT description scored bare
  acronym questions ("What is OPT?") at 0.50 confidence, just under the 0.55 clarification
  threshold — traced by embedding a few phrasings directly and comparing cosine scores. Fixed by
  adding "what is OPT" to the topic description text (`app/retrieval/topic_classifier.py`),
  verified not to regress the admissions/OPT collision the description was already tuned to avoid
  in an earlier pass.
- Two cases failed only because they didn't set a `student_type`, hitting the deliberate
  first-turn "what kind of student are you" profile gate (`check_student_profile_node`) — a golden
  set authoring bug, not an app bug, fixed by giving those cases a `student_type` since the
  content itself isn't type-scoped.
- Two more cases asked for facts the real source pages genuinely don't contain (a specific
  freshman GPA minimum, and student parking permit pricing) — correctly came back
  `grounded: false`. Also golden-set authoring bugs (asking for the wrong fact), not app bugs;
  reworded to ask what the sources actually state. The parking permit price gap is real and
  undocumented elsewhere — noted in the case's comment as a known, not-yet-fixed content gap.

## Performance

- **Rate limiting** (`app/core/rate_limit.py`, slowapi): `/chat` (20/min per IP, configurable via
  `Settings.chat_rate_limit`) and `/retrieve` (30/min) are throttled — `/chat` calls a paid Groq
  API per request and `/retrieve` runs embedding + cross-encoder inference, so an abusive or
  looping client shouldn't be able to run either up unbounded. Covered at two levels:
  `tests/test_chat_api.py::test_chat_enforces_rate_limit` proves the counter logic sequentially,
  and `tests/test_retrieve_api.py::test_retrieve_rate_limit_holds_under_real_concurrency` fires 10
  real concurrent requests via `asyncio.gather` against a 5/min limit and asserts an exact 5/5
  split — sequential calls alone don't prove a limiter is safe against requests that actually
  arrive at once.
- **Model loading**: the embedding model and cross-encoder reranker are loaded once per process
  (`@lru_cache`-wrapped singletons in `app/embeddings/embedder.py` and
  `app/retrieval/reranker.py`), not per-request — both are CPU-only and loading them is the
  expensive part.
- **DB connection pooling**: `Settings.db_pool_size` (default 5) and `Settings.db_max_overflow`
  (default 10) are now explicit, configurable settings passed to `create_async_engine`
  (`app/database/session.py`), rather than relying on SQLAlchemy's implicit defaults — tunable
  per deployment without a code change.

### Load testing

```bash
cd backend && uv run python -m scripts.load_test          # full run, needs a real GROQ_API_KEY
uv run python -m scripts.load_test --skip-chat              # skip the Groq-backed /chat benchmark
```

Not part of pytest/CI — needs a live backend and a real ingested corpus, and a full run takes a
couple of minutes (deliberately paced to stay under each endpoint's own rate limit, plus a 60s
settle period before the burst test). Measures two things: a sequential per-endpoint latency
profile (mean/p50/p95/p99), and a genuine concurrent burst (`asyncio.gather`, not a loop) against
`/retrieve`'s rate limiter.

**Results from a real run** (dev machine, local Docker Compose stack, 220-document corpus):

| Endpoint | Condition | Mean | p50 | p95 | p99 |
|---|---|---|---|---|---|
| `GET /health` | steady state | 3ms | 1ms | 15ms | 15ms |
| `GET /retrieve` | steady state (corpus cache warm) | 192ms | 148ms | 501ms | 501ms |
| `GET /retrieve` | first request after backend idle | up to ~4.9s (one-time) | — | — | — |
| `GET /retrieve` | 40 concurrent requests vs. a 30/min limit | 2366ms | 2649ms | 3373ms | 3374ms |

Two real findings, not just numbers:
- **First-request latency spike**: the very first `/retrieve` call after the backend has been
  idle took ~4.9s against a ~150-200ms steady state — confirmed by re-running immediately after
  (no more spike) and checking `HybridRetriever._get_corpus`
  (`app/retrieval/hybrid_search.py`), which lazily loads and BM25-indexes every matching chunk on
  first use per request-scoped instance. The corpus grew from 33 to 220 documents during this
  session's crawler work, making that cold path noticeably more expensive than it used to be.
  Not urgent at current corpus size, but worth a pre-warming request on startup if the corpus
  keeps growing.
- **Rate limiter enforces exactly, but accepted requests slow down under real contention**: 40
  concurrent `/retrieve` requests against the 30/min limit split exactly 30 accepted / 10
  rejected (`429`) — precise, not approximate. But the 30 accepted requests took a mean of 2.4s
  (vs. ~150-200ms uncontended), because the cross-encoder reranker's CPU-bound inference doesn't
  parallelize for free across 30 simultaneous requests on one process. The rate limit protects
  against unbounded cost, not against per-request slowdown under legitimate concurrent load —
  worth knowing before assuming 30/min is "free" at the ceiling.

`/chat` benchmarking was run but not usably reported here: Groq's free-tier daily token quota
(100k/day) was exhausted from earlier testing during this same session, so all 8 sampled
`/chat` calls hit the graceful-fallback path (`"I'm having trouble generating an answer..."`)
rather than real generation — the script itself detects and flags this
(`bench_chat`'s degraded-response check) rather than silently reporting fast-fail latency as if
it were real Groq generation time. Re-run `scripts/load_test.py` once quota resets for real
end-to-end `/chat` numbers.

## Deployment

```bash
cp .env.example .env   # fill in FRONTEND_PUBLIC_URL and BACKEND_PUBLIC_URL too
docker compose -f docker-compose.yml -f docker-compose.prod.yml up -d --build
```

`docker-compose.prod.yml` is an explicit overlay (only applied when named with `-f`), so it does
**not** stack with `docker-compose.override.yml` the way plain `docker compose up` does for local
dev. Relative to the base file, it:

- Doesn't publish Postgres/Qdrant ports to the host — plain `docker compose up` auto-loads
  `docker-compose.override.yml`, which publishes them for local debugging (`psql`, the Qdrant
  dashboard); production has no reason to expose the data stores beyond the Docker network the
  backend already shares with them.
- Sets CPU/memory limits per service (`deploy.resources.limits`), so one runaway container (e.g.
  a client stuck retrying against `/chat`) can't starve the host.
- Caps container log file size (`json-file`, 10MB × 3 files) — the default Docker log driver has
  no cap and grows unbounded on a long-lived host.
- Sets `ENVIRONMENT=production` and a real `CORS_ORIGINS` (from `FRONTEND_PUBLIC_URL`) instead of
  `localhost`, and builds the frontend against `BACKEND_PUBLIC_URL` instead of a local address.

This assumes a single host behind a reverse proxy (nginx, Caddy, Traefik) that terminates TLS
and forwards to the `backend`/`frontend` containers' published ports — the proxy itself isn't
included here since the right choice depends on the target host. Both Dockerfiles declare a
`HEALTHCHECK` (backend: `GET /api/v1/health`; frontend: `GET /`), so `docker ps` and any
orchestrator reading container health will reflect real service status rather than just "process
is running." Postgres data lives in the named `postgres_data` volume (survives container
recreation, e.g. after rebuilding for a code change) — back it up with `pg_dump` or a volume
snapshot before any migration that isn't purely additive.

### A real Docker networking bug this caught

Adding the frontend `HEALTHCHECK` surfaced a real bug, not just a missing feature: Docker sets
the `HOSTNAME` env var to the container ID automatically, and Next.js's standalone `server.js`
binds to `process.env.HOSTNAME` when it's set — so the server was listening only on the
container's internal Docker-network IP, never on `127.0.0.1` or `0.0.0.0`. It looked completely
fine (`next start` logs "Ready", the published port forwarded traffic in from outside the
container just fine because Docker's port mapping doesn't go through `localhost` inside the
container), which is exactly why a healthcheck run *from inside the container* was needed to
catch it — `curl localhost:3000` from inside that same container would already have failed.
Fixed with `ENV HOSTNAME=0.0.0.0` in `frontend/Dockerfile`, forcing the standalone server to bind
all interfaces.

## Environment Variables

See [.env.example](.env.example) (docker-compose), [backend/.env.example](backend/.env.example),
and [frontend/.env.example](frontend/.env.example). Never commit a real `.env` file — secrets
belong only in gitignored `.env` files, not the tracked `.env.example` templates.

## Privacy

This assistant never asks for or stores UIN, NetID, email, password, phone number, or any other
personally identifiable information. Personalization is limited to anonymous session context
(student type, semester, optional college/department).
