import pytest

from app.core.config import get_settings
from app.llm.query_decomposition import LlmQueryDecomposer

pytestmark = pytest.mark.skipif(
    not get_settings().groq_api_key, reason="GROQ_API_KEY not configured"
)


async def test_decompose_splits_a_genuinely_compound_question() -> None:
    decomposer = LlmQueryDecomposer()
    result = await decomposer.decompose(
        "What's the difference between OPT and CPT, and which one should I use if "
        "I want to work during the semester?"
    )
    assert len(result) >= 2


async def test_decompose_does_not_split_a_simple_focused_question() -> None:
    decomposer = LlmQueryDecomposer()
    result = await decomposer.decompose("Where do freshmen live on campus?")
    assert len(result) == 1
