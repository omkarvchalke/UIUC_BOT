from app.graph.nodes import make_context_builder_node
from app.graph.state import GraphState, RetrievedChunkState


def _chunk(
    *,
    chunk_id: str,
    document_id: str = "doc-1",
    content: str = "child content",
    section_index: int = 0,
    parent_text: str | None = None,
) -> RetrievedChunkState:
    return {
        "chunk_id": chunk_id,
        "document_id": document_id,
        "content": content,
        "title": "Title",
        "url": "https://example.illinois.edu/page",
        "department": "Dept",
        "topic": "housing",
        "subtopic": None,
        "fused_score": 1.0,
        "section_index": section_index,
        "parent_text": parent_text,
    }


async def test_expands_a_chunk_to_its_parent_text_when_present() -> None:
    node = make_context_builder_node()
    state: GraphState = {
        "session_id": "s",
        "messages": [],
        "reranked_chunks": [
            _chunk(chunk_id="1", parent_text="Full un-split section, all steps included."),
        ],
    }
    result = await node(state)
    assert "Full un-split section, all steps included." in result["context"]
    assert "child content" not in result["context"]


async def test_chunk_without_parent_text_uses_its_own_content() -> None:
    node = make_context_builder_node()
    state: GraphState = {
        "session_id": "s",
        "messages": [],
        "reranked_chunks": [_chunk(chunk_id="1", content="just this chunk")],
    }
    result = await node(state)
    assert "just this chunk" in result["context"]


async def test_sibling_chunks_from_the_same_split_section_expand_only_once() -> None:
    # Two children of the same split section (same document_id + section_index)
    # share identical parent_text -- only the first (highest-ranked) sibling
    # should carry the full section; the second falls back to its own content
    # so the section isn't duplicated in context.
    node = make_context_builder_node()
    shared_parent = "Full section covering both children's material."
    state: GraphState = {
        "session_id": "s",
        "messages": [],
        "reranked_chunks": [
            _chunk(chunk_id="1", section_index=2, content="first half", parent_text=shared_parent),
            _chunk(chunk_id="2", section_index=2, content="second half", parent_text=shared_parent),
        ],
    }
    result = await node(state)
    assert result["context"].count(shared_parent) == 1
    assert "second half" in result["context"]
    assert "first half" not in result["context"]


async def test_same_section_index_in_different_documents_is_not_deduplicated() -> None:
    # section_index is only meaningful scoped to its own document -- two
    # unrelated documents both having a section_index=0 must not be treated
    # as siblings of the same split section.
    node = make_context_builder_node()
    state: GraphState = {
        "session_id": "s",
        "messages": [],
        "reranked_chunks": [
            _chunk(chunk_id="1", document_id="doc-a", section_index=0, parent_text="Section A full text."),
            _chunk(chunk_id="2", document_id="doc-b", section_index=0, parent_text="Section B full text."),
        ],
    }
    result = await node(state)
    assert "Section A full text." in result["context"]
    assert "Section B full text." in result["context"]


async def test_context_entry_count_and_numbering_matches_chunk_count_regardless_of_expansion() -> None:
    # citation_generator maps 1-based citation_indices back into
    # reranked_chunks positionally -- context_builder must never drop or
    # reorder entries, even when a sibling's parent_text is suppressed.
    node = make_context_builder_node()
    shared_parent = "Shared section text."
    state: GraphState = {
        "session_id": "s",
        "messages": [],
        "reranked_chunks": [
            _chunk(chunk_id="1", section_index=0, parent_text=shared_parent),
            _chunk(chunk_id="2", section_index=0, parent_text=shared_parent),
            _chunk(chunk_id="3", section_index=1, content="unrelated"),
        ],
    }
    result = await node(state)
    assert result["context"].count("[1]") == 1
    assert result["context"].count("[2]") == 1
    assert result["context"].count("[3]") == 1
