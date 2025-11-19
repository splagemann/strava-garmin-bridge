# Strava-Garmin Sync Bridge

Automatically sync your activities from Strava to Garmin Connect with customizable filters.

## Features

- 🔄 **Automatic Sync**: Activities created in Strava are automatically synced to Garmin Connect via webhooks
- 🔐 **Secure Authentication**: OAuth2 for Strava, encrypted credential storage for Garmin
- 🎯 **Smart Filtering**: Include/exclude activities based on title patterns (supports regex)
- 📊 **Sync History**: Track all sync operations with detailed logs
- 🔁 **Retry Failed Syncs**: Manually retry failed synchronizations
- ⚡ **Async Processing**: Uses Celery for background task processing
- 🐳 **Docker Ready**: Easy deployment with Docker Compose

## Architecture

- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL
- **Task Queue**: Celery + Redis
- **Strava Integration**: OAuth2 + Webhooks
- **Garmin Integration**: python-garminconnect library

## Prerequisites

- Python 3.11+
- PostgreSQL
- Redis
- Docker & Docker Compose (optional)
- Strava API application ([create one here](https://www.strava.com/settings/api))

## Quick Start with Docker

1. **Clone the repository**
```bash
cd strava-garmin-bridge
```

2. **Create environment file**
```bash
cp .env.example .env
```

3. **Edit `.env` and configure:**
   - `STRAVA_CLIENT_ID`: Your Strava API client ID
   - `STRAVA_CLIENT_SECRET`: Your Strava API client secret
   - `STRAVA_WEBHOOK_VERIFY_TOKEN`: Random string for webhook verification
   - `ENCRYPTION_KEY`: Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   - `SECRET_KEY`: Random string for session management
   - `BASE_URL`: Your public URL (for webhooks)

4. **Start services**
```bash
docker-compose up -d
```

5. **Check service status**
```bash
docker-compose ps
docker-compose logs -f web
```

The API will be available at http://localhost:8000

## Manual Setup (Without Docker)

1. **Install dependencies**
```bash
pip install -r requirements.txt
```

2. **Set up PostgreSQL**
```bash
createdb strava_garmin_sync
```

3. **Configure environment**
```bash
cp .env.example .env
# Edit .env with your configuration
```

4. **Run database migrations**
```bash
alembic upgrade head
```

5. **Start services**

In separate terminals:

```bash
# Terminal 1: Web server
uvicorn app.main:app --reload

# Terminal 2: Celery worker
celery -A app.celery_app worker --loglevel=info

# Terminal 3: Redis (if not running as service)
redis-server
```

## Configuration

### Strava API Setup

1. Go to https://www.strava.com/settings/api
2. Create an application
3. Set "Authorization Callback Domain" to your domain (e.g., `localhost` or `yourdomain.com`)
4. Copy Client ID and Client Secret to `.env`

### Webhook Setup

After starting the application:

1. Create webhook subscription:
```bash
curl -X POST http://localhost:8000/webhook/subscribe
```

2. Note: Your `BASE_URL` must be publicly accessible for Strava to send webhook events

## Usage

### 1. Connect Strava Account

Visit: `http://localhost:8000/api/v1/auth/strava/login`

This will redirect you to Strava for authorization. After approval, you'll receive a user ID.

### 2. Configure Garmin Credentials

```bash
curl -X POST "http://localhost:8000/api/v1/auth/garmin/credentials?user_id=YOUR_USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "email": "your-garmin-email@example.com",
    "password": "your-garmin-password"
  }'
```

### 3. Set Up Activity Filters (Optional)

**Include only runs and rides:**
```bash
curl -X POST "http://localhost:8000/api/v1/filters/?user_id=YOUR_USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "filter_type": "include",
    "pattern": "run|ride",
    "is_regex": true
  }'
```

**Exclude activities with "test" in the title:**
```bash
curl -X POST "http://localhost:8000/api/v1/filters/?user_id=YOUR_USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "filter_type": "exclude",
    "pattern": "test",
    "is_regex": false
  }'
```

### 4. Manual Sync

Manually sync a specific activity:
```bash
curl -X POST "http://localhost:8000/api/v1/sync/manual?user_id=YOUR_USER_ID" \
  -H "Content-Type: application/json" \
  -d '{
    "strava_activity_id": 12345678
  }'
```

### 5. View Sync History

```bash
curl "http://localhost:8000/api/v1/sync/history?user_id=YOUR_USER_ID&limit=10"
```

### 6. Check Sync Statistics

```bash
curl "http://localhost:8000/api/v1/sync/stats?user_id=YOUR_USER_ID"
```

## API Documentation

Interactive API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
strava-garmin-bridge/
├── app/
│   ├── __init__.py
│   ├── main.py              # FastAPI application
│   ├── config.py            # Configuration
│   ├── database.py          # Database setup
│   ├── celery_app.py        # Celery configuration
│   ├── models/              # Database models
│   │   ├── user.py
│   │   ├── auth.py
│   │   ├── filter.py
│   │   └── sync_log.py
│   ├── routes/              # API routes
│   │   ├── auth.py
│   │   ├── webhook.py
│   │   ├── filters.py
│   │   └── sync.py
│   ├── services/            # Business logic
│   │   ├── strava_service.py
│   │   ├── garmin_service.py
│   │   └── sync_service.py
│   ├── tasks/               # Celery tasks
│   │   └── sync_tasks.py
│   └── utils/               # Utilities
│       ├── crypto.py
│       └── activity_converter.py
├── migrations/              # Database migrations
├── tests/                   # Tests
├── requirements.txt         # Python dependencies
├── Dockerfile              # Docker image
├── docker-compose.yml      # Docker services
├── .env.example            # Environment template
└── README.md               # This file
```

## How It Works

1. **User connects Strava**: OAuth2 flow stores access/refresh tokens
2. **User adds Garmin credentials**: Credentials are encrypted and stored
3. **Strava webhook**: When user creates activity, Strava sends webhook event
4. **Async processing**: Celery task fetches activity data from Strava
5. **Filter check**: Activity title is checked against user's filter rules
6. **Conversion**: Activity data is converted to GPX format
7. **Upload**: GPX file is uploaded to Garmin Connect
8. **Logging**: Sync result is stored in database

## Security Considerations

- Garmin credentials are encrypted using Fernet (symmetric encryption)
- Strava uses OAuth2 (no password storage)
- Use HTTPS in production
- Keep `ENCRYPTION_KEY` and `SECRET_KEY` secure
- Consider using a secrets manager in production

## Troubleshooting

### Activities not syncing automatically

1. Check webhook subscription: `curl http://localhost:8000/webhook/subscribe`
2. Ensure `BASE_URL` is publicly accessible
3. Check Celery worker logs: `docker-compose logs -f celery`

### Garmin login fails

- Verify credentials are correct
- Check if 2FA is enabled (may require manual session setup)
- Review Garmin service logs

### Database connection issues

```bash
docker-compose logs db
docker-compose exec db psql -U strava_garmin -d strava_garmin_sync
```

## Development

### Running tests
```bash
pytest tests/
```

### Database migrations
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migration
alembic upgrade head
```

### Code formatting
```bash
black app/
isort app/
```

## Contributing

1. Fork the repository
2. Create a feature branch
3. Make your changes
4. Add tests
5. Submit a pull request

## License

MIT License - see LICENSE file for details

## Acknowledgments

- [stravalib](https://github.com/stravalib/stravalib) - Strava API client
- [python-garminconnect](https://github.com/cyberjunky/python-garminconnect) - Garmin Connect API
- [FastAPI](https://fastapi.tiangolo.com/) - Web framework
- [Celery](https://docs.celeryproject.org/) - Task queue

## Support

For issues and questions:
- Open an issue on GitHub
- Check existing documentation
- Review API logs

## Roadmap

- [ ] Web UI for easier configuration
- [ ] Support for activity updates (not just creation)
- [ ] Bidirectional sync (Garmin → Strava)
- [ ] Activity deduplication
- [ ] Multi-user support with authentication
- [ ] Activity transformation rules (e.g., adjust distance/time)
- [ ] Notification system for sync failures
- [ ] Batch sync for historical activities
