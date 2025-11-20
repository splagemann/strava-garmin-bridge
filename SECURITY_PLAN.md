# Security Implementation Plan

## Critical Issues Identified

1. **No authentication/authorization** - All routes accept arbitrary `user_id` query params
2. **Webhook authentication missing** - Strava webhooks not verified with HMAC
3. **OAuth CSRF vulnerability** - No state validation in OAuth flow
4. **Credential exposure** - Garmin tokens stored in plaintext, exposed via API
5. **Insecure CORS** - Wide open with credentials allowed

---

## Implementation Plan

### Phase 1: Authentication & Authorization System ⚠️ CRITICAL

#### 1.1 JWT Authentication Infrastructure

**Files to create:**
- `app/auth/jwt.py` - JWT token creation, validation, refresh
- `app/auth/dependencies.py` - FastAPI auth dependencies
- `app/auth/password.py` - Password hashing with bcrypt
- `app/models/user.py` - Update User model with password fields

**Implementation:**
```python
# app/auth/jwt.py
- create_access_token(user_id: int, expires_delta: timedelta) -> str
- create_refresh_token(user_id: int) -> str
- verify_token(token: str) -> TokenData
- decode_token(token: str) -> dict

# app/auth/dependencies.py
- get_current_user(token: str = Depends(oauth2_scheme)) -> User
  * Extract JWT from Authorization header
  * Validate token signature
  * Load user from database
  * Raise 401 if invalid/expired

- get_current_active_user(user: User = Depends(get_current_user)) -> User
  * Check user.is_active
  * Return user or raise 403
```

**Database changes:**
```sql
ALTER TABLE users ADD COLUMN password_hash VARCHAR(255);
ALTER TABLE users ADD COLUMN email_verified BOOLEAN DEFAULT FALSE;
ALTER TABLE users ADD COLUMN created_at TIMESTAMP DEFAULT NOW();
ALTER TABLE users ADD COLUMN last_login TIMESTAMP;

CREATE TABLE refresh_tokens (
    id SERIAL PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    token_hash VARCHAR(255) UNIQUE NOT NULL,
    expires_at TIMESTAMP NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### 1.2 User Registration & Login Routes

**Files to create:**
- `app/routes/auth.py` - Rewrite with proper auth endpoints

**New endpoints:**
```python
POST /api/v1/auth/register
- Body: { email, password, confirm_password }
- Validate email format, password strength
- Hash password with bcrypt
- Create user record
- Return JWT tokens

POST /api/v1/auth/login
- Body: { email, password }
- Verify password hash
- Update last_login timestamp
- Return JWT tokens + user info

POST /api/v1/auth/refresh
- Body: { refresh_token }
- Validate refresh token
- Issue new access token
- Return new tokens

POST /api/v1/auth/logout
- Requires: Bearer token
- Invalidate refresh token in database
- Return 204 No Content

GET /api/v1/auth/me
- Requires: Bearer token
- Return current user info
```

#### 1.3 Protect All Existing Routes

**Files to update:**
- `app/routes/auth.py` - Remove `user_id` query param, use `current_user`
- `app/routes/filters.py` - Remove `user_id` query param, use `current_user`
- `app/routes/sync.py` - Remove `user_id` query param, use `current_user`

**Changes:**
```python
# BEFORE:
@router.get("/history")
async def sync_history(
    user_id: int = Query(...),  # ❌ INSECURE
    db: Session = Depends(get_db)
):
    user = db.query(User).filter(User.id == user_id).first()

# AFTER:
@router.get("/history")
async def sync_history(
    current_user: User = Depends(get_current_active_user),  # ✅ SECURE
    db: Session = Depends(get_db)
):
    # Use current_user directly, no need to query again
```

**Apply to all routes:**
- `/api/v1/auth/strava/*` - Connect Strava for current user
- `/api/v1/auth/garmin/*` - Connect Garmin for current user
- `/api/v1/filters/*` - CRUD filters for current user only
- `/api/v1/sync/*` - Sync operations for current user only

---

### Phase 2: Webhook Security ⚠️ CRITICAL

#### 2.1 Strava Webhook Signature Verification

**Files to update:**
- `app/routes/webhook.py`

**Implementation:**
```python
import hmac
import hashlib

def verify_strava_signature(
    body: bytes,
    signature: str,
    client_secret: str
) -> bool:
    """Verify Strava webhook signature using HMAC-SHA256."""
    expected = hmac.new(
        key=client_secret.encode(),
        msg=body,
        digestmod=hashlib.sha256
    ).hexdigest()
    return hmac.compare_digest(expected, signature)

@router.post("/strava")
async def strava_webhook(
    request: Request,
    db: Session = Depends(get_db)
):
    # Get raw body for signature verification
    body = await request.body()
    signature = request.headers.get("X-Strava-Signature")

    # Verify signature
    if not signature or not verify_strava_signature(
        body, signature, settings.STRAVA_CLIENT_SECRET
    ):
        logger.warning(f"Invalid webhook signature from {request.client.host}")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # Parse and process webhook...
```

**Security improvements:**
- Log failed verification attempts with IP addresses
- Add rate limiting per IP (max 100 webhooks/hour)
- Validate webhook structure before queueing Celery task

---

### Phase 3: OAuth CSRF Protection

#### 3.1 State Parameter Implementation

**Files to update:**
- `app/services/strava_service.py`
- `app/routes/auth.py`

**Database changes:**
```sql
CREATE TABLE oauth_states (
    state VARCHAR(64) PRIMARY KEY,
    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
    created_at TIMESTAMP DEFAULT NOW(),
    expires_at TIMESTAMP NOT NULL
);

CREATE INDEX idx_oauth_states_expires ON oauth_states(expires_at);
```

**Implementation:**
```python
# app/services/strava_service.py
def get_authorization_url(user_id: int, db: Session) -> str:
    """Generate Strava OAuth URL with CSRF state token."""
    import secrets

    # Generate cryptographically secure state
    state = secrets.token_urlsafe(32)

    # Store state with 10-minute expiration
    oauth_state = OAuthState(
        state=state,
        user_id=user_id,
        expires_at=datetime.utcnow() + timedelta(minutes=10)
    )
    db.add(oauth_state)
    db.commit()

    # Build URL with state
    client = Client()
    return client.authorization_url(
        client_id=settings.STRAVA_CLIENT_ID,
        redirect_uri=f"{settings.BASE_URL}/api/v1/auth/strava/callback",
        state=state,  # ✅ CSRF protection
        scope=["read", "activity:read_all"]
    )

# app/routes/auth.py
@router.get("/strava/callback")
async def strava_callback(
    code: str,
    state: str,  # ✅ Verify this
    current_user: User = Depends(get_current_active_user),
    db: Session = Depends(get_db)
):
    # Verify state token
    oauth_state = db.query(OAuthState).filter(
        OAuthState.state == state,
        OAuthState.user_id == current_user.id,
        OAuthState.expires_at > datetime.utcnow()
    ).first()

    if not oauth_state:
        raise HTTPException(status_code=400, detail="Invalid or expired state")

    # Delete used state (one-time use)
    db.delete(oauth_state)
    db.commit()

    # Exchange code for tokens...
```

**Add cleanup job:**
```python
# app/tasks/cleanup.py
@celery_app.task
def cleanup_expired_oauth_states():
    """Remove expired OAuth states (run every hour)."""
    db = SessionLocal()
    try:
        db.query(OAuthState).filter(
            OAuthState.expires_at < datetime.utcnow()
        ).delete()
        db.commit()
    finally:
        db.close()
```

---

### Phase 4: Credential Protection

#### 4.1 Encrypt Garmin Session Tokens

**Files to update:**
- `app/services/garmin_service.py`
- `app/models/garmin_auth.py`

**Current issue:**
```python
# ❌ INSECURE - Plaintext storage
auth.session_data = json.dumps(session_data)
```

**Fixed implementation:**
```python
# app/utils/encryption.py
from cryptography.fernet import Fernet

class FieldEncryption:
    """Encrypt sensitive fields before database storage."""

    def __init__(self, key: str):
        self.cipher = Fernet(key.encode())

    def encrypt(self, data: str) -> str:
        """Encrypt string data."""
        return self.cipher.encrypt(data.encode()).decode()

    def decrypt(self, encrypted: str) -> str:
        """Decrypt string data."""
        return self.cipher.decrypt(encrypted.encode()).decode()

# app/models/garmin_auth.py
from app.utils.encryption import FieldEncryption

class GarminAuth(Base):
    __tablename__ = "garmin_auth"

    _session_data = Column("session_data", Text, nullable=True)

    @property
    def session_data(self) -> dict | None:
        """Decrypt session data."""
        if not self._session_data:
            return None
        encryptor = FieldEncryption(settings.ENCRYPTION_KEY)
        decrypted = encryptor.decrypt(self._session_data)
        return json.loads(decrypted)

    @session_data.setter
    def session_data(self, value: dict):
        """Encrypt session data before storage."""
        encryptor = FieldEncryption(settings.ENCRYPTION_KEY)
        encrypted = encryptor.encrypt(json.dumps(value))
        self._session_data = encrypted
```

#### 4.2 Remove Sensitive Data from API Responses

**Files to update:**
- `app/routes/sync.py` - `/api/v1/sync/history/{id}/details`

**Changes:**
```python
# ❌ BEFORE - Exposes credentials and location data
class SyncLogDetailResponse(BaseModel):
    strava_data: Optional[dict]  # Contains OAuth tokens!
    gpx_data: Optional[str]  # Contains GPS coordinates!

# ✅ AFTER - Safe summary only
class SyncLogDetailResponse(BaseModel):
    strava_data_summary: Optional[dict]  # Metadata only, no tokens
    fit_summary: Optional[dict]  # File size, point count, no coordinates

    @staticmethod
    def sanitize_strava_data(data: dict) -> dict:
        """Remove sensitive fields from Strava data."""
        safe_fields = {
            "id", "name", "type", "distance", "moving_time",
            "elapsed_time", "total_elevation_gain", "sport_type"
        }
        return {k: v for k, v in data.items() if k in safe_fields}
```

---

### Phase 5: CORS Configuration

#### 5.1 Fix Invalid CORS Setup

**Files to update:**
- `app/main.py`

**Current issue:**
```python
# ❌ INSECURE - allow_origins=["*"] + allow_credentials=True is invalid
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,  # Cannot combine with wildcard!
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**Fixed implementation:**
```python
# ✅ SECURE - Explicit origins
ALLOWED_ORIGINS = [
    settings.FRONTEND_URL,  # http://localhost:5173 (dev)
    "https://yourdomain.com",  # Production frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,  # Now safe with explicit origins
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization"],
    max_age=600,  # Cache preflight for 10 minutes
)
```

**Environment configuration:**
```bash
# .env
ALLOWED_ORIGINS=http://localhost:5173,https://yourdomain.com
```

---

### Phase 6: Additional Security Hardening

#### 6.1 Rate Limiting

**Files to create:**
- `app/middleware/rate_limit.py`

**Implementation:**
```python
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

limiter = Limiter(key_func=get_remote_address)

# Add to main.py
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# Apply to routes
@router.post("/register")
@limiter.limit("5/hour")  # Prevent signup spam
async def register(request: Request, ...):
    pass

@router.post("/login")
@limiter.limit("10/minute")  # Prevent brute force
async def login(request: Request, ...):
    pass

@router.post("/webhook/strava")
@limiter.limit("100/hour")  # Limit webhook calls per IP
async def webhook(request: Request, ...):
    pass
```

#### 6.2 Input Validation & Sanitization

**Add Pydantic validators:**
```python
from pydantic import BaseModel, EmailStr, validator
import re

class RegisterRequest(BaseModel):
    email: EmailStr  # Built-in email validation
    password: str
    confirm_password: str

    @validator('password')
    def password_strength(cls, v):
        if len(v) < 12:
            raise ValueError('Password must be at least 12 characters')
        if not re.search(r'[A-Z]', v):
            raise ValueError('Password must contain uppercase letter')
        if not re.search(r'[a-z]', v):
            raise ValueError('Password must contain lowercase letter')
        if not re.search(r'[0-9]', v):
            raise ValueError('Password must contain number')
        return v

    @validator('confirm_password')
    def passwords_match(cls, v, values):
        if 'password' in values and v != values['password']:
            raise ValueError('Passwords do not match')
        return v
```

#### 6.3 Security Headers

**Files to update:**
- `app/main.py`

**Add middleware:**
```python
from starlette.middleware.trustedhost import TrustedHostMiddleware

# Prevent host header injection
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "yourdomain.com", "*.yourdomain.com"]
)

# Add security headers to all responses
@app.middleware("http")
async def add_security_headers(request, call_next):
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    response.headers["Content-Security-Policy"] = "default-src 'self'"
    return response
```

---

## Frontend Updates Required

### 1. Authentication Flow

**Files to create:**
- `frontend/src/contexts/AuthContext.tsx` - JWT token management
- `frontend/src/components/Login.tsx` - Login form
- `frontend/src/components/Register.tsx` - Registration form
- `frontend/src/utils/api-client.ts` - Axios interceptor for JWT

**Implementation:**
```typescript
// AuthContext.tsx
const AuthContext = createContext<AuthContextType | null>(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  // Load user from JWT on mount
  useEffect(() => {
    const token = localStorage.getItem('access_token');
    if (token) {
      loadUser(token);
    } else {
      setLoading(false);
    }
  }, []);

  const login = async (email: string, password: string) => {
    const response = await api.post('/auth/login', { email, password });
    localStorage.setItem('access_token', response.data.access_token);
    localStorage.setItem('refresh_token', response.data.refresh_token);
    setUser(response.data.user);
  };

  const logout = () => {
    localStorage.removeItem('access_token');
    localStorage.removeItem('refresh_token');
    setUser(null);
  };

  return (
    <AuthContext.Provider value={{ user, login, logout, loading }}>
      {children}
    </AuthContext.Provider>
  );
}

// api-client.ts
apiClient.interceptors.request.use((config) => {
  const token = localStorage.getItem('access_token');
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  }
  return config;
});

apiClient.interceptors.response.use(
  (response) => response,
  async (error) => {
    if (error.response?.status === 401) {
      // Try to refresh token
      const refreshToken = localStorage.getItem('refresh_token');
      if (refreshToken) {
        try {
          const response = await axios.post('/auth/refresh', {
            refresh_token: refreshToken
          });
          localStorage.setItem('access_token', response.data.access_token);
          // Retry original request
          error.config.headers.Authorization = `Bearer ${response.data.access_token}`;
          return axios(error.config);
        } catch {
          // Refresh failed, logout
          localStorage.clear();
          window.location.href = '/login';
        }
      }
    }
    return Promise.reject(error);
  }
);
```

### 2. Remove user_id from API Calls

**Update all API calls:**
```typescript
// ❌ BEFORE
const response = await api.get(`/sync/history?user_id=${userId}`);

// ✅ AFTER - user identified by JWT
const response = await api.get('/sync/history');
```

---

## Migration Strategy

### Step 1: Database Migrations (Zero Downtime)
```bash
# Create migration
alembic revision -m "add_authentication_system"

# Run migration
alembic upgrade head
```

### Step 2: Backward Compatibility (Temporary)
Keep `user_id` query param as **optional** during transition:
```python
@router.get("/history")
async def sync_history(
    current_user: User = Depends(get_current_active_user),
    user_id: Optional[int] = Query(None, deprecated=True),
    db: Session = Depends(get_db)
):
    # Warn about deprecation
    if user_id is not None:
        logger.warning(f"Deprecated user_id param used: {user_id}")

    # Use authenticated user
    logs = db.query(SyncLog).filter(
        SyncLog.user_id == current_user.id
    ).all()
```

### Step 3: Frontend Migration
1. Deploy new frontend with auth
2. Force existing users to register/login
3. Migrate any existing user data

### Step 4: Remove Deprecated Code
After 2 weeks, remove `user_id` query params entirely.

---

## Testing Plan

### Unit Tests
```python
# tests/test_auth.py
def test_jwt_creation():
    token = create_access_token(user_id=1)
    assert verify_token(token).user_id == 1

def test_webhook_signature_verification():
    body = b'{"object_type":"activity","aspect_type":"create"}'
    signature = hmac.new(b'secret', body, hashlib.sha256).hexdigest()
    assert verify_strava_signature(body, signature, 'secret')

def test_oauth_state_validation():
    # Test state token generation and validation
    pass

def test_password_hashing():
    password = "SecurePass123!"
    hashed = hash_password(password)
    assert verify_password(password, hashed)
    assert not verify_password("WrongPass", hashed)
```

### Integration Tests
```python
# tests/test_protected_routes.py
def test_sync_history_requires_auth(client):
    response = client.get("/api/v1/sync/history")
    assert response.status_code == 401

def test_sync_history_with_valid_token(client, auth_token):
    response = client.get(
        "/api/v1/sync/history",
        headers={"Authorization": f"Bearer {auth_token}"}
    )
    assert response.status_code == 200
```

---

## Deployment Checklist

### Before Deploying

- [ ] Generate strong `SECRET_KEY` and `ENCRYPTION_KEY`
- [ ] Update `ALLOWED_ORIGINS` in production `.env`
- [ ] Set up HTTPS/TLS certificates
- [ ] Configure reverse proxy (Nginx/Traefik) with security headers
- [ ] Enable database backups
- [ ] Set up monitoring and alerting

### After Deploying

- [ ] Force all existing users to register
- [ ] Rotate Strava webhook verification token
- [ ] Test OAuth flow end-to-end
- [ ] Verify webhook signature validation works
- [ ] Run security scan (OWASP ZAP, Burp Suite)
- [ ] Penetration testing if possible

---

## Timeline Estimate

- **Phase 1** (Auth System): 3-4 days
- **Phase 2** (Webhooks): 1 day
- **Phase 3** (OAuth CSRF): 1 day
- **Phase 4** (Credentials): 1 day
- **Phase 5** (CORS): 0.5 day
- **Phase 6** (Hardening): 1 day
- **Frontend Updates**: 2-3 days
- **Testing**: 2 days
- **Total**: ~12-14 days

---

## Priority Order

1. **CRITICAL** - Authentication & Authorization (Phase 1)
2. **CRITICAL** - Webhook Authentication (Phase 2)
3. **HIGH** - OAuth CSRF Protection (Phase 3)
4. **HIGH** - Credential Encryption (Phase 4)
5. **MEDIUM** - CORS Fix (Phase 5)
6. **MEDIUM** - Additional Hardening (Phase 6)

---

## Questions to Address

1. Do you want email verification for new users?
2. Should we implement 2FA for additional security?
3. Do you need admin roles for user management?
4. Should Garmin credentials be re-entered after encryption migration?
5. Do you want audit logging for sensitive operations?
