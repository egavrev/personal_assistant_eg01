"""Lazy SignalStore provider for the dashboard backend.

All Firestore access lives in the pipeline's ``src/signal_store.py``; the
dashboard reuses that single store rather than issuing its own queries. This
module makes it importable from the FastAPI app and exposes it as a dependency.

The store is built lazily on first use, so the app still boots (and auth keeps
working) even when Firestore isn't configured — only the stats endpoints fail,
with a clear 503, instead of crashing startup. It reuses the pipeline's
Application Default Credentials and ``GOOGLE_CLOUD_PROJECT``, exactly like
``run_ingestion.py``.
"""

from __future__ import annotations

import sys
from functools import lru_cache
from pathlib import Path
from typing import TYPE_CHECKING

import yaml
from fastapi import HTTPException

if TYPE_CHECKING:
    from src.signal_store import SignalStore

# The pipeline package (``src``) lives at the repo root, two levels above
# ``backend/app``. Put it on the import path so we can reuse its Firestore layer.
_REPO_ROOT = Path(__file__).resolve().parents[2]
if str(_REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT))

_CONFIG_PATH = _REPO_ROOT / "config" / "config.yaml"


@lru_cache(maxsize=1)
def get_store() -> "SignalStore":
    """Return a process-wide SignalStore, building it on first call.

    lru_cache never caches a raised exception, so a misconfigured environment
    retries on the next request and starts serving as soon as it's fixed —
    without a restart. Any wiring failure (missing project id, no credentials,
    unreadable config) surfaces as a clear 503 rather than a 500 or a crash.
    """
    try:
        from src.signal_store import SignalStore

        with open(_CONFIG_PATH) as f:
            config = yaml.safe_load(f) or {}
        return SignalStore(config.get("entities", {}))
    except Exception as e:  # noqa: BLE001 - any wiring failure -> clear 503
        raise HTTPException(
            status_code=503,
            detail=f"Stats backend unavailable: {type(e).__name__}: {e}",
        ) from e
