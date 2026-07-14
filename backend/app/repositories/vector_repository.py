import uuid
from functools import lru_cache

from qdrant_client import AsyncQdrantClient, models

from app.core.config import get_settings
from app.embeddings.embedder import EMBEDDING_DIMENSION
from app.models.conversation_session import StudentType
from app.models.document import Topic


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
    ) -> list[models.ScoredPoint]:
        result = await self._client.query_points(
            collection_name=self._collection_name,
            query=query_vector,
            limit=limit,
            query_filter=self._build_filter(topic=topic, student_type=student_type),
        )
        return result.points

    @staticmethod
    def _build_filter(
        *, topic: Topic | None, student_type: StudentType | None
    ) -> models.Filter | None:
        must: list[models.Condition] = []
        if topic is not None:
            must.append(
                models.FieldCondition(key="topic", match=models.MatchValue(value=topic.value))
            )

        should: list[models.Condition] = []
        if student_type is not None:
            # A document with no student_types applies to everyone, so it
            # must match too -- not just documents explicitly tagged with
            # this student type.
            should = [
                models.FieldCondition(
                    key="student_types", match=models.MatchAny(any=[student_type.value])
                ),
                models.IsEmptyCondition(is_empty=models.PayloadField(key="student_types")),
            ]

        if not must and not should:
            return None
        return models.Filter(must=must or None, should=should or None)
