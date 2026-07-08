# API Specification

Base URL (local dev): `http://localhost:8000`

All request/response bodies are JSON. All endpoints are implemented with FastAPI + Pydantic models (`backend/app/models/schemas.py`), and interactive docs are available at `/docs` (Swagger UI) and `/redoc`.

---

## `GET /health`

Health check.

**Response `200`**

```json
{
  "status": "healthy",
  "service": "campusguide-ai-backend"
}
```

---

## `POST /api/chat`

Ask a question and receive a cited, safety-checked answer.

**Request**

```json
{
  "question": "When is Welcome Week?",
  "history": [
    { "role": "user", "content": "Do first-year students have to live on campus?" },
    { "role": "assistant", "content": "Yes, first-year undergraduates are generally required to live in university housing..." }
  ]
}
```

`history` is optional (defaults to `[]`) and capped at 20 turns. Each turn's `role` is `"user"` or `"assistant"`. Pass the running conversation so far to get follow-up-aware answers — e.g. "What about for graduate students?" resolves correctly against the prior turn above. The most recent user turn in `history` is also concatenated onto the current question for retrieval, so short follow-ups still retrieve relevant chunks without a separate query-rewriting call.

**Response `200`**

```json
{
  "answer": "Welcome Week is listed as...",
  "sources": [
    {
      "title": "Welcome Week",
      "url": "https://newstudent.illinois.edu/orientation/welcomeweek",
      "category": "welcome_week",
      "department": "New Student & Family Experiences"
    }
  ],
  "confidence": "high",
  "next_steps": [
    "Review the official Welcome Week page for schedule updates."
  ],
  "requires_official_confirmation": false
}
```

`confidence` is one of `"high" | "medium" | "low"`. Sources are deduplicated by URL.

---

## `POST /api/chat/stream`

Same inputs and semantics as `POST /api/chat` (including `history`), but streams the answer token-by-token as [Server-Sent Events](https://developer.mozilla.org/en-US/docs/Web/API/Server-sent_events) instead of waiting for the full answer. Used by the Chat UI so responses render incrementally like a typical chat product.

**Request** — identical shape to `POST /api/chat`.

**Response `200`**, `Content-Type: text/event-stream`. Body is a sequence of `data: <json>\n\n` frames:

```
data: {"type": "delta", "text": "Welcome"}

data: {"type": "delta", "text": " Week"}

data: {"type": "delta", "text": " is..."}

data: {"type": "done", "sources": [...], "confidence": "high", "next_steps": [...], "requires_official_confirmation": false}
```

- **`delta`** events carry one chunk of the answer's plain text each, in order — concatenate `text` across all `delta` events to reconstruct the full answer. Sent as they arrive from the LLM provider.
- **`done`** is always the final event on success. It carries the same `sources` / `confidence` / `next_steps` / `requires_official_confirmation` fields as `ChatResponse`, computed the same way as `/api/chat` (never trusted from the model — see `docs/rag-pipeline.md`), once the full answer is known.
- **`error`** (`{"type": "error", "detail": "..."}`) can appear instead of `done` if generation fails mid-stream (e.g. a rate limit or missing API key). It's an SSE event rather than an HTTP error status because the `200` response and headers are already sent by the time a stream can fail — the status code can't change anymore. A client should treat an `error` event as terminal.

Internally this makes two LLM calls: a streaming plain-text call for the answer, then a small non-streaming JSON call for `next_steps`/`grounded` once the answer is complete (JSON mode and token streaming don't mix well — see `app/rag/prompt_builder.py`). If that second call fails, the already-streamed answer is kept and `next_steps`/confidence just fall back to defaults rather than the whole response erroring out.

---

## `POST /api/retrieve`

Return the raw top-k retrieved chunks for a question, without LLM generation. Useful for debugging retrieval quality.

**Request**

```json
{
  "question": "Do freshmen have to live on campus?"
}
```

**Response `200`**

```json
{
  "results": [
    {
      "chunk_text": "All first-year students...",
      "source_title": "University Housing New Resident FAQ",
      "source_url": "https://www.housing.illinois.edu/Apply/New-Resident/FAQ",
      "category": "housing",
      "department": "University Housing",
      "score": 0.91
    }
  ]
}
```

Returns the top 5 chunks by default.

---

## `GET /api/sources`

Return the full curated source list with metadata, for the Source Library page.

**Response `200`**

```json
{
  "sources": [
    {
      "title": "New Student Orientation",
      "category": "orientation",
      "department": "New Student & Family Experiences",
      "url": "https://newstudent.illinois.edu/orientation",
      "source_type": "official_public_webpage"
    }
  ]
}
```

Supports optional `?category=` query parameter to filter.

---

## `POST /api/checklist/generate`

Generate a general onboarding checklist. Collects only non-identifying fields.

**Request**

```json
{
  "student_type": "freshman",
  "student_status": "international",
  "term": "fall",
  "housing": "on-campus"
}
```

- `student_type`: `"freshman" | "transfer" | "graduate"`
- `student_status`: `"domestic" | "international"`
- `term`: `"fall" | "spring"`
- `housing`: `"on-campus" | "off-campus" | "not sure"`

**Response `200`**

```json
{
  "disclaimer": "This is a general checklist based on public sources. Check official pages for your individual situation.",
  "sections": [
    {
      "title": "Before Arrival",
      "items": [
        {
          "task": "Review New Student Orientation information.",
          "source_title": "New Student Orientation",
          "source_url": "https://newstudent.illinois.edu/orientation"
        }
      ]
    }
  ]
}
```

Sections returned: `Before Arrival`, `Before Classes Start`, `Move-In Week`, `First Week`, `First Month`.

---

## `POST /api/feedback`

Log lightweight feedback on an answer. No user identity required.

**Request**

```json
{
  "question": "When is Welcome Week?",
  "answer": "Welcome Week is...",
  "rating": "helpful",
  "comment": "Clear answer",
  "source_titles": ["Welcome Week"]
}
```

- `rating`: `"helpful" | "not_helpful" | "wrong_source" | "missing_information"`
- `comment`: optional string

**Response `200`**

```json
{
  "status": "received"
}
```

Feedback is appended to a local JSONL file (`backend/data/feedback.jsonl`) for MVP purposes — one JSON line per submission, with a server-generated `timestamp` (UTC ISO 8601) added on write; the client never supplies it. See `docs/safety-guardrails.md` for the storage boundary.

---

## Error Handling

- **`422`** — standard FastAPI/Pydantic validation errors for malformed requests (e.g. an empty `question`).
- **`503`** — `/api/chat` returns this with `{"detail": "GROQ_API_KEY is not set..."}` (or the equivalent for `OPENAI_API_KEY`/`GOOGLE_API_KEY`/`OPENROUTER_API_KEY`, depending on `LLM_PROVIDER`) once retrieval finds real chunks to generate an answer from. This is a deliberate, actionable error — never a raw stack trace. `/api/retrieve` essentially never hits this, since embeddings run locally with no API key at all — it would only apply if `EMBEDDING_PROVIDER`/`VECTOR_DB` were misconfigured to an unimplemented value.
- **Empty retrieval is not an error** — `/api/retrieve` returns `{"results": []}` and `/api/chat`/`/api/chat/stream` return a normal `200` with a safe "insufficient context" answer (`confidence: "low"`, `requires_official_confirmation: true`) if the vector index has no chunks yet — no LLM call is attempted in that case either.
- **`/api/chat/stream` never returns a `503`** — once the `200` streaming response starts, a config or provider failure is instead sent as a terminal `{"type": "error", "detail": "..."}` SSE event (see above), since the HTTP status can no longer change after headers are sent.
- **Private-data questions never reach the LLM** — `/api/chat` returns `200` with the safety fallback (see `docs/safety-guardrails.md`) even with zero API configuration, since the safety classifier runs before any embedding/LLM call.
