"""FastAPI application entrypoint for the dashboard auth backbone.

Wires the session cookie middleware, dev-only CORS for the Angular dev server,
and the auth router (which also serves /api/auth/me). Importing this module evaluates
``app.config.settings``, so a misconfigured environment fails loudly at startup.

Run locally from the ``backend/`` directory:

    uvicorn app.main:app --reload --port 8000
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.sessions import SessionMiddleware

from app.auth import router as auth_router
from app.config import settings
from app.routers.stats import router as stats_router

# Docs live under /api so they're reachable through the frontend's /api proxy.
app = FastAPI(
    title="Email Triage Dashboard API",
    docs_url="/api/docs",
    openapi_url="/api/openapi.json",
)

# Session cookie. Starlette's SessionMiddleware always sets HttpOnly; we pin
# SameSite=Lax and only enable Secure outside dev so localhost (http) works.
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    same_site="lax",
    https_only=settings.cookie_secure,
)

# CORS for the Angular dev server (http://localhost:4200), dev only. Added last
# so it stays outermost and applies to error responses too.
if settings.is_dev:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["http://localhost:4200"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(auth_router)
app.include_router(stats_router)
