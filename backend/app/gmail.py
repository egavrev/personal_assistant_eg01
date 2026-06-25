"""Lazy GmailClient provider for the dashboard backend.

The Review Queue needs to *add* Gmail labels (Safe Mode: add-only, never
archive/delete/remove) when the human accepts or corrects a classification. The
stats endpoints are read-only and never touched Gmail, so this is the first place
the dashboard process needs Gmail credentials.

Like ``get_store``, the client is built lazily on first use and any wiring
failure surfaces as a clear 503 (rather than crashing startup or auth). It reuses
the pipeline's credential path exactly: ``src.auth.get_gmail_credentials`` (the
gcloud Secret Manager refresh token) and the pipeline's ``GmailClient``.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

from fastapi import HTTPException

# Importing app.store puts the repo root on sys.path and exposes the shared
# env loader, so we never duplicate that wiring here.
from app.store import _ensure_pipeline_env

if TYPE_CHECKING:
    from src.gmail_client import GmailClient


@lru_cache(maxsize=1)
def get_gmail() -> "GmailClient":
    """Return a process-wide GmailClient, building it on first call.

    lru_cache never caches a raised exception, so a transient credential failure
    retries on the next request. The client only ever calls ``apply_label`` /
    ``get_body_excerpt`` from the review router — add-only, Safe Mode.
    """
    try:
        _ensure_pipeline_env()
        from src.auth import get_gmail_credentials
        from src.gmail_client import GmailClient

        return GmailClient(get_gmail_credentials())
    except Exception as e:  # noqa: BLE001 - any wiring failure -> clear 503
        raise HTTPException(
            status_code=503,
            detail=f"Gmail backend unavailable: {type(e).__name__}: {e}",
        ) from e
