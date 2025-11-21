# Production Deployment Guide

This guide covers deploying the Strava-Garmin Sync Bridge to production using pre-built Docker images from GitHub Container Registry (GHCR).

## Prerequisites

- Docker 20.10+ and Docker Compose 2.0+
- A server with at least 2GB RAM and 10GB disk space
- Linux server (amd64/x86_64 architecture)
- Domain name (optional but recommended)
- SSL certificate (recommended for production)

## Quick Start

### 1. Pull Docker Images

Images are automatically published to GHCR on every release. They are public and don't require authentication.

```bash
# Pull latest images
docker pull ghcr.io/splagemann/strava-garmin-bridge/backend:latest
docker pull ghcr.io/splagemann/strava-garmin-bridge/frontend:latest

# Or pull specific version
docker pull ghcr.io/splagemann/strava-garmin-bridge/backend:v1.0.0
docker pull ghcr.io/splagemann/strava-garmin-bridge/frontend:v1.0.0
```

### 2. Download Configuration Files

```bash
# Create project directory
mkdir -p strava-garmin-bridge
cd strava-garmin-bridge

# Download production docker-compose file
curl -O https://raw.githubusercontent.com/splagemann/strava-garmin-bridge/main/docker-compose.prod.yml

# Download environment template
curl -O https://raw.githubusercontent.com/splagemann/strava-garmin-bridge/main/.env.production.example
mv .env.production.example .env
```

### 3. Configure Environment

Edit `.env` file:

```bash
nano .env
```

**Required configuration:**

```bash
# Your GitHub repository (if using a fork)
GITHUB_REPO=splagemann/strava-garmin-bridge

# Image version (use 'latest' or specific version like 'v1.0.0')
IMAGE_TAG=latest

# Database password (generate a strong password)
DB_PASSWORD=$(openssl rand -base64 32)

# Strava API credentials from https://www.strava.com/settings/api
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret

# Security keys (generate new ones)
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
SECRET_KEY=$(openssl rand -hex 32)

# Your domain URLs
# BASE_URL is used by both backend (for OAuth redirects) and frontend (for API calls)
BASE_URL=https://api.yourdomain.com
FRONTEND_URL=https://yourdomain.com
```

**Important Notes:**
- The `BASE_URL` is automatically passed to the frontend container as `BACKEND_API_URL` at runtime
- Frontend Docker image supports runtime configuration - no rebuild needed for different environments
- The same Docker image can be deployed to dev/staging/production with different `BASE_URL` values

### 4. Configure Strava Application

1. Go to https://www.strava.com/settings/api
2. Create or update your application
3. Set **Authorization Callback Domain** to your domain (e.g., `yourdomain.com`)
4. The callback URL will be: `https://yourdomain.com/auth/callback`

### 5. Start Services

```bash
# Start all services
docker-compose -f docker-compose.prod.yml up -d

# View logs
docker-compose -f docker-compose.prod.yml logs -f

# Check service status
docker-compose -f docker-compose.prod.yml ps
```

### 6. Verify Services

```bash
# Check service status
docker-compose -f docker-compose.prod.yml ps

# View backend logs (migrations run automatically on startup)
docker-compose -f docker-compose.prod.yml logs backend

# You should see:
# "PostgreSQL is up - running database migrations..."
# "Migrations completed successfully!"
```

**Note:** Database migrations now run automatically when the backend container starts, so you don't need to run them manually.

### 7. Access Application

- **Frontend**: http://your-server-ip:3000 (or https://yourdomain.com with reverse proxy)
- **Backend API**: http://your-server-ip:8000 (or https://api.yourdomain.com with reverse proxy)
- **API Docs**: http://your-server-ip:8000/docs

## Production Setup with Reverse Proxy

### Using Nginx

Create `/etc/nginx/sites-available/strava-garmin`:

```nginx
# Frontend
server {
    listen 80;
    server_name yourdomain.com;

    # Redirect HTTP to HTTPS
    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name yourdomain.com;

    # SSL configuration
    ssl_certificate /etc/letsencrypt/live/yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/yourdomain.com/privkey.pem;

    # Security headers
    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;
    add_header X-Frame-Options "SAMEORIGIN" always;
    add_header X-Content-Type-Options "nosniff" always;

    location / {
        proxy_pass http://localhost:3000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
    }
}

# Backend API
server {
    listen 80;
    server_name api.yourdomain.com;

    return 301 https://$server_name$request_uri;
}

server {
    listen 443 ssl http2;
    server_name api.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/api.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/api.yourdomain.com/privkey.pem;

    add_header Strict-Transport-Security "max-age=31536000; includeSubDomains" always;

    location / {
        proxy_pass http://localhost:8000;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;

        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }
}
```

Enable and reload:

```bash
sudo ln -s /etc/nginx/sites-available/strava-garmin /etc/nginx/sites-enabled/
sudo nginx -t
sudo systemctl reload nginx
```

### Using Traefik

Create `docker-compose.traefik.yml`:

```yaml
version: '3.8'

services:
  traefik:
    image: traefik:v2.10
    command:
      - "--api.insecure=true"
      - "--providers.docker=true"
      - "--entrypoints.web.address=:80"
      - "--entrypoints.websecure.address=:443"
      - "--certificatesresolvers.myresolver.acme.tlschallenge=true"
      - "--certificatesresolvers.myresolver.acme.email=your@email.com"
      - "--certificatesresolvers.myresolver.acme.storage=/letsencrypt/acme.json"
    ports:
      - "80:80"
      - "443:443"
    volumes:
      - "/var/run/docker.sock:/var/run/docker.sock:ro"
      - "./letsencrypt:/letsencrypt"
    networks:
      - strava-garmin-network

  frontend:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.frontend.rule=Host(`yourdomain.com`)"
      - "traefik.http.routers.frontend.entrypoints=websecure"
      - "traefik.http.routers.frontend.tls.certresolver=myresolver"

  backend:
    labels:
      - "traefik.enable=true"
      - "traefik.http.routers.backend.rule=Host(`api.yourdomain.com`)"
      - "traefik.http.routers.backend.entrypoints=websecure"
      - "traefik.http.routers.backend.tls.certresolver=myresolver"
```

## Upgrading

See [UPGRADE.md](UPGRADE.md) for detailed upgrade instructions.

**Quick upgrade:**

```bash
# Pull latest images
docker-compose -f docker-compose.prod.yml pull

# Stop and remove old containers
docker-compose -f docker-compose.prod.yml down

# Start with new images
docker-compose -f docker-compose.prod.yml up -d

# Run database migrations
docker-compose -f docker-compose.prod.yml exec backend alembic upgrade head

# View logs to verify
docker-compose -f docker-compose.prod.yml logs -f
```

## Monitoring

### Health Checks

```bash
# Backend health
curl http://localhost:8000/health

# Check all service status
docker-compose -f docker-compose.prod.yml ps

# View resource usage
docker stats
```

### Logs

```bash
# All services
docker-compose -f docker-compose.prod.yml logs -f

# Specific service
docker-compose -f docker-compose.prod.yml logs -f backend
docker-compose -f docker-compose.prod.yml logs -f celery-worker

# Last 100 lines
docker-compose -f docker-compose.prod.yml logs --tail=100
```

## Backup

### Database Backup

```bash
# Create backup
docker-compose -f docker-compose.prod.yml exec db pg_dump -U strava_garmin strava_garmin_sync > backup-$(date +%Y%m%d-%H%M%S).sql

# Restore backup
docker-compose -f docker-compose.prod.yml exec -T db psql -U strava_garmin strava_garmin_sync < backup-20240101-120000.sql
```

### Full Backup Script

Create `backup.sh`:

```bash
#!/bin/bash
BACKUP_DIR="/backups/strava-garmin"
DATE=$(date +%Y%m%d-%H%M%S)

mkdir -p "$BACKUP_DIR"

# Backup database
docker-compose -f docker-compose.prod.yml exec -T db pg_dump -U strava_garmin strava_garmin_sync | \
  gzip > "$BACKUP_DIR/db-$DATE.sql.gz"

# Backup environment file
cp .env "$BACKUP_DIR/env-$DATE"

# Keep only last 7 days of backups
find "$BACKUP_DIR" -name "db-*.sql.gz" -mtime +7 -delete
find "$BACKUP_DIR" -name "env-*" -mtime +7 -delete

echo "Backup completed: $BACKUP_DIR"
```

Schedule with cron:

```bash
# Daily backup at 2 AM
0 2 * * * /path/to/strava-garmin-bridge/backup.sh >> /var/log/strava-garmin-backup.log 2>&1
```

## Scaling

### Increase Worker Processes

Edit `docker-compose.prod.yml`:

```yaml
celery-worker:
  deploy:
    replicas: 3  # Run 3 worker instances
```

Or scale manually:

```bash
docker-compose -f docker-compose.prod.yml up -d --scale celery-worker=3
```

### Resource Limits

Add resource limits:

```yaml
backend:
  deploy:
    resources:
      limits:
        cpus: '2'
        memory: 2G
      reservations:
        cpus: '1'
        memory: 512M
```

## Troubleshooting

### Services Won't Start

```bash
# Check logs
docker-compose -f docker-compose.prod.yml logs

# Check service health
docker-compose -f docker-compose.prod.yml ps

# Restart specific service
docker-compose -f docker-compose.prod.yml restart backend
```

### Database Connection Issues

```bash
# Check database is running
docker-compose -f docker-compose.prod.yml exec db pg_isready -U strava_garmin

# Access database console
docker-compose -f docker-compose.prod.yml exec db psql -U strava_garmin strava_garmin_sync
```

### Redis Connection Issues

```bash
# Check Redis is running
docker-compose -f docker-compose.prod.yml exec redis redis-cli ping

# Should return: PONG
```

### View Celery Tasks

```bash
# Access Redis CLI
docker-compose -f docker-compose.prod.yml exec redis redis-cli

# List queued tasks
LLEN celery

# Monitor in real-time
MONITOR
```

## Security Considerations

1. **Change default passwords** - Never use default passwords in production
2. **Use HTTPS** - Always use SSL/TLS in production with valid certificates
3. **Firewall rules** - Only expose necessary ports (80, 443)
4. **Keep images updated** - Regularly pull and deploy latest versions
5. **Secrets management** - Consider using Docker secrets or vault for sensitive data
6. **Regular backups** - Automate database backups
7. **Monitor logs** - Set up log aggregation and alerting
8. **Network isolation** - Use Docker networks to isolate services
9. **Read-only filesystem** - Consider running containers with read-only root filesystem
10. **Scan images** - Regularly scan images for vulnerabilities

## Performance Tuning

### PostgreSQL

Add to `docker-compose.prod.yml`:

```yaml
db:
  command:
    - "postgres"
    - "-c"
    - "max_connections=200"
    - "-c"
    - "shared_buffers=256MB"
    - "-c"
    - "effective_cache_size=1GB"
```

### Redis

```yaml
redis:
  command: redis-server --maxmemory 512mb --maxmemory-policy allkeys-lru
```

## Support

- **Documentation**: [README.md](README.md)
- **Issues**: [GitHub Issues](https://github.com/splagemann/strava-garmin-bridge/issues)
- **Discussions**: [GitHub Discussions](https://github.com/splagemann/strava-garmin-bridge/discussions)
