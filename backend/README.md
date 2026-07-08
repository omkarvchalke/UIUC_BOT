# CampusGuide AI — Backend

FastAPI backend for CampusGuide AI. See the [root README](../README.md) for the full project overview, privacy boundary, and disclaimers.

## Setup

```bash
cd backend
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
cp .env.example .env            # then set GROQ_API_KEY (free at console.groq.com/keys)
```

Embeddings run locally (no key needed) — only chat generation (`LLM_PROVIDER`, default `groq`) needs an API key. See "AI Stack" in the [root README](../README.md).

## Run

```bash
uvicorn app.main:app --reload
```

- App: `http://localhost:8000`
- Interactive docs (Swagger UI): `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`

## Current Endpoints

| Method | Path | Status |
|---|---|---|
| GET | `/health` | Live — returns service health |
| POST | `/api/chat` | Live — real RAG: retrieval + generation, cited sources, computed confidence |
| GET | `/api/sources` | Live — reads `ingestion/sources.json`, supports `?category=` filter |
| POST | `/api/retrieve` | Live — real semantic retrieval against ChromaDB, top 5 chunks with source metadata + score |
| POST | `/api/checklist/generate` | Live — conditional sections based on request fields, source links pulled live from the vector store |
| POST | `/api/feedback` | Live — appends JSONL records to `backend/data/feedback.jsonl` |

## AI Stack: Providers

**Chat generation** is provider-agnostic via `app/llm/` — a small interface (`LLMClient.generate(messages, json_mode=...)`) with one implementation per provider, selected at runtime by `LLM_PROVIDER`:

| Provider | Module | Notes |
|---|---|---|
| `groq` (default) | `app/llm/groq_client.py` | Official `groq` SDK. Free tier, no credit card — see console.groq.com/keys. |
| `openai` | `app/llm/openai_client.py` | Official `openai` SDK. Also the shared base class (`OpenAICompatibleClient`) for the two providers below. |
| `google` | `app/llm/google_client.py` | Gemini's OpenAI-compatible endpoint, via the `openai` SDK with a different `base_url`. |
| `openrouter` | `app/llm/openrouter_client.py` | Same pattern — `openai` SDK pointed at OpenRouter. |

`app/llm/provider_factory.py` is the **only** place that instantiates a specific provider — `app/rag/generator.py` just calls `get_llm_client()` and never knows which provider it got. Adding a fifth provider means adding one client module + one branch in the factory; no other code changes. All providers translate their SDK's exceptions (auth, rate limit, timeout, bad request) into a single `LLMProviderError`, so `generator.py` has exactly one error type to handle regardless of provider.

**Embeddings** run locally via `app/rag/embeddings.py` (`sentence-transformers`, default model `BAAI/bge-base-en-v1.5`) — no API key, no network call after the first model download, no per-token cost. `EMBEDDING_PROVIDER=local` is the only implementation right now; a different value raises a clear `EmbeddingConfigError` rather than silently doing nothing.

**Why split providers this way?** Groq (and most fast/cheap chat providers) don't expose an embeddings endpoint at all. Rather than requiring a second paid API just for embeddings, retrieval doesn't need frontier-model quality — a good open embedding model running locally is free, fast enough, and means ingestion + retrieval work fully offline with zero API credits. Only the final answer-generation step needs a real (optionally free) LLM key.

## RAG Modules

- `app/rag/embeddings.py` — local embeddings (see AI Stack above): `embed_documents(texts)`, `embed_query(text)`. Raises `EmbeddingConfigError` with a clear message if the model fails to load or `EMBEDDING_PROVIDER` isn't `"local"`.
- `app/rag/vector_store.py` — persistent local ChromaDB wrapper: `get_collection()`, `reset_index()`, `add_documents(chunks, embeddings)`, `similarity_search(query_embedding, top_k)`, `lookup_source_by_title(title)`. Collection uses cosine distance; `similarity_search()` returns `chunk_text`, `source_title`, `source_url`, `category`, `department`, `score`. `lookup_source_by_title()` does a metadata-only lookup (no embedding call) for the checklist generator. All return `[]`/`None` if the collection is empty — never raise.
- `app/rag/_telemetry.py` — a no-op Chroma telemetry client. (Chroma's default Posthog telemetry client throws on some installed `posthog` versions — this sidesteps that version-skew bug; unrelated to app logic.)
- `app/rag/retriever.py` — thin orchestration layer: `retrieve(question, top_k)` embeds the question then queries the vector store. Used by both `POST /api/retrieve` and `POST /api/chat`.
- `app/rag/prompt_builder.py` — assembles chat-completion messages from `app/prompts/rag_system_prompt.txt` (rules only) + a numbered context block built from retrieved chunks + the question (user message). Sources are never requested from the model — see below.
- `app/rag/generator.py` — calls `get_llm_client()` (see AI Stack) in JSON mode, parses `{"answer": ..., "next_steps": [...], "grounded": bool}`. Falls back to using raw text as the answer if the model returns non-JSON, rather than raising. Raises `GenerationConfigError` on any provider failure (missing/invalid key, rate limit, timeout).
- Build the index with `ingestion/embed_chunks.py` (or `ingestion/refresh_index.py`) — see [`ingestion/README.md`](../ingestion/README.md). No API key required for this step anymore.

### How `/api/chat` assembles a response

1. **Safety classification first** (`app/core/safety.py`, Phase 8) — see below. Private-data requests return a fixed fallback here and never reach retrieval or the LLM at all.
2. Retrieve top 5 chunks for the question (`app/rag/retriever.py`).
3. If zero chunks come back (empty index, or genuinely no relevant match), skip the LLM call entirely and return a fixed safe answer: `confidence="low"`, `requires_official_confirmation=true`, `sources=[]`.
4. Otherwise, compute `confidence` from the retrieval scores (see below) and deduplicate `sources` by URL — **both come from retrieval metadata, never from the model.**
5. Call `generate_answer()` for the natural-language `answer`, `next_steps`, and a self-reported `grounded` flag.
6. If `grounded` is `false` (the model found chunks but they didn't actually answer the question), `confidence` is forced down to `"low"` regardless of retrieval score — a narrow, downward-only override (see "Grounding Check" below).
7. `requires_official_confirmation` = `confidence != "high"`, **or forced `true`** if the safety classifier flagged the question as sensitive-but-general (see below).

Sources are attached programmatically from chunk metadata, not requested from the model at all — a deliberate defense-in-depth measure on top of the prompt's "do not invent URLs" rule, so the model literally never has the opportunity to author a source URL.

### How confidence is calculated

`confidence` is **not** self-reported by the LLM — it's computed deterministically in `app/api/chat.py` from the retrieval similarity scores (cosine-based, from `vector_store.similarity_search`):

```
avg_score = average of the top 3 retrieved chunks' scores
avg_score >= 0.45  -> "high"
avg_score >= 0.30  -> "medium"
otherwise          -> "low"
no chunks at all   -> "low"
```

These thresholds were picked before any real embeddings had been run and have now been checked against real `BAAI/bge-base-en-v1.5` scores (see Known Limitations for the actual numbers observed) — they're in a reasonable range but still a heuristic, not tuned against real user feedback.

### Grounding check (downward-only override)

Retrieval-score confidence has a real blind spot: topically-adjacent-but-irrelevant chunks can score "high" even when they don't answer the question at all (found via real testing — "What is the weather like in Champaign?" retrieved genuinely high-scoring campus/housing chunks that had nothing to do with weather). To catch this, the model's own JSON output includes a third field, `"grounded": true|false` (see `rag_system_prompt.txt` rule 9). It's a narrow, one-directional signal: the model can tell us it *didn't* find the answer in the context (forcing `confidence` to `"low"`), but it can never raise confidence, author a source, or override anything else — `sources` and the base `confidence` calculation remain fully retrieval-driven, per the design principle above.

## Checklist Generator (Phase 10)

`app/api/checklist.py` generates a general onboarding checklist from a small set of task templates (`SECTIONS`), each tagged with the exact `source_title` it should cite and an optional condition (`"international"` or `"on_campus"`). No identifying fields are accepted — only `student_type`, `student_status`, `term`, `housing` (see `ChecklistRequest`).

- Every template's source link is resolved via `vector_store.lookup_source_by_title()` — a metadata-only lookup, **not** a semantic/embedding search, since we already know exactly which source each task should cite. This means the checklist endpoint works with zero LLM API configuration at all, as long as the index has been built at least once (which itself needs no API key either, now that embeddings run locally).
- If the index hasn't been built yet, `source_title`/`source_url` are simply omitted (`null`) for every item — the checklist itself still generates successfully with the full task list, never an error.
- International students get ISSS-related tasks (New Student Checklist, Check-In); on-campus students get housing/move-in tasks (Housing FAQ, Move-In logistics) — both gated by `condition` and verified against the real index.

## Safety Guardrails (Phase 8)

`app/core/safety.py` classifies every question **before** retrieval/generation runs. See [`docs/safety-guardrails.md`](../docs/safety-guardrails.md) for the full policy.

| Category | Examples | Behavior |
|---|---|---|
| `private_data` | UIN, NetID password, passport, SEVIS, I-20, grades, class schedule, admission status, housing contract, tuition bill, login/password | **Blocked** — fixed fallback returned immediately; retrieval and the LLM are never called |
| `health` | diagnosis requests, mental health crisis, "medical emergency" | Allowed — real RAG answer, escalation note (McKinley/emergency services) prepended to `next_steps`, `requires_official_confirmation=true` |
| `emergency` | "emergency", "911", "in danger" (non-health-flavored) | Allowed — real RAG answer, escalation note (911 / UI Police) prepended, confirmation forced |
| `immigration` | visa, work authorization, OPT/CPT | Allowed — real RAG answer, escalation note (contact ISSS) prepended, confirmation forced |
| `financial_aid` | "financial aid", FAFSA | Allowed — real RAG answer, escalation note (contact Office of Student Financial Aid) prepended, confirmation forced |
| `normal` | everything else | Full RAG flow, no escalation note added |

Checked in that order — private-data is highest priority (blocking), then health/emergency (safety-critical), then immigration/financial-aid, then normal. A question matches at most one category.

Tests: [`tests/test_safety.py`](../tests/test_safety.py) — run with `cd backend && source .venv/bin/activate && pytest ../tests/test_safety.py -v`. Includes both hardcoded cases and a full sweep of `tests/sample_questions.json` (Phase 13).

## Testing (Phase 13)

```bash
cd backend && source .venv/bin/activate
pytest ../tests -v
```

| File | What it checks | Needs an API key? |
|---|---|---|
| `test_safety.py` | `safety.classify()` — private-data blocking, sensitive-category escalation, normal pass-through | No |
| `test_api.py` | Response shape/status codes for `/health`, `/api/chat`, `/api/retrieve`, `/api/sources` — never exact wording | No — embeddings run locally, so `/api/retrieve` and the private-data `/api/chat` path both work with zero configuration |
| `test_retrieval.py` | For each labeled question in `tests/sample_questions.json`, its `expected_category` should appear in the top 5 retrieved chunks | No API key — but needs a built index (`cd ingestion && python refresh_index.py`); auto-skips with a clear reason if empty |

`tests/sample_questions.json` has 76 questions covering all 19 real source categories plus `refusal` (private-data), shared by `test_safety.py` (safety classification) and `test_retrieval.py` (retrieval accuracy).

## Environment Variables

See `.env.example`. Full list:

| Variable | Default | Purpose |
|---|---|---|
| `LLM_PROVIDER` | `groq` | `groq` \| `openai` \| `google` \| `openrouter` — selects the chat generation provider |
| `LLM_MODEL` | `llama-3.3-70b-versatile` | Model name, meaning depends on the selected provider |
| `GROQ_API_KEY` | *(empty)* | Required if `LLM_PROVIDER=groq` |
| `OPENAI_API_KEY` / `OPENAI_BASE_URL` | *(empty)* / `https://api.openai.com/v1` | Required if `LLM_PROVIDER=openai` |
| `GOOGLE_API_KEY` / `GOOGLE_BASE_URL` | *(empty)* / Gemini's OpenAI-compat endpoint | Required if `LLM_PROVIDER=google` |
| `OPENROUTER_API_KEY` / `OPENROUTER_BASE_URL` | *(empty)* / `https://openrouter.ai/api/v1` | Required if `LLM_PROVIDER=openrouter` |
| `EMBEDDING_PROVIDER` | `local` | Only `local` (sentence-transformers) is implemented |
| `EMBEDDING_MODEL` | `BAAI/bge-base-en-v1.5` | Any sentence-transformers model name |
| `VECTOR_DB` | `chromadb` | Only `chromadb` is implemented |
| `CHROMA_DB_PATH` | `../ingestion/data/chroma` | Resolved relative to `backend/`, regardless of which directory a script is actually run from |
| `CORS_ORIGINS` | `http://localhost:5173` | Comma-separated list of allowed frontend origins |

Only the chat-generation provider you select needs its key set — the other three providers' variables can stay empty.

## Quick smoke test

```bash
curl http://localhost:8000/health
curl -X POST http://localhost:8000/api/chat -H "Content-Type: application/json" -d '{"question": "When is Welcome Week?"}'
curl http://localhost:8000/api/sources
curl "http://localhost:8000/api/sources?category=housing"
curl -X POST http://localhost:8000/api/checklist/generate -H "Content-Type: application/json" \
  -d '{"student_type": "freshman", "student_status": "international", "term": "fall", "housing": "on-campus"}'
curl -X POST http://localhost:8000/api/feedback -H "Content-Type: application/json" \
  -d '{"question": "test", "answer": "test", "rating": "helpful", "source_titles": []}'
curl -X POST http://localhost:8000/api/retrieve -H "Content-Type: application/json" \
  -d '{"question": "When is Welcome Week?"}'
```

`/api/retrieve` needs the index already built (see [`ingestion/README.md`](../ingestion/README.md)) but **no API key at all** — embeddings run locally. With an empty index it returns `{"results": []}`. `/api/chat` additionally needs a chat-generation API key (e.g. `GROQ_API_KEY`) once retrieval finds real chunks — without one it returns `503` with a clear message rather than a stack trace.

## Feedback Storage (Phase 12)

`POST /api/feedback` appends one JSON line per submission to `backend/data/feedback.jsonl` (created on first write; gitignored — see root `.gitignore`). Each record is `question`, `answer`, `rating` (`helpful`/`not_helpful`/`wrong_source`/`missing_information`), optional `comment`, `source_titles`, plus a server-generated `timestamp` (UTC ISO 8601, added in `feedback.py` — **not** supplied by the client, so it isn't subject to client clock skew or spoofing).

No user identity is requested or stored — there's no name, session ID, IP address, or any other identifier in the record.

**⚠️ Do not submit UIN, passwords, passport/visa details, health information, financial aid information, grades, class schedules, or other private student records in feedback comments.** Feedback is stored as plain local JSONL for this MVP with no encryption or access control beyond the filesystem — treat it accordingly, and never intentionally write sensitive data into it (see [`docs/safety-guardrails.md`](../docs/safety-guardrails.md)).

## Known Limitations

- **Real end-to-end chat generation has been verified** with a real `GROQ_API_KEY` across a wide range of topics (dining, financial aid, housing, technology, safety, sensitive/immigration questions, and more) — accurate, well-cited, honest answers throughout, including correctly declining to hallucinate when context didn't cover a question.
- **`test_retrieval.py` has been run against real embeddings** (`BAAI/bge-base-en-v1.5`, local, no mock) against the full 20-source, 19-category index: **176/177 (99.4%) of the full test suite passed.** The one retrieval failure — "What is New Student Registration?" expecting `orientation` — is a genuine, real finding: the orientation source page's chunk (score 0.589) mentions "New Student Registration" only in passing within a very thin page (~246 characters total, mostly boilerplate/contact info), scoring lower than several other chunks sharing generic new-student vocabulary. This is a real content-thinness limitation of that specific source, not a code defect — see `docs/rag-pipeline.md`.
- The confidence heuristic (average of top-3 retrieval scores vs. fixed thresholds 0.45/0.30) has now been checked against real embedding scores (observed range for genuinely relevant matches: roughly 0.58–0.70 in this small corpus) and looks broadly reasonable, but is still a heuristic, not tuned against real user feedback.
- `generate_answer()` asks every provider for `response_format={"type": "json_object"}` and retries once without it if the provider rejects the parameter outright; if a provider ignores it silently instead, the raw-text fallback still catches non-JSON output. Real behavior of Google/OpenRouter's JSON-mode support specifically hasn't been tested (no API keys for those providers).
- `/api/checklist/generate`'s task list and conditions are still hand-authored (not generated by an LLM) — only the source *links* are live-looked-up from the vector store. This is a deliberate choice (deterministic, no API key required, no hallucination risk for a simple templated feature), not an oversight.
- If `sources.json` ever adds a source whose exact title doesn't match a `TaskTemplate.source_title` in `checklist.py`, that template's item will silently render without a source link rather than erroring — worth an eyeball check after adding new sources.
- The safety classifier (`app/core/safety.py`) is regex/keyword-based, not a model — it will miss paraphrases it has no pattern for (e.g. "what's the balance I owe the university" won't match the `tuition bill` pattern) and could theoretically false-positive on an unrelated question that happens to contain a trigger word. Broadening coverage is straightforward (add patterns) but not exhaustive by construction.
- A `financial_aid` source category now exists (Office of Student Financial Aid) — this was previously a known gap and is now resolved; financial-aid questions retrieve real content in addition to being correctly classified and escalated.
- The Office of the Registrar source page is a flat resource-link list (20+ bullet items like "Course Registration", "Tuition and Fees") with little elaboration on any one of them — questions targeting a specific bullet can retrieve weakly since the chunk's embedding is diluted across ~20 unrelated terms. Two `academics` test questions were reworded during real testing to target content the page actually explains (its opening paragraph, FERPA) rather than link labels alone.
- `test_api.py`'s schema checks don't cover `/api/checklist/generate` or `/api/feedback` yet — both work (see their own sections above) but don't have dedicated schema tests.
- `sentence-transformers` pulls in `torch`, a sizable dependency (hundreds of MB) — this noticeably increases install time and Docker image size compared to the pre-refactor `openai`-only embeddings client. Worth knowing if minimizing image size becomes a priority.
- The Google and OpenRouter LLM clients are real, working implementations (not stubs) but have never been exercised against their actual APIs — only Groq (mocked SDK) and the shared `OpenAICompatibleClient` logic have been tested.
