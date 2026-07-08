# CampusGuide AI — backend
#
# Build context is the REPO ROOT, not backend/ — the app resolves a couple
# of paths relative to the repo layout (GET /api/sources reads
# ingestion/sources.json; the vector store persists under
# ingestion/data/chroma). Build and run from the repo root:
#
#   docker build -f backend/Dockerfile -t campusguide-backend .
#   docker run --rm -p 8000:8000 --env-file backend/.env \
#     -v "$(pwd)/ingestion/data/chroma:/repo/ingestion/data/chroma" \
#     campusguide-backend
#
# The vector index (ingestion/data/chroma) is NOT baked into the image —
# build it on the host first (cd ingestion && python refresh_index.py) and
# mount it in, so the image stays slim and the index can be rebuilt
# independently of the app code. See docker-compose.yml for the easier path.
FROM python:3.13-slim

# chromadb pulls in chroma-hnswlib, which compiles a C++ extension at
# install time — python:*-slim has no compiler by default, so this fails
# without build-essential. Discovered by actually building this image.
RUN apt-get update \
    && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /repo

# sentence-transformers depends on torch, whose default PyPI wheel pulls in
# ~9GB of NVIDIA CUDA libraries that a CPU-only container will never use
# (this backend has no GPU access on Render/Railway/Fly, or on most local
# machines). Installing the CPU-only torch build first — before it's
# pulled in as a sub-dependency — keeps the final image a fraction of the
# size. Discovered by actually building the image and checking its size.
RUN pip install --no-cache-dir torch --index-url https://download.pytorch.org/whl/cpu

COPY backend/requirements.txt backend/requirements.txt
RUN pip install --no-cache-dir -r backend/requirements.txt

COPY backend/app backend/app
COPY ingestion/sources.json ingestion/sources.json

WORKDIR /repo/backend

ENV PYTHONUNBUFFERED=1

EXPOSE 8000

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
