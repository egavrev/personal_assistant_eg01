"""Application configuration.

Loads settings from the environment, falling back to a local ``.env`` file in
dev via ``python-dotenv``. Required secrets are never hardcoded and never
logged. Fails loudly at import (startup) time if any required var is missing —
mirroring the fail-fast style of ``src/auth.py`` in the pipeline code.
"""

from __future__ import annotations

import os

from dotenv import load_dotenv
from pydantic import BaseModel

# Load a local .env if present (dev). In prod the vars come from the real
# environment and this is a no-op.
load_dotenv()

# Vars that must be present for the app to start. ENV is optional (default dev).
_REQUIRED_VARS: tuple[str, ...] = (
    "DASHBOARD_OAUTH_CLIENT_ID",
    "DASHBOARD_OAUTH_CLIENT_SECRET",
    "SESSION_SECRET",
    "ALLOWED_USER_EMAIL",
)


class Settings(BaseModel):
    """Typed, validated application settings.

    Secret values live here but are never logged. ``repr`` is left to Pydantic;
    do not print this object in full.
    """

    oauth_client_id: str
    oauth_client_secret: str
    session_secret: str
    allowed_user_email: str
    env: str = "dev"

    @property
    def is_dev(self) -> bool:
        """True when running the local dev environment."""
        return self.env == "dev"

    @property
    def cookie_secure(self) -> bool:
        """Session cookie ``Secure`` flag: off in dev so localhost works, on otherwise."""
        return not self.is_dev

    def is_allowed(self, email: str | None) -> bool:
        """Allowlist check: the email must match the single owner account.

        Compared case-insensitively and trimmed so trivial formatting
        differences don't lock out the owner. Used by both the OAuth callback
        and ``require_user()`` so they enforce the same rule.
        """
        if not email:
            return False
        return email.strip().lower() == self.allowed_user_email.strip().lower()


def _load_settings() -> Settings:
    """Read + validate settings from the environment, failing loudly if incomplete."""
    missing = [var for var in _REQUIRED_VARS if not os.environ.get(var)]
    if missing:
        raise RuntimeError(
            "Missing required environment variable(s): "
            + ", ".join(missing)
            + ". Set them in your environment or in backend/.env "
            "(see backend/README.md)."
        )

    return Settings(
        oauth_client_id=os.environ["DASHBOARD_OAUTH_CLIENT_ID"],
        oauth_client_secret=os.environ["DASHBOARD_OAUTH_CLIENT_SECRET"],
        session_secret=os.environ["SESSION_SECRET"],
        allowed_user_email=os.environ["ALLOWED_USER_EMAIL"],
        env=os.environ.get("ENV", "dev"),
    )


# Singleton settings instance, evaluated at import time so startup fails fast.
settings: Settings = _load_settings()
