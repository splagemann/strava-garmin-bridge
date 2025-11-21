# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Development Commands

### Docker (Recommended)
```bash
# Start all services
docker compose up -d

# View logs
docker compose logs -f web          # Backend API
docker compose logs -f celery       # Background worker
docker compose logs -f celery-beat  # Scheduled tasks
docker compose logs -f frontend     # React frontend

# Restart specific service
docker compose restart web
docker compose restart celery

# Stop all services
docker compose down

# Rebuild after dependency changes
docker compose up -d --build
```

### Backend Development (Manual)
```bash
# Install dependencies
pip install -r requirements.txt

# Database migrations
alembic upgrade head                                    # Apply migrations
alembic revision --autogenerate -m "description"        # Create migration

# Run services (in separate terminals)
uvicorn app.main:app --reload                          # API server
celery -A app.celery_app worker --loglevel=info        # Task worker
celery -A app.celery_app beat --loglevel=info          # Scheduler

# Code formatting
black app/
isort app/

# Testing
pytest tests/
```

### Frontend Development
```bash
cd frontend
npm install
npm run dev        # Development server at http://localhost:5173
npm run build      # Production build
npm run lint       # ESLint
```

## Architecture Overview

### Bidirectional Sync System

This application syncs activities **bidirectionally** between Strava and Garmin Connect:

- **Strava → Garmin**: Original sync direction
- **Garmin → Strava**: New sync direction (as of recent updates)

Both directions use the same polling pattern (every 5 minutes) but have separate services.

### Key Components

**Backend (FastAPI + Celery)**
- **app/routes/**: API endpoints (auth, sync, filters)
- **app/services/**: Core business logic
  - `strava_service.py`: Strava API interactions (OAuth, fetch activities)
  - `garmin_service.py`: Garmin Connect API (auth, fetch/upload activities)
  - `sync_service.py`: Strava → Garmin sync orchestration
  - `garmin_to_strava_sync_service.py`: Garmin → Strava sync orchestration
- **app/tasks/sync_tasks.py**: Celery background tasks
  - `poll_strava_activities_task`: Polls Strava every 5 minutes
  - `poll_garmin_activities_task`: Polls Garmin every 5 minutes
- **app/models/**: SQLAlchemy ORM models (User, StravaAuth, GarminAuth, ActivityFilter, SyncLog)
- **app/utils/**: Crypto, JWT, activity conversion utilities

**Frontend (React + TypeScript)**
- **src/pages/**: Page components (Dashboard, AuthPage, CallbackPage, FiltersPage)
- **src/api/**: API client with Axios interceptors
- **src/hooks/**: React hooks (useAuth, useSync)

### Sync Flow

**Automatic Polling (Both Directions)**
1. Celery Beat triggers scheduled task every 5 minutes
2. Task fetches activities from source (Strava or Garmin) from last 7 days
3. For each activity:
   - Check if already synced (duplicate prevention)
   - Check user's activity filters (include/exclude patterns)
   - Check if activity originated from opposite direction (ping-pong prevention)
   - If checks pass: download activity data, convert format, upload to destination
4. Log sync result to database with status (success/failed/skipped)

**Manual Sync**
- Users can manually trigger sync via API endpoints
- Supports activities older than 7 days (up to 90 days)
- Always attempts sync even if activity already in sync log (`force_sync=True`)

### Authentication

**Strava**: OAuth2 flow
- Frontend initiates OAuth via `/api/v1/auth/strava/auth-url`
- Returns signed state token (JWT) stored in sessionStorage/localStorage
- After OAuth redirect, backend validates state and exchanges code for tokens
- Access/refresh tokens stored in `strava_auth` table

**Garmin**: Credentials-based
- Email/password encrypted with Fernet symmetric encryption
- Session data stored for persistent authentication
- No 2FA support (may require app-specific passwords if 2FA enabled)

### Activity Filtering

Users can configure include/exclude filters:
- **Field**: Match against activity name or activity type
- **Pattern**: Simple substring or regex
- **Filter Logic**:
  - If include filters exist: activity must match at least one
  - Exclude filters: activity must not match any
  - If no filters: sync all activities

### Date Handling

**Important**: The Garmin API returns dates in different formats depending on the method used:
- `get_activities()`: Returns ISO format with timezone `'2025-11-21T14:21:56Z'`
- `get_activities_by_date()`: Returns simple format `'2025-11-21 14:21:56'` (no timezone)

Always handle both formats when parsing activity dates. Use timezone-aware datetime comparisons.

### Garmin API Methods

The `garminconnect` library has specific methods - do NOT make up method names:
- `get_activities(start, limit)`: Get recent activities (paginated, no date filter)
- `get_activities_by_date(startdate, enddate)`: Get activities in date range (preferred for cron)
- `get_activity(activity_id)`: Get single activity by ID
- `get_activity_details(activity_id)`: Get detailed activity with charts/polygons
- `upload_activity(fit_file)`: Upload FIT file

### Sync Direction Implementation

**Strava → Garmin** (`sync_service.py`):
- No duplicate check by default (creates new sync log each time)
- Converts Strava DetailedActivity to FIT format
- Uses `activity_converter.py` for type mapping

**Garmin → Strava** (`garmin_to_strava_sync_service.py`):
- Checks for duplicates by default (skips if already synced)
- Prevents ping-pong: won't sync activities that originally came from Strava
- Downloads FIT file from Garmin, uploads to Strava
- Has `force_sync` parameter for manual/retry operations

### Cron Job Optimization

For efficiency, the cron job passes pre-fetched activity data to avoid redundant API calls:
```python
# In poll_garmin_activities_task
activities = garmin_service.get_activities_by_date(start_date)
for activity in activities:
    # Pass full activity object to avoid second API call
    sync_service.sync_activity(garmin_id, activity_data=activity)
```

Manual sync still uses `get_activity_by_id()` since it doesn't have cached data.

## Common Development Patterns

### Adding a New API Endpoint
1. Define route in `app/routes/`
2. Add business logic to appropriate service in `app/services/`
3. Update frontend API client in `frontend/src/api/`
4. Add TypeScript types in `frontend/src/types/`

### Database Changes
1. Modify models in `app/models/`
2. Generate migration: `alembic revision --autogenerate -m "description"`
3. Review generated migration in `migrations/versions/`
4. Apply: `alembic upgrade head`

### Debugging Celery Tasks
```bash
# Watch celery logs in real-time
docker compose logs -f celery celery-beat

# Check task status
docker compose exec web python -c "from app.celery_app import celery_app; print(celery_app.control.inspect().registered())"

# Manually trigger task for testing
docker compose exec web python -c "from app.tasks.sync_tasks import poll_garmin_activities_task; poll_garmin_activities_task.apply(kwargs={'lookback_days': 1})"
```

### Working with Encrypted Data
Garmin credentials are encrypted using Fernet (app/utils/crypto.py). Always use the utility functions:
```python
from app.utils.crypto import encrypt_password, decrypt_password
encrypted = encrypt_password(password)
decrypted = decrypt_password(encrypted)
```

## Important Constraints

### File Naming Conflicts
**Never** create a file named `garminconnect.py` in the project root - it conflicts with the installed `garminconnect` package and causes import errors. The actual library source is in `../garminconnect.py` for reference only.

### OAuth State Management
The OAuth flow uses JWT-signed state tokens for CSRF protection. The frontend stores these in both sessionStorage (primary) and localStorage (fallback) to handle browser redirect issues. Backend validates state tokens with direct comparison fallback for resilience.

### Activity Deduplication
Three levels of duplicate prevention:
1. **Sync log check**: Don't sync if activity already in `sync_logs` table
2. **Ping-pong prevention**: Don't sync back activities that originated from the opposite platform
3. **Cron job only**: Skip activities already synced (manual/retry ignore this)

### Date Filtering
Cron jobs filter to last 7 days for efficiency. Manual sync supports up to 90 days. Always use `get_activities_by_date()` for cron jobs (server-side filtering) rather than `get_activities()` (client-side filtering).

## Configuration

Key environment variables in `.env`:
- `STRAVA_CLIENT_ID` / `STRAVA_CLIENT_SECRET`: Strava API credentials
- `ENCRYPTION_KEY`: Fernet key for encrypting Garmin credentials
- `SECRET_KEY`: JWT signing key
- `BASE_URL`: Backend API URL (for OAuth redirects)
- `FRONTEND_URL`: Frontend URL (for OAuth callbacks)
- `DATABASE_URL`: PostgreSQL connection string
- `REDIS_URL`: Redis connection string for Celery

Celery schedule configured in `app/celery_app.py` (both directions poll every 5 minutes by default).
