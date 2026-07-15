"""Full-site discovery crawler: reports every page found under one or more
domains to a CSV, without filtering thin content and without touching the
database. This is Phase 2's "spreadsheet of all data sources" deliverable,
produced by crawling instead of by hand -- review the CSV yourself and
build app/ingestion/sources.py (or hand a curated URL list back) from
whatever's actually worth keeping. Nothing here is auto-ingested.

Usage (from backend/):
    # Re-crawl every existing seed's domain at full breadth (no path
    # restriction, much higher page/depth caps than the bounded seeds in
    # app/ingestion/crawl_seeds.py use for the auto-ingesting crawl):
    uv run python -m scripts.discover_sources --full

    # Or point it at one specific site:
    uv run python -m scripts.discover_sources \
        --url https://housing.illinois.edu --department "University Housing"

Flags:
    --max-pages   Per-seed page cap (default 300)
    --max-depth   Per-seed link-following depth (default 6)
    --output      CSV path (default discovered_sources.csv)
"""

import argparse
import asyncio
import csv
import dataclasses

from app.core.logging import configure_logging
from app.ingestion.crawl_seeds import CRAWL_SEEDS
from app.ingestion.crawler import Crawler, CrawlSeed

configure_logging()


def _unbounded(seed: CrawlSeed, *, max_pages: int, max_depth: int) -> CrawlSeed:
    return dataclasses.replace(seed, path_prefixes=(), max_pages=max_pages, max_depth=max_depth)


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--full", action="store_true", help="Crawl every existing seed's domain")
    parser.add_argument("--url", help="A single starting URL to crawl instead of --full")
    parser.add_argument("--department", help="Department label to record for --url")
    parser.add_argument("--max-pages", type=int, default=300)
    parser.add_argument("--max-depth", type=int, default=6)
    parser.add_argument("--output", default="discovered_sources.csv")
    args = parser.parse_args()
    if not args.full and not (args.url and args.department):
        parser.error("either --full, or --url together with --department, is required")
    return args


async def main() -> None:
    args = _parse_args()

    if args.full:
        seeds = tuple(
            _unbounded(seed, max_pages=args.max_pages, max_depth=args.max_depth)
            for seed in CRAWL_SEEDS
        )
    else:
        seeds = (
            CrawlSeed(
                start_url=args.url,
                department=args.department,
                max_pages=args.max_pages,
                max_depth=args.max_depth,
            ),
        )

    # min_content_chars=0: this is a discovery report, not an ingestion
    # run -- report every page found, including thin ones, and let a human
    # judge quality rather than have the auto-filter silently drop pages
    # before anyone sees them.
    crawler = Crawler(min_content_chars=0)
    outcome = await crawler.crawl(seeds)

    with open(args.output, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["status", "url", "title", "department", "topic", "student_types", "char_count"]
        )
        for source in outcome.accepted:
            writer.writerow(
                [
                    "found",
                    source.url,
                    source.fallback_title,
                    source.department,
                    source.topic.value,
                    "|".join(t.value for t in source.student_types),
                    outcome.content_chars.get(source.url, ""),
                ]
            )
        for url, reason in outcome.rejected:
            writer.writerow([reason, url, "", "", "", "", ""])

    print(f"{len(outcome.accepted)} pages found, {len(outcome.rejected)} skipped.")
    print(f"Written to {args.output}")


if __name__ == "__main__":
    asyncio.run(main())
