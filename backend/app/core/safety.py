"""Privacy and sensitive-topic guardrails for CampusGuide AI.

Runs before retrieval/generation on every /api/chat request. Private-data
requests are intercepted here and never reach embeddings or the LLM at
all — see app/api/chat.py. Sensitive-but-general topics (immigration,
health, financial aid, emergency) are allowed through to the normal RAG
flow, but the caller attaches an office-escalation next step and forces
requires_official_confirmation.

See docs/safety-guardrails.md for the full policy this implements.
"""
import re
from dataclasses import dataclass
from typing import Literal, Optional

SafetyCategory = Literal[
    "private_data", "immigration", "health", "financial_aid", "emergency", "normal"
]


@dataclass(frozen=True)
class SafetyClassification:
    category: SafetyCategory
    is_blocked: bool  # True => return fallback immediately; retrieval/LLM are never called
    escalation_note: Optional[str]  # None only for "normal"


GENERIC_PRIVATE_DATA_FALLBACK = (
    "I cannot access private student systems or student records. I can only provide "
    "general information from public sources. Please use the official university portal "
    "or contact the relevant office."
)

IMMIGRATION_ESCALATION = (
    "I can provide general public information, but immigration and work authorization "
    "questions depend on your individual situation. Please contact ISSS for official guidance."
)

HEALTH_ESCALATION = (
    "I can summarize public health resource information, but I cannot provide medical advice. "
    "Please contact McKinley Health Center or emergency services if urgent."
)

FINANCIAL_AID_ESCALATION = (
    "I can share general public information about financial aid programs, but I cannot access "
    "or determine your individual award, bill, or eligibility. Please contact the Office of "
    "Student Financial Aid for official guidance."
)

EMERGENCY_ESCALATION = (
    "If this is an emergency, please contact 911 or the University of Illinois Police "
    "(217-333-1216) immediately. I can only provide general public information and cannot "
    "help in real time."
)

# Requests for access to a specific student's private record. These can never
# be answered by a public-source RAG system, so they're blocked before
# retrieval/generation is even attempted — no exceptions.
PRIVATE_DATA_PATTERNS = [
    r"\buin\b",
    r"\bpassword\b",
    r"passport number",
    r"\bpassport\b",
    r"\bsevis\b",
    r"\bi-?20\b",
    r"\bgrades?\b",
    r"\bgpa\b",
    r"class schedule",
    r"my schedule",
    r"admission status",
    r"application status",
    r"housing contract",
    r"tuition bill",
    r"account balance",
    r"\bnetid\b.*\baccount\b",
]

# Sensitive but generally-answerable topics, checked in this order
# (most safety-critical first). A question can only land in one bucket.
HEALTH_PATTERNS = [
    r"diagnos",
    r"mental health",
    r"suicid",
    r"self-?harm",
    r"\bdepress",
    r"anxiety",
    r"medical advice",
    r"medical emergency",
    r"\bsymptoms?\b",
]

EMERGENCY_PATTERNS = [
    r"\bemergency\b",
    r"\b911\b",
    r"in danger",
    r"life[- ]threatening",
]

IMMIGRATION_PATTERNS = [
    r"\bvisa\b",
    r"work authorization",
    r"work permit",
    r"\bopt\b",
    r"\bcpt\b",
    r"\bimmigration\b",
    r"i-?20 eligib",
]

FINANCIAL_AID_PATTERNS = [
    r"financial aid",
    r"\bfafsa\b",
]


def _matches_any(patterns: list[str], text: str) -> bool:
    return any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns)


def classify(question: str) -> SafetyClassification:
    """Classify a question before it reaches retrieval/generation.

    Order matters: private-data (blocking) is checked first, then the
    sensitive-but-allowed categories in order of safety priority
    (health/emergency before immigration/financial aid), then normal.
    """
    text = question.lower()

    if _matches_any(PRIVATE_DATA_PATTERNS, text):
        return SafetyClassification("private_data", True, GENERIC_PRIVATE_DATA_FALLBACK)

    if _matches_any(HEALTH_PATTERNS, text):
        return SafetyClassification("health", False, HEALTH_ESCALATION)

    if _matches_any(EMERGENCY_PATTERNS, text):
        return SafetyClassification("emergency", False, EMERGENCY_ESCALATION)

    if _matches_any(IMMIGRATION_PATTERNS, text):
        return SafetyClassification("immigration", False, IMMIGRATION_ESCALATION)

    if _matches_any(FINANCIAL_AID_PATTERNS, text):
        return SafetyClassification("financial_aid", False, FINANCIAL_AID_ESCALATION)

    return SafetyClassification("normal", False, None)
