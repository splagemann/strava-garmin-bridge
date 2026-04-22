# Development

## Recommended local setup

Use Docker for the backend stack and run the frontend natively with Vite.

This is the easiest development path, especially on machines without Python 3.12 installed locally.

## Start everything quickly

From the repo root:

```bash
./scripts/start-dev.sh
```

This starts the backend Docker stack and then launches the frontend Vite dev server.

## Start services manually

Backend stack:

```bash
docker compose up -d db redis backend celery celery-beat
```

Frontend in a separate terminal:

```bash
cd frontend
npm install
npm run dev
```

## URLs

- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- API docs: http://localhost:8000/docs

## Environment setup

Create the following local-only files:

```bash
cp backend/.env.example .env
cp frontend/.env.example frontend/.env.local
```

Fill in real values for:
- `STRAVA_CLIENT_ID`
- `STRAVA_CLIENT_SECRET`
- `SECRET_KEY`
- `ENCRYPTION_KEY`

Optional if you use Withings:
- `WITHINGS_CLIENT_ID`
- `WITHINGS_CLIENT_SECRET`

Notes:
- `.env` is gitignored
- `frontend/.env.local` is gitignored
- use `localhost` as the Strava callback domain for local development
- frontend callback URL: `http://localhost:5173/auth/callback`

## Why the Docker setup looks slightly unusual

The backend container runs database migrations on startup.

Celery and Celery Beat intentionally skip migrations via `RUN_MIGRATIONS=false` and wait for the backend service to start. This avoids Alembic startup races when multiple containers boot at once.

## Useful checks

```bash
docker compose ps
docker compose logs -f backend
docker compose logs -f celery
docker compose logs -f celery-beat
```

## Rebuild after dependency changes

```bash
docker compose up -d --build backend celery celery-beat
```
