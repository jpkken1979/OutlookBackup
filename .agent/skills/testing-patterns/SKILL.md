---
name: testing-patterns
description: "Master test design patterns, strategies, and architecture for reliable test suites. Covers testing pyramid (unit, integration, E2E), test organization, mocking strategies (stubs, spies, mocks, fakes), AAA pattern, factory fixtures, test data builders, and TDD practices. Includes concrete examples in Python (pytest, unittest.mock) and TypeScript/JavaScript (Jest, Vitest), testing async code, handling flaky tests, achieving code coverage, and organizing tests by layer. Covers parameterized tests, property-based testing, snapshot testing, and best practices for maintainable test suites. Use when designing test strategies, writing unit/integration/E2E tests, setting up test infrastructure, improving test reliability, achieving code coverage goals, or reviewing test code quality."
allowed-tools: Read, Write, Edit, Glob, Grep, Bash
type: feature
---

# Testing Patterns

Master test design patterns and create reliable, maintainable test suites.

## Testing Pyramid Strategy

```
        /\          E2E Tests (Few, Slow)
       /  \         - Critical user journeys
      /----\        - Cross-browser testing
     /      \       - Real browser/API interactions
    /--------\
   /          \     Integration Tests (Some, Medium)
  /            \    - API endpoints
 /              \   - Database queries
/----------------\  - Service interactions

Unit Tests (Many, Fast)
- Pure functions
- Business logic
- Error handling
- Edge cases
```

**Rule of Thumb:** 70% unit, 20% integration, 10% E2E

## Core Pattern: AAA (Arrange-Act-Assert)

```python
import pytest
from unittest.mock import Mock

def test_calculate_discount_for_vip_users():
    # ARRANGE: Set up test data and mocks
    user = Mock(vip_status=True, purchase_history=1000)
    order_total = 100.00

    # ACT: Execute the code under test
    discount = calculate_discount(user, order_total)

    # ASSERT: Verify the outcome
    assert discount == 10.00  # 10% VIP discount
    assert discount > 0
```

## Pattern 1: Unit Tests (Fast & Isolated)

### Basic Unit Test

```python
# Code under test
def add_numbers(a: int, b: int) -> int:
    if not isinstance(a, int) or not isinstance(b, int):
        raise TypeError("Both arguments must be integers")
    return a + b

# Unit test
def test_add_positive_numbers():
    result = add_numbers(2, 3)
    assert result == 5

def test_add_negative_numbers():
    result = add_numbers(-2, -3)
    assert result == -5

def test_add_mixed_numbers():
    result = add_numbers(5, -3)
    assert result == 2

def test_add_invalid_type_raises_error():
    with pytest.raises(TypeError):
        add_numbers("2", 3)
```

### Parameterized Tests (DRY)

```python
import pytest

@pytest.mark.parametrize("a,b,expected", [
    (2, 3, 5),
    (-2, -3, -5),
    (5, -3, 2),
    (0, 0, 0),
    (100, 200, 300),
])
def test_add_numbers(a, b, expected):
    assert add_numbers(a, b) == expected

def test_add_invalid_inputs(invalid_input):
    with pytest.raises(TypeError):
        add_numbers(invalid_input, 5)
```

## Pattern 2: Integration Tests

### API Integration Test

```python
import pytest
from httpx import AsyncClient
from sqlalchemy.orm import Session
from app import create_app
from db import Database

@pytest.fixture
async def client():
    """Create test client connected to test database."""
    app = create_app(config="test")
    async with AsyncClient(app=app, base_url="http://test") as client:
        yield client

@pytest.fixture
def db():
    """Create test database with migrations."""
    db = Database("sqlite:///:memory:")
    db.create_tables()
    yield db
    db.close()

@pytest.mark.asyncio
async def test_create_user_endpoint(client, db):
    # ARRANGE
    user_data = {
        "email": "test@example.com",
        "name": "Test User",
        "password": "SecurePassword123!"
    }

    # ACT
    response = await client.post("/api/users", json=user_data)

    # ASSERT
    assert response.status_code == 201
    assert response.json()["email"] == "test@example.com"
    assert "id" in response.json()

    # Verify saved to database
    saved_user = db.query("SELECT * FROM users WHERE email = ?", user_data["email"])
    assert saved_user is not None
```

### Database Integration Test

```python
def test_user_repository_find_by_id(db):
    # ARRANGE
    user = User(id=1, email="test@ex.com", name="Test")
    db.add(user)
    db.commit()

    # ACT
    repository = UserRepository(db)
    found_user = repository.find_by_id(1)

    # ASSERT
    assert found_user is not None
    assert found_user.email == "test@ex.com"

def test_user_repository_find_by_email_not_found(db):
    repository = UserRepository(db)

    with pytest.raises(UserNotFoundError):
        repository.find_by_email("nonexistent@ex.com")
```

## Pattern 3: Mocking Strategies

### Stub (Return Fixed Values)

```python
from unittest.mock import Mock

def test_fetch_user_with_stub():
    # Stub returns predefined value
    mock_db = Mock()
    mock_db.query.return_value = User(id=1, email="test@ex.com")

    service = UserService(db=mock_db)
    user = service.get_user(1)

    assert user.email == "test@ex.com"
```

### Spy (Track Calls)

```python
from unittest.mock import Mock, call

def test_send_email_called_correctly(mocker):
    # Spy on email service
    mock_email = Mock()

    service = NotificationService(email_service=mock_email)
    service.notify_user("user@ex.com", "Welcome!")

    # Verify called with correct arguments
    mock_email.send.assert_called_once_with(
        to="user@ex.com",
        subject="Welcome!",
        body="Welcome message"
    )
```

### Mock (Verify Behavior & State)

```python
def test_payment_service_retries_on_failure(mocker):
    # Mock payment gateway
    mock_gateway = Mock()
    mock_gateway.charge.side_effect = [
        ConnectionError("Timeout"),
        ConnectionError("Timeout"),
        {"status": "success", "transaction_id": "123"}
    ]

    service = PaymentService(gateway=mock_gateway)
    result = service.charge_with_retry(100.00, max_retries=3)

    assert result["status"] == "success"
    assert mock_gateway.charge.call_count == 3  # Verify retried
```

### Fake (Simplified Implementation)

```python
class FakeEmailService:
    """Fake email service for testing."""

    def __init__(self):
        self.sent_emails = []

    def send(self, to: str, subject: str, body: str):
        self.sent_emails.append({
            "to": to,
            "subject": subject,
            "body": body
        })
        return {"status": "sent"}

def test_user_signup_sends_welcome_email():
    email_service = FakeEmailService()
    user_service = UserService(email_service=email_service)

    user_service.signup("newuser@ex.com")

    assert len(email_service.sent_emails) == 1
    assert email_service.sent_emails[0]["to"] == "newuser@ex.com"
    assert "welcome" in email_service.sent_emails[0]["body"].lower()
```

## Pattern 4: Test Data Management

### Factory Pattern

```python
from factory import Factory, SubFactory, Faker

class UserFactory(Factory):
    class Meta:
        model = User

    id = Faker('uuid4')
    email = Faker('email')
    name = Faker('name')
    created_at = Faker('date_time')

# Usage
def test_user_service():
    user = UserFactory()  # Generates realistic fake data
    admin = UserFactory(role="admin")
    users = UserFactory.create_batch(10)
```

### Builder Pattern

```python
class UserBuilder:
    def __init__(self):
        self.data = {
            "id": 1,
            "email": "test@ex.com",
            "name": "Test User",
            "role": "user"
        }

    def with_email(self, email: str):
        self.data["email"] = email
        return self

    def with_admin_role(self):
        self.data["role"] = "admin"
        return self

    def build(self) -> User:
        return User(**self.data)

# Usage
def test_admin_permissions():
    admin = UserBuilder().with_admin_role().build()
    user = UserBuilder().with_email("user@ex.com").build()

    assert admin.role == "admin"
    assert user.email == "user@ex.com"
```

### Fixture Pattern

```python
import pytest

@pytest.fixture
def valid_user_data():
    return {
        "email": "test@example.com",
        "password": "SecurePass123!",
        "name": "Test User"
    }

@pytest.fixture
def admin_user(db, valid_user_data):
    user = User(**valid_user_data)
    user.role = "admin"
    db.add(user)
    db.commit()
    return user

def test_admin_can_delete_users(admin_user, db):
    # Fixture provides test data automatically
    user_to_delete = User(email="temp@ex.com")
    db.add(user_to_delete)
    db.commit()

    # Admin user already prepared by fixture
    service = PermissionService(db)
    assert service.can_delete(admin_user, user_to_delete)
```

## Pattern 5: Testing Async Code

```python
import pytest
import asyncio

# Pytest-asyncio for async tests
@pytest.mark.asyncio
async def test_async_user_fetch():
    service = AsyncUserService()
    user = await service.fetch_user(123)

    assert user.id == 123

# Multiple async operations
@pytest.mark.asyncio
async def test_concurrent_operations():
    service = AsyncUserService()

    # Arrange: Set up concurrent tasks
    tasks = [
        service.fetch_user(1),
        service.fetch_user(2),
        service.fetch_user(3),
    ]

    # Act: Run concurrently
    results = await asyncio.gather(*tasks)

    # Assert: Verify all completed
    assert len(results) == 3
    assert all(r is not None for r in results)

# Test timeout handling
@pytest.mark.asyncio
async def test_request_timeout():
    service = AsyncUserService()

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(
            service.slow_operation(),
            timeout=1.0
        )
```

## Pattern 6: Snapshot Testing

```python
def test_user_api_response(snapshot):
    user = User(id=1, email="test@ex.com", name="Test")

    response = {
        "id": user.id,
        "email": user.email,
        "name": user.name,
        "created_at": "2024-01-15T10:00:00Z"
    }

    # First run: snapshot created
    # Subsequent runs: compared against snapshot
    assert response == snapshot
```

## Pattern 7: Property-Based Testing

```python
from hypothesis import given, strategies as st

@given(
    a=st.integers(),
    b=st.integers()
)
def test_addition_is_commutative(a, b):
    """Test that addition works for ANY integer values."""
    assert add_numbers(a, b) == add_numbers(b, a)

@given(
    email=st.emails(),
    password=st.text(min_size=8)
)
def test_user_signup_accepts_valid_inputs(email, password):
    """Test signup with hundreds of random email/password combinations."""
    user = User.create(email=email, password=password)
    assert user.email == email
```

## Test Organization Best Practices

### File Structure

```
src/
  user/
    service.py
    repository.py
tests/
  unit/
    test_user_service.py        # Pure logic tests
    test_user_validation.py
  integration/
    test_user_api.py            # API endpoint tests
    test_user_repository.py     # Database tests
  e2e/
    test_user_signup_flow.py   # Full workflows
```

### Test Class Organization

```python
class TestUserService:
    """Group related tests in classes."""

    class TestCreate:
        """Organize by method/behavior."""

        def test_creates_user_with_valid_data(self): pass
        def test_raises_validation_error_on_invalid_email(self): pass
        def test_hashes_password(self): pass

    class TestFind:
        def test_returns_user_when_found(self): pass
        def test_raises_not_found_error_when_missing(self): pass
```

## Code Coverage

```bash
# Run pytest with coverage
pytest --cov=src --cov-report=html

# Target 80%+ coverage
# Aim for: 100% on critical paths, 85%+ overall
```

```python
# Use coverage.py to track
from coverage import Coverage

cov = Coverage()
cov.start()
# ... run tests ...
cov.stop()
cov.save()
```

## Common Anti-Patterns

| ❌ Anti-Pattern | ✅ Better Approach |
|-----------------|-------------------|
| Test implementation (private methods) | Test public API behavior |
| Duplicate setup code | Use fixtures, factories |
| Tests that depend on order | Independent, isolated tests |
| Asserting too much | One assertion per test (or related) |
| Ignoring flaky tests | Fix root cause, use retry strategies |
| Over-mocking | Mock only external dependencies |
| No cleanup | Use fixtures with teardown |
| Testing third-party code | Test YOUR integration only |

## Testing Checklist

- [ ] **Coverage**: 80%+ line coverage, 100% on critical paths
- [ ] **Speed**: Unit tests run in <1s total
- [ ] **Isolation**: No test dependencies or shared state
- [ ] **Naming**: Clear test names describe what they test
- [ ] **Assertions**: Specific, meaningful assertions
- [ ] **Data**: Realistic test data, avoid brittle fixtures
- [ ] **Mocking**: Mock external deps, not code under test
- [ ] **Async**: Proper async/await testing patterns
- [ ] **Error cases**: Test both success and failure paths
- [ ] **Documentation**: Tests serve as usage examples
