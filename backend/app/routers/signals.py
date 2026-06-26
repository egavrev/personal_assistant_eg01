"""Browse classified mail by category and flag mislabels.

Three endpoints, all protected by ``require_user``:

* ``GET  /api/signals?category=<cat>&limit=&after=`` — classified/corrected
  signals in a category, lowest-confidence first, paginated (+ total)
* ``GET  /api/signals/categories``                  — every category + count
  among classified/corrected signals (the Browse dropdown source)
* ``POST /api/signals/{message_id}/unsort``         — flip status -> needs_review

Every Firestore access goes through ``src/signal_store.py`` (injected via
``get_store``); this router holds no raw queries. The category counts reuse the
same projected read the dashboard uses (one field per doc, not the full
document), so Browse loads fast even with thousands of signals.

Safe Mode: ``unsort`` is a bare status flip. It writes no correction_log document
(the correction is logged later when the item is reviewed in the queue) and
touches no Gmail label — there is no Gmail call in this router at all.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.deps import require_user
from app.store import get_store

if TYPE_CHECKING:
    from src.signal_store import SignalStore

router = APIRouter(prefix="/api/signals", tags=["signals"])

# Excerpt cap for the dense Browse list. We derive it from the stored
# body_excerpt when present, else the snippet — no per-row live Gmail fetch, so
# a category page renders fast and works even when Gmail is unreachable.
_EXCERPT_CHARS = 300


# ---------- response models ----------
class BrowseClassification(BaseModel):
    """The AI label shown in a Browse row (just what's needed to scan/sort)."""

    category: str | None = None
    confidence: float = 0.0


class BrowseItem(BaseModel):
    id: str
    sender_raw: str
    subject: str
    snippet: str
    body_excerpt: str = ""
    status: str
    week: str | None = None
    classification: BrowseClassification


class BrowseResponse(BaseModel):
    items: list[BrowseItem]
    total: int  # full count for the category (for "showing N of total")


class CategoryCount(BaseModel):
    category: str
    count: int


class CategoriesResponse(BaseModel):
    categories: list[CategoryCount]


class UnsortResponse(BaseModel):
    status: str
    flagged_for_review: bool = True


# ---------- endpoints ----------
@router.get("", response_model=BrowseResponse)
def browse(
    category: str,
    limit: int = 50,
    after: str | None = None,
    _: str = Depends(require_user),
    store: "SignalStore" = Depends(get_store),
) -> BrowseResponse:
    """Classified/corrected signals in ``category``, lowest-confidence first."""
    limit = max(1, min(limit, 100))
    rows, total = store.get_signals_by_category(category, limit=limit, after_id=after)

    items: list[BrowseItem] = []
    for mid, sig in rows:
        cls = sig.get("classification") or {}
        excerpt = (sig.get("body_excerpt") or sig.get("snippet") or "")[:_EXCERPT_CHARS]
        items.append(
            BrowseItem(
                id=mid,
                sender_raw=sig.get("sender_raw", ""),
                subject=sig.get("subject", ""),
                snippet=sig.get("snippet", ""),
                body_excerpt=excerpt,
                status=sig.get("status", ""),
                week=sig.get("week"),
                classification=BrowseClassification(
                    category=cls.get("category"),
                    confidence=float(cls.get("confidence", 0.0) or 0.0),
                ),
            )
        )
    return BrowseResponse(items=items, total=total)


@router.get("/categories", response_model=CategoriesResponse)
def categories(
    _: str = Depends(require_user),
    store: "SignalStore" = Depends(get_store),
) -> CategoriesResponse:
    """Every category (with count) among classified/corrected signals, descending."""
    return CategoriesResponse(
        categories=[
            CategoryCount(category=name, count=count)
            for name, count in store.category_counts(top=None)
        ]
    )


@router.post("/{message_id}/unsort", response_model=UnsortResponse)
def unsort(
    message_id: str,
    _: str = Depends(require_user),
    store: "SignalStore" = Depends(get_store),
) -> UnsortResponse:
    """Send a signal back to the Review Queue: status -> needs_review, flagged.

    No correction is logged here and the Gmail label is left untouched (Safe
    Mode). The correction, if any, is logged later when the item is reviewed in
    the queue via the existing correct path.
    """
    try:
        new_status = store.unsort_signal(message_id)
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e)) from e
    return UnsortResponse(status=new_status, flagged_for_review=True)
