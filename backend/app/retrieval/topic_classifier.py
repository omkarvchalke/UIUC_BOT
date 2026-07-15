import math
from dataclasses import dataclass
from functools import lru_cache

from app.embeddings.embedder import Embedder
from app.models.document import Topic

# Short natural-language description of each topic, embedded once and
# compared against the user's message via cosine similarity. Chosen over
# keyword matching (brittle, misses paraphrases) and over an extra LLM call
# per message (an added network round-trip and cost for every turn) as a
# middle ground that's deterministic, CPU-only, and reuses the embedding
# infrastructure already built in Phase 4.
#
# Used only to decide whether to ask a clarifying question -- NOT as a
# retrieval filter (see nodes.make_retrieve_node): "How do I apply for OPT?"
# classified as "admissions" at 0.65 confidence (above the clarification
# threshold) purely from "apply"/"application" overlapping with the
# admissions description below, while hybrid search with no topic filter
# ranked the real OPT page #1. A wrong classification here just means an
# occasional unnecessary clarifying question; as a hard filter it would
# have silently returned zero results instead.
_TOPIC_DESCRIPTIONS: dict[Topic, str] = {
    Topic.ADMISSIONS: (
        "becoming a new UIUC student: freshman or transfer admission requirements, "
        "essays, deadlines for prospective and incoming students"
    ),
    Topic.REGISTRATION: "registering as a new or continuing student",
    Topic.ORIENTATION: "new student orientation, welcome week, orientation programs",
    Topic.HOUSING: "on-campus housing, residence halls, dorms, where students live",
    Topic.DINING: "dining halls, meal plans, food on campus",
    Topic.FINANCIAL_AID: "financial aid, tuition costs, paying for college, FAFSA",
    Topic.SCHOLARSHIPS: "scholarships and merit awards",
    Topic.STUDENT_EMPLOYMENT: "on-campus jobs, work study, student employment",
    Topic.INTERNATIONAL_STUDENT_SERVICES: "international student services and support",
    Topic.VISA: "visa status, I-20, immigration documents",
    Topic.CPT: "curricular practical training, CPT work authorization",
    Topic.OPT: "optional practical training, OPT work authorization after graduation",
    Topic.TECHNOLOGY_SERVICES: "campus technology, wifi, email, IT help desk",
    Topic.LIBRARIES: "university library hours, services, and locations",
    Topic.TRANSPORTATION: "parking, campus buses, getting around campus",
    Topic.HEALTH_INSURANCE: "student health insurance and health services",
    Topic.CAMPUS_RECREATION: "gym, fitness, recreation center membership",
    Topic.STUDENT_ORGANIZATIONS: "student clubs and registered student organizations",
    Topic.ACADEMIC_CALENDAR: "academic calendar, semester dates, add/drop deadlines",
    Topic.COURSE_REGISTRATION: "registering for classes, course registration",
}


@dataclass(frozen=True)
class TopicClassification:
    topic: Topic | None
    confidence: float


def _cosine(a: list[float], b: list[float]) -> float:
    dot = sum(x * y for x, y in zip(a, b, strict=True))
    norm_a = math.sqrt(sum(x * x for x in a))
    norm_b = math.sqrt(sum(x * x for x in b))
    return dot / (norm_a * norm_b)


@lru_cache
def _topic_embeddings() -> dict[Topic, list[float]]:
    embedder = Embedder()
    topics = list(_TOPIC_DESCRIPTIONS)
    vectors = embedder.embed_documents([_TOPIC_DESCRIPTIONS[topic] for topic in topics])
    return dict(zip(topics, vectors, strict=True))


class TopicClassifier:
    """Classifies a message into a Topic by embedding similarity, with a
    confidence score the caller uses to decide whether to trust it or ask
    for clarification instead of guessing."""

    def __init__(
        self, *, confidence_threshold: float = 0.55, embedder: Embedder | None = None
    ) -> None:
        self._threshold = confidence_threshold
        self._embedder = embedder or Embedder()

    def classify(self, message: str) -> TopicClassification:
        query_vector = self._embedder.embed_query(message)
        topic_vectors = _topic_embeddings()

        best_topic: Topic | None = None
        best_score = -1.0
        for topic, vector in topic_vectors.items():
            score = _cosine(query_vector, vector)
            if score > best_score:
                best_topic, best_score = topic, score

        if best_score < self._threshold:
            return TopicClassification(topic=None, confidence=best_score)
        return TopicClassification(topic=best_topic, confidence=best_score)
