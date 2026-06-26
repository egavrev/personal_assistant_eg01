"""Bulk week-processing control for the dashboard.

Three endpoints, all protected by ``require_user``:

* ``POST /api/pipeline/run-weeks?count=&dry_run=`` — start a background run of the
  real pipeline for ``count`` consecutive cursor windows; returns a ``job_id``
* ``GET  /api/pipeline/run-weeks/{job_id}/status`` — progress for that job
* ``GET  /api/pipeline/state``                     — cursor + the next window

The work itself is *not* reimplemented here: each week calls
``run_ingestion.run_one_week``, which reuses ``stage_ingest``/``stage_classify``
(the same code the CLI runs) and advances the cursor only after the week
completes. So the run is idempotent (signals keyed by message_id) and
interrupt-safe — a failure mid-run leaves the cursor at the last completed week.

Job state is kept in-process (this is a single-user local app); a restart loses
it, which is fine for a POC. Only one run is allowed at a time, because every run
advances the shared ingestion cursor and two concurrent runs would race it.
"""

from __future__ import annotations

import threading
import uuid
from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from pydantic import BaseModel

from app.deps import require_user
from app.store import _ensure_pipeline_env

router = APIRouter(prefix="/api/pipeline", tags=["pipeline"])

# Per-week figures we surface and accumulate (subset of the run stats dict).
_TOTAL_KEYS = ("fetched", "junk_filtered", "classified", "needs_review")
# Safety cap on a single bulk run (a year of weeks) — guards against a fat-finger
# "process 9999 weeks" that would burn LLM budget.
_MAX_WEEKS = 52

# In-process job registry, guarded by a lock (the worker runs in a threadpool).
_jobs: dict[str, dict[str, Any]] = {}
_jobs_lock = threading.Lock()


# ---------- response models ----------
class WeekResult(BaseModel):
    week: str
    fetched: int = 0
    junk_filtered: int = 0
    classified: int = 0
    needs_review: int = 0


class JobStatus(BaseModel):
    job_id: str
    state: str  # running | done | error
    dry_run: bool
    weeks_total: int
    weeks_done: int
    current_week: str | None = None
    totals: dict[str, int]  # running sums across completed weeks
    weeks: list[WeekResult]
    error: str | None = None


class StartResponse(BaseModel):
    job_id: str
    state: str
    weeks_total: int


class PipelineState(BaseModel):
    last_processed_date: str  # the cursor (also the next window's start)
    next_start: str
    next_end: str


# ---------- background worker ----------
def _fail(job_id: str, exc: Exception) -> None:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is not None:
            job["state"] = "error"
            job["error"] = f"{type(exc).__name__}: {exc}"
            job["current_week"] = None


def _run_weeks_job(job_id: str, count: int, dry_run: bool) -> None:
    """Build the pipeline clients once, then run ``count`` weeks, updating the job
    after each completed week. Any failure stops the run with the cursor left at
    the last completed week (run_one_week advances it only on success)."""
    try:
        _ensure_pipeline_env()
        import os

        from run_ingestion import load_config, run_one_week
        from src.classifier import Classifier
        from src.state_manager import StateManager
        from src.triage_filter import TriageFilter

        from app.gmail import get_gmail
        from app.store import get_store

        config = load_config()
        project = os.environ["GOOGLE_CLOUD_PROJECT"]
        gmail = get_gmail()
        store = get_store()
        firewall = TriageFilter(config.get("triage_filter", {}))
        state = StateManager()
        clf_cfg = {
            **config["classifier"],
            "seed_interests": config["preferences"]["seed_interests"],
        }
        classifier = Classifier(project, clf_cfg)
    except Exception as exc:  # noqa: BLE001 - report wiring failure on the job
        _fail(job_id, exc)
        return

    for _ in range(count):
        try:
            result = run_one_week(
                gmail, firewall, store, classifier, config, state, dry_run=dry_run
            )
        except Exception as exc:  # noqa: BLE001 - stop here; cursor not advanced
            _fail(job_id, exc)
            return
        with _jobs_lock:
            job = _jobs.get(job_id)
            if job is None:  # never happens, but stay defensive
                return
            week = {k: int(result.get(k, 0) or 0) for k in _TOTAL_KEYS}
            week["week"] = result["week"]
            job["weeks"].append(week)
            job["weeks_done"] += 1
            job["current_week"] = result["week"]
            for k in _TOTAL_KEYS:
                job["totals"][k] += week[k]

    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is not None:
            job["state"] = "done"
            job["current_week"] = None


# ---------- endpoints ----------
@router.post("/run-weeks", response_model=StartResponse)
def run_weeks(
    background: BackgroundTasks,
    count: int = 1,
    dry_run: bool = False,
    _: str = Depends(require_user),
) -> StartResponse:
    """Kick off a background run of ``count`` weeks. Returns immediately with a
    ``job_id`` to poll; rejects a second run while one is already in progress."""
    count = max(1, min(count, _MAX_WEEKS))
    with _jobs_lock:
        if any(j["state"] == "running" for j in _jobs.values()):
            raise HTTPException(
                status_code=409, detail="A pipeline run is already in progress."
            )
        job_id = uuid.uuid4().hex[:12]
        _jobs[job_id] = {
            "job_id": job_id,
            "state": "running",
            "dry_run": dry_run,
            "weeks_total": count,
            "weeks_done": 0,
            "current_week": None,
            "totals": {k: 0 for k in _TOTAL_KEYS},
            "weeks": [],
            "error": None,
        }
    background.add_task(_run_weeks_job, job_id, count, dry_run)
    return StartResponse(job_id=job_id, state="running", weeks_total=count)


@router.get("/run-weeks/{job_id}/status", response_model=JobStatus)
def run_weeks_status(
    job_id: str,
    _: str = Depends(require_user),
) -> JobStatus:
    with _jobs_lock:
        job = _jobs.get(job_id)
        if job is None:
            raise HTTPException(status_code=404, detail="Unknown job id.")
        return JobStatus(
            job_id=job["job_id"],
            state=job["state"],
            dry_run=job["dry_run"],
            weeks_total=job["weeks_total"],
            weeks_done=job["weeks_done"],
            current_week=job["current_week"],
            totals=dict(job["totals"]),
            weeks=[WeekResult(**w) for w in job["weeks"]],
            error=job["error"],
        )


@router.get("/state", response_model=PipelineState)
def state(_: str = Depends(require_user)) -> PipelineState:
    """The ingestion cursor and the next window it would process."""
    try:
        _ensure_pipeline_env()
        from run_ingestion import load_config
        from src.state_manager import StateManager

        config = load_config()
        days = config["ingestion"]["days_per_batch"]
        start, end = StateManager().get_date_window(days_to_fetch=days)
        return PipelineState(last_processed_date=start, next_start=start, next_end=end)
    except Exception as e:  # noqa: BLE001 - any wiring failure -> clear 503
        raise HTTPException(
            status_code=503,
            detail=f"Pipeline state unavailable: {type(e).__name__}: {e}",
        ) from e
