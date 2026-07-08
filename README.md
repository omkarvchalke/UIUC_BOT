# CampusGuide AI

CampusGuide AI is a **standalone, student-built** RAG (Retrieval-Augmented Generation) chatbot that helps new University of Illinois Urbana-Champaign (UIUC) students find general public information about onboarding topics — orientation, Welcome Week, housing, move-in, i-cards, NetID basics, international student check-in, transportation, health/immunization info, and accessibility accommodations.

> **⚠️ Unofficial project.** CampusGuide AI is not affiliated with, endorsed by, or operated by the University of Illinois Urbana-Champaign. It is a portfolio/MVP project. Answers are generated from publicly available university webpages and may not cover every individual situation. For official guidance, always contact the relevant university office.

---

## Table of Contents

- [Problem Statement](#problem-statement)
- [Product Overview](#product-overview)
- [Features](#features)
- [Screenshots](#screenshots)
- [Tech Stack](#tech-stack)
- [Architecture](#architecture)
- [RAG Pipeline](#rag-pipeline)
- [Data Ingestion Flow](#data-ingestion-flow)
- [Safety & Privacy Guardrails](#safety--privacy-guardrails)
- [Repository Structure](#repository-structure)
- [Local Setup](#local-setup)
- [API Examples](#api-examples)
- [Testing & Evaluation](#testing--evaluation)
- [Deployment](#deployment)
- [Demo Script](#demo-script)
- [Future Improvements](#future-improvements)
- [Resume Bullets](#resume-bullets)

---

## Problem Statement

New students face a maze of scattered official webpages (orientation, housing, ISSS, i-card, McKinley, DRES, MTD, etc.) when trying to answer simple onboarding questions. CampusGuide AI centralizes **public** university information into a conversational interface with transparent source citations — without ever touching private student data or login-protected systems.

## Product Overview

CampusGuide AI answers new-student questions using Retrieval-Augmented Generation over a curated set of public UIUC webpages:

1. Fetch curated public webpage URLs (`ingestion/sources.json`).
2. Clean and chunk the page content.
3. Embed chunks and store them in a local ChromaDB vector store.
4. Retrieve the most relevant chunks for a user's question.
5. Send the retrieved context to an LLM with a strict system prompt.
6. Return a cited answer with a confidence level and suggested next steps.

A privacy/safety classifier runs before all of this — private-data questions never reach retrieval or the LLM at all (see [Safety & Privacy Guardrails](#safety--privacy-guardrails)).

## Features

- 💬 **Chat** — ask general new-student questions across 19 topics (orientation, housing, dining, academics, technology, financial aid, safety, recreation, and more), get cited, streamed answers with confidence scoring, and ask natural follow-ups thanks to multi-turn conversation memory
- 📋 **Checklist generator** — general onboarding checklist based on student type/status/term/housing, with source links pulled live from the vector store
- 📚 **Source library** — browse and filter every public source the app is indexed on
- 🛡️ **Safety guardrails** — automatic detection and safe fallback for private-data requests (blocked before any LLM call) and official-office escalation for sensitive-but-general topics
- 👍 **Feedback** — lightweight helpful/not-helpful feedback logging, no user identity required

## Screenshots

> Placeholders — capture these from a local run (`npm run dev` + a real `GROQ_API_KEY`) before sharing this README externally.

| Page | Screenshot |
|---|---|
| Home | `docs/screenshots/home.png` *(not yet captured)* |
| Chat — cited answer | `docs/screenshots/chat-answer.png` *(not yet captured)* |
| Chat — private-data safety fallback | `docs/screenshots/chat-safety-fallback.png` *(not yet captured)* |
| Checklist | `docs/screenshots/checklist.png` *(not yet captured)* |
| Source Library | `docs/screenshots/sources.png` *(not yet captured)* |

## Tech Stack

| Layer | Technology |
|---|---|
| Frontend | React, TypeScript, Vite, Tailwind CSS |
| Backend | Python, FastAPI, Pydantic, Uvicorn |
| LLM (chat generation) | Groq (default), OpenAI, Google Gemini, or OpenRouter — selectable via env var |
| Embeddings | sentence-transformers, local, `BAAI/bge-base-en-v1.5` by default |
| Vector DB | ChromaDB (local persistence) |
| Ingestion | requests, BeautifulSoup, trafilatura |
| Storage | ChromaDB (local persistence), JSON/JSONL files |
| Deployment | Docker (backend), Vercel (frontend) |

## AI Stack

- **LLM: Groq** (default) — fast inference, genuinely free tier (no credit card, console.groq.com/keys), used only for the final answer-generation step.
- **Embeddings: sentence-transformers** (local, `BAAI/bge-base-en-v1.5`) — runs on CPU/GPU on the same machine, no API key, no per-token cost, no network call after the first model download.
- **Vector DB: ChromaDB** — local persistence, unchanged regardless of which LLM provider is selected.

**Why embeddings run locally while the LLM doesn't:** Groq (and most fast/cheap chat providers) don't expose an embeddings endpoint at all — you'd need a second provider just for that. Retrieval also doesn't need frontier-model quality; a good open embedding model is free, fast, and keeps ingestion + retrieval fully functional with zero API credits. Only the final natural-language answer needs a real LLM call.

**Switching providers is an environment-variable-only change** — no code edits. Set `LLM_PROVIDER` to `groq` | `openai` | `google` | `openrouter` in `backend/.env`, plus that provider's API key (`GROQ_API_KEY`, `OPENAI_API_KEY`, `GOOGLE_API_KEY`, or `OPENROUTER_API_KEY`) and `LLM_MODEL`. Example — switching from Groq to OpenAI:

```bash
# backend/.env
LLM_PROVIDER=openai
LLM_MODEL=gpt-4o-mini
OPENAI_API_KEY=sk-...
```

Adding a fifth provider means adding one new client module under `backend/app/llm/` implementing the same `generate(messages, json_mode)` interface, plus one branch in `provider_factory.py` — no changes anywhere else in the app. See `backend/README.md` → "AI Stack: Providers" for the full architecture.

## Architecture

```text
┌─────────────────┐        HTTP/JSON        ┌──────────────────────┐
│  React Frontend  │  ───────────────────▶  │   FastAPI Backend    │
│  (Vite+TS+Tailwind)                        │  safety → retrieve →  │
│                  │  ◀───────────────────  │  generate             │
└─────────────────┘                         └──────────┬───────────┘
                                                        │
                                             ┌──────────▼───────────┐
                                             │   ChromaDB (local)    │
                                             │   persisted vector    │
                                             │   store of chunks     │
                                             └──────────▲───────────┘
                                                        │
                                             ┌──────────┴───────────┐
                                             │  Ingestion Pipeline   │
                                             │  fetch→clean→chunk→   │
                                             │  embed (offline)      │
                                             └───────────────────────┘
```

Full breakdown, request-flow diagram, and per-module notes: [`docs/architecture.md`](docs/architecture.md).

## RAG Pipeline

Question → **safety classification** (blocks private-data questions before anything else runs) → **retrieval** (top-5 chunks from ChromaDB, cosine similarity, local embeddings — no API key) → **prompt assembly** (system rules + numbered context, sources never given to the model — they're attached programmatically from chunk metadata and deduplicated by URL) → **generation** (JSON-mode chat completion via the configured `LLM_PROVIDER`, parsed into `answer` + `next_steps`) → **confidence** (computed deterministically from retrieval scores, not self-reported by the LLM).

Full explanation of each stage, confidence-scoring math, and the evaluation approach: [`docs/rag-pipeline.md`](docs/rag-pipeline.md).

## Data Ingestion Flow

```text
sources.json (curated public URLs)
  → fetch_pages.py    (raw HTML + metadata, failed URLs logged & skipped)
  → clean_text.py     (trafilatura primary, BeautifulSoup fallback)
  → chunk_text.py     (~650-token chunks, ~100-token overlap, metadata preserved)
  → embed_chunks.py   (local sentence-transformers embeddings → ChromaDB, no API key)
  → refresh_index.py  (runs all four in order, stops on first failure)
```

Full details on extraction strategy, chunk boundaries, and output structure: [`ingestion/README.md`](ingestion/README.md).

## Safety & Privacy Guardrails

CampusGuide AI **never** requests, collects, stores, or processes:

- UIN, NetID password, passport number, SEVIS ID, I-20 details, visa document numbers
- Health or immunization records
- Financial aid or tuition bill details
- Grades or class schedules
- Admission record details or housing contract details
- Any other private student record

CampusGuide AI **never**:

- Claims to be an official UIUC service, or uses UIUC logos/wordmarks/official branding
- Accesses Canvas, Banner, student portals, email, or any login-protected system
- Gives immigration, legal, medical, financial, or academic-record advice
- Makes official decisions or eligibility determinations for students

A regex/keyword classifier (`backend/app/core/safety.py`) runs on every question **before** retrieval or generation:

| Category | Behavior |
|---|---|
| `private_data` (UIN, password, SEVIS, grades, admission status, tuition bill, etc.) | **Blocked** — fixed fallback returned immediately, zero embedding/LLM calls |
| `health`, `emergency`, `immigration`, `financial_aid` | Allowed — real RAG answer still generated, but an office-escalation note is prepended to `next_steps` and official confirmation is always required |
| everything else | Full RAG flow, no escalation |

**Disclaimer (shown on landing page and chat page):**

> CampusGuide AI is an unofficial student-built project. It is not affiliated with, endorsed by, or operated by the University of Illinois Urbana-Champaign. Answers are generated from publicly available university webpages and may not cover every individual situation. For official guidance, please contact the relevant university office.

**Privacy warning (shown near chat input):**

> Please do not enter UIN, passwords, passport details, visa document numbers, health information, financial aid information, grades, class schedules, or other private student records.

Full policy, escalation wording, and test coverage: [`docs/safety-guardrails.md`](docs/safety-guardrails.md).

## Repository Structure

```text
campusguide-ai/
├── frontend/        # React + TypeScript + Vite chat UI (+ Dockerfile, local demo only)
├── backend/         # FastAPI app, RAG pipeline, safety guardrails (+ Dockerfile)
├── ingestion/        # Fetch, clean, chunk, embed pipeline + sources.json
├── tests/            # Sample questions, safety/retrieval/API tests
├── docs/             # Architecture, RAG pipeline, safety, API spec, demo script
├── docker-compose.yml
├── .dockerignore
└── README.md
```

See [`docs/architecture.md`](docs/architecture.md) for a full breakdown.

## Local Setup

### Prerequisites

- Node.js 18+
- Python 3.10+ (3.13 used in development)
- A free Groq API key (console.groq.com/keys) for chat generation — or a key for OpenAI/Google/OpenRouter if you'd rather use one of those (see [AI Stack](#ai-stack))
- Docker (optional — only needed for containerized backend testing)
- No API key needed for embeddings — they run locally

### 1. Clone and configure environment variables

```bash
cp .env.example .env
cp backend/.env.example backend/.env
cp frontend/.env.example frontend/.env
```

Edit `backend/.env` and set `GROQ_API_KEY` to your key (or switch `LLM_PROVIDER` and set a different provider's key). **Never commit real API keys** — `.env` files are gitignored; only `.env.example` templates are tracked.

| Variable | File | Purpose |
|---|---|---|
| `APP_ENV` | `.env` | Environment label (dev/prod), currently informational |
| `LLM_PROVIDER` | `backend/.env` | `groq` (default) \| `openai` \| `google` \| `openrouter` |
| `LLM_MODEL` | `backend/.env` | Chat model name (default: `llama-3.3-70b-versatile`) |
| `GROQ_API_KEY` | `backend/.env` | **Required** if `LLM_PROVIDER=groq` (the default) |
| `OPENAI_API_KEY` / `GOOGLE_API_KEY` / `OPENROUTER_API_KEY` | `backend/.env` | Required only if you switch `LLM_PROVIDER` to that provider |
| `EMBEDDING_PROVIDER` | `backend/.env` | `local` (only option implemented) — no API key needed |
| `EMBEDDING_MODEL` | `backend/.env` | sentence-transformers model name (default: `BAAI/bge-base-en-v1.5`) |
| `VECTOR_DB` | `backend/.env` | `chromadb` (only option implemented) |
| `CHROMA_DB_PATH` | `backend/.env` | Vector store path, resolved relative to `backend/` regardless of invoking directory |
| `CORS_ORIGINS` | `backend/.env` | Comma-separated list of allowed frontend origins |
| `VITE_API_BASE_URL` | `frontend/.env` | Backend URL the frontend calls |

Full details on every variable: [`backend/README.md`](backend/README.md#environment-variables).

### 2. Backend setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Backend runs at `http://localhost:8000`. Interactive API docs at `http://localhost:8000/docs`.

### 3. Frontend setup

```bash
cd frontend
npm install
npm run dev
```

Frontend runs at `http://localhost:5173`.

### 4. Ingestion pipeline (build the knowledge base)

```bash
cd ingestion
python fetch_pages.py
python clean_text.py
python chunk_text.py
python embed_chunks.py
```

Or run all steps at once:

```bash
python refresh_index.py
```

### Running the app

1. Start the backend (`uvicorn app.main:app --reload` from `backend/`).
2. Start the frontend (`npm run dev` from `frontend/`).
3. Open `http://localhost:5173` and ask a question on the Chat page.

## API Examples

See [`docs/api-spec.md`](docs/api-spec.md) for full request/response contracts for `/health`, `/api/chat`, `/api/chat/stream`, `/api/retrieve`, `/api/sources`, `/api/checklist/generate`, and `/api/feedback`.

Quick example:

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "When is Welcome Week?"}'
```

```json
{
  "answer": "Welcome Week is listed as...",
  "sources": [
    {"title": "Welcome Week", "url": "https://newstudent.illinois.edu/orientation/welcomeweek", "category": "welcome_week", "department": "New Student & Family Experiences"}
  ],
  "confidence": "high",
  "next_steps": ["Review the official Welcome Week page for schedule updates."],
  "requires_official_confirmation": false
}
```

## Testing & Evaluation

```bash
cd backend && source .venv/bin/activate
pytest ../tests -v              # full suite
pytest ../tests/test_safety.py -v      # safety classifier (no API key needed)
pytest ../tests/test_api.py -v         # endpoint schemas (mostly no API key needed)
pytest ../tests/test_retrieval.py -v   # retrieval-category accuracy (needs a built index)
```

`tests/sample_questions.json` contains 76 labeled sample questions across 19 real categories (`orientation`, `welcome_week`, `housing`, `move_in`, `international`, `icard`, `transportation`, `health`, `accessibility`, `dining`, `academics`, `technology`, `library`, `recreation`, `safety`, `counseling`, `parking`, `financial_aid`, `student_life`) plus `refusal` (private-data), each tagged `type: "normal" | "sensitive" | "private_data"`. It's shared by two test files:

- **`test_safety.py`** sweeps every question and checks the `safety.classify()` category/blocking/escalation behavior — this never needs an API key.
- **`test_retrieval.py`** embeds each non-refusal question and checks that its `expected_category` appears among the top 5 retrieved chunks — embeddings run locally (no API key), so the only prerequisite is a built index (`cd ingestion && python refresh_index.py`); tests auto-skip with a clear reason if it's empty. **Run for real against genuine local embeddings across all 19 categories: 176/177 (99.4%) of the full suite passed** — the one miss is a documented content-thinness limitation of a specific source page, not a code defect (see `docs/rag-pipeline.md`).

`test_api.py` checks response *shapes* (status codes, field names/types, enum values) for `/health`, `/api/chat`, `/api/chat/stream`, `/api/retrieve`, and `/api/sources` — deliberately never asserting exact LLM wording, since that depends on a real model call. The `/api/chat` and `/api/chat/stream` schema tests use a private-data question specifically because that path is blocked before any embedding/LLM call, so it's meaningful with zero configuration.

See [`docs/rag-pipeline.md`](docs/rag-pipeline.md) for the evaluation approach.

**Note:** feedback logs (`backend/data/feedback.jsonl`) are local MVP storage and must never intentionally contain sensitive user data.

## Deployment

### Docker (backend)

The backend Dockerfile builds from the **repo root** as context (not `backend/`), because the app resolves `ingestion/sources.json` and the ChromaDB path relative to the repo layout:

```bash
# Build
docker build -f backend/Dockerfile -t campusguide-backend .

# Run standalone (mount a prebuilt index; see Troubleshooting if you skip this)
docker run --rm -p 8000:8000 --env-file backend/.env \
  -v "$(pwd)/ingestion/data/chroma:/repo/ingestion/data/chroma" \
  campusguide-backend

# Or bring up backend + frontend together for a local demo
cp backend/.env.example backend/.env   # then set a real GROQ_API_KEY
docker compose up --build
```

`docker-compose.yml` is for **local multi-service convenience only** — it is not the production deployment path (see below). The frontend's `Dockerfile` runs the Vite dev server for the same reason; production frontend deploys as a static build via Vercel.

The vector index (`ingestion/data/chroma`) is intentionally **not baked into the image** — build it on the host first (`cd ingestion && python refresh_index.py`) and mount it in, so the image stays slim and the index can be rebuilt independently of app code.

> **Note on the Python base image:** `chromadb` depends on `chroma-hnswlib`, which compiles a C++ extension at install time. `python:3.13-slim` has no compiler by default — the Dockerfile installs `build-essential` before `pip install` specifically to fix this (discovered by actually building the image, not assumed).

### Frontend → Vercel

1. Import the repo into Vercel, set the project **root directory to `frontend/`**.
2. Build command: `npm run build` — output directory: `dist`.
3. Set the environment variable `VITE_API_BASE_URL` to your deployed backend's URL (e.g. `https://campusguide-backend.onrender.com`).
4. Deploy. Vite bakes `VITE_API_BASE_URL` in at build time, so redeploy after changing it.

### Backend → Render / Railway / Fly.io

All three can build directly from `backend/Dockerfile` with the repo root as build context:

- **Render:** New Web Service → connect repo → Dockerfile path `backend/Dockerfile`, Docker build context `.` (repo root) → set env vars from `backend/.env.example` in the dashboard → expose port `8000`.
- **Railway:** New Project → Deploy from repo → set the Dockerfile path and build context the same way → add env vars → Railway auto-detects the exposed port.
- **Fly.io:** `fly launch` from the repo root, pointing `--dockerfile backend/Dockerfile`; set secrets with `fly secrets set GROQ_API_KEY=... CORS_ORIGINS=https://your-frontend.vercel.app`.

**On all three:** set `CORS_ORIGINS` to your deployed frontend's exact origin (comma-separated if more than one, e.g. a Vercel preview + production domain). The vector index needs to exist on a persistent disk/volume for that service (Render/Railway/Fly all support persistent volumes) — build it once via a one-off job/shell that runs `ingestion/refresh_index.py` against the same volume, or bake a prebuilt index into a custom image layer if your index is small and stable.

### Troubleshooting

| Symptom | Cause | Fix |
|---|---|---|
| `/api/chat` returns `503` with `"GROQ_API_KEY is not set..."` (or `OPENAI_`/`GOOGLE_`/`OPENROUTER_API_KEY`) | No key configured for the selected `LLM_PROVIDER`, or a placeholder value | Set a real key for whichever provider `LLM_PROVIDER` is set to, in `backend/.env` (local) or your host's env var dashboard (deployed). This is a deliberate, clear error — not a bug. Note `/api/retrieve` never needs a key at all (embeddings are local). |
| `/api/chat` returns `200` with a "not enough information" answer and empty `sources` | Vector index is empty | Run `cd ingestion && python refresh_index.py` (no API key needed — embeddings are local) and confirm `ingestion/data/chroma/chroma.sqlite3` exists. In Docker, confirm the volume mount actually points at that directory. |
| `EmbeddingConfigError: Failed to load embedding model...` | No internet access on first run (sentence-transformers needs to download the model once), or a typo'd `EMBEDDING_MODEL` | Check network access, or fix `EMBEDDING_MODEL` to a valid sentence-transformers model name. After the first successful load, the model is cached locally and no network is needed. |
| ChromaDB errors about a missing/unreadable path, or the index seems to reset | `CHROMA_DB_PATH` resolved to somewhere unexpected | It's resolved relative to `backend/`, not the process's cwd (see `vector_store._resolve_persist_dir`) — this is intentional so it works the same whether invoked from `backend/` or `ingestion/`. In Docker, make sure the bind mount target is `/repo/ingestion/data/chroma` to match. |
| Browser console shows a CORS error calling the backend | The frontend's origin isn't in `CORS_ORIGINS` | Add the exact origin (scheme + host + port, no trailing slash) to `CORS_ORIGINS` in `backend/.env`, comma-separated for multiple origins, and restart the backend. |
| `docker build` fails on `chroma-hnswlib` with a compiler error | Missing C++ toolchain in the base image | Already fixed in `backend/Dockerfile` via `build-essential` — if you see this, you're likely on a modified Dockerfile or a different base image that dropped it. |
| `docker compose config` fails with "env file ... not found" | `backend/.env` doesn't exist yet | `cp backend/.env.example backend/.env` and set a real key before running compose commands. |
| `docker build` is slow / image is large | `sentence-transformers` pulls in `torch` | Expected — this is a real, sizable dependency now that embeddings run locally. Worth knowing if minimizing image size becomes a priority. |

## Demo Script

A ~5 minute walkthrough — see [`docs/demo-script.md`](docs/demo-script.md) for the full talking-point version.

1. Open the landing page — point out the unofficial disclaimer and privacy warning.
2. Ask **"When is Welcome Week?"** — show the cited answer, confidence badge, and source cards.
3. Ask **"Do first-year students have to live on campus?"** — show retrieval pulling from the Housing FAQ.
4. Ask **"What is international student check-in?"** — show ISSS sources cited.
5. Ask **"Can you check my admission status?"** — show the safety guardrail intercepting the question before any LLM call.
6. Generate a checklist (Freshman / International / Fall / On-campus) — show ISSS + housing tasks with live source links.
7. Open the Source Library — filter by category, show every source is a real, clickable public UIUC page.

## Future Improvements

- Continue expanding curated source list (bookstore, mail services, decentralized per-college advising) and add automated staleness checks
- Add richer evaluation harness with automated grading
- Add admin dashboard for reviewing feedback trends
- Exercise the Google/OpenRouter LLM providers against their real APIs (currently real-verified: Groq; mechanics-verified: OpenAI-compatible shared logic)
- Recalibrate confidence thresholds against real usage data at scale
- Replace the Office of the Registrar's thin resource-link-list page with richer per-topic pages (registration steps, academic calendar) if/when better public pages are identified

## Resume Bullets

**Main:**
> Built a standalone RAG-based campus assistant using React, FastAPI, ChromaDB, and LLM APIs to answer new-student questions from public university webpages with source citations, confidence scoring, checklist generation, and privacy-focused guardrails.

**Software Engineering:**
> Designed and built a full-stack RAG application (React/TypeScript frontend, FastAPI backend, ChromaDB vector store) with a 6-stage ingestion pipeline, Dockerized deployment, and a 24+ test suite covering safety classification, API schemas, and retrieval accuracy.

**AI Engineering:**
> Implemented a retrieval-augmented generation pipeline with deterministic confidence scoring derived from retrieval similarity (not self-reported by the LLM), programmatic source-citation injection to eliminate URL hallucination, and JSON-mode structured generation with a raw-text fallback for parsing resilience.

**Data Engineering:**
> Built a resilient web-to-vector ingestion pipeline (fetch → trafilatura/BeautifulSoup extraction → token-aware chunking with whitespace-safe overlap → batched embedding) that gracefully degrades on fetch failures, empty extractions, and missing API keys without crashing the pipeline.

**Product Engineering:**
> Shipped a privacy-first AI product with a regex-based safety classifier that blocks private-data requests before any model call, category-specific escalation for sensitive topics, and a source-transparency page — balancing genuine usefulness against a hard no-private-data, no-official-claims boundary.
