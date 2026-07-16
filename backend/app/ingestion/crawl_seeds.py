"""Thin re-export: the actual seed definitions live in
`app/ingestion/domains/`, organized one file per Knowledge Domain. See
that package for the per-domain seed lists and the rationale (robots.txt,
login-wall, thinness-floor, and dedup checks all happen per-page inside
Crawler itself -- these seeds are deliberately domain-only, no
path_prefixes scoping).
"""

from app.ingestion.domains import ALL_SEEDS as CRAWL_SEEDS

__all__ = ["CRAWL_SEEDS"]
