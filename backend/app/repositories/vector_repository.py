from dataclasses import dataclass

from sqlalchemy import ColumnElement, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.conversation_session import StudentType
from app.models.document import Audience, Document, DocumentChunk, DocumentType, Topic


@dataclass(frozen=True)
class ScoredChunk:
    """One pgvector search hit. Only carries an id -- HybridRetriever never
    reads anything else off a semantic-search result (see its docstring):
    Postgres, via DocumentRepository, stays the single source of truth for
    chunk/document metadata, and this is purely a similarity ranking."""

    id: str


class VectorRepository:
    """Semantic search over DocumentChunk.embedding (pgvector), scoped to
    the same Postgres database and session as everything else -- there used
    to be a separate Qdrant service/client here; folding vector search into
    Postgres removed it, since nothing downstream of `search()` ever read
    Qdrant's payload for anything (metadata always came from Postgres via
    DocumentRepository, even when Qdrant existed)."""

    def __init__(self, db: AsyncSession) -> None:
        self._db = db

    async def search(
        self,
        query_vector: list[float],
        *,
        limit: int,
        topic: Topic | None = None,
        student_type: StudentType | None = None,
        audience: Audience | None = None,
        document_type: DocumentType | None = None,
    ) -> list[ScoredChunk]:
        stmt = (
            select(DocumentChunk.id)
            .join(Document, DocumentChunk.document_id == Document.id)
            .where(DocumentChunk.embedding.is_not(None))
        )
        for condition in self._filters(
            topic=topic,
            student_type=student_type,
            audience=audience,
            document_type=document_type,
        ):
            stmt = stmt.where(condition)
        stmt = stmt.order_by(DocumentChunk.embedding.cosine_distance(query_vector)).limit(limit)

        result = await self._db.execute(stmt)
        return [ScoredChunk(id=str(chunk_id)) for chunk_id in result.scalars().all()]

    @staticmethod
    def _filters(
        *,
        topic: Topic | None,
        student_type: StudentType | None,
        audience: Audience | None,
        document_type: DocumentType | None,
    ) -> list[ColumnElement[bool]]:
        # Same four independent AND-ed conditions HybridRetriever's
        # in-Python corpus filter (_filter_corpus/_get_corpus) applies to
        # the BM25 side -- both sides have to agree on which chunks are
        # eligible, or semantic and keyword ranking would be scoring two
        # different candidate pools.
        conditions: list[ColumnElement[bool]] = []
        if topic is not None:
            conditions.append(Document.topic == topic)

        if student_type is not None:
            # A document with no student_types applies to everyone, so it
            # must match too -- not just documents explicitly tagged with
            # this student type. .any() here is ARRAY.Comparator.any()
            # (SQL `x = ANY(array_column)`), not the unrelated relationship
            # .any() -- mypy's stubs resolve it to the latter's signature
            # against a plain str value and misflag it; confirmed correct
            # at runtime by tests/retrieval/test_vector_repository.py.
            conditions.append(
                or_(
                    Document.student_types == [],
                    Document.student_types.any(student_type.value),  # type: ignore[arg-type]
                )
            )

        if audience is not None:
            # audience is a *list* field on Document, same shape as
            # student_types -- identical "explicit match OR absent" rule.
            conditions.append(
                or_(
                    Document.audience == [],
                    Document.audience.any(audience.value),  # type: ignore[arg-type]
                )
            )

        if document_type is not None:
            # document_type is a nullable *scalar* on Document (unlike
            # topic, which is required) -- a document with no classified
            # type must still match, same "absent = applies to everyone"
            # reasoning as student_type/audience above.
            conditions.append(
                or_(Document.document_type == document_type, Document.document_type.is_(None))
            )

        return conditions
