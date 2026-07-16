import uuid
from functools import lru_cache

from qdrant_client import AsyncQdrantClient, models

from app.core.config import get_settings
from app.embeddings.embedder import EMBEDDING_DIMENSION
from app.models.conversation_session import StudentType
from app.models.document import Audience, DocumentType, Topic


@lru_cache
def get_qdrant_client() -> AsyncQdrantClient:
    return AsyncQdrantClient(url=get_settings().qdrant_url)


class VectorRepository:
    def __init__(
        self, client: AsyncQdrantClient | None = None, *, collection_name: str | None = None
    ) -> None:
        settings = get_settings()
        self._client = client or get_qdrant_client()
        self._collection_name = collection_name or settings.qdrant_collection_name

    async def ensure_collection(self) -> None:
        if not await self._client.collection_exists(self._collection_name):
            await self._client.create_collection(
                collection_name=self._collection_name,
                vectors_config=models.VectorParams(
                    size=EMBEDDING_DIMENSION, distance=models.Distance.COSINE
                ),
            )

    async def delete_collection(self) -> None:
        if await self._client.collection_exists(self._collection_name):
            await self._client.delete_collection(self._collection_name)

    async def upsert_chunks(self, points: list[models.PointStruct]) -> None:
        if not points:
            return
        await self._client.upsert(collection_name=self._collection_name, points=points)

    async def delete_by_document_id(self, document_id: uuid.UUID) -> None:
        await self._client.delete(
            collection_name=self._collection_name,
            points_selector=models.FilterSelector(
                filter=models.Filter(
                    must=[
                        models.FieldCondition(
                            key="document_id", match=models.MatchValue(value=str(document_id))
                        )
                    ]
                )
            ),
        )

    async def search(
        self,
        query_vector: list[float],
        *,
        limit: int,
        topic: Topic | None = None,
        student_type: StudentType | None = None,
        audience: Audience | None = None,
        document_type: DocumentType | None = None,
    ) -> list[models.ScoredPoint]:
        result = await self._client.query_points(
            collection_name=self._collection_name,
            query=query_vector,
            limit=limit,
            query_filter=self._build_filter(
                topic=topic,
                student_type=student_type,
                audience=audience,
                document_type=document_type,
            ),
        )
        return result.points

    @staticmethod
    def _build_filter(
        *,
        topic: Topic | None,
        student_type: StudentType | None,
        audience: Audience | None,
        document_type: DocumentType | None,
    ) -> models.Filter | None:
        # Every condition below lives in `must` -- including the
        # "explicit match OR field absent" fallbacks, which are each their
        # own nested Filter(should=[...]). They can't sit in one flat
        # top-level `should` list: Qdrant ORs everything in `should`
        # together, so two independent should-shaped conditions (e.g.
        # student_type and audience) in the same list would match a point
        # satisfying *either* one, not both -- wrong the moment a second
        # such condition exists. Nesting each as its own must-entry keeps
        # every dimension independently required (AND of ORs), same as
        # student_type alone worked correctly before audience/document_type
        # existed.
        must: list[models.Condition] = []
        if topic is not None:
            # str(), not .value: Topic is a StrEnum, so this is identical
            # output for a real Topic instance, but also safe if a plain
            # str with the same value ever reaches here -- see the
            # identical comment in app/graph/nodes.py for the real crash
            # that motivated this pattern (a checkpoint-restored Topic
            # round-tripping through JSON and coming back a plain str).
            must.append(
                models.FieldCondition(key="topic", match=models.MatchValue(value=str(topic)))
            )

        if student_type is not None:
            # A document with no student_types applies to everyone, so it
            # must match too -- not just documents explicitly tagged with
            # this student type.
            must.append(
                models.Filter(
                    should=[
                        models.FieldCondition(
                            key="student_types", match=models.MatchAny(any=[student_type.value])
                        ),
                        models.IsEmptyCondition(is_empty=models.PayloadField(key="student_types")),
                    ]
                )
            )

        if audience is not None:
            # audience is a *list* field on Document, same shape as
            # student_types -- identical "explicit match OR absent" rule.
            must.append(
                models.Filter(
                    should=[
                        models.FieldCondition(
                            key="audience", match=models.MatchAny(any=[audience.value])
                        ),
                        models.IsEmptyCondition(is_empty=models.PayloadField(key="audience")),
                    ]
                )
            )

        if document_type is not None:
            # document_type is a nullable *scalar* on Document (unlike
            # topic, which is required) -- a document with no classified
            # type must still match, same "absent = applies to everyone"
            # reasoning as student_type/audience above.
            must.append(
                models.Filter(
                    should=[
                        models.FieldCondition(
                            key="document_type", match=models.MatchValue(value=str(document_type))
                        ),
                        models.IsNullCondition(is_null=models.PayloadField(key="document_type")),
                    ]
                )
            )

        return models.Filter(must=must) if must else None
