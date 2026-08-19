import pytest

from app.core.config import get_settings
from app.graph.generation import ExtractiveAnswerGenerator
from app.graph.generation_router import RoutingAnswerGenerator
from app.graph.state import RetrievedChunkState
from app.llm.groq_answer_generator import GroqAnswerGenerator

pytestmark = pytest.mark.skipif(
    not get_settings().groq_api_key, reason="GROQ_API_KEY not configured"
)


def _router() -> RoutingAnswerGenerator:
    return RoutingAnswerGenerator(
        extractive=ExtractiveAnswerGenerator(), groq=GroqAnswerGenerator()
    )


async def test_interpreter_request_now_gets_a_grounded_answer() -> None:
    # Confirmed real, live during the content-coverage-gap audit: this DRES page scores below
    # min_rerank_score even under its correct topic, so ExtractiveAnswerGenerator alone returns
    # "I couldn't find anything" despite the page directly answering the question.
    chunk: RetrievedChunkState = {
        "chunk_id": "11111111-1111-1111-1111-111111111111",
        "document_id": "22222222-2222-2222-2222-222222222222",
        "content": (
            "If you possess a Usked account for regular requests, please log in to submit a new "
            "request specifically for registered DRES students and U. of I. faculty/staff. Our "
            "staff will follow up if further details are needed, and you will receive email "
            "notifications upon request fulfillment. If you do not have a Usked account, kindly "
            "email us for Interpreting or Live Captioning services and we will help you set up "
            "an account to make your requests."
        ),
        "title": "Interpreting and Live Captioning – DRES",
        "url": "https://dres.illinois.edu/accommodations/interpreting-and-live-captioning/",
        "department": "Disability Resources and Educational Services",
        "topic": "accessibility_disability_support",
        "fused_score": 1.0,
        "rerank_score": -1.37,
    }

    result = await _router().generate(
        "How do I request an interpreter for a lecture?",
        [chunk],
        context=f"[1] {chunk['title']} ({chunk['department']}):\n{chunk['content']}",
        history=[],
        student_type=None,
    )

    assert result.grounded is True
    assert len(result.text) > 0


async def test_academic_probation_question_now_gets_a_grounded_answer() -> None:
    # Same shape as above -- Student Code 3-110 scores below min_rerank_score even under its
    # correct topic (registration_records).
    chunk: RetrievedChunkState = {
        "chunk_id": "33333333-3333-3333-3333-333333333333",
        "document_id": "44444444-4444-4444-4444-444444444444",
        "content": (
            "Students are considered in Good Academic Standing when they meet or exceed all "
            "required university and program-specific grade point averages (GPAs) as well as "
            "other academic program-specific requirements. Students who are not in Good "
            "Academic Standing are considered in Academic Warning status. When students are "
            "placed on Academic Warning status, they receive notice from their college, "
            "division, or school that describes the reason(s) the student is on Academic "
            "Warning and requirements needing to be met to return to Good Academic Standing."
        ),
        "title": "Academic Standing Rules (Student Code 3-110)",
        "url": "https://studentcode.illinois.edu/article3/part1/3-110",
        "department": "Office of the Registrar",
        "topic": "registration_records",
        "fused_score": 1.0,
        "rerank_score": -1.89,
    }

    result = await _router().generate(
        "What GPA counts toward academic probation?",
        [chunk],
        context=f"[1] {chunk['title']} ({chunk['department']}):\n{chunk['content']}",
        history=[],
        student_type=None,
    )

    assert result.grounded is True
    assert len(result.text) > 0


async def test_comparison_query_synthesizes_across_two_chunks() -> None:
    chunks: list[RetrievedChunkState] = [
        {
            "chunk_id": "55555555-5555-5555-5555-555555555555",
            "document_id": "66666666-6666-6666-6666-666666666666",
            "content": (
                "The ARC (Activities & Recreation Center) is open 24 hours a day, 7 days a week."
            ),
            "title": "ARC Facilities",
            "url": "https://campusrec.illinois.edu/facilities",
            "department": "Campus Recreation",
            "topic": "campus_recreation",
            "fused_score": 1.0,
            "rerank_score": 3.0,
        },
        {
            "chunk_id": "77777777-7777-7777-7777-777777777777",
            "document_id": "88888888-8888-8888-8888-888888888888",
            "content": "CRCE is open Monday through Friday from 6:00 AM to 11:00 PM.",
            "title": "CRCE Hours",
            "url": "https://campusrec.illinois.edu/facilities",
            "department": "Campus Recreation",
            "topic": "campus_recreation",
            "fused_score": 1.0,
            "rerank_score": 2.5,
        },
    ]

    result = await _router().generate(
        "What's the difference between the ARC and CRCE recreation facilities?",
        chunks,
        context=(
            f"[1] {chunks[0]['title']} ({chunks[0]['department']}):\n{chunks[0]['content']}\n\n"
            f"[2] {chunks[1]['title']} ({chunks[1]['department']}):\n{chunks[1]['content']}"
        ),
        history=[],
        student_type=None,
    )

    assert result.grounded is True
    assert len(result.text) > 0
