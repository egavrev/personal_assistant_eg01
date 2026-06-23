# Dashboard backend

FastAPI backend providing Google OAuth2 login, a session cookie, a single-owner
email allowlist, and **read-only mail-processing stats** for the personal
email-triage dashboard.

The backend is additive and does not modify the pipeline (`run_ingestion.py`).
The stats endpoints **reuse** the pipeline's Firestore layer
(`src/signal_store.py`) rather than issuing their own queries — counts use
Firestore `count()` aggregations, so the full signal collection is never
streamed into memory.

## Endpoints

| Method | Path                 | Auth        | Purpose                                                      |
| ------ | -------------------- | ----------- | ------------------------------------------------------------ |
| GET    | `/api/auth/login`    | public      | Redirect to Google's consent screen (`openid email profile`) |
| GET    | `/api/auth/callback` | public      | Exchange code, enforce allowlist, set session, redirect to `/` |
| GET    | `/api/auth/logout`   | public      | Clear the session, return `200`                              |
| GET    | `/api/auth/me`       | owner only  | Return `{"email": ...}` for the logged-in owner              |
| GET    | `/api/stats/summary` | owner only  | Headline counts, top categories, cumulative cost, last run   |
| GET    | `/api/stats/weekly`  | owner only  | Per-week pipeline series (fetched/junk/classified/needs_review) |

`require_user()` (in `app/deps.py`) is the single gate for protected routes:
no session → `401`; session present but not the allowlisted owner → `403`.
Interactive API docs are served at `/api/docs`.

## Environment variables

The app reads these from the environment, falling back to a `.env` file in dev
(auto-discovered by `python-dotenv`, walking up from `app/config.py` — the
repo-root `.env` is found automatically; a `backend/.env`, if present, takes
precedence). **Startup fails loudly if any required var is missing.**

| Variable                        | Required | Description                                                  |
| ------------------------------- | -------- | ----------------------------------------------------------- |
| `DASHBOARD_OAUTH_CLIENT_ID`     | yes      | Google OAuth 2.0 client ID                                  |
| `DASHBOARD_OAUTH_CLIENT_SECRET` | yes      | Google OAuth 2.0 client secret                              |
| `SESSION_SECRET`                | yes      | Random secret used to sign the session cookie               |
| `ALLOWED_USER_EMAIL`            | yes      | The single account allowed to log in (the owner)            |
| `ENV`                           | no       | `dev` (default) → cookie `Secure` off; anything else → on   |
| `GOOGLE_CLOUD_PROJECT`          | stats    | GCP project for Firestore. Required by `/api/stats/*` only — auth boots without it (stats then return `503`). Same var the pipeline uses. |

The stats endpoints read Firestore via `src/signal_store.py` using **Application
Default Credentials** — the same ADC the pipeline relies on. Locally, run
`gcloud auth application-default login` once if you haven't already. The store is
built lazily on first stats request, so a missing project or missing credentials
surfaces as a `503` on `/api/stats/*` rather than blocking startup or login.

Secrets are read from env/`.env` only — never hardcoded, never logged. In
production, fetch them from Secret Manager (mirroring `src/auth.py`'s
`gcloud secrets versions access` pattern) and export them into the environment.

Example `.env` (do not commit — `.env` is gitignored):

```dotenv
DASHBOARD_OAUTH_CLIENT_ID=xxxxxxxx.apps.googleusercontent.com
DASHBOARD_OAUTH_CLIENT_SECRET=your-client-secret
SESSION_SECRET=generate-a-long-random-string
ALLOWED_USER_EMAIL=you@example.com
ENV=dev
```

Generate a session secret with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`.

## Google OAuth client setup (one-time)

In Google Cloud Console → APIs & Services → Credentials, create an **OAuth 2.0
Client ID** of type *Web application* and add this **Authorized redirect URI**:

```
http://localhost:8000/api/auth/callback
```

Only the `openid email profile` scopes are requested — **no Gmail scopes**.

## Install deps with uv

From the `backend/` directory:

```bash
uv venv --python 3.12
uv pip install -r requirements.txt
```

## Run locally

From the `backend/` directory:

```bash
uv run uvicorn app.main:app --reload --port 8000
# or, with the venv activated:
uvicorn app.main:app --reload --port 8000
```

## Local login test

1. Start the server (above).
2. In a browser, visit:

   ```
   http://localhost:8000/api/auth/login
   ```

3. You are redirected to Google's consent screen. Sign in with the
   `ALLOWED_USER_EMAIL` account and approve.
4. Google redirects back to `/api/auth/callback`; on success you are redirected
   to `/` and an `HttpOnly` session cookie is set.
5. Confirm the session works:

   ```
   http://localhost:8000/api/auth/me   →  {"email": "you@example.com"}
   ```

6. Log out, then re-check `/api/me`:

   ```
   http://localhost:8000/api/auth/logout   →  {"status": "logged out"}
   http://localhost:8000/api/auth/me            →  401 {"detail": "Not authenticated."}
   ```

Signing in with a **non-allowlisted** account returns `403`
(`{"detail": "Access restricted to the account owner."}`) at the callback and
**no session is created**.
