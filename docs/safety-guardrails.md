# Safety Guardrails

CampusGuide AI is scoped tightly to be a **public-information-only** assistant. This document is the source of truth for what it will and will not do.

## Scope Boundary

CampusGuide AI only answers from public university webpages curated in `ingestion/sources.json`. It never accesses Canvas, Banner, student portals, email, or any login-protected system.

## Data It Must Never Request, Collect, Store, or Process

- UIN
- NetID password
- Passport number
- SEVIS ID
- I-20 details
- Visa document numbers
- Health records
- Immunization records
- Financial aid details
- Tuition bill details
- Grades
- Class schedules
- Admission record details
- Housing contract details
- Any other private student record

## Behavioral Boundaries

CampusGuide AI must not:

- Claim to be an official UIUC service
- Use UIUC logos, Block I, official wordmarks, or official-looking branding
- Give immigration, legal, medical, financial, academic-record, or emergency advice
- Make official decisions or eligibility determinations for students
- Ask students to provide private student information

## Guardrail Implementation (`backend/app/core/safety.py`)

Every incoming question is classified before retrieval/generation runs:

| Classification (`category`) | Examples | Behavior |
|---|---|---|
| `private_data` | UIN, NetID password, passport, SEVIS, I-20, admission status, grades, schedule, tuition bill, housing contract access, login/password | Return safe fallback immediately. **No embedding or LLM call is made at all.** |
| `health` | Diagnosis requests, mental health crisis, "medical emergency" | Real RAG answer still generated; health/emergency-services escalation note prepended to `next_steps`; official confirmation always required. |
| `emergency` | "emergency", "911", "in danger" (non-health-flavored) | Same as above, with a 911/UI Police escalation note. |
| `immigration` | Visa, work authorization, OPT/CPT | Same as above, with an ISSS escalation note. |
| `financial_aid` | "financial aid", FAFSA | Same as above, with an Office of Student Financial Aid escalation note. |
| `normal` | Orientation, Welcome Week, housing, move-in, i-card, transportation, accessibility, etc. | Full RAG pipeline runs normally, no escalation note added. |

Checked in that priority order — `private_data` first (blocking), then `health`/`emergency` (safety-critical), then `immigration`/`financial_aid`, then `normal`. A question matches at most one category.

### Safe Fallback Responses

**Private student record request:**

> I cannot access private student systems or student records. I can only provide general information from public sources. Please use the official university portal or contact the relevant office.

**Immigration-specific request:**

> I can provide general public information, but immigration and work authorization questions depend on your individual situation. Please contact ISSS for official guidance.

**Health-specific request:**

> I can summarize public health resource information, but I cannot provide medical advice. Please contact McKinley Health Center or emergency services if urgent.

**Financial aid request:**

> I can share general public information about financial aid programs, but I cannot access or determine your individual award, bill, or eligibility. Please contact the Office of Student Financial Aid for official guidance.

**Emergency (non-health-flavored):**

> If this is an emergency, please contact 911 or the University of Illinois Police (217-333-1216) immediately. I can only provide general public information and cannot help in real time.

## Prompt-Level Guardrails

The system prompt (`backend/app/prompts/rag_system_prompt.txt`) additionally instructs the model to:

1. Use only the retrieved context provided.
2. Never invent policies, dates, deadlines, requirements, office contacts, or URLs.
3. Never claim to be an official university service.
4. Never ask for or process private student data.
5. For immigration/legal/medical/financial-aid/emergency/admission/housing-contract/academic-record questions, give general information only and recommend contacting the relevant office.
6. State explicitly when the retrieved context is insufficient rather than guessing.
7. **Never mention specific URLs in the answer or next steps at all** — sources are shown to the user separately (as structured data, not model-authored text), and the model has no channel through which to surface a URL of its own even if it wanted to. This is defense-in-depth beyond rule 2: `sources` in the API response are computed programmatically from retrieval metadata, never parsed out of the model's output.

## UI-Level Guardrails

- **Disclaimer banner** (landing page + chat page): states the project is unofficial and not affiliated with, endorsed by, or operated by UIUC.
- **Privacy banner** (near chat input): warns users not to enter UIN, passwords, passport details, visa document numbers, health information, financial aid information, grades, class schedules, or other private student records.
- The Checklist feature (Phase 10) only collects non-identifying fields (student type, status, term, housing preference) — never name, UIN, NetID, password, or visa document details.

## Testing

`tests/test_safety.py` exercises the classifier and fallback responses against a library of private-data and sensitive-topic questions (see `tests/sample_questions.json`, `type: "private_data"` / `"sensitive"` entries) to ensure guardrails hold as the app evolves.

## Feedback Logging Boundary

`POST /api/feedback` stores question, answer, rating, optional comment, source titles, and timestamp only — no user identity is required or requested, and comments should not intentionally contain sensitive data (see root README).
