# Security Implementation Guide

This document details the security measures implemented in the Strava-Garmin Sync Bridge to protect user data and prevent unauthorized access.

## Security Vulnerabilities Fixed

### 1. **Authentication & Authorization** ✅ FIXED

**Previous Issue**: No authentication - all routes accepted `user_id` as a query parameter, allowing anyone to access any user's data.

**Solution**: Implemented JWT (JSON Web Token) based authentication with Bearer token scheme.

#### Implementation Details:

- **JWT Token Generation**: After successful Strava OAuth, the API returns a JWT token
- **Token Structure**: Contains `sub` (user ID), `exp` (expiration), `iat` (issued at), and `type` claims
- **Token Expiration**: 7 days by default
- **Middleware Protection**: All API routes now require valid JWT token via `Authorization: Bearer <token>` header

#### Example Usage:

```bash
# 1. Complete Strava OAuth and receive JWT token
POST /api/v1/auth/strava/exchange
{
  "code": "oauth_code_from_strava",
  "state": "random_state_value",
  "signed_state": "jwt_signed_state_token"
}

# Response:
{
  "access_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...",
  "token_type": "bearer",
  "email": "user@example.com",
  "athlete_id": "12345"
}

# 2. Use token in subsequent requests
GET /api/v1/auth/status
Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
```

### 2. **CSRF Protection in OAuth Flow** ✅ FIXED

**Previous Issue**: OAuth flow returned empty state and never validated it, allowing CSRF attacks.

**Solution**: Implemented cryptographically secure state parameter with JWT signing.

#### Implementation Details:

- **State Generation**: Uses `secrets.token_urlsafe(32)` for cryptographic randomness
- **State Signing**: State is signed with JWT and server secret key
- **State Validation**: On callback, signed state token is verified before proceeding
- **Expiration**: State tokens expire after 10 minutes

#### OAuth Flow:

```
1. Frontend calls GET /api/v1/auth/strava/auth-url
   Response: { "auth_url": "...", "state": "signed_jwt_token" }

2. Frontend stores signed_state and redirects user to auth_url

3. Strava redirects back with code and state query parameters

4. Frontend calls POST /api/v1/auth/strava/exchange with:
   - code (from Strava)
   - state (from Strava)
   - signed_state (stored from step 1)

5. Backend verifies state matches signed_state before exchanging code
```

### 3. **Sensitive Data Exposure** ✅ FIXED

**Previous Issue**: API responses exposed sensitive data including:
- Garmin session tokens (plaintext)
- Raw GPX data with precise location data
- Strava API tokens
- Internal user IDs

**Solution**: Removed sensitive fields from API responses and implemented proper data sanitization.

#### Changes:

- **Removed from API responses**:
  - `session_data` (Garmin session tokens)
  - `garmin_data` (file summary or Garmin response data)
  - `strava_data` (may contain tokens)
  - Internal `user_id` (use JWT sub claim instead)

- **Encrypted in database**:
  - Garmin credentials (email, password) - already encrypted
  - Uses Fernet symmetric encryption with `ENCRYPTION_KEY`

- **Never exposed**:
  - Strava access tokens
  - Strava refresh tokens
  - Garmin session data
  - Secret keys

### 4. **CORS Configuration** ✅ FIXED

**Previous Issue**: `allow_origins=["*"]` with `allow_credentials=True` is invalid and insecure, allowing any website to make authenticated requests.

**Solution**: Restricted CORS to specific origins with explicit methods and headers.

#### Configuration:

```python
# Production
allowed_origins = [settings.FRONTEND_URL]

# Development (only if ENVIRONMENT=development)
allowed_origins = [
    "http://localhost:3000",
    "http://localhost:5173",  # Vite
    "http://127.0.0.1:3000",
    "http://127.0.0.1:5173"
]

# Settings
allow_credentials = True
allow_methods = ["GET", "POST", "PUT", "DELETE", "OPTIONS"]
allow_headers = ["Content-Type", "Authorization"]
max_age = 600  # Cache preflight for 10 minutes
```

## API Endpoint Changes

All API endpoints now require JWT authentication. Here's the migration guide:

### Before (INSECURE):
```bash
# Anyone could access any user's data
GET /api/v1/auth/status?user_id=123
GET /api/v1/filters/?user_id=123
POST /api/v1/sync/manual?user_id=123
```

### After (SECURE):
```bash
# Requires valid JWT token, automatically uses authenticated user
GET /api/v1/auth/status
Authorization: Bearer <jwt_token>

GET /api/v1/filters/
Authorization: Bearer <jwt_token>

POST /api/v1/sync/manual
Authorization: Bearer <jwt_token>
```

## Frontend Integration

### 1. Store JWT Token

After successful OAuth, store the JWT token securely:

```typescript
// After OAuth callback
const response = await fetch('/api/v1/auth/strava/exchange', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({
    code,
    state,
    signed_state  // From initial auth URL request
  })
});

const { access_token } = await response.json();

// Store token (localStorage, sessionStorage, or memory)
localStorage.setItem('auth_token', access_token);
```

### 2. Include Token in API Requests

```typescript
// Update API client to include Authorization header
const apiClient = axios.create({
  baseURL: API_BASE_URL,
  headers: {
    'Content-Type': 'application/json',
  },
});

// Add request interceptor for auth token
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('auth_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

// Handle 401 responses (token expired/invalid)
apiClient.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401) {
      // Clear token and redirect to login
      localStorage.removeItem('auth_token');
      window.location.href = '/login';
    }
    return Promise.reject(error);
  }
);
```

### 3. Update OAuth Flow

```typescript
// Step 1: Get auth URL with signed state
const { auth_url, state: signedState } = await fetch('/api/v1/auth/strava/auth-url')
  .then(r => r.json());

// Store signed state for later validation
sessionStorage.setItem('oauth_state', signedState);

// Redirect to Strava
window.location.href = auth_url;

// Step 2: Handle OAuth callback
const urlParams = new URLSearchParams(window.location.search);
const code = urlParams.get('code');
const state = urlParams.get('state');
const signedState = sessionStorage.getItem('oauth_state');

// Exchange code for JWT token
const response = await fetch('/api/v1/auth/strava/exchange', {
  method: 'POST',
  headers: { 'Content-Type': 'application/json' },
  body: JSON.stringify({ code, state, signed_state: signedState })
});

const { access_token } = await response.json();
localStorage.setItem('auth_token', access_token);
```

## Security Best Practices

### Environment Variables

Ensure these are set securely in production:

```bash
# Required security variables
SECRET_KEY=<strong-random-secret-key>  # For JWT signing
ENCRYPTION_KEY=<fernet-encryption-key>  # For Garmin credentials

# Generate secure keys:
SECRET_KEY=$(openssl rand -hex 32)
ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())")
```

### JWT Token Storage

**Options** (in order of security):

1. **Memory only** (most secure, lost on refresh)
2. **SessionStorage** (secure, cleared on tab close)
3. **LocalStorage** (persistent, vulnerable to XSS)
4. **Cookies with HttpOnly** (secure if implemented properly)

**Recommendation**: Use sessionStorage for production, with automatic re-authentication on refresh.

### Token Expiration Handling

```typescript
// Decode JWT to check expiration
function isTokenExpired(token: string): boolean {
  try {
    const payload = JSON.parse(atob(token.split('.')[1]));
    return payload.exp * 1000 < Date.now();
  } catch {
    return true;
  }
}

// Check before making requests
if (isTokenExpired(token)) {
  // Redirect to re-authenticate
  redirectToLogin();
}
```

## Database Security

### Encrypted Fields

Garmin credentials are encrypted at rest using Fernet symmetric encryption:

```python
# app/models/auth.py
class GarminAuth(Base):
    encrypted_email = Column(Text, nullable=False)
    encrypted_password = Column(Text, nullable=False)
    session_data = Column(Text, nullable=True)  # OAuth session tokens
```

**Note**: `session_data` should also be encrypted in a future update.

### Access Control

All database queries now enforce user isolation:

```python
# Before (INSECURE)
filters = db.query(ActivityFilter).filter(ActivityFilter.user_id == user_id).all()

# After (SECURE) - user_id from JWT token, not user input
filters = db.query(ActivityFilter).filter(ActivityFilter.user_id == current_user.id).all()
```

## Testing Security

### Test Authentication

```bash
# Should fail without token
curl http://localhost:8000/api/v1/auth/status
# Expected: 401 Unauthorized

# Should succeed with valid token
curl -H "Authorization: Bearer <token>" http://localhost:8000/api/v1/auth/status
# Expected: 200 OK with user data
```

### Test CSRF Protection

```bash
# Should fail with invalid state
curl -X POST http://localhost:8000/api/v1/auth/strava/exchange \
  -H "Content-Type: application/json" \
  -d '{"code": "test", "state": "wrong", "signed_state": "invalid"}'
# Expected: 400 Bad Request - Invalid state token
```

### Test Authorization

```bash
# User A's token should not access User B's data
# This is enforced by JWT sub claim matching database user_id
```

## Compliance & Standards

- **OWASP Top 10 Compliance**: Addressed authentication, sensitive data exposure, and CORS issues
- **OAuth 2.0 Security Best Practices**: State parameter for CSRF protection
- **JWT Best Practices**: Expiration, signing, proper claims structure
- **CORS Security**: Specific origins, no wildcards with credentials

## Future Security Enhancements

Recommended improvements for future releases:

1. **Refresh Tokens**: Implement refresh token flow for longer sessions
2. **Rate Limiting**: Add rate limiting to prevent brute force attacks
3. **Audit Logging**: Log all authentication and authorization events
4. **Session Data Encryption**: Encrypt Garmin `session_data` field
5. **Multi-Factor Authentication**: Support for 2FA/MFA
6. **Token Revocation**: Implement token blacklist for immediate logout
7. **HTTPS Enforcement**: Enforce HTTPS in production with HSTS headers
8. **CSP Headers**: Add Content Security Policy headers
9. **Input Validation**: Enhanced validation for all user inputs
10. **Dependency Scanning**: Regular security scanning of dependencies

## Security Contacts

For security issues or vulnerabilities, please:

1. **Do not** open a public GitHub issue
2. Contact the maintainer directly via email
3. Allow reasonable time for fixes before public disclosure

## References

- [OWASP Top 10](https://owasp.org/www-project-top-ten/)
- [JWT Best Practices](https://tools.ietf.org/html/rfc8725)
- [OAuth 2.0 Security Best Current Practice](https://datatracker.ietf.org/doc/html/draft-ietf-oauth-security-topics)
- [CORS Security](https://developer.mozilla.org/en-US/docs/Web/HTTP/CORS)
