"""Google OAuth2 login via Authlib.

Implements the three auth endpoints mounted under ``/api/auth``:

* ``GET /api/auth/login``    -> redirect to Google's consent screen
* ``GET /api/auth/callback`` -> exchange code, enforce allowlist, set session
* ``GET /api/auth/logout``   -> clear the session

Scopes are limited to ``openid email profile`` — no Gmail scopes are
requested here; the pipeline's Gmail access is entirely separate.
"""

from __future__ import annotations

from authlib.integrations.starlette_client import OAuth, OAuthError
from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import JSONResponse, RedirectResponse

from app.config import settings

# Single OIDC client, configured from Google's published metadata document so we
# never hardcode token/authorize/jwks URLs.
oauth = OAuth()
oauth.register(
    name="google",
    client_id=settings.oauth_client_id,
    client_secret=settings.oauth_client_secret,
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

router = APIRouter(prefix="/api/auth", tags=["auth"])

# Where to send the browser once login succeeds (the future Angular SPA root).
_POST_LOGIN_REDIRECT = "/"


@router.get("/login")
async def login(request: Request) -> RedirectResponse:
    """Kick off the OAuth flow by redirecting to Google's consent screen."""
    redirect_uri = request.url_for("auth_callback")
    return await oauth.google.authorize_redirect(request, redirect_uri)


@router.get("/callback", name="auth_callback")
async def callback(request: Request) -> RedirectResponse:
    """Handle Google's redirect: verify the user, enforce the allowlist, set session."""
    try:
        token = await oauth.google.authorize_access_token(request)
    except OAuthError:
        # Bad/expired code, state mismatch, user denied consent, etc.
        raise HTTPException(status_code=400, detail="OAuth authorization failed.")

    # With OIDC, Authlib parses the id_token into token["userinfo"].
    userinfo = token.get("userinfo") or {}
    email = userinfo.get("email")
    email_verified = userinfo.get("email_verified", False)

    if not email or not email_verified:
        raise HTTPException(status_code=403, detail="Email address is not verified.")

    if not settings.is_allowed(email):
        # Do NOT create a session for non-owner accounts.
        raise HTTPException(
            status_code=403, detail="Access restricted to the account owner."
        )

    # Store only the verified email — nothing else goes in the session.
    request.session["email"] = email
    return RedirectResponse(url=_POST_LOGIN_REDIRECT, status_code=302)


@router.get("/logout")
async def logout(request: Request) -> JSONResponse:
    """Clear the session cookie's contents and confirm with 200."""
    request.session.clear()
    return JSONResponse({"status": "logged out"}, status_code=200)
