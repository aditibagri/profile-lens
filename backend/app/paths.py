from __future__ import annotations

from pathlib import Path


def resolve_frontend_dir() -> Path:
    """Locate the Vue frontend whether running from repo or Docker layout."""
    here = Path(__file__).resolve()
    candidates = [
        here.parents[2] / "frontend",  # <root>/backend/app/main.py
        here.parents[1] / "frontend",  # <root>/app/main.py (Docker)
    ]
    for path in candidates:
        if path.is_dir() and (path / "index.html").is_file():
            return path
    return candidates[0]
