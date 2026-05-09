---
name: auth-implementation-patterns
description: "Master authentication and authorization patterns: JWT, OAuth2, session management, RBAC, MFA, token lifecycle, and credential storage. Covers identity flows (password, social, SSO), authorization models (RBAC, ABAC, ReBAC), threat modeling, secret rotation, and audit logging. Use when implementing secure auth systems, designing access control, adding multi-factor authentication, securing APIs, integrating OAuth2/social login, debugging authentication issues, or conducting security reviews."
type: feature
---

# Authentication & Authorization Implementation Patterns

Build secure, scalable authentication and authorization systems using industry-standard patterns, proven best practices, and threat-aware design.

## Core Auth Strategies (Decision Tree)

| Strategy | Best For | Token TTL | State | Complexity |
|----------|----------|-----------|-------|-----------|
| **Session-based** | Traditional web apps, same-origin | N/A (server-side) | Server-side store | Low |
| **JWT (Stateless)** | SPAs, mobile apps, microservices | 15-60 min | Client-side (signed) | Medium |
| **OIDC (OpenID Connect)** | SSO, multi-tenant, federation | Varies | IdP-managed | High |
| **OAuth2 + PKCE** | Third-party integrations, native apps | 1-24 hours | Auth server-managed | High |
| **mTLS (Mutual TLS)** | Service-to-service, zero-trust | N/A (cert-based) | Certificate store | High |

## Pattern 1: JWT Implementation (Stateless)

### Token Structure

```javascript
// Header
{
  "alg": "HS256",  // or RS256 for asymmetric
  "typ": "JWT"
}

// Payload (issued claims)
{
  "sub": "user_123",
  "email": "user@example.com",
  "role": "admin",
  "permissions": ["read:posts", "write:posts", "delete:posts"],
  "iat": 1704067200,  // Issued at
  "exp": 1704070800,  // Expires in 1 hour
  "iss": "https://auth.example.com",
  "aud": "api.example.com"
}

// Signature (HMAC-SHA256)
HMACSHA256(base64UrlEncode(header) + "." + base64UrlEncode(payload), secret)
```

### Refresh Token Pattern

```python
# Issue pair at login
access_token = sign_jwt(user_id, exp=15_min, secret)
refresh_token = sign_jwt(user_id, exp=7_days, secret)  # Longer lived

# Client stores refresh_token securely (httpOnly cookie or secure storage)
# When access_token expires → POST /refresh with refresh_token
# Server validates refresh_token, issues new access_token

# Security: Refresh tokens should be:
# - Stored in httpOnly, Secure, SameSite cookies (not localStorage)
# - Rotated on each use (new refresh token + new access token)
# - Revocable (invalidated on logout, device change)
```

### Validation Checklist

- [ ] Signature verified with correct key
- [ ] Expiration (`exp`) checked (not expired)
- [ ] Issuer (`iss`) matches expected domain
- [ ] Audience (`aud`) matches API server
- [ ] Critical claims present (`sub`, `iat`)
- [ ] Token not in revocation list (for logout)

## Pattern 2: RBAC (Role-Based Access Control)

### Simple RBAC Model

```python
# Define roles with permissions
ROLES = {
    "admin": ["read:users", "write:users", "delete:users", "read:posts"],
    "editor": ["read:posts", "write:posts", "delete:own_posts"],
    "viewer": ["read:posts", "read:comments"]
}

# On login, attach role to user
user = {
    "id": "user_123",
    "role": "editor",
    "permissions": ROLES["editor"]  # Flatten for quick lookup
}

# At endpoint, check permission
@app.post("/posts/{id}")
def update_post(id: str, user: User):
    if "write:posts" not in user.permissions:
        raise Forbidden("Insufficient permissions")
    return update_post_service(id)
```

### Escalation Protection (Prevent Privilege Escalation)

```python
# NEVER trust client-provided roles
# Always fetch from authoritative source

@app.post("/users/{id}/role")
def change_role(id: str, new_role: str, current_user: User):
    # ❌ BAD: Trust client role
    if current_user.role == "admin":  # From JWT
        user.role = new_role

    # ✓ GOOD: Fetch from server, check with policy engine
    auth_user = db.get_user(current_user.id)  # Refresh from DB
    if not can_grant_role(auth_user, new_role):
        raise Forbidden("Cannot grant this role")
    user.role = new_role
    db.save(user)
```

## Pattern 3: OAuth2 Authorization Code Flow (Social Login)

### Flow Diagram

```
User → App: "Login with GitHub"
  ↓
App → GitHub: GET /authorize?client_id=X&redirect_uri=http://app.local/callback&scope=user:email
  ↓
User → GitHub: Authenticate, approve scopes
  ↓
GitHub → App: redirect to /callback?code=AUTH_CODE_XYZ
  ↓
App → GitHub: POST /token (code=XYZ, client_secret=SECRET) [BACKEND ONLY]
  ↓
GitHub → App: { access_token: "...", user: { id, email, name } }
  ↓
App → Database: Create/link user, issue session/JWT
  ↓
App → User: Set session cookie or return JWT
```

### PKCE (Proof Key for Code Exchange) - For Native/Mobile Apps

```bash
# Client (mobile app) generates code verifier
code_verifier = random_alphanumeric(128)

# Hash it
code_challenge = base64url(sha256(code_verifier))

# Step 1: Authorization request includes code_challenge
GET https://auth.example.com/authorize?
  client_id=app123&
  redirect_uri=com.app://callback&
  scope=openid+profile&
  code_challenge=E9Mrozoa2owUednSPFjqKXV_5PgqAXcEMy6IilapEE&
  code_challenge_method=S256

# Step 2: Auth server returns authorization code
# callback: com.app://callback?code=ABC123

# Step 3: Token exchange (MUST include code_verifier)
POST https://auth.example.com/token
{
  "grant_type": "authorization_code",
  "code": "ABC123",
  "client_id": "app123",
  "code_verifier": "asdfjkl;asdfjkl;asdfjkl;asdfjkl;...",  # Original value
  "redirect_uri": "com.app://callback"
}
# Without code_verifier, token exchange fails → protects against code interception
```

## Pattern 4: Multi-Factor Authentication (MFA)

### TOTP (Time-based One-Time Password) Implementation

```python
import pyotp

# Registration: Generate secret for user
secret = pyotp.random_base32()
totp = pyotp.TOTP(secret)
qr_code_url = totp.provisioning_uri(name=user.email, issuer_name="MyApp")
# Share QR code with user, store secret in DB (encrypted)

# Login: User enters 6-digit code
@app.post("/login/verify-mfa")
def verify_mfa(user_id: str, code: str):
    user = db.get_user(user_id)
    totp = pyotp.TOTP(user.mfa_secret)

    # Verify code with time window (30 seconds)
    if not totp.verify(code, valid_window=1):
        raise Unauthorized("Invalid MFA code")

    # Issue session
    return create_session(user)
```

### Backup Codes Pattern

```python
# Generate 10 one-time backup codes during MFA setup
import secrets

backup_codes = [
    secrets.token_hex(3) for _ in range(10)  # "a1b2c3", "d4e5f6", ...
]
# Store hashed in DB: bcrypt.hashpw(code, salt) for each code

# During login, allow:
# 1. TOTP code, OR
# 2. Backup code (one-time use)

# Mark backup code as used: DELETE FROM backup_codes WHERE code_hash = ...
```

## Pattern 5: Session Management (Traditional Web Apps)

### Secure Session Configuration

```javascript
// Express.js + express-session
app.use(session({
  secret: process.env.SESSION_SECRET,  // Strong, unique
  resave: false,
  saveUninitialized: false,
  cookie: {
    httpOnly: true,        // Prevent JS access (XSS protection)
    secure: true,          // HTTPS only
    sameSite: 'strict',    // CSRF protection
    maxAge: 30 * 60 * 1000 // 30 minutes
  },
  store: new RedisStore()  // Use Redis, not memory
}))
```

### Session Fixation Prevention

```python
# ❌ BAD: Reuse same session ID after login
session['user_id'] = user.id  # Attacker has old session ID

# ✓ GOOD: Regenerate session after authentication
session.regenerate()  # New session ID
session['user_id'] = user.id
# Old session ID becomes invalid → session fixation blocked
```

## Pattern 6: Authorization Models Comparison

| Model | Best For | Example |
|-------|----------|---------|
| **RBAC** (Role-Based) | Simple hierarchies | admin, editor, viewer |
| **ABAC** (Attribute-Based) | Complex rules | `user.department == "finance" AND resource.classification == "restricted"` |
| **ReBAC** (Relationship-Based) | Shared/owned resources | "Can edit if: (owner OR collaborator) AND not archived" |
| **PBAC** (Permission-Based) | Fine-grained | Check specific permission `user:create`, `post:delete:own` |

### ReBAC Example (Google Docs-like sharing)

```python
# User A creates document
document = create_document(owner=user_a)

# User A shares with User B as "editor"
share(document, user_b, role="editor")

# Check: Can User B edit?
can_edit = (
    document.owner == user_b OR
    any(share.user == user_b and share.role == "editor" for share in document.shares)
)
```

## Implementation Checklist

- [ ] **Threat Model**: Identify what you're protecting (data, authentication, sessions)
- [ ] **Auth Strategy**: Choose session/JWT/OAuth2/mTLS based on architecture
- [ ] **Token Lifecycle**: Define TTL, refresh, revocation, rotation policies
- [ ] **Secret Management**: Use encrypted environment variables, rotation every 90 days
- [ ] **Logging & Audit**: Log auth events (login, MFA, permission denials) without secrets
- [ ] **Rate Limiting**: Protect login endpoint from brute force (max 5 attempts per 5 min)
- [ ] **HTTPS/TLS**: Enforce TLS 1.3, disable insecure versions
- [ ] **Secure Cookies**: httpOnly, Secure, SameSite=Strict
- [ ] **CSRF Protection**: Token-based CSRF, SameSite cookies
- [ ] **Input Validation**: Validate email format, password strength (12+ chars, mixed case)
- [ ] **Error Messages**: Generic errors ("Invalid credentials") not "user not found"
- [ ] **Password Hashing**: Use bcrypt/argon2 with unique salt per user
- [ ] **Session Timeout**: Server-side session expiry (30 min inactivity)
- [ ] **Device/Location Tracking**: Alert on unusual login locations (optional)
- [ ] **Compliance**: GDPR right-to-deletion, SOC2 audit logging

## Common Vulnerabilities & Fixes

| Vulnerability | Risk | Fix |
|----------------|------|-----|
| Hardcoded secrets | Credential exposure | Use `.env`, vault, secrets manager |
| Missing HTTPS | Token/password interception | Enforce TLS, HSTS headers |
| No rate limiting | Brute force attacks | Max 5 login attempts per 5 min |
| JWT in localStorage | XSS token theft | Use httpOnly cookies instead |
| No session validation | Session hijacking | Regenerate session after login |
| Weak password policy | Dictionary/brute force attacks | Enforce 12+ chars, mixed case |
| Logging secrets | Exposure in logs | Never log tokens, passwords, API keys |
| No token revocation | Logged-out user still has valid token | Maintain revocation list or use stateful sessions |

## Decision Flow

```
Choose auth strategy:
├─ Same-origin web app? → Sessions (simpler, server-managed)
├─ SPA / Mobile / Microservices? → JWT (stateless, mobile-friendly)
├─ Multi-tenant / Federation? → OIDC (IdP-managed)
├─ B2B integrations? → OAuth2 (user consent, scoped access)
└─ Service-to-service? → mTLS (certificate-based, mutual auth)

For authorization:
├─ Simple roles (admin, editor, viewer)? → RBAC (simple to implement)
├─ Complex attribute rules? → ABAC (policy engine)
├─ Document ownership / sharing? → ReBAC (relationship-based)
└─ Fine-grained permissions? → PBAC (permission matrix)
```
