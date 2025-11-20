# Configuration Guide

This document explains how environment variables are handled across development, build, and production environments.

## Frontend API URL Configuration

The frontend needs to know the backend API URL. This can be configured in three ways:

### 1. Runtime Configuration (Production - Recommended) ⭐

**Variable:** `BACKEND_API_URL`
**When:** Container startup
**How:** Environment variable passed to Docker container
**Priority:** Highest (checked first)

```bash
# Docker Compose
environment:
  BACKEND_API_URL: https://api.yourdomain.com

# Docker Run
docker run -e BACKEND_API_URL=https://api.example.com ...

# Kubernetes
env:
  - name: BACKEND_API_URL
    value: "https://api.production.com"
```

**Benefits:**
- ✅ Same image works in all environments (dev/staging/production)
- ✅ No rebuild required to change API URL
- ✅ Cloud-native and container-friendly
- ✅ Secrets can be injected at runtime

### 2. Build-time Configuration (Advanced)

**Variable:** `VITE_API_URL`
**When:** Docker image build
**How:** Build argument in Dockerfile / GitHub Actions
**Priority:** Medium (fallback if runtime config not set)

```bash
# Docker Build
docker build --build-arg VITE_API_URL=https://api.example.com ...

# GitHub Actions (set as secret)
VITE_API_URL: ${{ secrets.VITE_API_URL }}
```

**Use cases:**
- Custom default URL for specific environments
- Private deployments with fixed endpoints
- When runtime configuration is not available

**Drawbacks:**
- ❌ Requires rebuilding for different environments
- ❌ URL is baked into the image
- ❌ Less flexible than runtime config

### 3. Development Default (Fallback)

**Variable:** `VITE_API_URL` in `.env.local`
**When:** Local development with `npm run dev`
**How:** Vite environment file
**Priority:** Lowest (last fallback)

```env
# frontend/.env.local
VITE_API_URL=http://localhost:8000
```

If no configuration is provided anywhere, defaults to `http://localhost:8000`.

## Configuration Priority

The frontend checks for the API URL in this order:

```
1. window.ENV.BACKEND_API_URL (runtime - Docker entrypoint)
   ↓ (if not set)
2. import.meta.env.VITE_API_URL (build-time - Vite)
   ↓ (if not set)
3. http://localhost:8000 (hardcoded fallback)
```

## Environment-Specific Configuration

### Development (Local)

```bash
# frontend/.env.local
VITE_API_URL=http://localhost:8000

# Run dev server
npm run dev
```

### Development (Docker)

```yaml
# docker-compose.yml
frontend:
  environment:
    - VITE_API_URL=${BASE_URL:-http://localhost:8000}
```

### Production (Docker Compose)

```yaml
# docker-compose.prod.yml
frontend:
  image: ghcr.io/.../frontend:latest
  environment:
    BACKEND_API_URL: ${BASE_URL}  # Runtime config
```

### Production (Kubernetes)

```yaml
apiVersion: apps/v1
kind: Deployment
spec:
  template:
    spec:
      containers:
        - name: frontend
          image: ghcr.io/.../frontend:latest
          env:
            - name: BACKEND_API_URL
              value: "https://api.production.com"
```

### CI/CD Build (GitHub Actions)

```yaml
# .github/workflows/docker-publish.yml
build-args: |
  VITE_API_URL=${{ secrets.VITE_API_URL || 'http://localhost:8000' }}
```

## Backend Configuration

### Required Environment Variables

```bash
# Database
DATABASE_URL=postgresql://user:password@host:5432/dbname

# Redis
REDIS_URL=redis://host:6379/0

# Strava API
STRAVA_CLIENT_ID=your_client_id
STRAVA_CLIENT_SECRET=your_client_secret

# Security
ENCRYPTION_KEY=your_encryption_key  # Generate with Fernet
SECRET_KEY=your_secret_key          # Random string

# URLs
BASE_URL=https://api.yourdomain.com      # Backend API URL
FRONTEND_URL=https://yourdomain.com      # Frontend URL (for OAuth)

# Environment
ENVIRONMENT=production  # or development
```

### Optional Environment Variables

```bash
# Logging
LOG_LEVEL=INFO  # DEBUG, INFO, WARNING, ERROR, CRITICAL

# Celery
CELERY_BROKER_URL=redis://redis:6379/0
CELERY_RESULT_BACKEND=redis://redis:6379/0

# Ports (if not using docker-compose defaults)
BACKEND_PORT=8000
FRONTEND_PORT=3000
```

## Configuration Files

### Development

- `frontend/.env.local` - Frontend development config (gitignored)
- `frontend/.env.example` - Frontend example config (committed)
- `.env` - Backend development config (gitignored)
- `.env.example` - Backend example config (committed)

### Production

- `.env.production.example` - Production config template (committed)
- `docker-compose.prod.yml` - Production Docker Compose (uses .env)

### Docker

- `frontend/public/config.js` - Runtime config placeholder
- `frontend/docker-entrypoint.sh` - Generates runtime config

## Testing Configuration

### Test Runtime Configuration Locally

```bash
# Build frontend image
docker build -t test-frontend ./frontend

# Test with different API URLs
docker run -p 3000:80 -e BACKEND_API_URL=http://localhost:8000 test-frontend
docker run -p 3000:80 -e BACKEND_API_URL=https://api.example.com test-frontend

# Check generated config
docker run test-frontend cat /usr/share/nginx/html/config.js
```

### Verify Configuration in Browser

1. Open the frontend in your browser
2. Open DevTools Console (F12)
3. Check the configuration:

```javascript
// Check runtime config
console.log(window.ENV)

// Check what the app is using
console.log(window.ENV?.BACKEND_API_URL ||
            import.meta.env.VITE_API_URL ||
            'http://localhost:8000')
```

## Common Issues

### Frontend can't connect to backend

**Symptom:** Network errors, 404s, CORS errors

**Solutions:**
1. Check `BACKEND_API_URL` is set correctly
2. Verify backend is accessible from frontend container
3. Check network configuration (Docker networks, firewall)
4. Inspect `config.js` in the container: `docker exec <container> cat /usr/share/nginx/html/config.js`

### Configuration not updating

**Symptom:** Old API URL still being used after change

**Solutions:**
1. Restart the frontend container: `docker-compose restart frontend`
2. Check environment variable is set: `docker-compose exec frontend env | grep BACKEND`
3. Verify entrypoint is running: `docker-compose logs frontend | grep "Configuring frontend"`

### Build-time vs Runtime confusion

**Remember:**
- Production deployments should use **runtime** config (`BACKEND_API_URL`)
- GitHub Actions builds use **build-time** config (`VITE_API_URL`) for defaults only
- Development uses **Vite** config (`.env.local`)

## Best Practices

1. ✅ **Use runtime configuration in production** - Most flexible
2. ✅ **Store secrets in proper secret management** - Don't commit sensitive data
3. ✅ **Use different configs per environment** - Dev/staging/production
4. ✅ **Test configuration changes** - Verify before deploying
5. ✅ **Document custom configs** - Help future you and your team
6. ❌ **Don't hardcode URLs** - Always use configuration
7. ❌ **Don't commit `.env` files** - Use `.env.example` instead
8. ❌ **Don't use build-time config for prod** - Use runtime instead

## Migration Guide

### From Build-time to Runtime Config

If you're currently using `VITE_API_URL` as a GitHub secret:

1. Remove `VITE_API_URL` from GitHub secrets (optional)
2. Update deployment to use `BACKEND_API_URL`:

```yaml
# Before
docker run ghcr.io/.../frontend:latest

# After
docker run -e BACKEND_API_URL=https://api.yourdomain.com \
  ghcr.io/.../frontend:latest
```

3. Update docker-compose files to pass `BACKEND_API_URL`
4. Test in staging first
5. Deploy to production

The frontend will still work with old images - it just won't be configurable at runtime until you deploy the new image.

## References

- [DEPLOYMENT.md](DEPLOYMENT.md) - Production deployment guide
- [DOCKER_WORKFLOW.md](DOCKER_WORKFLOW.md) - CI/CD and Docker image publishing
- [UPGRADE.md](UPGRADE.md) - Upgrading existing deployments
- [Vite Environment Variables](https://vitejs.dev/guide/env-and-mode.html)
- [Docker Environment Variables](https://docs.docker.com/compose/environment-variables/)
