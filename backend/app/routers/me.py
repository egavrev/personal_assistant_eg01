"""Protected test endpoint: GET /api/me.

Exists solely to prove the auth backbone works end to end — it returns the
logged-in owner's email and 401/403 otherwise, via ``require_user``.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.deps import require_user

router = APIRouter(prefix="/api", tags=["me"])


class MeResponse(BaseModel):
    """Shape of the /api/me payload."""

    email: str


@router.get("/me", response_model=MeResponse)
def get_me(email: str = Depends(require_user)) -> MeResponse:
    """Return the authenticated owner's email."""
    return MeResponse(email=email)
