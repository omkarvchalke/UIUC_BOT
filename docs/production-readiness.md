# IlliniAssist AI — Production Readiness Report

Date: 2026-07-16 (final pass, this rebuild)

## 1. What this is

A RAG chatbot answering UIUC-specific questions (admissions, housing, dining,
financial aid, registration, and more), grounded only in crawled official
UIUC pages — never the model's parametric knowledge presented as fact. Built
this rebuild as: FastAPI + LangGraph backend, Postgres + Qdrant storage,
Groq-hosted LLM, Next.js/React 19 frontend.

## 2. Architecture

**Backend** (`backend/app`): FastAPI app; a LangGraph state machine
(`app/graph`) does intent classification → topic classification → hybrid
retrieval (BM25 + vector, RRF-fused) → rerank → citation generation →
grounded-answer generation, with clarification branches for ambiguous
profile/topic. Ingestion (`app/ingestion`) crawls 14 knowledge-domain source
modules, does heading-aware semantic chunking, and extracts
audience/document_type/keyword metadata. Postgres holds documents/sessions/
feedback/analytics events; Qdrant holds chunk embeddings
(`BAAI/bge-small-en-v1.5`, local, no paid embedding API).

**Frontend** (`frontend/src`): Next.js 16 App Router, React 19, shadcn/ui
(Base UI primitives) + Tailwind 4, a "neo-brutalist" design system
(`brutal-border`/`brutal-shadow` utilities). Two routes: `/` (chat) and
`/analytics` (live usage dashboard).

**Infra**: `docker-compose.yml` (dev, with an `override.yml` publishing
Postgres/Qdrant ports to the host) and `docker-compose.prod.yml` (overlay
adding per-service resource limits, bounded JSON log files, and a real CORS
origin instead of localhost). Migrations run automatically on container
start via `docker-entrypoint.sh` → `alembic upgrade head`.

## 3. What's implemented (all 6 original roadmap phases, plus this session's UI/UX pass)

- Domain-driven ingestion across 14 knowledge domains, incremental re-crawl
  via conditional GET, document version tracking on content change
- Heading-aware semantic chunking (not fixed-size) with subtopic tagging
- Hybrid retrieval (BM25 + vector, RRF fusion) + reranking, with
  student-type/audience/document_type/topic filters
- LangGraph turn flow with clarification branches (ambiguous profile,
  ambiguous/off-topic query) instead of guessing or hallucinating
- A `grounded` self-report field on every answer (fixes a real "confident
  but the model doesn't actually know" failure mode found earlier this
  project)
- Real token streaming (SSE) and multi-turn conversation memory
- Analytics: `chat_turn_events` persisted per turn, `/api/v1/analytics/summary`
  (grounded rate, clarification rate, topic distribution, feedback ratio,
  latency percentiles via Postgres `percentile_cont`), surfaced on `/analytics`
- RAG evaluation harness (`scripts/eval_rag.py`): Precision@5/Recall@5/MRR/
  Context Precision against a hand-curated golden set, a heuristic (default)
  + optional LLM-judge faithfulness scorer, latency percentiles
- This session: markdown-rendered answers, wider/rebalanced chat layout,
  analytics page brought to the same visual language, copy-answer button
  (with a visual highlight of exactly what was copied), no-lost-message on
  send failure, composer auto-focus (skipped on touch devices), a "still
  thinking" hint + aria-live announcements, retry on session-start failure,
  a confirmation dialog before wiping an in-progress conversation

## 4. Verification (this pass, run end-to-end just before this report)

| Check | Result |
|---|---|
| Backend `ruff format --check` | 169 files, clean |
| Backend `ruff check` | clean |
| Backend `mypy app` | clean, 110 files |
| Backend `pytest` | **257/257 passed**, 88% line coverage |
| Frontend `eslint` | clean |
| Frontend `tsc --noEmit` | clean |
| Frontend `vitest` | **70/70 passed** |
| Frontend `next build` | succeeds |
| CI (`.github/workflows/ci.yml`) | mirrors all of the above on push/PR to `main` |

**Live end-to-end run** (this session, driving the actual running app with
Playwright, not mocks): 20 real, varied UIUC questions asked in one
continuous conversation — 20/20 answered, 0 timeouts, 0 error banners, 0
browser console errors, 0 failed network requests, 0 page crashes. Avg
latency 2.9s, max 4.3s. Confirmed the UI holds up visually after sustained
use (no rendering drift, no memory-related slowdown). Verified responsive
layout with zero horizontal overflow across 320px–1440px viewports.

## 5. Known gaps (found via the live run above, not theoretical)

**Content coverage** — of the 20 live questions, only 9 (45%) came back
grounded with citations; 11 came back correctly flagged as
possibly-incomplete rather than hallucinated, but 8 of those got **zero**
retrieved citations at all, meaning the corpus has no matching content for:
OPT, CPT, graduate application submission, student organizations, career
services, contacting an academic advisor, and out-of-state tuition costs.
The app's honesty guardrail worked exactly as designed here (it said "I
don't have enough information" rather than making something up), but this
is a real corpus gap, not a code bug — closing it means adding source pages
for those topics in `app/ingestion/domains/`.

**Topic misclassification** — 2 of 20 live questions were misclassified
("career services" → `international_student_services`, "contact my academic
advisor" → `academic_calendar`). Doesn't affect grounding correctness
directly but does affect which filtered corpus slice retrieval searches.

**Groq daily token quota** — hit repeatedly across this project's earlier
phases (real 429s during test runs). The account is on a free/shared tier;
production traffic at any real volume needs a paid tier or the tests will
intermittently fail for reasons unrelated to the code.

**1 pre-existing content-thinness test finding** (noted in earlier project
memory, not re-verified in this pass): a known gap, not a regression.

## 6. Security / privacy posture

- No PII collected by design — sessions are anonymous UUIDs, no login, no
  name/NetID ever requested (stated to the user directly on the landing
  screen)
- CORS locked to a specific origin (`CORS_ORIGINS`, defaults to
  `localhost:3000` in dev; must be set to the real origin in prod — the
  prod compose overlay does this)
- Rate limiting via `slowapi` on `/api/v1/chat` and `/api/v1/retrieve`
  (`chat_rate_limit`/`retrieve_rate_limit` settings)
- Prod compose overlay isolates Postgres/Qdrant from the host network
  entirely (only reachable from other containers), caps container
  CPU/memory, and bounds log file growth
- `.env`/`.env.example` handling: real secrets never committed (this has
  been manually caught and fixed twice this project when a real key ended
  up in the tracked `.env.example` instead of the gitignored `.env`) — worth
  a `git log -p -- '*.env.example'` sanity check before any public release
  of this repo

## 7. Before a real launch, in priority order

1. **Expand corpus coverage** for the 6-7 topics found with zero citations
   above — the single highest-leverage fix, directly improves the 45%
   grounded rate.
2. **Move off the shared/free Groq tier** — quota exhaustion is a recurring,
   documented operational risk, not a hypothetical one.
3. **Fix the 2 topic misclassifications** found live, and consider a small
   held-out live-traffic eval (not just the golden set) to find more like
   them.
4. **Add uptime/error monitoring** for the deployed containers — right now
   the only signal is `docker compose logs` and the `/analytics` dashboard,
   both of which require someone to actively check them.
5. Nothing found in this pass blocks a staged/limited launch — stability,
   tests, CI, and the core RAG pipeline are all solid. The gaps above are
   about answer *completeness*, not correctness or safety: the app never
   hallucinated in 20 live questions, it just didn't always have an answer.
