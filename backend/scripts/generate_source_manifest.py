"""Generates docs/source-manifest.md: every URL currently ingested into the
corpus, grouped by Topic, with a per-document chunk count.

This is the live corpus (every Document row, including pages discovered by
a broad CrawlSeed crawl), not just the manually-curated SourceConfig entries
in app/ingestion/sources.py -- most of the corpus comes from the crawler,
not the manual manifest, so only the database has the real, current answer.

Re-run this after any ingestion run that changes the corpus (a new source
added, scripts/run_ingestion.py, a rechunk/backfill script) to keep
docs/source-manifest.md from drifting out of date -- it's a generated
snapshot, not something to hand-edit.

Usage (from backend/):
    uv run python -m scripts.generate_source_manifest
"""

import asyncio
from collections import defaultdict
from pathlib import Path

from sqlalchemy import func, select

from app.database.session import get_session_factory
from app.models.document import Document, DocumentChunk, Topic

_OUTPUT_PATH = Path(__file__).resolve().parent.parent.parent / "docs" / "source-manifest.md"


_ACRONYM_TOPICS = {Topic.CPT: "CPT", Topic.OPT: "OPT"}


def _format_topic(topic: Topic) -> str:
    if topic in _ACRONYM_TOPICS:
        return _ACRONYM_TOPICS[topic]
    return topic.value.replace("_", " ").title()


async def main() -> None:
    session_factory = get_session_factory()
    async with session_factory() as session:
        result = await session.execute(
            select(
                Document.topic,
                Document.title,
                Document.url,
                Document.department,
                func.count(DocumentChunk.id).label("chunk_count"),
            )
            .join(DocumentChunk, DocumentChunk.document_id == Document.id)
            .group_by(
                Document.id, Document.topic, Document.title, Document.url, Document.department
            )
            .order_by(Document.topic, Document.department, Document.title)
        )
        rows = result.all()

    by_topic: dict[Topic, list] = defaultdict(list)
    for topic, title, url, department, chunk_count in rows:
        by_topic[topic].append((title, url, department, chunk_count))

    total_docs = len(rows)
    total_chunks = sum(row.chunk_count for row in rows)
    topics_sorted = sorted(by_topic, key=lambda t: len(by_topic[t]), reverse=True)

    lines: list[str] = [
        "# Source Manifest",
        "",
        "Every URL currently scraped and chunked into the retrieval corpus, grouped by topic.",
        "**Generated, not hand-maintained** -- re-run",
        "`uv run python -m scripts.generate_source_manifest` (from `backend/`) after any ingestion",
        "change and commit the result, rather than editing this file directly.",
        "",
        f"**{total_docs:,} documents, {total_chunks:,} chunks, across {len(by_topic)} topics.**",
        "",
        "| Topic | Documents | Chunks |",
        "|---|---:|---:|",
    ]
    for topic in topics_sorted:
        docs = by_topic[topic]
        anchor = topic.value.replace("_", "-")
        chunk_total = sum(d[3] for d in docs)
        lines.append(f"| [{_format_topic(topic)}](#{anchor}) | {len(docs)} | {chunk_total} |")
    lines.append("")

    for topic in topics_sorted:
        docs = by_topic[topic]
        lines.append(f"## {_format_topic(topic)}")
        lines.append("")
        lines.append(f"{len(docs)} documents, {sum(d[3] for d in docs)} chunks.")
        lines.append("")
        lines.append("| Title | URL | Department | Chunks |")
        lines.append("|---|---|---|---:|")
        for title, url, department, chunk_count in docs:
            escaped_title = title.replace("|", "\\|")
            escaped_department = department.replace("|", "\\|")
            lines.append(f"| {escaped_title} | <{url}> | {escaped_department} | {chunk_count} |")
        lines.append("")

    _OUTPUT_PATH.write_text("\n".join(lines))
    print(f"Wrote {_OUTPUT_PATH} ({total_docs} documents, {len(by_topic)} topics)")


if __name__ == "__main__":
    asyncio.run(main())
