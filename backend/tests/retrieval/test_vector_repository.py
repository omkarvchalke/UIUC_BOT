import uuid

from qdrant_client import models

from app.embeddings.embedder import EMBEDDING_DIMENSION
from app.models.conversation_session import StudentType
from app.models.document import Audience, DocumentType, Topic
from app.repositories.vector_repository import VectorRepository


def _vector(seed: int) -> list[float]:
    vector = [0.0] * EMBEDDING_DIMENSION
    vector[seed % EMBEDDING_DIMENSION] = 1.0
    return vector


def _point(
    *,
    document_id: uuid.UUID,
    seed: int,
    topic: str = Topic.HOUSING.value,
    student_types: list[str] | None = None,
    audience: list[str] | None = None,
    document_type: str | None = None,
) -> models.PointStruct:
    return models.PointStruct(
        id=str(uuid.uuid4()),
        vector=_vector(seed),
        payload={
            "document_id": str(document_id),
            "topic": topic,
            "student_types": student_types or [],
            "audience": audience or [],
            "document_type": document_type,
            "content": f"chunk {seed}",
        },
    )


async def test_search_returns_upserted_points(test_vector_repository: VectorRepository) -> None:
    document_id = uuid.uuid4()
    point = _point(document_id=document_id, seed=1)
    await test_vector_repository.upsert_chunks([point])

    results = await test_vector_repository.search(_vector(1), limit=5)

    assert any(r.id == point.id for r in results)


async def test_delete_by_document_id_removes_only_that_documents_points(
    test_vector_repository: VectorRepository,
) -> None:
    keep_document_id = uuid.uuid4()
    delete_document_id = uuid.uuid4()
    keep_point = _point(document_id=keep_document_id, seed=1)
    delete_point = _point(document_id=delete_document_id, seed=2)
    await test_vector_repository.upsert_chunks([keep_point, delete_point])

    await test_vector_repository.delete_by_document_id(delete_document_id)

    results = await test_vector_repository.search(_vector(1), limit=10)
    result_ids = {r.id for r in results}
    assert keep_point.id in result_ids
    assert delete_point.id not in result_ids


async def test_search_filters_by_topic(test_vector_repository: VectorRepository) -> None:
    housing_point = _point(document_id=uuid.uuid4(), seed=1, topic=Topic.HOUSING.value)
    dining_point = _point(document_id=uuid.uuid4(), seed=1, topic=Topic.DINING.value)
    await test_vector_repository.upsert_chunks([housing_point, dining_point])

    results = await test_vector_repository.search(_vector(1), limit=10, topic=Topic.DINING)

    result_ids = {r.id for r in results}
    assert dining_point.id in result_ids
    assert housing_point.id not in result_ids


async def test_search_filters_by_student_type_including_documents_with_no_student_types(
    test_vector_repository: VectorRepository,
) -> None:
    freshman_point = _point(
        document_id=uuid.uuid4(), seed=1, student_types=[StudentType.FRESHMAN.value]
    )
    international_point = _point(
        document_id=uuid.uuid4(), seed=1, student_types=[StudentType.INTERNATIONAL.value]
    )
    everyone_point = _point(document_id=uuid.uuid4(), seed=1, student_types=[])
    await test_vector_repository.upsert_chunks(
        [freshman_point, international_point, everyone_point]
    )

    results = await test_vector_repository.search(
        _vector(1), limit=10, student_type=StudentType.FRESHMAN
    )

    result_ids = {r.id for r in results}
    assert freshman_point.id in result_ids
    assert everyone_point.id in result_ids
    assert international_point.id not in result_ids


async def test_ensure_collection_is_idempotent(test_vector_repository: VectorRepository) -> None:
    await test_vector_repository.ensure_collection()
    await test_vector_repository.ensure_collection()


async def test_search_filters_by_audience_including_documents_with_no_audience(
    test_vector_repository: VectorRepository,
) -> None:
    alumni_point = _point(document_id=uuid.uuid4(), seed=1, audience=[Audience.ALUMNI.value])
    student_point = _point(
        document_id=uuid.uuid4(), seed=1, audience=[Audience.CURRENT_STUDENT.value]
    )
    everyone_point = _point(document_id=uuid.uuid4(), seed=1, audience=[])
    await test_vector_repository.upsert_chunks([alumni_point, student_point, everyone_point])

    results = await test_vector_repository.search(
        _vector(1), limit=10, audience=Audience.CURRENT_STUDENT
    )

    result_ids = {r.id for r in results}
    assert student_point.id in result_ids
    assert everyone_point.id in result_ids
    assert alumni_point.id not in result_ids


async def test_search_filters_by_document_type(test_vector_repository: VectorRepository) -> None:
    faq_point = _point(document_id=uuid.uuid4(), seed=1, document_type=DocumentType.FAQ.value)
    policy_point = _point(document_id=uuid.uuid4(), seed=1, document_type=DocumentType.POLICY.value)
    await test_vector_repository.upsert_chunks([faq_point, policy_point])

    results = await test_vector_repository.search(
        _vector(1), limit=10, document_type=DocumentType.FAQ
    )

    result_ids = {r.id for r in results}
    assert faq_point.id in result_ids
    assert policy_point.id not in result_ids


async def test_search_filters_by_document_type_includes_documents_with_no_document_type_set(
    test_vector_repository: VectorRepository,
) -> None:
    faq_point = _point(document_id=uuid.uuid4(), seed=1, document_type=DocumentType.FAQ.value)
    unclassified_point = _point(document_id=uuid.uuid4(), seed=1, document_type=None)
    await test_vector_repository.upsert_chunks([faq_point, unclassified_point])

    results = await test_vector_repository.search(
        _vector(1), limit=10, document_type=DocumentType.FAQ
    )

    result_ids = {r.id for r in results}
    assert faq_point.id in result_ids
    assert unclassified_point.id in result_ids
