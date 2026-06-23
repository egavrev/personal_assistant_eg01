# Personal Assistant — frontend

Angular 22 (standalone, no NgModules) dashboard for the personal email-triage
assistant: a login screen, an auth guard, an app layout (sidebar + content),
and a **Dashboard page** showing real mail-processing status from Firestore —
stat cards, the last pipeline run, and two charts. Pipeline controls and the
review queue are still to come in later sessions.

Authentication is handled entirely by the FastAPI backend (Google OAuth2 +
an HttpOnly session cookie). The frontend never implements OAuth and never
stores tokens; it only asks the backend "who am I?" and reacts.

## Stack

- Angular 22, standalone components, Angular signals for state (no NgRx).
- Tailwind CSS v3 (utility classes only, no component library).
- Angular Router with a functional auth guard.
- `provideHttpClient(withFetch)` + a credentials interceptor.
- **Charts are hand-rolled SVG/CSS** (`features/dashboard/charts/`) — no chart
  library, so there is no extra dependency to install. `npm install` is enough.

## Prerequisites

- Node.js 22 LTS recommended. (It runs on newer odd-numbered releases such as
  Node 25, but those print an `EBADENGINE`/non-LTS warning — harmless for dev.)
- The auth backend in [`../backend`](../backend) configured and runnable.

## Install

```bash
cd frontend
npm install
```

## Run in development

The app talks only to its own origin (`http://localhost:4200`) and proxies
`/api/*` to the backend, so the session cookie works without CORS friction.
**Both servers must be running.**

**Terminal 1 — backend (port 8000):**

```bash
cd backend
uv run uvicorn app.main:app --reload --port 8000
```

The backend needs these set (in the repo-root `.env`) for the dev login flow:

```dotenv
OAUTH_REDIRECT_URI=http://localhost:8000/api/auth/callback
POST_LOGIN_REDIRECT=http://localhost:4200/
```

`POST_LOGIN_REDIRECT` is what sends you back to *this* app after Google login —
without it the callback would leave you on the backend origin (`:8000`).

**Terminal 2 — frontend (port 4200):**

```bash
cd frontend
ng serve
```

The proxy is already wired into `angular.json` (`serve.options.proxyConfig`), so
plain `ng serve` is enough. Equivalently, you can pass it explicitly:

```bash
ng serve --proxy-config proxy.conf.json
```

Then open `http://localhost:4200/`. Unauthenticated, the guard redirects you to
`/login`; sign in with Google and you land on the Dashboard inside the shell.

## Build

```bash
ng build
```

Compiles to `dist/frontend` with no errors and no `any` types (strict mode).

## How auth flows through the UI

- On startup, an app initializer calls `AuthService.loadMe()` → `GET /api/auth/me`
  (with credentials). `200` sets `currentUser`; `401` clears it.
- `login()` is a full-page redirect to `/api/auth/login` (OAuth needs a real
  browser navigation — it is **not** an `HttpClient` call).
- `logout()` calls `/api/auth/logout`, clears local state, and routes to `/login`.
- The `credentialsInterceptor` sets `withCredentials: true` on every request so
  the HttpOnly session cookie travels. No tokens are kept in `localStorage`.

## Adding a page later (the extension seam)

The shell is built so a new module is **two lines**:

1. One entry in `NAV_ITEMS` in
   [`core/nav.ts`](src/app/core/nav.ts) — `{ label, route, icon? }`. The
   ShellComponent renders this array in a loop.
2. One child route under the shell in
   [`app.routes.ts`](src/app/app.routes.ts).

Both files have a marked `… GO HERE` / `ADD FUTURE …` comment showing exactly where.

## Project structure

```
src/app/
  app.config.ts            # bootstrap: router, http client, auth initializer
  app.routes.ts            # routes + auth guard
  app.component.ts/html    # root: <router-outlet>
  core/
    auth.service.ts        # signals + loadMe/login/logout
    auth.guard.ts          # CanActivateFn -> /login when unauthenticated
    credentials.interceptor.ts  # withCredentials on every request
    nav.ts                 # NAV_ITEMS — the sidebar menu seam
  features/
    login/                 # public login screen
    shell/                 # sidebar layout (renders NAV_ITEMS)
    dashboard/             # status page
      dashboard.service.ts # fetches /api/stats summary + weekly -> signals
      charts/              # weekly-trend (SVG) + category-breakdown (CSS) charts
```

## Notes

- Filenames keep the classic `.component.ts` / `.service.ts` suffix even though
  Angular 22's CLI default drops it. `angular.json` `schematics` is configured to
  match, so future `ng generate` stays consistent with this layout.
