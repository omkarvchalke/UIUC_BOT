import httpx

from app.models.conversation_session import StudentType

# Matches Settings.retrieval_candidate_limit's own default -- the same
# candidate pool the app's own reranker chooses citations from, so a real
# citation should almost always be found within it. See retrieval_runner.py
# for the identical rationale.
_RETRIEVE_LIMIT = 20


async def fetch_cited_context(
    client: httpx.AsyncClient,
    message: str,
    citation_urls: list[str],
    *,
    student_type: StudentType | None = None,
    limit: int = _RETRIEVE_LIMIT,
) -> str:
    """Re-fetches retrieval results for `message` and concatenates the
    content of every returned chunk whose URL was actually cited in the
    chat answer.

    ChatCitation (app/schemas/chat.py) never carries chunk content -- only
    title/url/department/topic/subtopic/scores -- so faithfulness scoring
    has no way to get the cited text except by re-querying retrieval for
    the same message and matching by URL. A cited URL that matches nothing
    in the returned chunks is silently skipped (rare, since `limit` matches
    the app's own candidate pool) rather than treated as an error -- the
    caller decides what an empty/partial result means for its own scoring.
    """
    if not citation_urls:
        return ""

    params: dict[str, str | int] = {"query": message, "limit": limit}
    if student_type is not None:
        params["student_type"] = student_type.value

    response = await client.get("/api/v1/retrieve", params=params)
    response.raise_for_status()
    body = response.json()

    cited = set(citation_urls)
    matching_chunks = [result["content"] for result in body["results"] if result["url"] in cited]
    return "\n\n".join(matching_chunks)
