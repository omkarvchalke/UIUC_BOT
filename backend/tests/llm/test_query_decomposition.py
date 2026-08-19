from app.llm.groq_client import GroqError
from app.llm.query_decomposition import LlmQueryDecomposer


def test_parse_single_item_pass_through() -> None:
    raw = '{"sub_queries": ["What is OPT?"]}'
    result = LlmQueryDecomposer._parse(raw, "What is OPT?")
    assert result == ["What is OPT?"]


def test_parse_genuine_split() -> None:
    raw = (
        '{"sub_queries": ["What is the difference between OPT and CPT?", '
        '"Can I work during the semester on CPT?"]}'
    )
    result = LlmQueryDecomposer._parse(raw, "original")
    assert result == [
        "What is the difference between OPT and CPT?",
        "Can I work during the semester on CPT?",
    ]


def test_parse_malformed_json_fails_open_to_original_query() -> None:
    result = LlmQueryDecomposer._parse("not json at all", "original question")
    assert result == ["original question"]


def test_parse_missing_sub_queries_key_fails_open() -> None:
    result = LlmQueryDecomposer._parse('{"reasoning": "x"}', "original question")
    assert result == ["original question"]


def test_parse_non_list_sub_queries_fails_open() -> None:
    result = LlmQueryDecomposer._parse('{"sub_queries": "not a list"}', "original question")
    assert result == ["original question"]


def test_parse_empty_list_fails_open() -> None:
    result = LlmQueryDecomposer._parse('{"sub_queries": []}', "original question")
    assert result == ["original question"]


def test_parse_blank_entries_are_dropped() -> None:
    raw = '{"sub_queries": ["  ", "What is OPT?", ""]}'
    result = LlmQueryDecomposer._parse(raw, "original")
    assert result == ["What is OPT?"]


def test_parse_all_blank_entries_falls_open() -> None:
    raw = '{"sub_queries": ["  ", ""]}'
    result = LlmQueryDecomposer._parse(raw, "original question")
    assert result == ["original question"]


def test_parse_truncates_to_max_subqueries() -> None:
    raw = '{"sub_queries": ["a", "b", "c", "d", "e"]}'
    result = LlmQueryDecomposer._parse(raw, "original")
    assert len(result) == 3  # Settings.query_decomposition_max_subqueries default


async def test_decompose_fails_open_when_groq_call_raises() -> None:
    class _FailingClient:
        async def complete_json(self, messages: list[dict[str, str]], **kwargs: object) -> str:
            raise GroqError("boom")

    decomposer = LlmQueryDecomposer(client=_FailingClient())  # type: ignore[arg-type]
    result = await decomposer.decompose("What is OPT?")
    assert result == ["What is OPT?"]


async def test_decompose_parses_a_successful_groq_response() -> None:
    class _StubClient:
        async def complete_json(self, messages: list[dict[str, str]], **kwargs: object) -> str:
            return '{"sub_queries": ["sub one", "sub two"]}'

    decomposer = LlmQueryDecomposer(client=_StubClient())  # type: ignore[arg-type]
    result = await decomposer.decompose("a compound question")
    assert result == ["sub one", "sub two"]
