from dataclasses import dataclass

_DEFAULT_SEPARATORS = ("\n\n", "\n", ". ", " ", "")


@dataclass(frozen=True)
class ChunkerConfig:
    chunk_size: int = 1000
    chunk_overlap: int = 150


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

    def _split_recursive(self, text: str, separators: list[str]) -> list[str]:
        if len(text) <= self._config.chunk_size:
            return [text]

        if not separators:
            size = self._config.chunk_size
            return [text[i : i + size] for i in range(0, len(text), size)]

        separator, *rest = separators
        parts = text.split(separator) if separator else list(text)

        atoms: list[str] = []
        for part in parts:
            if not part:
                continue
            if len(part) > self._config.chunk_size:
                atoms.extend(self._split_recursive(part, rest))
            else:
                atoms.append(part)
        return atoms

    def _merge_atoms(self, atoms: list[str]) -> list[str]:
        chunk_size = self._config.chunk_size
        chunk_overlap = self._config.chunk_overlap

        chunks: list[str] = []
        current: list[str] = []
        current_len = 0

        for atom in atoms:
            added_len = len(atom) + (1 if current else 0)
            if current and current_len + added_len > chunk_size:
                chunks.append(" ".join(current))
                current, current_len = self._carry_overlap(current, chunk_overlap)
                added_len = len(atom) + (1 if current else 0)

            current.append(atom)
            current_len += added_len

        if current:
            chunks.append(" ".join(current))

        return chunks

    @staticmethod
    def _carry_overlap(atoms: list[str], chunk_overlap: int) -> tuple[list[str], int]:
        if chunk_overlap <= 0:
            return [], 0

        carried: list[str] = []
        carried_len = 0
        for atom in reversed(atoms):
            extra = len(atom) + (1 if carried else 0)
            if carried and carried_len + extra > chunk_overlap:
                break
            carried.insert(0, atom)
            carried_len += extra

        return carried, carried_len
