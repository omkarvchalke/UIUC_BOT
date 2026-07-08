# Ingestion Pipeline

Offline scripts that turn curated public UIUC webpages into clean text ready for chunking and embedding. See [`docs/rag-pipeline.md`](../docs/rag-pipeline.md) for the full pipeline explanation.

**Scope boundary:** this pipeline only fetches URLs listed in `sources.json`, all of which are public, non-login-protected pages. It never accesses Canvas, Banner, student portals, or any authenticated system.

## Setup

Ingestion scripts use the same Python environment as the backend:

```bash
cd backend
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # embed_chunks.py needs no API key (local embeddings);
                        # only set an LLM_PROVIDER key if you'll also run the backend for chat
cd ../ingestion
```

## Usage

```bash
python fetch_pages.py    # sources.json -> data/raw/*.html + *.meta.json
python clean_text.py     # data/raw/*.html -> data/processed/*.txt + *.meta.json
python chunk_text.py     # data/processed/*.txt -> data/chunks/chunks.jsonl
python embed_chunks.py   # data/chunks/chunks.jsonl -> ChromaDB (data/chroma/)
```

Or run the entire pipeline in one command:

```bash
python refresh_index.py  # fetch -> clean -> chunk -> embed, stops on first failure
```

## `fetch_pages.py`

- Reads `sources.json`.
- Fetches each URL with a descriptive, honest `User-Agent` and a 15 second timeout.
- On success: saves raw HTML to `data/raw/<document_id>.html` and metadata to `data/raw/<document_id>.meta.json`.
- On failure (timeout, DNS error, 4xx/5xx, etc.): logs a warning and records the error in the `.meta.json` file with `"success": false` — the rest of the pipeline continues unaffected.
- Writes `data/raw/fetch_manifest.json`, a combined summary of every fetch attempt.

`document_id` is a stable slug derived from `category` + `title` (e.g. `housing__university-housing-new-resident-faq`), used consistently through cleaning, chunking, and embedding.

## `clean_text.py`

- Reads every `data/raw/*.meta.json`, skipping any page whose fetch was not successful.
- **Primary extraction:** [trafilatura](https://trafilatura.readthedocs.io/), which uses text-density heuristics to find the main content — this matters because several UIUC pages don't wrap their nav menus in semantic `<nav>`/`<footer>` tags, so naive tag-stripping alone leaves mostly menu links behind.
- **Fallback:** if trafilatura returns fewer than 200 characters (extraction failed or the page is unusually thin), falls back to a manual BeautifulSoup pass that strips `<script>`, `<style>`, `<nav>`, `<footer>`, `<header>`, `<aside>`, `<noscript>`, `<form>`, `<iframe>`, `<svg>` and extracts remaining visible text.
- Either way, output is normalized: blank/whitespace-only lines stripped, repeated blank lines collapsed.
- Saves plain text to `data/processed/<document_id>.txt` and metadata (original fields + `cleaned_at`, `char_count`) to `data/processed/<document_id>.meta.json`.
- Writes `data/processed/processed_manifest.json`, a combined summary of every page actually cleaned.
- Malformed HTML or empty extraction results in a logged warning and a skip, not a crash.

## `chunk_text.py`

- Reads every `data/processed/*.meta.json` + matching `.txt`.
- Splits each document into chunks of roughly **500–800 tokens**, approximated at **4 characters/token** (no tokenizer dependency) — target chunk size is ~650 tokens (~2,600 characters).
- Uses roughly **100 token** (~400 character) overlap between consecutive chunks, so context isn't lost across a chunk boundary.
- Chunk boundaries snap to the nearest whitespace on **both** ends (end-of-chunk and start-of-next-chunk), so chunks never begin or end mid-word.
- Every chunk is written as one JSON line with `chunk_id`, `document_id`, `source_title`, `source_url`, `category`, `department`, `chunk_text`, `chunk_index`, `created_at` to `data/chunks/chunks.jsonl` (the file is fully rewritten on each run).
- Documents with missing or empty processed text are logged and skipped rather than aborting the run.
- Logs a summary: documents processed, total chunks created, documents skipped.

## `embed_chunks.py`

- Reads `data/chunks/chunks.jsonl`.
- **Resets the ChromaDB index first**, so every run reflects `chunks.jsonl` exactly — no stale or orphaned chunks from a previous source list survive a rebuild.
- Embeds chunk text in batches of 64 **locally** via `backend/app/rag/embeddings.py` (`sentence-transformers`, default model `BAAI/bge-base-en-v1.5`, configured through `EMBEDDING_PROVIDER`/`EMBEDDING_MODEL`) — no API key, no network call after the model's first download.
- Adds each batch into the local persistent ChromaDB index via `backend/app/rag/vector_store.py`.
- **Fails fast with a clear message (not a stack trace)** if the embedding model fails to load (bad model name, no network on first run) — nothing is partially written in an inconsistent state beyond what's already been added batch-by-batch.
- Logs progress (`Embedded N/Total chunk(s)`) and a final summary.

## `refresh_index.py`

- Runs `fetch_pages` → `clean_text` → `chunk_text` → `embed_chunks` in order, importing each script's `main()` directly (no subprocesses).
- Stops immediately if any step returns a non-zero exit code — earlier steps' output on disk is left untouched, so a failed embed step doesn't lose the fetch/clean/chunk work already done.
- No API key is required for any of the four steps.

## Output Structure

```text
ingestion/data/
├── raw/
│   ├── housing__university-housing-new-resident-faq.html
│   ├── housing__university-housing-new-resident-faq.meta.json
│   ├── ...
│   └── fetch_manifest.json
├── processed/
│   ├── housing__university-housing-new-resident-faq.txt
│   ├── housing__university-housing-new-resident-faq.meta.json
│   ├── ...
│   └── processed_manifest.json
├── chunks/
│   └── chunks.jsonl
└── chroma/                 # ChromaDB's own persistent storage files
```

None of these generated files are committed to git (see root `.gitignore`) — only the pipeline scripts and `sources.json` are tracked.

## Testing a Retrieval Query Manually

With the index built (`embed_chunks.py` or `refresh_index.py` already run — no API key needed for either), you can query the vector store directly from a Python shell:

```bash
cd ingestion
source ../backend/.venv/bin/activate
python3 -c "
import sys
sys.path.insert(0, '../backend')
from app.rag.embeddings import embed_query
from app.rag.vector_store import similarity_search

q = embed_query('When is Welcome Week?')
for r in similarity_search(q, top_k=3):
    print(round(r['score'], 3), r['source_title'], '-', r['chunk_text'][:100])
"
```
