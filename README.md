# Sporafind

Ghanaian diaspora intelligence platform — Express+EJS frontend, FastAPI backend, Supabase (PostgreSQL).

## Deploy

| Service | URL | Source |
|---|---|---|
| Frontend | https://www.sporafind.com | `frontend/` → Vercel (`frontend/vercel.json`, rewrites → `api/server.js`) |
| Backend | https://api.sporafind.com | `backend/` → Vercel (`backend/vercel.json` → `api/index.py`) |

## Env vars

### Backend (`backend/.env` — see `.env.example`)
- `DATABASE_URL` — **Supabase pooler** `...pooler.supabase.com:6543` (port 5432 is IPv6-only, breaks on Vercel). `DIRECT_URL` optional for migrations.
- `SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY`
- `AUTH_SECRET`, `ADMIN_KEY`
- `PUBLIC_API_KEY` — optional. If set, required on **data** endpoints (`/profiles`, `/orgs`, `/search`) via `X-Api-Key`. Marketing endpoints (`/pricing`, `/stats`, `/blog/posts*`) are **always public** (no key).
- `CORS_ORIGINS` — must include `https://sporafind.com,https://www.sporafind.com,https://api.sporafind.com`
- `STRIPE_SECRET_KEY / STRIPE_WEBHOOK_SECRET / STRIPE_PRICE_*`, `TEST_DATABASE_URL`, `REDIS_URL`, `ENVIRONMENT`

### Frontend (Vercel env)
- `API_BASE` (default `http://localhost:8000`), `ADMIN_KEY`, `PUBLIC_API_KEY` (forwarded as `X-Api-Key`)

## Pricing (single source of truth)
`pricing_plans` table (seed `backend/migrations/003_pricing_plans.sql`): **Free $0 / Pro $29 / Enterprise $99**. Frontend `pricing.html` renders DB plans, falls back to the same hardcoded values. Export caps enforced in `backend/app/routers/subscriber.py` (`PLAN_EXPORT_LIMITS = free:100, pro:1000, enterprise:100000`; active Stripe sub counts as pro).

## Auth
Token-based (`backend/app/auth.py`, `routers/auth.py`). Browser client `frontend/js/session.js` calls `/api/workspace/login|signup|me` and stores `sf_token` + `sf_user` in localStorage. No demo credentials. Admin cookie `admin_token` is HttpOnly.

## Tests
- Backend: `cd backend; python -m pytest tests/test_export_limits.py -v` (unit, no DB). Full suite needs `TEST_DATABASE_URL` postgres.
- Frontend: `cd frontend; npm test` (vitest: 18 tests).
