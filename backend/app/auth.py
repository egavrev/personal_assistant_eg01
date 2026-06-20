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
import os

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
async def login(request: Request):
    print(">>> redirect ",os.environ["OAUTH_REDIRECT_URI"])
    return await oauth.google.authorize_redirect(
        request,
        os.environ["OAUTH_REDIRECT_URI"],
    )

@router.get("/callback")
async def callback(request: Request):
    try:
        token = await oauth.google.authorize_access_token(request)   # no redirect_uri arg
        user = token.get("userinfo")
        email = user["email"]
        print(">>> email  ", email)
        print(">> allowed emails",os.environ["ALLOWED_USER_EMAIL"])
        if email != os.environ["ALLOWED_USER_EMAIL"]:
            raise HTTPException(status_code=403, detail="Access restricted to the account owner.")
        request.session["user_email"] = email
        return RedirectResponse(url="/")
    except HTTPException:
        raise
    except Exception as e:
        import traceback; traceback.print_exc()
        raise HTTPException(status_code=400, detail=f"{type(e).__name__}: {e}")

@router.get("/me")
def me(request: Request):
    print(">>> session contents:", dict(request.session))
    email = request.session.get("user_email")
    if not email:
        raise HTTPException(status_code=401, detail="Not authenticated")
    return {"email": email}


@router.get("/logout")
async def logout(request: Request) -> JSONResponse:
    """Clear the session cookie's contents and confirm with 200."""
    request.session.clear()
    return JSONResponse({"status": "logged out"}, status_code=200)
