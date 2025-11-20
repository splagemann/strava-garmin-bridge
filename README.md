# Strava-Garmin Sync Bridge

Automatically sync your activities from Strava to Garmin Connect with customizable filters.

## Features

- 🔄 **Automatic Sync**: Strava activities from the last 7 days are polled every 5 minutes and synced to Garmin based on your filters
- 🔐 **Secure Authentication**: OAuth2 for Strava, encrypted credential storage for Garmin
- 🎯 **Smart Filtering**: Include/exclude activities based on title patterns (supports regex)
- 📊 **Sync History**: Track all sync operations with detailed logs
- 🔁 **Retry Failed Syncs**: Manually retry failed synchronizations
- ⚡ **Async Processing**: Uses Celery for background task processing
- 🐳 **Docker Ready**: Easy deployment with Docker Compose

## Architecture

- **Frontend**: React + TypeScript + Vite + Tailwind CSS
- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL
- **Task Queue**: Celery + Redis
- **Strava Integration**: OAuth2 + periodic polling
- **Garmin Integration**: python-garminconnect library

## Prerequisites

- Python 3.11+
- PostgreSQL
- Redis
- Docker & Docker Compose (optional)
- Strava API application ([create one here](https://www.strava.com/settings/api))

## Production Deployment

For production deployment using pre-built Docker images from GitHub Container Registry:

📖 **See [DEPLOYMENT.md](DEPLOYMENT.md)** for complete production deployment instructions including:
- Using pre-built Docker images
- Setting up reverse proxy (Nginx/Traefik)
- SSL/TLS configuration
- Monitoring and backups
- Security best practices

📖 **See [UPGRADE.md](UPGRADE.md)** for upgrade instructions and rollback procedures.

## Quick Start with Docker (Development)

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
   - `ENCRYPTION_KEY`: Generate with: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
   - `SECRET_KEY`: Random string for session management
   - `BASE_URL`: Backend API URL (default: http://localhost:8000)
   - `FRONTEND_URL`: Frontend URL for OAuth callbacks (default: http://localhost:3000)

4. **Start services**
```bash
docker-compose up -d
```

5. **Check service status**
```bash
docker-compose ps
docker-compose logs -f web
docker-compose logs -f frontend
```

Services will be available at:
- **Frontend**: http://localhost:3000
- **Backend API**: http://localhost:8000
- **API Docs**: http://localhost:8000/docs

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

# Terminal 3: Celery beat (scheduled polling every 5 minutes)
celery -A app.celery_app beat --loglevel=info

# Terminal 4: Redis (if not running as service)
redis-server
```

## Configuration

### Strava API Setup

1. Go to https://www.strava.com/settings/api
2. Create an application
3. Set "Authorization Callback Domain" to match your frontend URL:
   - For local development: `localhost`
   - For production: your domain (e.g., `yourdomain.com`)
4. The callback URL will be: `http://localhost:3000/auth/callback` (or your FRONTEND_URL + `/auth/callback`)
5. Copy Client ID and Client Secret to `.env`

### Scheduled Polling

- A Celery beat schedule polls Strava every 5 minutes for activities from the last 7 days
- Previously synced activities are automatically skipped (no duplicates)
- Ensures no activities are missed even if the service is temporarily down
- Ensure `celery -A app.celery_app beat` is running (Docker Compose already includes a `celery-beat` service)
- Activities are automatically filtered based on your configured patterns before syncing

## Usage

### 1. Connect Strava Account

1. Open your browser and navigate to: `http://localhost:3000/auth`
2. Click "Connect with Strava"
3. Authorize the application on Strava
4. You'll be redirected back to complete the setup

### 2. Configure Garmin Credentials

After connecting Strava, you'll be prompted to add your Garmin credentials on the same page. Enter your Garmin Connect email and password to complete the setup.

### 3. Set Up Activity Filters (Optional)

Navigate to the Filters page in the web interface to configure which activities should be synced:

- **Include filters**: Only sync activities that match these patterns
- **Exclude filters**: Skip activities that match these patterns
- Supports both simple text matching and regex patterns
- Filter by activity name or activity type

### 4. Monitor Sync Activity

- View the **Dashboard** for sync statistics and recent activity
- Check **Sync History** to see all past synchronizations and their status
- Manually trigger syncs for specific activities if needed

## API Documentation

Interactive API documentation is available at:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## Project Structure

```
strava-garmin-bridge/
├── app/                     # Backend (FastAPI)
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
├── frontend/                # Frontend (React + Vite)
│   ├── src/                 # React source code
│   ├── public/              # Static assets
│   ├── Dockerfile           # Frontend Docker image
│   ├── nginx.conf           # Nginx configuration
│   ├── package.json         # Node dependencies
│   └── vite.config.ts       # Vite configuration
├── migrations/              # Database migrations
├── tests/                   # Tests
├── requirements.txt         # Python dependencies
├── Dockerfile               # Backend Docker image
├── docker-compose.yml       # Docker services
├── .env.example             # Environment template
└── README.md                # This file
```

## How It Works

1. **User connects Strava**: Frontend initiates OAuth2 flow, backend stores access/refresh tokens
2. **User adds Garmin credentials**: Credentials are encrypted and stored securely
3. **Scheduled polling**: Celery beat polls Strava every 5 minutes for activities from the last 7 days
4. **Duplicate check**: Activities already synced are automatically skipped
5. **Filter check**: Activities are checked against user's filter rules before syncing
6. **Async processing**: Celery worker fetches activity streams from Strava API
7. **Conversion**: Activity data is converted to FIT format with proper activity type mapping
8. **Upload**: FIT file is uploaded to Garmin Connect
9. **Logging**: Sync result is stored in database with detailed metadata

## Security Considerations

- Garmin credentials are encrypted using Fernet (symmetric encryption)
- Strava uses OAuth2 (no password storage)
- Use HTTPS in production
- Keep `ENCRYPTION_KEY` and `SECRET_KEY` secure
- Consider using a secrets manager in production

## Troubleshooting

### Activities not syncing automatically

1. Verify Celery beat is running: `docker-compose ps celery-beat`
2. Check Celery beat logs: `docker-compose logs -f celery-beat`
3. Check Celery worker logs: `docker-compose logs -f celery`
4. Verify your activity filters aren't excluding activities

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

### Frontend Development

To run the frontend in development mode (with hot reload):

```bash
cd frontend
npm install
npm run dev
```

The frontend will be available at http://localhost:5173 and will proxy API requests to http://localhost:8000.

### Backend Development

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
# Backend
black app/
isort app/

# Frontend
cd frontend
npm run lint
```

## Contributing

We welcome contributions! Please follow these guidelines:

### Quick Start

1. Fork the repository
2. Clone your fork: `git clone https://github.com/YOUR_USERNAME/strava-garmin-bridge.git`
3. Install development dependencies: `pip install -r requirements-dev.txt`
4. Set up pre-commit hooks: `pre-commit install --hook-type pre-commit --hook-type commit-msg`
5. Create a feature branch: `git checkout -b feat/your-feature`
6. Make your changes and commit using [Conventional Commits](https://www.conventionalcommits.org/)
7. Push and submit a pull request

### Commit Message Format

This project uses conventional commits for automatic changelog generation:

```bash
# Examples
git commit -m "feat: add new feature"
git commit -m "fix: resolve bug"
git commit -m "docs: update documentation"
```

Pre-commit hooks will validate your commit messages automatically.

### Documentation

- **[DEPLOYMENT.md](DEPLOYMENT.md)** - Production deployment guide
- **[CONFIGURATION.md](CONFIGURATION.md)** - Environment variables and configuration guide
- **[UPGRADE.md](UPGRADE.md)** - Upgrade and rollback instructions
- **[CONTRIBUTING.md](CONTRIBUTING.md)** - Full contributing guidelines
- **[PRE_COMMIT_SETUP.md](PRE_COMMIT_SETUP.md)** - Pre-commit hooks setup and usage
- **[DOCKER_WORKFLOW.md](DOCKER_WORKFLOW.md)** - Docker image publishing workflow

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
