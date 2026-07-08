# Demo Script

A ~5 minute walkthrough for showing CampusGuide AI in an interview or portfolio review.

**Before demoing:** run `cd ingestion && python refresh_index.py` at least once to build the vector index (no API key needed — embeddings run locally), start the backend (`cd backend && uvicorn app.main:app --reload`) with a real `GROQ_API_KEY` in `backend/.env` (free at console.groq.com/keys), then start the frontend (`cd frontend && npm run dev`). Without a real chat-generation key, `/api/chat` returns a clear `503` instead of an answer once it finds real chunks — fine for showing the error handling, not for the rest of this script. `/api/retrieve` works either way, since it never needs an LLM key.

## 1. Landing Page

- Open the Home page.
- Point out the project title/subtitle, the unofficial disclaimer, and the privacy warning.
- Highlight the four feature cards: Ask questions, Get source-cited answers, Generate general checklist, Find correct office/resource.

**Talking point:** "This is explicitly scoped as an unofficial, student-built project — it only reads public webpages and never touches private student data or login-protected systems."

## 2. Ask a Welcome Week Question

- Go to the Chat page.
- Ask: **"When is Welcome Week?"**
- Show the answer, the source card(s) linking back to the official `newstudent.illinois.edu` page, the confidence badge, and next steps.

**Talking point:** "Every answer is grounded in retrieved chunks from curated public pages — nothing is invented, and you can always click through to the source."

## 3. Ask a Housing Question

- Ask: **"Do first-year students have to live on campus?"**
- Show retrieval pulling from the University Housing FAQ.

## 4. Ask an International Student Question

- Ask: **"What is international student check-in?"**
- Show the answer citing ISSS pages, and note the general-info framing rather than individualized advice.

## 5. Ask a Private-Data Question (Guardrail Demo)

- Ask: **"Can you check my admission status?"**
- Show the safe fallback response and explain that this is intercepted by the safety classifier *before* any LLM call — no private data is requested or processed.

**Talking point:** "This is the guardrail layer — sensitive or private-record questions never reach the model ungated. They're classified and redirected to the right office."

## 6. Generate a Checklist

- Go to the Checklist page.
- Select: Freshman / International / Fall / On-campus.
- Generate and show the sectioned checklist (Before Arrival, Before Classes Start, Move-In Week, First Week, First Month) with source links, and note it required zero personal-identifying input.

## 7. Show the Source Library

- Go to the Sources page.
- Filter by category (e.g., `international`).
- Emphasize transparency: every answer traces back to a specific, browsable public source.

## Closing Talking Point

"The whole system — ingestion, chunking, embeddings, retrieval, generation, and guardrails — is built to be provider-agnostic (any OpenAI-compatible endpoint) and privacy-first by construction, not as an afterthought."
