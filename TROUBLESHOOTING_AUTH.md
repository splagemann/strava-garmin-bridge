# Troubleshooting Auth Flow

## Issue: Redirect to `/undefined`

This means the `auth_url` is coming back as undefined from the backend.

## Quick Checks

### 1. Check Backend is Running
```bash
curl http://localhost:8000/health
# Should return: {"status":"healthy"}
```

### 2. Test Auth URL Endpoint Directly
```bash
curl http://localhost:8000/api/v1/auth/strava/auth-url
# Should return: {"auth_url":"https://www.strava.com/oauth/authorize?...","state":""}
```

### 3. Check Backend Logs
```bash
docker-compose logs -f web
# Look for: "Generating Strava auth URL" and "Generated auth_url"
```

### 4. Check Frontend is Built with Correct API URL
```bash
# The frontend needs to be rebuilt if VITE_API_URL changes
docker-compose build frontend
docker-compose up -d frontend
```

### 5. Check Browser Console
Open browser dev tools (F12) and look for console logs:
- "Starting Strava connection..."
- "Fetching Strava auth URL..."
- "Auth URL response: ..."
- "Redirecting to: ..."

### 6. Check Environment Variables
```bash
# Check backend env
docker-compose exec web env | grep FRONTEND_URL

# Check what was baked into frontend at build time
docker-compose exec frontend cat /usr/share/nginx/html/index.html | grep -o 'VITE_API_URL'
```

## Common Issues

### Issue 1: Frontend API URL is Wrong
**Symptom**: Network error in browser console

**Solution**: Rebuild frontend with correct API URL
```bash
# Edit .env and set BASE_URL=http://localhost:8000
docker-compose build frontend --no-cache
docker-compose up -d frontend
```

### Issue 2: STRAVA_CLIENT_ID or SECRET Not Set
**Symptom**: Backend returns error 500

**Solution**: Check .env file has valid Strava credentials
```bash
cat .env | grep STRAVA_CLIENT
```

### Issue 3: FRONTEND_URL Not Set Correctly
**Symptom**: Strava redirects to wrong URL after auth

**Solution**: Update .env
```bash
# For Docker setup
FRONTEND_URL=http://localhost:3000

# Restart backend
docker-compose restart web
```

## Complete Reset

If all else fails:
```bash
# Stop everything
docker-compose down

# Rebuild everything
docker-compose build --no-cache

# Start fresh
docker-compose up -d

# Check logs
docker-compose logs -f
```

## Manual Test of Full Flow

1. Open http://localhost:3000/auth in browser
2. Open browser dev tools (F12) → Console tab
3. Click "Connect with Strava"
4. Check console logs for errors
5. Should redirect to Strava
6. After authorizing on Strava, should redirect back to http://localhost:3000/auth/callback
7. Should process code and redirect to http://localhost:3000/auth
8. Should show "Connected to Strava" ✓
