---
name: error-handling-patterns
description: "Comprehensive error handling strategies for production applications. Covers custom exception hierarchies, retry patterns (exponential backoff, jitter), circuit breaker pattern, error propagation, error translation across layers, async error handling (Python/TypeScript), structured logging, HTTP error mapping, and testing error cases. Includes fail-fast principles, specific exception catching, error context preservation, and security-aware logging (no PII). Covers validation errors, not-found errors, conflict errors, database errors, external service errors, and transient vs permanent failure handling. Use when designing error handling architecture, implementing resilient systems, debugging production issues, setting up monitoring, preventing cascading failures, or reviewing error handling code."
type: feature
---

# Error Handling Patterns

> Estrategias robustas para manejo de errores en aplicaciones de producción.

## Cuándo Usar Esta Skill

- Diseñando manejo de errores
- Implementando retry logic
- Debugging problemas de producción
- Code review de error handling

---

## Principios Fundamentales

### 1. Fail Fast, Fail Loud

```python
# ❌ MAL: Silencia errores
def get_user(user_id):
    try:
        return db.query(User, user_id)
    except:
        return None  # ¿Por qué falló?

# ✅ BIEN: Falla explícitamente
def get_user(user_id: int) -> User:
    if user_id <= 0:
        raise ValueError(f"Invalid user_id: {user_id}")
    
    user = db.query(User, user_id)
    if not user:
        raise UserNotFoundError(f"User {user_id} not found")
    
    return user
```

### 2. Catch Specific, Not General

```python
# ❌ MAL: Catch genérico
try:
    result = process_data(data)
except Exception as e:
    log.error(f"Error: {e}")

# ✅ BIEN: Catch específico
try:
    result = process_data(data)
except ValidationError as e:
    return {"error": "invalid_input", "details": str(e)}, 400
except DatabaseError as e:
    log.error(f"DB error: {e}")
    return {"error": "internal_error"}, 500
except ExternalServiceError as e:
    log.warning(f"External service failed: {e}")
    return {"error": "service_unavailable"}, 503
```

### 3. Don't Catch and Ignore

```python
# ❌ MAL: Catch y nada
try:
    send_notification(user)
except:
    pass  # 💀 Silencioso

# ✅ BIEN: Log mínimo
try:
    send_notification(user)
except NotificationError as e:
    log.warning(f"Notification failed for {user.id}: {e}")
    # Continúa ejecución (no crítico)
```

---

## Exception Hierarchy

### Diseño de Excepciones Personalizadas

```python
# Base exception para tu dominio
class AppError(Exception):
    """Base exception for application errors."""
    
    def __init__(self, message: str, code: str = None, details: dict = None):
        super().__init__(message)
        self.message = message
        self.code = code or "UNKNOWN_ERROR"
        self.details = details or {}
    
    def to_dict(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "details": self.details
        }


# Errores de dominio
class DomainError(AppError):
    """Business logic errors."""
    pass

class ValidationError(DomainError):
    """Input validation errors."""
    
    def __init__(self, field: str, message: str):
        super().__init__(
            message=f"Validation failed for '{field}': {message}",
            code="VALIDATION_ERROR",
            details={"field": field}
        )

class NotFoundError(DomainError):
    """Resource not found."""
    
    def __init__(self, resource: str, identifier: any):
        super().__init__(
            message=f"{resource} not found: {identifier}",
            code="NOT_FOUND",
            details={"resource": resource, "id": identifier}
        )

class ConflictError(DomainError):
    """Resource conflict (duplicate, version mismatch)."""
    
    def __init__(self, message: str):
        super().__init__(message=message, code="CONFLICT")


# Errores de infraestructura
class InfrastructureError(AppError):
    """External system errors."""
    pass

class DatabaseError(InfrastructureError):
    """Database operation failed."""
    pass

class ExternalServiceError(InfrastructureError):
    """Third-party service failed."""
    
    def __init__(self, service: str, message: str):
        super().__init__(
            message=f"{service} failed: {message}",
            code="EXTERNAL_SERVICE_ERROR",
            details={"service": service}
        )
```

---

## Retry Patterns

### Exponential Backoff

```python
import time
import random
from functools import wraps
from typing import Type, Tuple

def retry_with_backoff(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
    exponential_base: float = 2,
    jitter: bool = True,
    retryable_exceptions: Tuple[Type[Exception], ...] = (Exception,)
):
    """
    Decorator for retry with exponential backoff.
    
    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Initial delay in seconds
        max_delay: Maximum delay cap in seconds
        exponential_base: Base for exponential calculation
        jitter: Add randomness to prevent thundering herd
        retryable_exceptions: Exceptions that trigger retry
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            last_exception = None
            
            for attempt in range(max_retries + 1):
                try:
                    return func(*args, **kwargs)
                except retryable_exceptions as e:
                    last_exception = e
                    
                    if attempt == max_retries:
                        raise
                    
                    delay = min(
                        base_delay * (exponential_base ** attempt),
                        max_delay
                    )
                    
                    if jitter:
                        delay *= (0.5 + random.random())
                    
                    log.warning(
                        f"Retry {attempt + 1}/{max_retries} for {func.__name__} "
                        f"after {delay:.2f}s: {e}"
                    )
                    time.sleep(delay)
            
            raise last_exception
        return wrapper
    return decorator


# Uso
@retry_with_backoff(
    max_retries=3,
    base_delay=1.0,
    retryable_exceptions=(ConnectionError, TimeoutError)
)
def call_external_api(endpoint: str) -> dict:
    response = requests.get(endpoint, timeout=5)
    response.raise_for_status()
    return response.json()
```

### Circuit Breaker

```python
import time
from enum import Enum
from threading import Lock
from typing import Callable

class CircuitState(Enum):
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery

class CircuitBreaker:
    """
    Circuit breaker pattern implementation.
    
    States:
    - CLOSED: Normal operation, tracking failures
    - OPEN: Too many failures, reject requests immediately
    - HALF_OPEN: Testing if service recovered
    """
    
    def __init__(
        self,
        failure_threshold: int = 5,
        recovery_timeout: float = 30.0,
        expected_exception: type = Exception
    ):
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.expected_exception = expected_exception
        
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.last_failure_time = 0
        self.lock = Lock()
    
    def call(self, func: Callable, *args, **kwargs):
        with self.lock:
            if self.state == CircuitState.OPEN:
                if time.time() - self.last_failure_time >= self.recovery_timeout:
                    self.state = CircuitState.HALF_OPEN
                else:
                    raise CircuitOpenError("Circuit breaker is open")
        
        try:
            result = func(*args, **kwargs)
            self._on_success()
            return result
        except self.expected_exception as e:
            self._on_failure()
            raise
    
    def _on_success(self):
        with self.lock:
            self.failure_count = 0
            self.state = CircuitState.CLOSED
    
    def _on_failure(self):
        with self.lock:
            self.failure_count += 1
            self.last_failure_time = time.time()
            
            if self.failure_count >= self.failure_threshold:
                self.state = CircuitState.OPEN


# Uso
payment_circuit = CircuitBreaker(
    failure_threshold=5,
    recovery_timeout=60.0,
    expected_exception=PaymentServiceError
)

def process_payment(amount: float):
    return payment_circuit.call(
        payment_service.charge,
        amount=amount
    )
```

---

## Error Propagation

### Cuándo Catch vs Propagar

```python
# Propagar: No puedes manejar el error aquí
def get_user_profile(user_id: int) -> UserProfile:
    user = user_repository.find(user_id)  # Puede lanzar DBError
    return UserProfile.from_user(user)    # Propaga al caller

# Catch: Puedes recuperar o agregar contexto
def get_user_or_default(user_id: int) -> UserProfile:
    try:
        user = user_repository.find(user_id)
        return UserProfile.from_user(user)
    except NotFoundError:
        return UserProfile.anonymous()  # Fallback

# Catch + Re-raise: Agregar contexto
def process_order(order_id: int):
    try:
        order = order_repository.find(order_id)
        return payment_service.charge(order.total)
    except PaymentError as e:
        raise OrderProcessingError(
            f"Failed to process order {order_id}: {e}"
        ) from e  # Preserva stack trace original
```

### Error Translation

```python
# API → Domain → Infrastructure
# Cada capa traduce errores a su nivel

# Infrastructure layer
class UserRepository:
    def find(self, user_id: int) -> User:
        try:
            row = self.db.query("SELECT * FROM users WHERE id = ?", user_id)
            if not row:
                raise NotFoundError("User", user_id)
            return User.from_row(row)
        except sqlite3.OperationalError as e:
            raise DatabaseError(f"Query failed: {e}") from e

# Domain layer
class UserService:
    def get_profile(self, user_id: int) -> UserProfile:
        user = self.repository.find(user_id)  # NotFoundError, DatabaseError
        return self._build_profile(user)

# API layer
@app.get("/users/{user_id}")
def get_user(user_id: int):
    try:
        return user_service.get_profile(user_id)
    except NotFoundError:
        raise HTTPException(status_code=404, detail="User not found")
    except DatabaseError:
        log.error(f"Database error for user {user_id}")
        raise HTTPException(status_code=500, detail="Internal error")
```

---

## Async Error Handling

### Python async/await

```python
import asyncio
from typing import List

async def fetch_with_timeout(url: str, timeout: float = 5.0) -> dict:
    try:
        async with asyncio.timeout(timeout):
            async with aiohttp.ClientSession() as session:
                async with session.get(url) as response:
                    return await response.json()
    except asyncio.TimeoutError:
        raise ExternalServiceError(url, "Request timed out")
    except aiohttp.ClientError as e:
        raise ExternalServiceError(url, str(e))


async def fetch_all_with_errors(urls: List[str]) -> List[dict]:
    """Fetch all URLs, collecting errors separately."""
    results = []
    errors = []
    
    tasks = [fetch_with_timeout(url) for url in urls]
    
    for url, result in zip(urls, await asyncio.gather(*tasks, return_exceptions=True)):
        if isinstance(result, Exception):
            errors.append({"url": url, "error": str(result)})
        else:
            results.append(result)
    
    if errors:
        log.warning(f"Partial failures: {errors}")
    
    return results
```

### TypeScript async/await

```typescript
// Error wrapper para async
async function withErrorHandling<T>(
  fn: () => Promise<T>,
  context: string
): Promise<T> {
  try {
    return await fn();
  } catch (error) {
    if (error instanceof ValidationError) {
      throw error; // Re-throw domain errors
    }
    
    console.error(`Error in ${context}:`, error);
    throw new AppError(`${context} failed`, { cause: error });
  }
}

// Uso
const user = await withErrorHandling(
  () => userService.findById(userId),
  "UserService.findById"
);
```

---

## Logging Errors

### Structured Error Logging

```python
import logging
import json
from datetime import datetime
from typing import Optional
import traceback

class StructuredLogger:
    def __init__(self, name: str):
        self.logger = logging.getLogger(name)
    
    def error(
        self,
        message: str,
        error: Optional[Exception] = None,
        **context
    ):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": "ERROR",
            "message": message,
            **context
        }
        
        if error:
            log_entry["error"] = {
                "type": type(error).__name__,
                "message": str(error),
                "traceback": traceback.format_exc()
            }
        
        self.logger.error(json.dumps(log_entry))


# Uso
log = StructuredLogger("payment")

try:
    process_payment(order_id, amount)
except PaymentError as e:
    log.error(
        "Payment processing failed",
        error=e,
        order_id=order_id,
        amount=amount,
        user_id=current_user.id,
        request_id=request.id
    )
    raise
```

### Qué NO Loggear

```python
# ❌ NUNCA loggear:
log.error(f"Auth failed: password={password}")  # Passwords
log.error(f"Card: {card_number}")               # PII/PCI
log.error(f"Token: {api_token}")                # Secrets
log.error(f"SSN: {social_security}")            # PII

# ✅ Loggear de forma segura:
log.error(f"Auth failed for user_id={user_id}")
log.error(f"Card ending in {card_number[-4:]}")
log.error(f"Token starting with {api_token[:8]}...")
```

---

## Testing Error Cases

```python
import pytest
from unittest.mock import Mock, patch

class TestUserService:
    def test_get_user_not_found(self):
        # Arrange
        service = UserService(repository=Mock())
        service.repository.find.side_effect = NotFoundError("User", 123)
        
        # Act & Assert
        with pytest.raises(NotFoundError) as exc_info:
            service.get_profile(123)
        
        assert exc_info.value.code == "NOT_FOUND"
        assert "123" in str(exc_info.value)
    
    def test_get_user_db_error_propagates(self):
        service = UserService(repository=Mock())
        service.repository.find.side_effect = DatabaseError("Connection lost")
        
        with pytest.raises(DatabaseError):
            service.get_profile(123)
    
    def test_retry_on_transient_error(self):
        service = UserService(repository=Mock())
        # Falla 2 veces, luego éxito
        service.repository.find.side_effect = [
            ConnectionError("Timeout"),
            ConnectionError("Timeout"),
            User(id=123, name="John")
        ]
        
        result = service.get_profile_with_retry(123)
        
        assert result.name == "John"
        assert service.repository.find.call_count == 3
```

---

## HTTP Error Responses

### Mapeo de Excepciones a HTTP Status

```python
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

app = FastAPI()

ERROR_STATUS_MAPPING = {
    ValidationError: 400,
    AuthenticationError: 401,
    AuthorizationError: 403,
    NotFoundError: 404,
    ConflictError: 409,
    RateLimitError: 429,
    ExternalServiceError: 502,
    DatabaseError: 503,
}

@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    status_code = ERROR_STATUS_MAPPING.get(type(exc), 500)
    
    return JSONResponse(
        status_code=status_code,
        content=exc.to_dict()
    )

@app.exception_handler(Exception)
async def generic_error_handler(request: Request, exc: Exception):
    log.error(f"Unhandled error: {exc}", exc_info=True)
    
    return JSONResponse(
        status_code=500,
        content={
            "error": "INTERNAL_ERROR",
            "message": "An unexpected error occurred"
        }
    )
```

---

## Checklist de Error Handling

### Code Review

- [ ] ¿Excepciones específicas, no genéricas?
- [ ] ¿Se preserva el stack trace con `from e`?
- [ ] ¿Se loggea contexto útil (no PII)?
- [ ] ¿Retry solo para errores transitorios?
- [ ] ¿Circuit breaker para servicios externos?
- [ ] ¿Tests para casos de error?
- [ ] ¿Mensajes de error user-friendly?
- [ ] ¿HTTP status codes apropiados?

---

*Skill: error-handling-patterns v1.0*
