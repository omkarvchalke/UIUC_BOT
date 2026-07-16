from dataclasses import dataclass, field

from app.models.conversation_session import StudentType
from app.models.document import SourceType, Topic


@dataclass(frozen=True)
class SourceConfig:
    """One entry in the ingestion manifest: an official UIUC URL plus the
    metadata that isn't reliably extractable from the page itself.

    Lives in its own module, not app.ingestion.sources, specifically so
    app/ingestion/domains/*.py can import it without a circular import:
    app.ingestion.crawler imports SOURCES from sources.py, and sources.py
    (via app.ingestion.domains) needs every domain module's SourceConfig
    entries -- if SourceConfig lived in sources.py, that would be
    crawler.py -> sources.py -> domains -> sources.py.
    """

    url: str
    department: str
    topic: Topic
    source_type: SourceType
    fallback_title: str
    student_types: tuple[StudentType, ...] = field(default_factory=tuple)
