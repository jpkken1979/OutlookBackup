---
name: fastapi-templates
description: "Master production-ready FastAPI architecture with async patterns, dependency injection, middleware, testing, and scaling. Covers project structure (layered, modular), request/response validation with Pydantic, async database access (SQLAlchemy async, SQLx), dependency injection (Depends, Services), middleware for logging/auth/CORS, error handling strategies, testing patterns (pytest-asyncio, fixtures), rate limiting, JWT authentication, and horizontal scaling (load balancing, caching). Includes templates for REST APIs, GraphQL, WebSocket servers, and microservices. Use when building new FastAPI applications, scaling to production, implementing complex business logic, optimizing database access, or architecting distributed systems."
type: feature
---

# FastAPI Production Architecture

Master building scalable, maintainable FastAPI applications from project structure to horizontal scaling.

---

## Project Structure Template

### Recommended Layered Architecture

```
fastapi-app/
├── app/
│   ├── __init__.py
│   ├── main.py                 # FastAPI app creation
│   ├── config.py               # Settings & environment
│   ├── dependencies.py         # Dependency injection
│   ├── middleware.py           # Custom middleware
│   ├── exceptions.py           # Custom exceptions
│   │
│   ├── api/                    # API routes (version-specific)
│   │   ├── __init__.py
│   │   ├── v1/
│   │   │   ├── __init__.py
│   │   │   ├── users.py        # User endpoints
│   │   │   ├── products.py
│   │   │   └── orders.py
│   │   └── v2/
│   │       └── users.py        # Versioning support
│   │
│   ├── models/                 # Pydantic schemas
│   │   ├── __init__.py
│   │   ├── user.py
│   │   ├── product.py
│   │   └── common.py           # Shared schemas
│   │
│   ├── database/               # Database layer
│   │   ├── __init__.py
│   │   ├── session.py          # Session management
│   │   ├── orm.py              # SQLAlchemy models
│   │   └── migrations/         # Alembic migrations
│   │
│   ├── services/               # Business logic
│   │   ├── __init__.py
│   │   ├── user_service.py
│   │   ├── product_service.py
│   │   └── order_service.py
│   │
│   └── utils/                  # Utilities
│       ├── __init__.py
│       ├── security.py         # JWT, hashing
│       ├── cache.py            # Caching
│       └── email.py            # Email sending
│
├── tests/
│   ├── conftest.py             # Pytest fixtures
│   ├── test_api/
│   │   ├── test_users.py
│   │   └── test_products.py
│   └── test_services/
│       └── test_user_service.py
│
├── requirements.txt
├── pyproject.toml
├── .env.example
└── README.md
```

---

## Pattern 1: Settings & Environment Management

### Configuration with Pydantic

```python
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application settings from environment."""

    # App config
    app_name: str = "FastAPI App"
    debug: bool = False
    version: str = "1.0.0"

    # Database
    database_url: str = "postgresql+asyncpg://user:password@localhost/db"
    database_pool_size: int = 5
    database_max_overflow: int = 10

    # Security
    secret_key: str  # Must set in .env
    algorithm: str = "HS256"
    access_token_expire_minutes: int = 30
    cors_origins: list[str] = ["http://localhost:3000"]

    # External services
    redis_url: str = "redis://localhost:6379"
    email_provider: str = "sendgrid"
    email_from: str = "noreply@example.com"

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'
        case_sensitive = True

# Global settings instance
settings = Settings()

# Usage in FastAPI
from fastapi import FastAPI

app = FastAPI(
    title=settings.app_name,
    debug=settings.debug,
    version=settings.version,
)
```

---

## Pattern 2: Dependency Injection

### Clean Dependency Management

```python
from fastapi import Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
from typing import Annotated

# Database session dependency
async def get_db() -> AsyncSession:
    """Provide database session for endpoint."""
    async with SessionLocal() as session:
        yield session

# Authorization dependency
async def get_current_user(
    token: str = Depends(oauth2_scheme),
) -> UserSchema:
    """Extract & validate JWT token."""
    try:
        payload = jwt.decode(
            token,
            settings.secret_key,
            algorithms=[settings.algorithm]
        )
        user_id: str = payload.get("sub")
        if user_id is None:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid token"
            )
    except JWTError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Could not validate token"
        )

    # Get user from database
    user = await get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")

    return user

# Service dependency
class UserService:
    def __init__(self, db: Annotated[AsyncSession, Depends(get_db)]):
        self.db = db

    async def get_user(self, user_id: int) -> UserSchema:
        """Business logic."""
        result = await self.db.execute(
            select(UserORM).where(UserORM.id == user_id)
        )
        return result.scalars().first()

# Endpoint with clean dependencies
@app.get("/users/{user_id}")
async def get_user_endpoint(
    user_id: int,
    service: Annotated[UserService, Depends()],
    current_user: Annotated[UserSchema, Depends(get_current_user)],
):
    """Get user (requires authentication)."""
    user = await service.get_user(user_id)
    if user is None:
        raise HTTPException(status_code=404)
    return user
```

---

## Pattern 3: Request/Response Validation

### Pydantic Models for Type Safety

```python
from pydantic import BaseModel, Field, EmailStr, validator
from typing import Optional
from datetime import datetime

class UserBase(BaseModel):
    """Base user schema (shared fields)."""
    email: EmailStr
    full_name: str = Field(..., min_length=1, max_length=100)
    is_active: bool = True

class UserCreate(UserBase):
    """User creation payload."""
    password: str = Field(..., min_length=8, max_length=50)

    @validator('password')
    def password_strength(cls, v):
        if not any(c.isupper() for c in v):
            raise ValueError('Password must contain uppercase letter')
        return v

class UserUpdate(BaseModel):
    """User update (partial)."""
    email: Optional[EmailStr] = None
    full_name: Optional[str] = None

class UserResponse(UserBase):
    """Response schema (no password)."""
    id: int
    created_at: datetime

    class Config:
        from_attributes = True  # Map ORM to Pydantic

# Endpoint with validation
@app.post("/users", response_model=UserResponse)
async def create_user(
    user_in: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
):
    """Create user with automatic validation."""
    # Pydantic validates email, password strength, etc.
    user = UserORM(**user_in.dict(exclude={'password'}))
    user.password_hash = hash_password(user_in.password)

    db.add(user)
    await db.commit()
    await db.refresh(user)

    return user
```

---

## Pattern 4: Middleware & Request Processing

### Custom Middleware for Cross-Cutting Concerns

```python
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response
import time
import logging

logger = logging.getLogger(__name__)

class LoggingMiddleware(BaseHTTPMiddleware):
    """Log request/response with timing."""

    async def dispatch(self, request: Request, call_next) -> Response:
        start = time.time()

        # Add request ID
        request.state.request_id = uuid.uuid4()

        # Log request
        logger.info(
            "Request",
            extra={
                "request_id": request.state.request_id,
                "method": request.method,
                "path": request.url.path,
                "client": request.client.host,
            }
        )

        # Process request
        response = await call_next(request)

        # Log response with timing
        duration_ms = (time.time() - start) * 1000
        logger.info(
            "Response",
            extra={
                "request_id": request.state.request_id,
                "status_code": response.status_code,
                "duration_ms": duration_ms,
            }
        )

        response.headers["X-Process-Time"] = str(duration_ms)
        return response

# Add middleware to app
app.add_middleware(LoggingMiddleware)

# CORS middleware
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
```

---

## Pattern 5: Error Handling

### Custom Exception Handlers

```python
from fastapi import FastAPI, HTTPException
from pydantic import ValidationError

class AppException(Exception):
    """Base application exception."""
    def __init__(self, message: str, status_code: int = 400, code: str = "ERROR"):
        self.message = message
        self.status_code = status_code
        self.code = code

class UserNotFound(AppException):
    def __init__(self, user_id: int):
        super().__init__(
            message=f"User {user_id} not found",
            status_code=404,
            code="USER_NOT_FOUND"
        )

class DuplicateEmail(AppException):
    def __init__(self, email: str):
        super().__init__(
            message=f"Email {email} already in use",
            status_code=409,
            code="DUPLICATE_EMAIL"
        )

# Exception handler
@app.exception_handler(AppException)
async def app_exception_handler(request: Request, exc: AppException):
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "error": {
                "code": exc.code,
                "message": exc.message,
                "request_id": request.state.request_id,
            }
        },
    )

# Validation error handler
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "details": exc.errors(),
                "request_id": request.state.request_id,
            }
        },
    )
```

---

## Pattern 6: Testing with Pytest

### Async Test Fixtures

```python
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

@pytest.fixture
async def test_db():
    """Create test database."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async_session_local = sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with async_session_local() as session:
        yield session

@pytest.fixture
async def client(test_db):
    """FastAPI test client."""
    app.dependency_overrides[get_db] = lambda: test_db

    async with AsyncClient(app=app, base_url="http://test") as ac:
        yield ac

@pytest.mark.asyncio
async def test_create_user(client):
    """Test user creation."""
    response = await client.post(
        "/users",
        json={
            "email": "test@example.com",
            "full_name": "Test User",
            "password": "SecurePassword123",
        }
    )

    assert response.status_code == 200
    assert response.json()["email"] == "test@example.com"

@pytest.mark.asyncio
async def test_duplicate_email(client):
    """Test duplicate email rejection."""
    # Create first user
    await client.post(
        "/users",
        json={
            "email": "test@example.com",
            "full_name": "Test User",
            "password": "SecurePassword123",
        }
    )

    # Try creating again
    response = await client.post(
        "/users",
        json={
            "email": "test@example.com",
            "full_name": "Another User",
            "password": "SecurePassword456",
        }
    )

    assert response.status_code == 409
    assert response.json()["error"]["code"] == "DUPLICATE_EMAIL"
```

---

## Pattern 7: Scaling & Performance

### Caching & Load Distribution

```python
from fastapi_cache2 import FastAPICache2
from fastapi_cache2.backends.redis import RedisBackend
from fastapi_cache2.decorator import cache

# Initialize cache
@app.on_event("startup")
async def startup():
    redis = aioredis.from_url(settings.redis_url)
    FastAPICache2.init(RedisBackend(redis), prefix="fastapi-cache")

# Cache endpoint response
@app.get("/products")
@cache(expire=300)  # Cache for 5 minutes
async def get_products(skip: int = 0, limit: int = 10):
    """Cached product list."""
    return await product_service.list_products(skip, limit)

# Async database batch query (prevent N+1)
async def get_users_with_orders(db: AsyncSession) -> list:
    """Load users with orders efficiently."""
    # Without selectinload: N+1 queries
    users = await db.execute(select(UserORM))

    # With selectinload: 1 query (joins orders)
    stmt = select(UserORM).options(selectinload(UserORM.orders))
    result = await db.execute(stmt)
    return result.scalars().all()
```

---

## Best Practices Checklist

| Practice | Why | How |
|----------|-----|-----|
| **Async all the way** | Non-blocking I/O | Use async db drivers, async libraries |
| **Dependency Injection** | Testability, separation | Use Depends() for all services |
| **Pydantic validation** | Type safety | Validate at API boundary |
| **Graceful error handling** | User feedback | Custom exception handlers |
| **Middleware for cross-cutting** | Centralized logic | Logging, auth, CORS |
| **Connection pooling** | Database efficiency | Configure pool_size, max_overflow |
| **Caching** | Performance | Use Redis for frequently accessed data |
| **Structured logging** | Debugging | Include request_id in all logs |
| **Test with async fixtures** | Realistic tests | pytest-asyncio with fixtures |

---

## Implementation Checklist

- [ ] Create project structure (app/, tests/)
- [ ] Set up Pydantic Settings for config
- [ ] Implement database layer (async SQLAlchemy)
- [ ] Create service layer for business logic
- [ ] Set up dependency injection patterns
- [ ] Implement custom exceptions & handlers
- [ ] Add middleware (logging, CORS, auth)
- [ ] Create Pydantic models for validation
- [ ] Write pytest fixtures for testing
- [ ] Add caching layer (Redis)
- [ ] Implement rate limiting
- [ ] Set up OpenAPI documentation
- [ ] Configure database migrations (Alembic)
