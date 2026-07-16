import uuid

from langgraph.checkpoint.postgres.aio import AsyncPostgresSaver
from langgraph.graph.state import CompiledStateGraph
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.graph.dependencies import GraphDependencies
from app.graph.generation import ExtractiveAnswerGenerator
from app.graph.graph import build_graph, config_for, turn_input
from app.graph.state import GraphState
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


def _build_deps(session: AsyncSession, vector_repository: VectorRepository) -> GraphDependencies:
    return GraphDependencies(
        session_service=SessionService(SessionRepository(session)),
        hybrid_retriever=HybridRetriever(DocumentRepository(session), vector_repository),
        topic_classifier=TopicClassifier(),
        reranker=CrossEncoderReranker(),
        answer_generator=ExtractiveAnswerGenerator(),
    )


def _build_test_graph(
    session: AsyncSession, vector_repository: VectorRepository, checkpointer: AsyncPostgresSaver
) -> CompiledStateGraph[GraphState, None, GraphState, GraphState]:
    return build_graph(_build_deps(session, vector_repository), checkpointer=checkpointer)


async def _create_session(session: AsyncSession, *, student_type: StudentType | None) -> uuid.UUID:
    conversation = await SessionRepository(session).create(
        student_type=student_type, semester=None, college=None, department=None
    )
    return conversation.id


async def _seed_and_index(
    session: AsyncSession,
    vector_repository: VectorRepository,
    *,
    url: str,
    title: str,
    chunk_texts: list[str],
    topic: Topic,
) -> None:
    repository = DocumentRepository(session)
    document = await repository.upsert_document(
        url=url,
        title=title,
        department="Test Department",
        topic=topic,
        source_type=SourceType.HTML,
        student_types=(),
        last_updated=None,
        content_hash=f"hash-{url}",
    )
    await repository.replace_chunks(document.id, [ChunkResult(text=t) for t in chunk_texts])
    loaded = await repository.get_by_id(document.id)
    assert loaded is not None
    await IndexingService(repository, vector_repository).index_document(loaded)


async def test_greeting_returns_canned_response_without_retrieval(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_vector_repository: VectorRepository,
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    async with db_session_factory() as session:
        session_id = await _create_session(session, student_type=StudentType.FRESHMAN)
        graph = _build_test_graph(session, test_vector_repository, test_checkpointer)

        result = await graph.ainvoke(turn_input(session_id, "hello"), config=config_for(session_id))

    assert result["intent"] == "greeting"
    assert "IlliniGuide" in result["answer"]
    assert result["citations"] == []
    assert result.get("retrieved_chunks", []) == []


async def test_first_turn_missing_profile_triggers_clarification(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_vector_repository: VectorRepository,
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    async with db_session_factory() as session:
        session_id = await _create_session(session, student_type=None)
        graph = _build_test_graph(session, test_vector_repository, test_checkpointer)

        result = await graph.ainvoke(
            turn_input(session_id, "How do I apply for OPT?"), config=config_for(session_id)
        )

    assert result["needs_clarification"] is True
    assert result["clarification_reason"] == "missing_profile"
    assert "freshman" in result["answer"].lower()
    assert result.get("retrieved_chunks", []) == []


async def test_ambiguous_question_triggers_topic_clarification(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_vector_repository: VectorRepository,
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    async with db_session_factory() as session:
        session_id = await _create_session(session, student_type=StudentType.FRESHMAN)
        graph = _build_test_graph(session, test_vector_repository, test_checkpointer)

        result = await graph.ainvoke(
            turn_input(session_id, "asdfghjkl qwerty"), config=config_for(session_id)
        )

    assert result["needs_clarification"] is True
    assert result["clarification_reason"] == "ambiguous_topic"
    assert result.get("retrieved_chunks", []) == []


async def test_full_question_flow_returns_grounded_answer_with_citations(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_vector_repository: VectorRepository,
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/housing",
            title="Undergraduate Housing",
            chunk_texts=[
                "Freshmen must live in undergraduate residence halls during their first year."
            ],
            topic=Topic.HOUSING,
        )
        session_id = await _create_session(session, student_type=StudentType.FRESHMAN)
        graph = _build_test_graph(session, test_vector_repository, test_checkpointer)

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


async def test_retrieval_falls_back_when_topic_classification_is_wrong(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_vector_repository: VectorRepository,
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    """Regression test for a real bug: the topic classifier confidently (0.65)
    misclassified "How do I apply for OPT?" as "admissions" purely from
    "apply"/"application" word overlap. topic *is* now used as a Qdrant
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
            test_vector_repository,
            url="https://example.illinois.edu/opt",
            title="Optional Practical Training",
            chunk_texts=["Optional Practical Training (OPT) allows F-1 students to work."],
            topic=Topic.OPT,
        )
        deps = _build_deps(session, test_vector_repository)
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
    test_vector_repository: VectorRepository,
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

    async with db_session_factory() as session:
        for i in range(3):
            await _seed_and_index(
                session,
                test_vector_repository,
                url=f"https://example.illinois.edu/cpt-{i}",
                title="Curricular Practical Training",
                chunk_texts=[
                    "Curricular Practical Training (CPT) requires an offer letter and "
                    "academic advisor approval before F-1 students may begin work "
                    "authorization for training tied to their curriculum."
                ],
                topic=Topic.CPT,
            )
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/opt",
            title="Optional Practical Training",
            chunk_texts=[
                "Optional Practical Training (OPT) is practical training work "
                "authorization available to F-1 students after graduation."
            ],
            topic=Topic.OPT,
        )
        deps = _build_deps(session, test_vector_repository)
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


async def test_checkpointer_persists_messages_across_turns(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_vector_repository: VectorRepository,
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    async with db_session_factory() as session:
        session_id = await _create_session(session, student_type=StudentType.FRESHMAN)
        graph = _build_test_graph(session, test_vector_repository, test_checkpointer)
        config = config_for(session_id)

        first = await graph.ainvoke(turn_input(session_id, "hello"), config=config)
        second = await graph.ainvoke(turn_input(session_id, "hi again"), config=config)

    assert len(first["messages"]) == 2
    assert len(second["messages"]) == 4


async def test_greeting_after_a_classified_question_does_not_crash(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_vector_repository: VectorRepository,
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
            test_vector_repository,
            url="https://example.illinois.edu/housing",
            title="Undergraduate Housing",
            chunk_texts=[
                "Freshmen must live in undergraduate residence halls during their first year."
            ],
            topic=Topic.HOUSING,
        )
        session_id = await _create_session(session, student_type=StudentType.FRESHMAN)
        graph = _build_test_graph(session, test_vector_repository, test_checkpointer)
        config = config_for(session_id)

        first = await graph.ainvoke(
            turn_input(session_id, "Where do freshmen live on campus?"), config=config
        )
        second = await graph.ainvoke(turn_input(session_id, "hello"), config=config)

    assert first["topic"] is Topic.HOUSING
    assert second["intent"] == "greeting"


async def test_clarification_asked_once_then_question_proceeds(
    db_session_factory: async_sessionmaker[AsyncSession],
    test_vector_repository: VectorRepository,
    test_checkpointer: AsyncPostgresSaver,
) -> None:
    async with db_session_factory() as session:
        await _seed_and_index(
            session,
            test_vector_repository,
            url="https://example.illinois.edu/dining",
            title="Meal Plans",
            chunk_texts=["Meal plans include Classic Meals and Dining Dollars."],
            topic=Topic.DINING,
        )
        session_id = await _create_session(session, student_type=None)
        graph = _build_test_graph(session, test_vector_repository, test_checkpointer)
        config = config_for(session_id)

        first = await graph.ainvoke(
            turn_input(session_id, "What meal plans are available?"), config=config
        )
        # Second turn: student_type is still unset in Postgres (Phase 6 will
        # parse the free-text answer and persist it), but profile_asked is
        # now True in checkpointed state, so the graph must not ask again --
        # it should proceed to actually answer this time.
        second = await graph.ainvoke(
            turn_input(session_id, "I meant the dining hall meal plans"), config=config
        )

    assert first["clarification_reason"] == "missing_profile"
    assert second.get("clarification_reason") != "missing_profile"
    assert second["grounded"] is True
