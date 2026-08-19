import uuid

import pytest
from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

import app.graph.edges as edges_module
from app.core.config import Settings
from app.graph.dependencies import GraphDependencies
from app.graph.generation import ExtractiveAnswerGenerator
from app.graph.graph import build_graph, config_for, turn_input
from app.graph.retrieval_agent import AlwaysSufficientChecker, SufficiencyAssessment
from app.graph.state import GraphState, RetrievedChunkState
from app.ingestion.chunking import ChunkResult
from app.models.conversation_session import StudentType
from app.models.document import SourceType, Topic
from app.repositories.document_repository import DocumentRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.vector_repository import VectorRepository
from app.retrieval.hybrid_search import HybridRetriever
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.topic_classifier import TopicClassification, TopicClassifier
from app.services.indexing_service import IndexingService
from app.services.session_service import SessionService


def _build_deps(session: AsyncSession) -> GraphDependencies:
    return GraphDependencies(
        session_service=SessionService(SessionRepository(session)),
        hybrid_retriever=HybridRetriever(DocumentRepository(session), VectorRepository(session)),
        topic_classifier=TopicClassifier(),
        reranker=CrossEncoderReranker(),
        answer_generator=ExtractiveAnswerGenerator(),
        retrieval_sufficiency_checker=AlwaysSufficientChecker(),
    )


def _build_test_graph(
    session: AsyncSession, checkpointer: AsyncPostgresSaver
) -> CompiledStateGraph[GraphState, None, GraphState, GraphState]:
    return build_graph(_build_deps(session), checkpointer=checkpointer)


async def _create_session(session: AsyncSession, *, student_type: StudentType | None) -> uuid.UUID:
    conversation = await SessionRepository(session).create(
        student_type=student_type, semester=None, college=None, department=None
    )
    return conversation.id


async def _seed_and_index(
    session: AsyncSession,
    *,
    url: str,
    title: str,
    chunk_texts: list[str],
    topic: Topic,
    student_types: tuple[StudentType, ...] = (),
) -> None:
    repository = DocumentRepository(session)
    document = await repository.upsert_document(
        url=url,
        title=title,
        department="Test Department",
        topic=topic,
        source_type=SourceType.HTML,
        student_types=student_types,
        last_updated=None,
        content_hash=f"hash-{url}",
    )
    await repository.replace_chunks(document.id, [ChunkResult(text=t) for t in chunk_texts])
    loaded = await repository.get_by_id(document.id)
    assert loaded is not None
    await IndexingService(repository).index_document(loaded)


async def test_greeting_returns_canned_response_without_retrieval(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    async with db_session_factory() as session:
        session_id = await _create_session(session, student_type=StudentType.FRESHMAN)
        graph = _build_test_graph(session, test_checkpointer)

        result = await graph.ainvoke(turn_input(session_id, "hello"), config=config_for(session_id))

    assert result["intent"] == "greeting"
    assert "IlliniAssist" in result["answer"]
    assert result["citations"] == []
    assert result.get("retrieved_chunks", []) == []
    assert result.get("topic") is None
    assert result.get("classification_confidence") is None


async def test_first_turn_missing_profile_triggers_clarification(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    async with db_session_factory() as session:
        session_id = await _create_session(session, student_type=None)
        graph = _build_test_graph(session, test_checkpointer)

        result = await graph.ainvoke(
            turn_input(session_id, "How do I apply for OPT?"), config=config_for(session_id)
        )

    assert result["needs_clarification"] is True
    assert result["clarification_reason"] == "missing_profile"
    assert "freshman" in result["answer"].lower()
    assert result.get("retrieved_chunks", []) == []


async def test_ambiguous_question_triggers_topic_clarification(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    async with db_session_factory() as session:
        session_id = await _create_session(session, student_type=StudentType.FRESHMAN)
        graph = _build_test_graph(session, test_checkpointer)

        result = await graph.ainvoke(
            turn_input(session_id, "asdfghjkl qwerty"), config=config_for(session_id)
        )

    assert result["needs_clarification"] is True
    assert result["clarification_reason"] == "ambiguous_topic"
    assert result.get("retrieved_chunks", []) == []


async def test_full_question_flow_returns_grounded_answer_with_citations(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            url="https://example.illinois.edu/housing",
            title="Undergraduate Housing",
            chunk_texts=[
                "Freshmen must live in undergraduate residence halls during their first year."
            ],
            topic=Topic.HOUSING,
        )
        session_id = await _create_session(session, student_type=StudentType.FRESHMAN)
        graph = _build_test_graph(session, test_checkpointer)

        result = await graph.ainvoke(
            turn_input(session_id, "Where do freshmen live on campus?"),
            config=config_for(session_id),
        )

    assert result["intent"] == "question"
    assert result["needs_clarification"] is False
    assert result["grounded"] is True
    assert "residence halls" in result["answer"]
    assert len(result["citations"]) >= 1
    assert result["citations"][0]["url"] == "https://example.illinois.edu/housing"
    assert isinstance(result["citations"][0]["fused_score"], float)
    assert "subtopic" in result["citations"][0]
    reranked = result.get("reranked_chunks", [])
    assert reranked and reranked[0]["url"] == "https://example.illinois.edu/housing"
    assert reranked[0]["subtopic"] == result["citations"][0]["subtopic"]


async def test_retrieval_falls_back_when_topic_classification_is_wrong(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    """Regression test for a real bug: the topic classifier confidently (0.65)
    misclassified "How do I apply for OPT?" as "admissions" purely from
    "apply"/"application" word overlap. topic *is* now used as a pgvector
    filter (app/graph/nodes.py's retrieve node), but only provisionally --
    a topic-filtered result count below Settings.topic_filter_min_results
    falls back to an unfiltered search, so this wrong classification still finds
    the real OPT content instead of returning nothing. Uses a stub
    classifier that always returns the wrong topic with high confidence, so
    this doesn't depend on the embedding model's specific behavior staying
    the same -- it proves the fallback directly, regardless of how good or
    bad classification is.
    """

    class AlwaysWrongTopicClassifier:
        def classify(self, message: str) -> TopicClassification:
            return TopicClassification(topic=Topic.ADMISSIONS, confidence=0.99)

    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            url="https://example.illinois.edu/opt",
            title="Optional Practical Training",
            chunk_texts=["Optional Practical Training (OPT) allows F-1 students to work."],
            topic=Topic.OPT,
        )
        deps = _build_deps(session)
        deps.topic_classifier = AlwaysWrongTopicClassifier()  # type: ignore[assignment]
        graph = build_graph(deps, checkpointer=test_checkpointer)
        session_id = await _create_session(session, student_type=StudentType.FRESHMAN)

        result = await graph.ainvoke(
            turn_input(session_id, "How do I apply for OPT?"), config=config_for(session_id)
        )

    assert result["topic"] is Topic.ADMISSIONS
    assert result["grounded"] is True
    assert len(result["citations"]) >= 1
    assert result["citations"][0]["url"] == "https://example.illinois.edu/opt"


async def test_topic_filter_excludes_a_keyword_overlapping_different_topic_doc(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    """Happy-path counterpart to the fallback test above: when the
    topic-filtered corpus has enough matching content
    (>= Settings.topic_filter_min_results), the filter is trusted and applied --
    proven here by seeding an OPT document that shares heavy keyword
    overlap ("practical training", "F-1 students", "work authorization")
    with a CPT query, then asserting it's excluded from citations rather
    than sneaking in via BM25/semantic overlap the way it would without a
    topic filter.
    """

    class AlwaysCptTopicClassifier:
        def classify(self, message: str) -> TopicClassification:
            return TopicClassification(topic=Topic.CPT, confidence=0.99)

    # Distinct wording per document, not just a distinct URL/title: the
    # answer generator (ExtractiveAnswerGenerator) dedupes identical
    # sentences across chunks (two real UIUC pages sharing boilerplate text
    # otherwise showed the same line twice), which would collapse these 3
    # citations down to 1 if their content were byte-identical -- this test
    # is about topic filtering finding all 3 documents, not about that
    # dedup behavior, so keep the content distinguishable.
    async with db_session_factory() as session:
        detail_by_index = (
            "an offer letter",
            "academic advisor approval",
            "work authorization tied to their curriculum",
        )
        for i, detail in enumerate(detail_by_index):
            await _seed_and_index(
                session,
                url=f"https://example.illinois.edu/cpt-{i}",
                title="Curricular Practical Training",
                chunk_texts=[
                    "Curricular Practical Training (CPT) requires "
                    f"{detail} before F-1 students may begin CPT work authorization."
                ],
                topic=Topic.CPT,
            )
        await _seed_and_index(
            session,
            url="https://example.illinois.edu/opt",
            title="Optional Practical Training",
            chunk_texts=[
                "Optional Practical Training (OPT) is practical training work "
                "authorization available to F-1 students after graduation."
            ],
            topic=Topic.OPT,
        )
        deps = _build_deps(session)
        deps.topic_classifier = AlwaysCptTopicClassifier()  # type: ignore[assignment]
        graph = build_graph(deps, checkpointer=test_checkpointer)
        session_id = await _create_session(session, student_type=StudentType.FRESHMAN)

        result = await graph.ainvoke(
            turn_input(session_id, "What do I need for CPT work authorization?"),
            config=config_for(session_id),
        )

    assert result["topic"] is Topic.CPT
    citation_urls = {citation["url"] for citation in result["citations"]}
    assert len(citation_urls) >= 3
    assert "https://example.illinois.edu/opt" not in citation_urls
    assert all(citation["topic"] == Topic.CPT.value for citation in result["citations"])


async def test_retrieval_falls_back_when_student_type_filter_excludes_everything(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    """Regression test for a real bug found live: student_type/topic aren't
    independent facts about a person -- a real international *graduate*
    student answering "graduate" to the profile-clarifying question had
    every international-scoped source (visa/OPT/CPT) hard-filtered out,
    even though it was exactly the content their question needed. Same
    relaxation pattern as the topic fallback above: below
    Settings.topic_filter_min_results even after the topic-level fallback,
    retry with no student_type filter rather than surface a false "nothing
    found."
    """
    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            url="https://example.illinois.edu/visa-status",
            title="Maintaining F-1 Visa Status",
            chunk_texts=["Maintain your F-1 visa status by staying enrolled full-time."],
            topic=Topic.VISA,
            student_types=(StudentType.INTERNATIONAL,),
        )
        session_id = await _create_session(session, student_type=StudentType.GRADUATE)
        graph = _build_test_graph(session, test_checkpointer)

        result = await graph.ainvoke(
            turn_input(session_id, "How do I maintain my F-1 visa status?"),
            config=config_for(session_id),
        )

    assert result["grounded"] is True
    citation_urls = {citation["url"] for citation in result["citations"]}
    assert "https://example.illinois.edu/visa-status" in citation_urls


async def test_checkpointer_persists_messages_across_turns(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    async with db_session_factory() as session:
        session_id = await _create_session(session, student_type=StudentType.FRESHMAN)
        graph = _build_test_graph(session, test_checkpointer)
        config = config_for(session_id)

        first = await graph.ainvoke(turn_input(session_id, "hello"), config=config)
        second = await graph.ainvoke(turn_input(session_id, "hi again"), config=config)

    assert len(first["messages"]) == 2
    assert len(second["messages"]) == 4


async def test_greeting_after_a_classified_question_does_not_crash(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    """Regression test for a real bug hit live: a question that gets a real
    topic classified, followed by a greeting-classified message in the same
    session, crashed with "AttributeError: 'str' object has no attribute
    'value'" in save_conversation_state. The greeting path (graph.py's
    routing) skips question_classification entirely, so `topic` in state is
    whatever the Postgres checkpointer restored from the *previous* turn --
    and it comes back a plain str, not a Topic instance, once round-tripped
    through the checkpointer's JSON serialization. Uses the real
    AsyncPostgresSaver checkpointer (not a stub) since the bug is in that
    serialization round-trip, not in graph logic a stub would still exercise.
    """
    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            url="https://example.illinois.edu/housing",
            title="Undergraduate Housing",
            chunk_texts=[
                "Freshmen must live in undergraduate residence halls during their first year."
            ],
            topic=Topic.HOUSING,
        )
        session_id = await _create_session(session, student_type=StudentType.FRESHMAN)
        graph = _build_test_graph(session, test_checkpointer)
        config = config_for(session_id)

        first = await graph.ainvoke(
            turn_input(session_id, "Where do freshmen live on campus?"), config=config
        )
        second = await graph.ainvoke(turn_input(session_id, "hello"), config=config)

    assert first["topic"] is Topic.HOUSING
    assert second["intent"] == "greeting"


async def test_clarification_asked_once_then_question_proceeds(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            url="https://example.illinois.edu/dining",
            title="Meal Plans",
            chunk_texts=[
                "Meal plans include Classic Meals and Dining Dollars, with options for "
                "students living in residence halls across campus dining locations."
            ],
            topic=Topic.DINING,
        )
        session_id = await _create_session(session, student_type=None)
        graph = _build_test_graph(session, test_checkpointer)
        config = config_for(session_id)

        first = await graph.ainvoke(
            turn_input(session_id, "What meal plans are available?"), config=config
        )
        # Second turn: student_type is still unset in Postgres (this
        # message doesn't parse as a student-type reply -- see
        # test_bare_student_type_reply_answers_the_original_question below
        # for that path), but profile_asked is now True in checkpointed
        # state, so the graph must not ask again -- it should proceed to
        # actually answer this time.
        second = await graph.ainvoke(
            turn_input(session_id, "I meant the dining hall meal plans"), config=config
        )

    assert first["clarification_reason"] == "missing_profile"
    assert second.get("clarification_reason") != "missing_profile"
    assert second["grounded"] is True


async def test_bare_student_type_reply_answers_the_original_question(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    # Regression test for a real bug found live: a user who replies to the
    # profile-clarifying question with just their student type (e.g.
    # "Graduate"), not a restated question, had that single word become the
    # *entire* query for topic classification and retrieval -- producing an
    # irrelevant answer -- while student_type itself was never actually
    # parsed or persisted (a "Phase 6 will parse the free-text answer and
    # persist it" TODO that was never built). Fixed: check_student_profile
    # now parses a bare student-type reply, persists it, and substitutes
    # the *original* question (the human message before the clarifying
    # question) as the effective query for the rest of this turn.
    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            url="https://example.illinois.edu/dining",
            title="Meal Plans",
            chunk_texts=[
                "Meal plans include Classic Meals and Dining Dollars, with options for "
                "students living in residence halls across campus dining locations."
            ],
            topic=Topic.DINING,
        )
        session_id = await _create_session(session, student_type=None)
        graph = _build_test_graph(session, test_checkpointer)
        config = config_for(session_id)

        first = await graph.ainvoke(
            turn_input(session_id, "What meal plans are available?"), config=config
        )
        second = await graph.ainvoke(turn_input(session_id, "Graduate"), config=config)

        persisted = await SessionRepository(session).get_by_id(session_id)

    assert first["clarification_reason"] == "missing_profile"
    assert second.get("clarification_reason") != "missing_profile"
    assert second["student_type"] == StudentType.GRADUATE
    assert persisted is not None and persisted.student_type == StudentType.GRADUATE
    assert second["grounded"] is True
    assert "Meal plan" in second["answer"] or "meal plan" in second["answer"]


async def test_query_override_does_not_leak_into_a_later_unrelated_turn(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    # Regression test for a real bug found live in the fix above:
    # query_override, once set by a bare student-type reply, was never
    # cleared on a later turn that doesn't set a fresh one -- GraphState
    # has no reducer for that key, so LangGraph's default merge left the
    # previous turn's override sitting in checkpointed state. A THIRD turn
    # asking a completely unrelated question got silently answered using
    # the *second* turn's stale override instead of its own actual text
    # (confirmed live: identical classification_confidence between an
    # unrelated question and the stale override proved it wasn't using its
    # own text at all).
    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            url="https://example.illinois.edu/dining",
            title="Meal Plans",
            chunk_texts=[
                "Meal plans include Classic Meals and Dining Dollars, with options for "
                "students living in residence halls across campus dining locations."
            ],
            topic=Topic.DINING,
        )
        await _seed_and_index(
            session,
            url="https://example.illinois.edu/registration",
            title="Class Registration",
            chunk_texts=[
                "Select Register for Classes from the Class Registration Main Menu and "
                "choose the term you would like to register for."
            ],
            topic=Topic.COURSE_REGISTRATION,
        )
        session_id = await _create_session(session, student_type=None)
        graph = _build_test_graph(session, test_checkpointer)
        config = config_for(session_id)

        await graph.ainvoke(
            turn_input(session_id, "What meal plans are available?"), config=config
        )
        await graph.ainvoke(turn_input(session_id, "Graduate"), config=config)
        third = await graph.ainvoke(
            turn_input(session_id, "How do I register for classes?"), config=config
        )

    assert third["topic"] == Topic.COURSE_REGISTRATION
    assert third["grounded"] is True
    assert "Register for Classes" in third["answer"]


class _InsufficientThenSufficientChecker:
    """Stub sufficiency checker: reports insufficient exactly once (with a
    reformulated query), then sufficient on every call after -- proves the
    agentic retrieval loop actually retries and still reaches a normal
    completion, without depending on a real Groq call."""

    def __init__(self) -> None:
        self.call_count = 0

    async def assess(
        self, *, query: str, context: str, chunks: list[RetrievedChunkState]
    ) -> SufficiencyAssessment:
        self.call_count += 1
        if self.call_count == 1:
            return SufficiencyAssessment(
                sufficient=False,
                reformulated_query=f"{query} freshman residence hall requirement",
                reasoning="stub: first pass insufficient",
            )
        return SufficiencyAssessment(sufficient=True, reformulated_query=None, reasoning="stub: now sufficient")


class _AlwaysInsufficientChecker:
    """Stub sufficiency checker that never agrees the context is enough --
    proves route_after_sufficiency_check's own attempt-count bound stops
    the loop, not LangGraph's recursion_limit (a very different failure
    mode: GraphRecursionError instead of a normal completed turn)."""

    def __init__(self) -> None:
        self.call_count = 0

    async def assess(
        self, *, query: str, context: str, chunks: list[RetrievedChunkState]
    ) -> SufficiencyAssessment:
        self.call_count += 1
        return SufficiencyAssessment(
            sufficient=False, reformulated_query=f"{query} v{self.call_count}", reasoning="stub: always insufficient"
        )


async def test_agentic_retrieval_loop_retries_then_terminates_on_sufficient(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_checkpointer: AsyncPostgresSaver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(edges_module, "get_settings", lambda: Settings(agentic_retrieval_max_attempts=2))

    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            url="https://example.illinois.edu/housing",
            title="Freshman Housing",
            chunk_texts=["Freshmen must live on campus during their first year in residence halls."],
            topic=Topic.HOUSING,
        )
        deps = _build_deps(session)
        checker = _InsufficientThenSufficientChecker()
        deps.retrieval_sufficiency_checker = checker  # type: ignore[assignment]
        graph = build_graph(deps, checkpointer=test_checkpointer)
        session_id = await _create_session(session, student_type=StudentType.FRESHMAN)

        result = await graph.ainvoke(
            turn_input(session_id, "Where do freshmen live?"), config=config_for(session_id)
        )

    assert checker.call_count == 2
    assert result["retrieval_attempt"] == 2
    assert result["grounded"] is True


async def test_agentic_retrieval_loop_stops_at_max_attempts_not_recursion_limit(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_checkpointer: AsyncPostgresSaver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(edges_module, "get_settings", lambda: Settings(agentic_retrieval_max_attempts=2))

    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            url="https://example.illinois.edu/housing",
            title="Freshman Housing",
            chunk_texts=["Freshmen must live on campus during their first year in residence halls."],
            topic=Topic.HOUSING,
        )
        deps = _build_deps(session)
        checker = _AlwaysInsufficientChecker()
        deps.retrieval_sufficiency_checker = checker  # type: ignore[assignment]
        graph = build_graph(deps, checkpointer=test_checkpointer)
        session_id = await _create_session(session, student_type=StudentType.FRESHMAN)

        result = await graph.ainvoke(
            turn_input(session_id, "Where do freshmen live?"), config=config_for(session_id)
        )

    assert checker.call_count == 2
    assert result["retrieval_attempt"] == 2
    assert "answer" in result


async def test_agentic_retrieval_state_does_not_leak_into_a_later_turn(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_checkpointer: AsyncPostgresSaver,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Regression-shaped test for the exact stale-state pitfall this
    codebase already hit once with query_override: a second turn in the
    same session must not inherit reformulated_query/retrieval_attempt
    left over from an earlier turn's loop."""
    monkeypatch.setattr(edges_module, "get_settings", lambda: Settings(agentic_retrieval_max_attempts=2))

    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            url="https://example.illinois.edu/housing",
            title="Freshman Housing",
            chunk_texts=["Freshmen must live on campus during their first year in residence halls."],
            topic=Topic.HOUSING,
        )
        deps = _build_deps(session)
        checker = _InsufficientThenSufficientChecker()
        deps.retrieval_sufficiency_checker = checker  # type: ignore[assignment]
        graph = build_graph(deps, checkpointer=test_checkpointer)
        session_id = await _create_session(session, student_type=StudentType.FRESHMAN)
        config = config_for(session_id)

        first = await graph.ainvoke(turn_input(session_id, "Where do freshmen live?"), config=config)
        second = await graph.ainvoke(turn_input(session_id, "Where do freshmen live?"), config=config)

    assert first["retrieval_attempt"] == 2
    # Second turn's checker call_count kept climbing (3rd call overall is
    # "insufficient" again per the stub's own count == 1 check never
    # re-triggering -- call_count is 3 by the time turn 2 starts, so the
    # stub's `if self.call_count == 1` branch doesn't fire again), but the
    # real assertion that matters is state: retrieval_attempt must reset
    # to reflect only *this* turn's retrieve() calls, not accumulate
    # across turns.
    assert second["retrieval_attempt"] == 1
