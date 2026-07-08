import sys
from pathlib import Path

# Tests import the backend app package (e.g. `from app.core.safety import classify`),
# so backend/ needs to be on sys.path the same way uvicorn expects when run from there.
BACKEND_DIR = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND_DIR))
