"""Read-only mail-processing stats for the dashboard.

Two endpoints, both protected by ``require_user``:

* ``GET /api/stats/summary`` — headline counts, top categories, last run
* ``GET /api/stats/weekly``  — per-week pipeline series for the trend chart

Every Firestore read goes through ``src/signal_store.py`` (injected via
``get_store``); this router holds no raw queries. Counts use Firestore's
server-side ``count()`` aggregation, so it never streams the full signal
collection into memory.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.deps import require_user
from app.store import get_store

if TYPE_CHECKING:
    from src.signal_store import SignalStore

router = APIRouter(prefix="/api/stats", tags=["stats"])


# ---------- response models ----------
class StatusCounts(BaseModel):
    """Signal count per status value (the five the pipeline writes)."""

    classified: int = 0
    needs_review: int = 0
    junk_filtered: int = 0
    pending_classification: int = 0
    corrected: int = 0


class CategoryCount(BaseModel):
    name: str
    count: int


class LastRun(BaseModel):
    """Headline figures from the most recent pipeline run."""

    week: str | None = None
    fetched: int = 0
    classified: int = 0
    needs_review: int = 0
    est_cost_usd: float = 0.0


class StatsSummary(BaseModel):
    status_counts: StatusCounts
    total_signals: int
    backlog_pending: int       # pending_classification — waiting for the brain
    needs_review_count: int    # waiting for the human to review
    corrections_total: int     # number of correction_log documents
    categories: list[CategoryCount]
    last_run: LastRun | None


class WeeklyPoint(BaseModel):
    week: str
    fetched: int
    junk_filtered: int
    classified: int
    needs_review: int


# ---------- endpoints ----------
@router.get("/summary", response_model=StatsSummary)
def summary(
    _: str = Depends(require_user),
    store: "SignalStore" = Depends(get_store),
) -> StatsSummary:
    counts = store.get_status_counts()
    last = store.last_run()
    return StatsSummary(
        status_counts=StatusCounts(**counts),
        total_signals=sum(counts.values()),
        backlog_pending=counts.get("pending_classification", 0),
        needs_review_count=counts.get("needs_review", 0),
        corrections_total=store.corrections_count(),
        categories=[
            CategoryCount(name=name, count=count)
            for name, count in store.category_counts(top=10)
        ],
        last_run=(
            LastRun(
                week=last.get("week"),
                fetched=int(last.get("fetched", 0) or 0),
                classified=int(last.get("classified", 0) or 0),
                needs_review=int(last.get("needs_review", 0) or 0),
                est_cost_usd=float(last.get("est_cost_usd", 0) or 0),
            )
            if last
            else None
        ),
    )


@router.get("/weekly", response_model=list[WeeklyPoint])
def weekly(
    _: str = Depends(require_user),
    store: "SignalStore" = Depends(get_store),
) -> list[WeeklyPoint]:
    return [WeeklyPoint(**point) for point in store.weekly_runs()]
