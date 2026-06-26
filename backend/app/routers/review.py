"""Human-in-the-loop review queue.

Four endpoints, all protected by ``require_user``:

* ``GET  /api/review/queue``               — needs_review signals, newest first, paginated
* ``POST /api/review/{message_id}/accept`` — confirm the AI: status -> classified, label
* ``POST /api/review/{message_id}/correct``— log corrections, status -> corrected, relabel
* ``GET  /api/review/config``              — categories + seed interests (source of truth)

Every Firestore mutation goes through ``src/signal_store.py`` (injected via
``get_store``); this router holds no raw queries. The atomic correction logic
(diff, one correction_log doc per changed field, status flip, entity override)
lives in ``SignalStore.apply_correction`` and is reused, not reimplemented.

Safe Mode: the only Gmail call is ``apply_label`` (add-only). Nothing here can
archive, delete, trash, or remove a label.
"""

from __future__ import annotations

from functools import lru_cache
from typing import TYPE_CHECKING

import yaml
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import require_user
from app.gmail import get_gmail
from app.store import _CONFIG_PATH, _ensure_pipeline_env, get_store

if TYPE_CHECKING:
    from src.gmail_client import GmailClient
    from src.signal_store import SignalStore

router = APIRouter(prefix="/api/review", tags=["review"])

# Display cap for the body excerpt fetched live from Gmail.
_BODY_CHARS = 800


@lru_cache(maxsize=1)
def _config() -> dict:
    """The pipeline config (categories, seed interests), read once and cached."""
    try:
        _ensure_pipeline_env()
        with open(_CONFIG_PATH) as f:
            return yaml.safe_load(f) or {}
    except Exception as e:  # noqa: BLE001 - any read failure -> clear 503
        raise HTTPException(
            status_code=503, detail=f"Config unavailable: {type(e).__name__}: {e}"
        ) from e


# ---------- response models ----------
class AIClassification(BaseModel):
    """The AI's proposed classification, as shown in the review card."""

    category: str | None = None
    topics: list[str] = []
    sender_type: str | None = None
    needs_reply: bool = False
    confidence: float = 0.0


class QueueItem(BaseModel):
    id: str
    sender_raw: str
    sender_ref: str | None = None
    subject: str
    snippet: str
    body_excerpt: str = ""
    week: str | None = None
    # True when a human sent this item back from Browse ("mark unsorted"), as
    # opposed to it landing here because the AI was unsure. Lets the UI badge it.
    flagged_for_review: bool = False
    classification: AIClassification


class QueueResponse(BaseModel):
    items: list[QueueItem]
    remaining: int  # total still in needs_review (for the progress indicator)


class ReviewConfig(BaseModel):
    categories: list[str]
    seed_interests: list[str]


class AcceptResponse(BaseModel):
    status: str
    category: str | None = None
    labeled: bool


class CorrectRequest(BaseModel):
    """Only the changed fields are sent; ``exclude_unset`` recovers exactly which."""

    category: str | None = None
    topics: list[str] | None = None
    needs_reply: bool | None = None
    sender_type: str | None = None


class CorrectResponse(BaseModel):
    status: str
    corrections_written: int
    changed_fields: list[str]
    labeled: bool


# ---------- endpoints ----------
@router.get("/queue", response_model=QueueResponse)
def queue(
    limit: int = 20,
    after: str | None = None,
    _: str = Depends(require_user),
    store: "SignalStore" = Depends(get_store),
) -> QueueResponse:
    limit = max(1, min(limit, 50))
    rows = store.get_review_queue(limit=limit, after_id=after)

    # Body excerpt is fetched live via the pipeline's get_body_excerpt. It's a
    # display nicety, so a Gmail outage degrades to "no body" rather than failing
    # the whole page — the queue still loads with sender/subject/snippet.
    gmail: "GmailClient | None"
    try:
        gmail = get_gmail()
    except HTTPException:
        gmail = None

    items: list[QueueItem] = []
    for mid, sig in rows:
        cls = sig.get("classification") or {}
        body = sig.get("body_excerpt") or ""
        if not body and gmail is not None:
            try:
                body = gmail.get_body_excerpt(mid, _BODY_CHARS)
            except Exception:  # noqa: BLE001 - per-item best effort
                body = ""
        items.append(
            QueueItem(
                id=mid,
                sender_raw=sig.get("sender_raw", ""),
                sender_ref=sig.get("sender_ref"),
                subject=sig.get("subject", ""),
                snippet=sig.get("snippet", ""),
                body_excerpt=body[:_BODY_CHARS],
                week=sig.get("week"),
                flagged_for_review=bool(sig.get("flagged_for_review", False)),
                classification=AIClassification(
                    category=cls.get("category"),
                    topics=cls.get("topics") or [],
                    sender_type=cls.get("sender_type"),
                    needs_reply=bool(cls.get("needs_reply", False)),
                    confidence=float(cls.get("confidence", 0.0) or 0.0),
                ),
            )
        )

    return QueueResponse(items=items, remaining=store.count_status("needs_review"))


@router.post("/{message_id}/accept", response_model=AcceptResponse)
def accept(
    message_id: str,
    _: str = Depends(require_user),
    store: "SignalStore" = Depends(get_store),
    gmail: "GmailClient" = Depends(get_gmail),
) -> AcceptResponse:
    """Confirm the AI was right: status -> classified, apply AI/<category>.

    No correction is logged. The label is add-only (Safe Mode); if Gmail labeling
    fails the status change still stands and ``labeled`` reports false.
    """
    try:
        category = store.accept_classification(message_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    labeled = _try_label(gmail, message_id, category)
    return AcceptResponse(status="classified", category=category, labeled=labeled)


@router.post("/{message_id}/correct", response_model=CorrectResponse)
def correct(
    message_id: str,
    body: CorrectRequest,
    _: str = Depends(require_user),
    store: "SignalStore" = Depends(get_store),
    gmail: "GmailClient" = Depends(get_gmail),
) -> CorrectResponse:
    """Log a correction per actually-changed field and flip status -> corrected.

    Reuses ``SignalStore.apply_correction`` (atomic Firestore batch): it diffs the
    submitted fields against the stored classification, writes one correction_log
    doc per changed field, updates the classification, and sets override=True on
    the entity when sender_type changes. We only re-apply the Gmail label when the
    category changed (add-only; the old label is intentionally left in place).
    """
    changes = body.model_dump(exclude_unset=True)
    try:
        result = store.apply_correction(message_id, changes)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e

    changed_fields = result["changed_fields"]
    labeled = False
    if "category" in changed_fields and changes.get("category"):
        labeled = _try_label(gmail, message_id, changes["category"])

    status = "corrected" if result["corrections_written"] else "needs_review"
    return CorrectResponse(
        status=status,
        corrections_written=result["corrections_written"],
        changed_fields=changed_fields,
        labeled=labeled,
    )


@router.get("/config", response_model=ReviewConfig)
def config(_: str = Depends(require_user)) -> ReviewConfig:
    cfg = _config()
    return ReviewConfig(
        categories=list(cfg.get("classifier", {}).get("categories", [])),
        seed_interests=list(cfg.get("preferences", {}).get("seed_interests", [])),
    )


def _try_label(gmail: "GmailClient", message_id: str, category: str | None) -> bool:
    """Add the AI/<category> label (add-only). Best effort: a labeling failure
    never undoes the Firestore write, so we report success instead of raising."""
    if not category:
        return False
    try:
        gmail.apply_label(message_id, f"AI/{category}")
        return True
    except Exception:  # noqa: BLE001 - label is non-critical; data already persisted
        return False
