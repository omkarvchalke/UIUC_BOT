"""Deterministic DocumentChunk.id computation (Source Manifest V2, Part 16).

Chunk IDs are content-derived, not random: re-chunking a document whose section text hasn't
changed reproduces the exact same chunk IDs, instead of every re-chunk (DocumentRepository.
replace_chunks does a full delete+reinsert) churning every chunk's identity even when nothing
about that chunk actually changed.

Deliberately scoped: this makes IDs *stable*, not the reinsert itself smarter -- replace_chunks
still deletes and reinserts every chunk on every re-chunk, gated at the whole-Document level by
content_hash (a document with unchanged content never reaches replace_chunks at all -- see
IngestionService.ingest_source's skip-on-unchanged-hash check). Per-chunk-level diffing so an
unchanged chunk's *row* (and therefore its embedding) survives a partial re-chunk is real, useful
future work, not required for chunk IDs to stop churning pointlessly -- noted as a scope
boundary, not an oversight.
"""

import hashlib
import uuid

# Namespace UUID for chunk-id generation via uuid5 -- an arbitrary but fixed constant (any valid
# UUID works as a uuid5 namespace; this one has no other meaning). Must never change once any
# chunk IDs have been generated with it, or every chunk's ID would silently shift.
_CHUNK_ID_NAMESPACE = uuid.UUID("6f1c9b1a-6c3e-4b0a-9a2e-8e6d1b7c4a10")


def compute_chunk_id(
    document_id: uuid.UUID, *, section_index: int, local_index: int, content: str
) -> uuid.UUID:
    """local_index: this chunk's position among its section's own child chunks (0-based) --
    distinct from DocumentChunk.chunk_number, which is 1-based across the whole document.
    Included so two chunks in the same section with coincidentally identical text (e.g. a
    repeated boilerplate line) still get distinct, stable IDs."""
    content_hash = hashlib.sha256(content.encode("utf-8")).hexdigest()
    key = f"{document_id}:{section_index}:{local_index}:{content_hash}"
    return uuid.uuid5(_CHUNK_ID_NAMESPACE, key)
