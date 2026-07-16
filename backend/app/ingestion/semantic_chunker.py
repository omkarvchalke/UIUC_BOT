from app.core.config import get_settings
from app.ingestion.chunking import ChunkerConfig, ChunkResult, RecursiveCharacterChunker
from app.ingestion.extracted_document import ExtractedDocument, Section

_SUBTOPIC_SEPARATOR = " > "
_SUBTOPIC_MAX_LEN = 255  # DocumentChunk.subtopic is String(255)


class SemanticChunker:
    """Heading-aware chunking: splits within section boundaries (so a
    chunk never straddles two unrelated <h2> sections) and tags each
    resulting chunk with the heading path it came from.

    Falls back to flat RecursiveCharacterChunker behavior (subtopic=None
    for every chunk) whenever extracted.sections is None or empty -- PDFs
    today, any future non-HTML source tomorrow. A single-section,
    no-heading HTML page converges to the identical output via the normal
    path too (one Section with heading_path=()), so no special-casing is
    needed for that case.
    """

    def __init__(
        self, config: ChunkerConfig | None = None, *, min_section_chars: int | None = None
    ) -> None:
        self._config = config or ChunkerConfig()
        self._min_section_chars = (
            min_section_chars
            if min_section_chars is not None
            else get_settings().semantic_chunk_min_section_chars
        )
        self._recursive = RecursiveCharacterChunker(self._config)

    def split(self, extracted: ExtractedDocument) -> list[ChunkResult]:
        if not extracted.sections:
            return [ChunkResult(text=text) for text in self._recursive.split(extracted.text)]

        results: list[ChunkResult] = []
        for section in self._merge_small_sections(extracted.sections):
            subtopic = self._subtopic_for(section.heading_path)
            results.extend(
                ChunkResult(text=piece, subtopic=subtopic)
                for piece in self._recursive.split(section.text)
            )
        return results

    def _merge_small_sections(self, sections: tuple[Section, ...]) -> list[Section]:
        """Sections shorter than min_section_chars merge into a neighbor
        rather than becoming their own tiny, low-value chunk.

        Forward merge (the common case): a short section's text is
        prepended onto the *next* section, and the merged group's subtopic
        is the next (most specific) heading -- a short lead-in paragraph
        naturally belongs to the section that follows it. The one
        exception is a too-small *trailing* section with no next section
        to merge into: it merges backward into the last finalized section
        instead, keeping that section's subtopic (there's no "next"
        heading to attribute it to).
        """
        merged: list[Section] = []
        pending: str | None = None

        for index, section in enumerate(sections):
            text = f"{pending}\n\n{section.text}" if pending else section.text
            is_last = index == len(sections) - 1

            if len(text) < self._min_section_chars:
                if not is_last:
                    pending = text
                    continue
                # Trailing section too small to have a "next" section to
                # merge into: fold it backward into the last finalized
                # section (keeping that section's subtopic) instead of
                # emitting it as its own low-value chunk. If nothing has
                # been finalized yet, the whole document is this one small
                # section -- keep it standalone with its own heading path.
                if merged:
                    last = merged[-1]
                    merged[-1] = Section(
                        heading_path=last.heading_path, text=f"{last.text}\n\n{text}"
                    )
                else:
                    merged.append(Section(heading_path=section.heading_path, text=text))
                pending = None
                continue

            merged.append(Section(heading_path=section.heading_path, text=text))
            pending = None

        return merged

    @staticmethod
    def _subtopic_for(heading_path: tuple[str, ...]) -> str | None:
        if not heading_path:
            return None
        # Prefer the fullest path that fits; if even the most specific
        # (innermost) heading alone doesn't fit, hard-truncate it.
        for start in range(len(heading_path)):
            joined = _SUBTOPIC_SEPARATOR.join(heading_path[start:])
            if len(joined) <= _SUBTOPIC_MAX_LEN:
                return joined
        return heading_path[-1][: _SUBTOPIC_MAX_LEN - 3] + "..."
