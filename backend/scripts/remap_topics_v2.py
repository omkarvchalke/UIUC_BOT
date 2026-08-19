"""One-off follow-up to the Source Manifest V2 schema migration
(migrations/versions/bcd06e256c7d_...py).

That migration remapped every Document.topic value that had an unambiguous
1:1 old-topic -> new-topic rename via plain SQL, and gave the one genuinely
ambiguous old topic (course_registration -- Source Manifest V2 splits it
between ACADEMICS and CAMPUS_SERVICES_FACILITIES depending on each page's
actual content) a defensible temporary default plus index_status="review".

This script finds every index_status="review" Document and reclassifies it
properly: runs the real (already-migrated, 21-topic) TopicClassifier against
its own ingested content (its chunks' text, standing in for the
extracted.text a live crawl would have used -- Document itself doesn't
store full body text, only chunks do), then sets topic to whatever the
classifier confidently returns. A document the classifier can't confidently
place (confidence below threshold) is left on its migration-time default
topic AND left as index_status="review" for a human to check -- never
silently guessed.

While iterating the whole corpus anyway, this also backfills
authority_score/retrieval_priority for every Document (computed fields the
schema migration didn't populate -- see app/retrieval/priority.py), by
routing every document through DocumentRepository.upsert_document, which
computes them unconditionally. All other fields are passed straight through
from the document's current value, so nothing else changes.

Usage (from backend/):
    uv run python -m scripts.remap_topics_v2
"""

import asyncio

from app.core.logging import configure_logging, get_logger
from app.database.session import get_session_factory
from app.models.document import IndexStatus
from app.repositories.document_repository import DocumentRepository
from app.retrieval.topic_classifier import TopicClassifier

configure_logging()
logger = get_logger(__name__)

_ALL_DOCUMENTS_LIMIT = 100_000
# How much chunk text to feed the classifier per document -- matches the 2000-char budget
# app/ingestion/crawler.py already uses for the same classify() call on freshly-crawled pages,
# so this reclassification pass sees a comparable amount of signal.
_CLASSIFY_TEXT_CHARS = 2000


async def main() -> None:
    classifier = TopicClassifier()
    session_factory = get_session_factory()
    async with session_factory() as session:
        repository = DocumentRepository(session)
        documents = await repository.list_documents(limit=_ALL_DOCUMENTS_LIMIT, offset=0)

        reclassified = 0
        still_needs_review = 0
        backfilled = 0
        for summary in documents:
            document = await repository.get_by_id(summary.id)
            if document is None:
                continue

            topic = document.topic
            index_status = document.index_status
            if document.index_status == IndexStatus.REVIEW:
                text = "\n\n".join(chunk.content for chunk in document.chunks)[
                    :_CLASSIFY_TEXT_CHARS
                ]
                result = classifier.classify(text)
                if result.topic is not None:
                    topic = result.topic
                    index_status = IndexStatus.APPROVED
                    reclassified += 1
                    logger.info(
                        "remap_topics_v2_reclassified",
                        url=document.url,
                        old_topic=document.topic.value,
                        new_topic=topic.value,
                        confidence=result.confidence,
                    )
                else:
                    still_needs_review += 1
                    logger.warning(
                        "remap_topics_v2_low_confidence",
                        url=document.url,
                        topic=document.topic.value,
                        confidence=result.confidence,
                    )

            await repository.upsert_document(
                url=document.url,
                title=document.title,
                department=document.department,
                topic=topic,
                source_type=document.source_type,
                student_types=tuple(document.student_types),
                audience=tuple(document.audience),
                document_type=document.document_type,
                keywords=tuple(document.keywords),
                last_updated=document.last_updated,
                last_crawled_at=document.last_crawled_at,
                content_hash=document.content_hash,
                subtopic=document.subtopic,
                source_role=document.source_role,
                http_status=document.http_status,
                word_count=document.word_count,
            )
            document.index_status = index_status
            backfilled += 1

        await session.commit()

    logger.info(
        "remap_topics_v2_complete",
        total=len(documents),
        reclassified=reclassified,
        still_needs_review=still_needs_review,
        backfilled=backfilled,
    )


if __name__ == "__main__":
    asyncio.run(main())
