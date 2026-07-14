from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True)
class ExtractedDocument:
    title: str
    text: str
    last_updated: datetime | None
