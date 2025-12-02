# Setup Guide

Step-by-step guide to get your Strava-Garmin Sync Bridge up and running.

## Quick Start (TL;DR)

```bash
# 1. Generate encryption key
pip install cryptography
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"

# 2. Configure environment
cp .env.example .env
# Edit .env with your Strava API credentials and encryption key

# 3. Start services
docker compose up -d

# 4. Initialize database
docker compose exec web alembic upgrade head

# 5. Connect accounts
# Visit: http://localhost:8000/api/v1/auth/strava/login
# Then add Garmin credentials via API or docs
```

API Documentation: http://localhost:8000/docs

---

## Step 1: Prerequisites

### Required Accounts
- [Strava](https://www.strava.com) account
- [Garmin Connect](https://connect.garmin.com) account
- [Strava API Application](https://www.strava.com/settings/api)

### Required Software (Docker Method)
- Docker
- Docker Compose

### Required Software (Manual Method)
- Python 3.11+
- PostgreSQL 15+
- Redis 7+

## Step 2: Strava API Setup

1. **Create a Strava API Application**
   - Go to https://www.strava.com/settings/api
   - Click "Create Application"
   - Fill in the form:
     - **Application Name**: Strava-Garmin Sync
     - **Category**: Training
     - **Website**: http://localhost:8000 (for testing)
     - **Authorization Callback Domain**: localhost (or your domain)
     - **Application Description**: Automatically sync activities to Garmin Connect

2. **Save Your Credentials**
   - Copy the **Client ID**
   - Copy the **Client Secret**
   - You'll need these for the `.env` file

## Step 3: Generate Encryption Key

Run this command to generate an encryption key for Garmin credentials:

```bash
# If you don't have cryptography installed locally:
pip install cryptography

# Generate the key:
python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
```

Save the output - you'll need it for the `.env` file.

**Example output:**
```
RDG3wCbonI_zTV0M6o9kIs8qe2jn8mL7JTDc05bxmQA=
```

## Step 4: Clone and Configure

1. **Navigate to project directory**
```bash
cd strava-garmin-bridge
```

2. **Create environment file**
```bash
cp backend/.env.example .env
```

3. **Edit `.env` file**
```bash
# Open in your editor
nano .env  # or vim .env or code .env
```

Fill in the following values:
```env
# Database (leave as-is for Docker)
DATABASE_URL=postgresql://strava_garmin:changeme@db:5432/strava_garmin_sync

# Strava API (from Step 2)
STRAVA_CLIENT_ID=your_client_id_here
STRAVA_CLIENT_SECRET=your_client_secret_here

# Redis (leave as-is for Docker)
REDIS_URL=redis://redis:6379/0

# Security (from Step 3)
ENCRYPTION_KEY=your_encryption_key_here
SECRET_KEY=another_random_string_here  # Any random string

# Application
BASE_URL=http://localhost:8000  # Change in production
ENVIRONMENT=development
LOG_LEVEL=INFO
```

## Step 5: Start the Application

### Option A: Docker (Recommended)

1. **Start all services**
```bash
docker compose up -d
```
# Note: This will start the backend services. The frontend needs to be started separately as described in the "Frontend Development" section of the README.md.

**Note:** Use `docker compose` (space) not `docker-compose` (hyphen) for newer Docker versions.

2. **Initialize the database**

First time only - create the database tables:

```bash
# Generate the initial migration (if not already present)
docker compose exec web alembic revision --autogenerate -m "Initial migration"

# Apply the migration to create tables
docker compose exec web alembic upgrade head
```

3. **Check status**
```bash
docker compose ps
```

All services should show "Up" status.

4. **View logs**
```bash
docker compose logs -f web
```

To view specific service logs:
```bash
docker compose logs -f web      # Web application
docker compose logs -f celery   # Background tasks
docker compose logs -f db       # Database
```

### Option B: Manual Setup

1. **Create virtual environment**
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
```

2. **Install dependencies**
```bash
pip install -r backend/requirements.txt
```

3. **Start PostgreSQL and Redis**
```bash
# Make sure PostgreSQL and Redis are running
# Instructions vary by OS
```

4. **Initialize database**
```bash
# Create database (if not exists)
createdb strava_garmin_sync

# Run migrations to create tables
cd backend
alembic upgrade head
cd ..
```

5. **Start services in separate terminals**

Terminal 1 - Web Server:
```bash
uvicorn backend.app.main:app --reload --host 0.0.0.0 --port 8000
```

Terminal 2 - Celery Worker:
```bash
celery -A backend.app.celery_app worker --loglevel=info
```

## Step 6: Connect Your Accounts

### 6.1 Connect Strava

1. **Open your browser**
   - Navigate to: http://localhost:8000/api/v1/auth/strava/login

2. **Authorize the application**
   - You'll be redirected to Strava
   - Click "Authorize"
   - You'll be redirected back with your user info

3. **Save your User ID**
   - The response will include a `user_id` and `athlete_id`
   - Save the `user_id` - you'll need it for all API calls

**Example successful response:**
```json
{
  "message": "Successfully connected to Strava",
  "user_id": 1,
  "athlete_id": "25760900"
}
```

### 6.2 Connect Garmin

Using curl (replace YOUR_USER_ID with your actual user ID):

```bash
curl -X POST "http://localhost:8000/api/v1/auth/garmin/credentials?user_id=YOUR_USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-garmin-email@example.com",
    "password": "your-garmin-password"
  }'
```

Or using a tool like Postman:
- Method: POST
- URL: `http://localhost:8000/api/v1/auth/garmin/credentials?user_id=YOUR_USER_ID`
- Body (JSON):
```json
{
  "email": "your-garmin-email@example.com",
  "password": "your-garmin-password"
}
```

### 6.3 Verify Connection Status

```bash
curl "http://localhost:8000/api/v1/auth/status?user_id=YOUR_USER_ID"
```

Expected response:
```json
{
  "user_id": 1,
  "email": "athlete_123456@strava.local",
  "strava_connected": true,
  "garmin_connected": true,
  "strava_athlete_id": "123456"
}
```

## Step 7: Set Up Webhook (For Automatic Sync)

**Note**: Your application must be publicly accessible for webhooks to work. For local development, use a tool like [ngrok](https://ngrok.com/).

### 7.1 Make Your App Publicly Accessible (Development)

```bash
# Install ngrok
# Then run:
ngrok http 8000
```

Copy the HTTPS URL (e.g., `https://abc123.ngrok.io`)

### 7.2 Update BASE_URL

Edit `.env`:
```env
BASE_URL=https://abc123.ngrok.io
```

Restart the application:
```bash
docker compose restart web
```

### 7.3 Create Webhook Subscription

```bash
curl -X POST "http://localhost:8000/webhook/subscribe"
```

Or visit: http://localhost:8000/webhook/subscribe (in browser)

Expected response:
```json
{
  "message": "Webhook subscription created",
  "subscription": {
    "id": 12345,
    "resource_state": 2,
    ...
  }
}
```

## Step 8: Test Manual Sync

Before relying on webhooks, test manual sync:

1. **Get a Strava activity ID**
   - Go to Strava website
   - Open any activity
   - The URL will be like: `https://www.strava.com/activities/12345678`
   - Copy the ID (12345678)

2. **Trigger manual sync**
```bash
curl -X POST "http://localhost:8000/api/v1/sync/manual?user_id=YOUR_USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "strava_activity_id": 12345678
  }'
```

3. **Check sync status**
```bash
curl "http://localhost:8000/api/v1/sync/history?user_id=YOUR_USER_ID&limit=5"
```

## Step 9: Configure Filters (Optional)

### Example: Only sync runs

```bash
curl -X POST "http://localhost:8000/api/v1/filters/?user_id=YOUR_USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "filter_type": "include",
    "pattern": ".*run.*",
    "is_regex": true,
    "active": true
  }'
```

### Example: Exclude activities with "test"

```bash
curl -X POST "http://localhost:8000/api/v1/filters/?user_id=YOUR_USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "filter_type": "exclude",
    "pattern": "test",
    "is_regex": false,
    "active": true
  }'
```

### List all filters

```bash
curl "http://localhost:8000/api/v1/filters/?user_id=YOUR_USER_ID"
```

## Step 10: Monitor and Maintain

### View Logs

Docker:
```bash
docker compose logs -f web
docker compose logs -f celery
```

### Check Sync Statistics

```bash
curl "http://localhost:8000/api/v1/sync/stats?user_id=YOUR_USER_ID"
```

### Retry Failed Syncs

```bash
# First, get the sync log ID from history
curl "http://localhost:8000/api/v1/sync/history?user_id=YOUR_USER_ID&status=failed"

# Then retry
curl -X POST "http://localhost:8000/api/v1/sync/history/SYNC_LOG_ID/retry?user_id=YOUR_USER_ID"
```

### Access API Documentation

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Troubleshooting

### Activities not syncing

1. **Check webhook subscription**
```bash
curl -X POST "http://localhost:8000/webhook/subscribe"
```

2. **Check Celery worker**
```bash
docker compose logs celery
```

3. **Verify webhook is receiving events**
```bash
docker compose logs web | grep "webhook"
```

### Garmin authentication issues

- Verify credentials are correct
- Check if 2FA is enabled on Garmin (may cause issues)
- Look at Celery logs for specific error messages

### Database issues

**Error: "relation 'users' does not exist"**

This means the database tables haven't been created. Run the migration:

```bash
docker compose exec web alembic upgrade head
```

**Check database tables:**

```bash
# Connect to database
docker compose exec db psql -U strava_garmin -d strava_garmin_sync

# Check tables
\dt

# View recent sync logs
SELECT * FROM sync_logs ORDER BY created_at DESC LIMIT 5;

# Exit psql
\q
```

**Reset database (if needed):**

```bash
# Stop all services
docker compose down -v

# Start services
docker compose up -d

# Initialize database
docker compose exec web alembic upgrade head
```

## Production Deployment

For production deployment:

1. **Use a proper domain** (not localhost)
2. **Enable HTTPS** (required for webhooks)
3. **Use strong passwords** for database
4. **Store secrets securely** (use a secrets manager)
5. **Set up monitoring** (e.g., Sentry, CloudWatch)
6. **Configure backup** for database
7. **Set resource limits** in docker-compose.yml
8. **Review security settings** in CORS middleware

## Next Steps

- Set up monitoring and alerts
- Create a web UI for easier management
- Configure automatic backups
- Set up logging aggregation
- Implement rate limiting

## Support

If you encounter issues:

1. Check the logs
2. Review this setup guide
3. Check the ../README.md
4. Look for similar issues on GitHub
5. Create a new issue with:
   - Error messages
   - Steps to reproduce
   - Environment details
