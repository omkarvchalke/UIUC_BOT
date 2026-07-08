# RAG Pipeline

This document explains how CampusGuide AI turns curated public webpages into cited, grounded answers.

## 1. Source Curation

Public UIUC webpages are curated by hand into `ingestion/sources.json`. Each entry includes a `title`, `category`, `department`, `url`, and `source_type`. Only `official_public_webpage` entries are fetched — no login-protected systems, no scraping outside the curated list.

Categories actually present in `sources.json` (20 sources, 19 categories): `orientation`, `welcome_week`, `housing`, `move_in`, `international`, `icard`, `transportation`, `health`, `accessibility`, `dining`, `academics`, `technology`, `library`, `recreation`, `safety`, `counseling`, `parking`, `financial_aid`, `student_life`.

## 2. Fetching (`ingestion/fetch_pages.py`)

- Reads `sources.json`.
- Fetches each URL with a descriptive, honest user-agent and a request timeout.
- Saves raw HTML to `ingestion/data/raw/` and metadata (title, URL, category, department, crawled timestamp) alongside it.
- Failures (timeouts, 404s, etc.) are logged and skipped — a single bad URL never blocks the rest of the pipeline.

## 3. Cleaning (`ingestion/clean_text.py`)

- **Primary extraction:** [trafilatura](https://trafilatura.readthedocs.io/), which uses text-density heuristics to find main content. This matters in practice — several UIUC pages don't wrap nav menus in semantic `<nav>`/`<footer>` tags, so naive tag-stripping alone leaves mostly menu-link junk.
- **Fallback:** if trafilatura returns fewer than 200 characters, falls back to a manual BeautifulSoup pass that strips `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, `<aside>`, `<noscript>`, `<form>`, `<iframe>`, `<svg>`.
- Either way, output is normalized (blank lines stripped, repeated blank lines collapsed) and saved to `ingestion/data/processed/`, one file per source, metadata preserved.

## 4. Chunking (`ingestion/chunk_text.py`)

- Splits cleaned text into chunks of roughly 500–800 tokens (character-length approximation), with ~100 token overlap between consecutive chunks to preserve context across boundaries.
- Every chunk carries: `chunk_id`, `document_id`, `source_title`, `source_url`, `category`, `department`, `chunk_text`, `chunk_index`, `created_at`.
- All chunks are appended to `ingestion/data/chunks/chunks.jsonl`.

## 5. Embedding + Vector Storage (`ingestion/embed_chunks.py`, `backend/app/rag/vector_store.py`)

- Reads `chunks.jsonl`.
- Generates embeddings **locally** via `sentence-transformers` (default model `BAAI/bge-base-en-v1.5`, configured via `EMBEDDING_MODEL`) — no API key, no network call after the model's first download, no per-token cost.
- Adds chunk text + metadata + embeddings into a persistent local ChromaDB collection (`vector_store.add_documents()`, path via `CHROMA_DB_PATH`).
- `refresh_index.py` runs fetch → clean → chunk → embed as a single command, so the whole index can be rebuilt from scratch at any time — with no API key required for any of the four steps.

## 6. Retrieval (`backend/app/rag/retriever.py`, `POST /api/retrieve`)

- Embeds the user's question locally, with the same embedding model used at index time.
- Queries ChromaDB (`vector_store.similarity_search()`) for the top-k (default 5) most similar chunks.
- Returns chunk text plus full source metadata (title, URL, category, department) and a similarity score.
- Because embeddings are local, `POST /api/retrieve` works with **zero API configuration** — only chat generation (step 7) needs a real LLM key.

## 7. Generation (`backend/app/rag/prompt_builder.py`, `generator.py`, `POST /api/chat`, `POST /api/chat/stream`)

- The question first passes through the safety classifier (`core/safety.py`). `private_data` requests short-circuit with a fixed safe fallback before any retrieval or generation happens — zero embedding/LLM calls.
- For allowed questions, `prompt_builder.py` assembles chat-completion messages: a system message built from `rag_system_prompt.txt` (rules 1-8, no `{question}`/`{context}` placeholders in it) plus a format-specific suffix, any prior conversation turns (`ChatRequest.history`, capped at 20), and a user message containing a numbered context block built from the retrieved chunks plus the current question.
- The prompt instructs the model to: use only the provided context, never invent policies/dates/URLs, and never mention specific URLs at all (sources are shown to the user separately, not authored by the model).
- `generator.py` asks `app/llm/provider_factory.py` for the configured provider's client (Groq by default; also supports OpenAI, Google Gemini, or OpenRouter via `LLM_PROVIDER`) and exposes three entry points:
  - `generate_answer()` — used by `POST /api/chat`. Calls the provider in JSON mode (`response_format={"type": "json_object"}`, with an automatic retry without it if the provider rejects the parameter), parsing `{"answer": str, "next_steps": [str], "grounded": bool}` — falling back to raw text as the answer if the model returns non-JSON.
  - `generate_answer_stream()` / `generate_metadata()` — used together by `POST /api/chat/stream`. JSON mode and token-by-token streaming don't mix well (a client can't usefully render partial JSON), so streaming is split into two calls: a plain-text streaming call for the answer (`prompt_builder.build_stream_messages()`, `PLAIN_TEXT_INSTRUCTION`), then once the full answer text is known, a small non-streaming JSON call (`generate_metadata()`) that reuses the same context plus the already-streamed answer to get just `next_steps`/`grounded`. If that second call fails, the streamed answer is kept and `next_steps`/`grounded` fall back to defaults rather than erroring the whole response.
  - **`sources` and `confidence` are never requested from the model at all**, on either path — they're computed by `app/api/chat.py` from retrieval metadata (see below), a deliberate defense-in-depth measure beyond just the prompt rule.
- **Follow-up questions**: `app/api/chat.py::_build_retrieval_query()` prepends the most recent user turn from `history` onto the current question before retrieval — a cheap heuristic so a short follow-up like "What about for graduate students?" still retrieves relevant chunks, without a separate query-rewriting LLM call. The full `history` is also passed into the prompt so the model sees the actual conversation, not just the augmented retrieval query.

## 8. Confidence Scoring

Confidence is **not** self-reported by the LLM — it's computed deterministically in `app/api/chat.py` from the retrieval similarity scores (`vector_store.similarity_search()`'s cosine-based score):

```text
avg_score = average of the top 3 retrieved chunks' scores
avg_score >= 0.45  → "high"
avg_score >= 0.30  → "medium"
otherwise          → "low"
zero chunks at all → "low" (skips generation entirely)
```

These thresholds were picked before any real embeddings had been run. They've since been checked against a real local index (`BAAI/bge-base-en-v1.5`) via `test_retrieval.py`: genuinely relevant matches in this small corpus scored roughly 0.58–0.70, so the 0.45/0.30 cutoffs are in a sane range, though still a heuristic rather than tuned against real user feedback. `requires_official_confirmation` is `true` whenever confidence isn't `"high"`, **or** whenever the safety classifier flagged the question as sensitive-but-allowed (health/emergency/immigration/financial_aid) — regardless of confidence.

## Evaluation Approach

`tests/sample_questions.json` contains 76 labeled questions across all 19 real source categories plus a `refusal` (private-data) category, each tagged `type: "normal" | "sensitive" | "private_data"`. `tests/test_retrieval.py` checks that, for each non-refusal question, its expected category appears among the top 5 retrieved chunks — it auto-skips (not fails) if no vector index is built, and needs no API key at all since embeddings are local. **Run for real against a genuine local index: 176/177 passed (99.4%)** across the full suite. The one retrieval miss — "What is New Student Registration?" expecting `orientation` — is a real, documented finding: that source page's content is only ~246 characters, mostly boilerplate, mentioning "New Student Registration" just once in passing, so it scores lower (0.589) than several other chunks sharing generic new-student vocabulary. This reflects thin source content, not a retrieval bug. (A similar issue on the Office of the Registrar page — a flat 20-item resource-link list with no elaboration — was caught the same way while adding the `academics` category; two of three test questions had to be reworded to match content the page actually explains, rather than link labels alone.) `tests/test_safety.py` sweeps the same dataset to check that `private_data` questions are always blocked and `sensitive` questions always carry an escalation note. `tests/test_api.py` checks response shapes for `/health`, `/api/chat`, `/api/chat/stream`, `/api/retrieve`, and `/api/sources` without asserting exact LLM wording. Together these give a lightweight, repeatable way to catch retrieval regressions, guardrail regressions, and schema breaks as the source list and prompt evolve.

## 9. Grounding Check

Since retrieval-score confidence can be high even when the retrieved chunks don't actually contain the answer (e.g. topically-adjacent-but-irrelevant chunks), the model's JSON output includes a third field, `"grounded": true|false`, alongside `answer` and `next_steps` (see `JSON_MODE_INSTRUCTION` in `prompt_builder.py`; on the streaming path this comes from the separate `generate_metadata()` call instead, see above). This is a narrow, downward-only signal — the model can tell `app/api/chat.py` that the context didn't actually answer the question (forcing `confidence` to `"low"` and `requires_official_confirmation` to `true`), but it can never raise confidence or claim something it isn't. Found and fixed via real testing: a question like "What is the weather like in Champaign?" was retrieving topically-related-but-irrelevant chunks (all about campus/housing) that scored high on cosine similarity despite not answering the question at all — `grounded` catches exactly this case.
