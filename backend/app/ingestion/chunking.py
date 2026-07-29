from dataclasses import dataclass

_DEFAULT_SEPARATORS = ("\n\n", "\n", ". ", " ", "")


@dataclass(frozen=True)
class ChunkerConfig:
    chunk_size: int = 1000
    chunk_overlap: int = 150


@dataclass(frozen=True)
class ChunkResult:
    """One persisted chunk: its text plus the heading-derived section it
    came from, if any (see app/ingestion/semantic_chunker.py)."""

    text: str
    subtopic: str | None = None


class RecursiveCharacterChunker:
    """Splits text into overlapping chunks, preferring paragraph/sentence/word
    boundaries over hard character cuts.

    Two stages:
    1. Recursively split on separators (paragraph, line, sentence, word,
       character) until every atom is <= chunk_size.
    2. Greedily merge atoms back together up to chunk_size, carrying the
       trailing `chunk_overlap` characters of atoms into the next chunk.

    `chunk_size` is a soft target: an atom immediately following an overlap
    carry-over can push a chunk slightly over it, since atoms are never
    split further once whole (a mid-sentence cut would be worse).
    """

    def __init__(self, config: ChunkerConfig | None = None) -> None:
        self._config = config or ChunkerConfig()
        if self._config.chunk_overlap >= self._config.chunk_size:
            raise ValueError("chunk_overlap must be smaller than chunk_size")

    def split(self, text: str) -> list[str]:
        text = text.strip()
        if not text:
            return []

        atoms = self._split_recursive(text, list(_DEFAULT_SEPARATORS))
        return self._merge_atoms(atoms)

    def _split_recursive(self, text: str, separators: list[str]) -> list[tuple[str, str]]:
        """Returns (atom_text, join_separator) pairs, where join_separator
        is whatever separator originally appeared between this atom and the
        *previous* one in `text` (empty string for the very first atom).

        Threading the real separator through -- rather than discarding it,
        the way plain str.split() does -- is what _merge_atoms needs to
        reassemble a chunk without corrupting it: confirmed live, a page's
        <li> items (each a complete sentence-like fragment with no
        trailing period, since they're bullet points, not prose) were
        split apart here on their "\\n" separator correctly, but then
        glued back together in _merge_atoms with a hardcoded " ".join(...)
        -- e.g. "...for the work" + " " + "Training which is not..."
        with nothing marking the sentence boundary between them, which the
        answer generator's sentence splitter (app/graph/generation.py)
        then had no way to recover, treating three separate bullet points
        as one unreadable run-on "sentence".
        """
        if len(text) <= self._config.chunk_size:
            return [(text, "")]

        if not separators:
            size = self._config.chunk_size
            return [(text[i : i + size], "") for i in range(0, len(text), size)]

        separator, *rest = separators
        parts = text.split(separator) if separator else list(text)

        atoms: list[tuple[str, str]] = []
        for part in parts:
            if not part:
                continue
            join_sep = separator if atoms else ""
            if len(part) > self._config.chunk_size:
                sub_atoms = self._split_recursive(part, rest)
                for index, (sub_text, sub_sep) in enumerate(sub_atoms):
                    atoms.append((sub_text, join_sep if index == 0 else sub_sep))
            else:
                atoms.append((part, join_sep))
        return atoms

    def _merge_atoms(self, atoms: list[tuple[str, str]]) -> list[str]:
        # Length budgeting below always counts a flat 1 char per join, not
        # each join_sep's real length -- chunk_size is already a soft
        # target (see class docstring), and this keeps the budget as
        # simple an approximation as before this method started tracking
        # real separators. Only _join, which actually inserts text, needs
        # the real separator to be correct.
        chunk_size = self._config.chunk_size
        chunk_overlap = self._config.chunk_overlap

        chunks: list[str] = []
        current: list[tuple[str, str]] = []
        current_len = 0

        for atom_text, join_sep in atoms:
            added_len = len(atom_text) + (1 if current else 0)
            if current and current_len + added_len > chunk_size:
                chunks.append(self._join(current))
                current, current_len = self._carry_overlap(current, chunk_overlap)
                added_len = len(atom_text) + (1 if current else 0)

            current.append((atom_text, join_sep))
            current_len += added_len

        if current:
            chunks.append(self._join(current))

        return chunks

    @staticmethod
    def _join(atoms: list[tuple[str, str]]) -> str:
        # atoms[0]'s own join_sep describes what preceded it *before this
        # chunk* (irrelevant here, possibly nonempty after an overlap
        # carry-over) -- only atoms[1:]'s separators describe adjacency
        # within this chunk, so only those are used.
        parts = [atoms[0][0]]
        for atom_text, join_sep in atoms[1:]:
            parts.append(join_sep or " ")
            parts.append(atom_text)
        return "".join(parts)

    @staticmethod
    def _carry_overlap(
        atoms: list[tuple[str, str]], chunk_overlap: int
    ) -> tuple[list[tuple[str, str]], int]:
        if chunk_overlap <= 0:
            return [], 0

        carried: list[tuple[str, str]] = []
        carried_len = 0
        for atom_text, join_sep in reversed(atoms):
            extra = len(atom_text) + (1 if carried else 0)
            if carried and carried_len + extra > chunk_overlap:
                break
            carried.insert(0, (atom_text, join_sep))
            carried_len += extra

        return carried, carried_len
