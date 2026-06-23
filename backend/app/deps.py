"""Shared FastAPI dependencies.

``require_user`` is the single auth gate every protected route depends on: it
reads the email the OAuth callback stored in the session and enforces the
allowlist on every request (not just at login).
"""

from __future__ import annotations

from fastapi import HTTPException, Request

from app.config import settings


def require_user(request: Request) -> str:
    """Return the logged-in owner's email, or raise.

    * No session email          -> 401 (not authenticated)
    * Session email not allowed  -> 403 (authenticated, but not the owner)
    * Otherwise                  -> the verified email string
    """
    email = request.session.get("user_email")
    if not email:
        raise HTTPException(status_code=401, detail="Not authenticated.")
    if not settings.is_allowed(email):
        raise HTTPException(
            status_code=403, detail="Access restricted to the account owner."
        )
    return email
