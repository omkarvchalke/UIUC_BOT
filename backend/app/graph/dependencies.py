from dataclasses import dataclass

from app.graph.generation import AnswerGenerator
from app.retrieval.hybrid_search import HybridRetriever
from app.retrieval.reranker import CrossEncoderReranker
from app.retrieval.topic_classifier import TopicClassifier
from app.services.session_service import SessionService


@dataclass
class GraphDependencies:
    """Everything the graph's nodes need, bundled so build_graph() can close
    over it once rather than each node reaching for its own global/singleton
    -- keeps nodes testable with fake/in-memory dependencies."""

    session_service: SessionService
    hybrid_retriever: HybridRetriever
    topic_classifier: TopicClassifier
    reranker: CrossEncoderReranker
    answer_generator: AnswerGenerator
