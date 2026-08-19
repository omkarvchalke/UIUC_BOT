"""In-process golden-set non-regression gate for automatic retrieval
tuning (scripts/tune_retrieval_params.py).

Deliberately does NOT reuse the HTTP-based runners in this package
(runner.py, retrieval_runner.py) -- both drive a live server's
/api/v1/chat / /api/v1/retrieve, and neither is sensitive to
ExtractiveAnswerGenerator's min_rerank_score: GroqAnswerGenerator (used
whenever GROQ_API_KEY is set) never reads it, and /api/v1/retrieve never
reranks at all. Reusing that harness as a gate would report "no
regression" regardless of the candidate value -- a false guarantee, not a
real one. This instead builds the same compiled graph app/api/chat.py's
real endpoint runs (build_graph), wired with an ExtractiveAnswerGenerator
set to the candidate value, and invokes it in-process (no HTTP, no live
server) -- reusing 100% of the actual retrieve/rerank/classify/generate
logic instead of re-implementing it.
"""

from dataclasses import dataclass

from langgraph.checkpoint.memory import InMemorySaver
from sqlalchemy.ext.asyncio import AsyncSession

from app.evaluation.golden_set import GOLDEN_SET, EvalCase
from app.evaluation.retrieval_metrics import context_precision
from app.graph.dependencies import GraphDependencies
from app.graph.generation import ExtractiveAnswerGenerator
from app.graph.graph import build_graph, config_for, turn_input
from app.graph.query_decomposition import NoOpQueryDecomposer
from app.graph.retrieval_agent import AlwaysSufficientChecker
from app.repositories.document_repository import DocumentRepository
from app.repositories.session_repository import SessionRepository
from app.repositories.vector_repository import VectorRepository
from app.retrieval.hybrid_search import HybridRetriever
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.topic_classifier import TopicClassifier
from app.services.session_service import SessionService


@dataclass(frozen=True)
class TuningGateResult:
    grounded_rate: float
    citation_sufficiency_rate: float
    # None if no case in `cases` carries retrieval ground truth
    # (EvalCase.expected_relevant_urls) -- can't compute a meaningless 0.0.
    context_precision: float | None
    case_count: int


async def run_tuning_gate(
    min_rerank_score: float,
    db: AsyncSession,
    *,
    topic_classification_confidence_threshold: float,
    cases: tuple[EvalCase, ...] = GOLDEN_SET,
) -> TuningGateResult:
    """Runs every golden-set case through the real conversation graph with
    ExtractiveAnswerGenerator pinned to `min_rerank_score`, and reports
    aggregate metrics comparable across two calls with different candidate
    values (that comparability, not any absolute meaning, is the point --
    see the gate rule in scripts/tune_retrieval_params.py).

    Each case gets its own throwaway ConversationSession (mirroring
    tests/test_graph.py's pattern) and an in-memory checkpointer -- no
    golden-set case is multi-turn, so nothing here needs conversation
    memory to persist, and InMemorySaver avoids writing eval-run
    checkpoints into the real langgraph checkpoint tables.
    """
    deps = GraphDependencies(
        session_service=SessionService(SessionRepository(db)),
        hybrid_retriever=HybridRetriever(DocumentRepository(db), VectorRepository(db)),
        topic_classifier=TopicClassifier(
            confidence_threshold=topic_classification_confidence_threshold
        ),
        reranker=CrossEncoderReranker(),
        answer_generator=ExtractiveAnswerGenerator(min_rerank_score=min_rerank_score),
        # This gate is specifically about isolating min_rerank_score's own
        # effect (see the module docstring) -- the agentic retrieval loop
        # and query decomposition are different, independent knobs and
        # must stay disabled here so neither can confound the comparison.
        retrieval_sufficiency_checker=AlwaysSufficientChecker(),
        query_decomposer=NoOpQueryDecomposer(),
    )
    graph = build_graph(deps, checkpointer=InMemorySaver())
    session_repository = SessionRepository(db)

    grounded_hits = 0
    citation_sufficiency_hits = 0
    precision_scores: list[float] = []

    for case in cases:
        session = await session_repository.create(
            student_type=case.student_type, semester=None, college=None, department=None
        )
        result = await graph.ainvoke(
            turn_input(session.id, case.message), config=config_for(session.id)
        )

        if result.get("grounded", False):
            grounded_hits += 1

        citations = result.get("citations", [])
        if len(citations) >= case.min_citations:
            citation_sufficiency_hits += 1

        if case.expected_relevant_urls:
            urls = [citation["url"] for citation in citations]
            precision_scores.append(
                context_precision(urls, set(case.expected_relevant_urls))
            )

    case_count = len(cases)
    return TuningGateResult(
        grounded_rate=grounded_hits / case_count,
        citation_sufficiency_rate=citation_sufficiency_hits / case_count,
        context_precision=(
            sum(precision_scores) / len(precision_scores) if precision_scores else None
        ),
        case_count=case_count,
    )
