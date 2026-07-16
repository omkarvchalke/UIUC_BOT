"""Thin re-export: `SourceConfig` lives in `app/ingestion/source_config.py`
(a standalone leaf module, to avoid a circular import with
`app/ingestion/domains/`) and the actual manual-manifest entries live in
`app/ingestion/domains/`, organized one file per Knowledge Domain.
"""

from app.ingestion.domains import ALL_SOURCES as SOURCES
from app.ingestion.source_config import SourceConfig

__all__ = ["SOURCES", "SourceConfig"]
