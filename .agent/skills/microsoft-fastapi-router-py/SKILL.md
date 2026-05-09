---
name: microsoft-fastapi-router-py
description: "Patrones de routers FastAPI siguiendo convenciones de Microsoft. Estructura modular, dependency injection, validación Pydantic, manejo de errores y OpenAPI."
type: feature
---

# Microsoft FastAPI Router Patterns

Patrones para estructurar routers FastAPI de forma modular y escalable.

## Estructura de Proyecto

```
app/
├── main.py              # FastAPI app, router registration
├── config.py            # Settings via Pydantic
├── dependencies.py      # Shared dependencies
├── routers/
│   ├── __init__.py
│   ├── users.py         # /users router
│   ├── items.py         # /items router
│   └── health.py        # /health router
├── models/
│   ├── __init__.py
│   ├── user.py          # User Pydantic models
│   └── item.py          # Item Pydantic models
├── services/
│   ├── __init__.py
│   ├── user_service.py  # Business logic
│   └── item_service.py
└── tests/
    ├── conftest.py
    ├── test_users.py
    └── test_items.py
```

## Router Pattern

```python
# routers/users.py
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Annotated

from ..dependencies import get_db, get_current_user
from ..models.user import UserCreate, UserResponse, UserUpdate
from ..services.user_service import UserService

router = APIRouter(
    prefix="/users",
    tags=["users"],
    responses={404: {"description": "Not found"}},
)


@router.get("/", response_model=list[UserResponse])
async def list_users(
    db: Annotated[AsyncSession, Depends(get_db)],
    skip: int = 0,
    limit: int = 100,
) -> list[UserResponse]:
    """Lista todos los usuarios con paginación.

    Args:
        db: Sesión de base de datos.
        skip: Registros a saltar.
        limit: Máximo de registros a retornar.

    Returns:
        Lista de usuarios.
    """
    service = UserService(db)
    return await service.get_all(skip=skip, limit=limit)


@router.get("/{user_id}", response_model=UserResponse)
async def get_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Obtiene un usuario por ID.

    Args:
        user_id: ID del usuario.
        db: Sesión de base de datos.

    Returns:
        Usuario encontrado.

    Raises:
        HTTPException: Si el usuario no existe.
    """
    service = UserService(db)
    user = await service.get_by_id(user_id)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"User {user_id} not found",
        )
    return user


@router.post("/", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
async def create_user(
    user_data: UserCreate,
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Crea un nuevo usuario.

    Args:
        user_data: Datos del usuario a crear.
        db: Sesión de base de datos.

    Returns:
        Usuario creado.
    """
    service = UserService(db)
    return await service.create(user_data)


@router.patch("/{user_id}", response_model=UserResponse)
async def update_user(
    user_id: int,
    user_data: UserUpdate,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> UserResponse:
    """Actualiza un usuario existente.

    Args:
        user_id: ID del usuario a actualizar.
        user_data: Campos a actualizar.
        db: Sesión de base de datos.
        current_user: Usuario autenticado.

    Returns:
        Usuario actualizado.
    """
    service = UserService(db)
    return await service.update(user_id, user_data)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_user(
    user_id: int,
    db: Annotated[AsyncSession, Depends(get_db)],
    current_user: Annotated[UserResponse, Depends(get_current_user)],
) -> None:
    """Elimina un usuario."""
    service = UserService(db)
    await service.delete(user_id)
```

## Pydantic Models

```python
# models/user.py
from pydantic import BaseModel, Field, EmailStr
from datetime import datetime


class UserBase(BaseModel):
    """Campos compartidos por todos los schemas de User."""
    name: str = Field(..., min_length=1, max_length=100)
    email: EmailStr


class UserCreate(UserBase):
    """Schema para crear usuario."""
    password: str = Field(..., min_length=8, max_length=128)


class UserUpdate(BaseModel):
    """Schema para actualizar usuario (todos opcionales)."""
    name: str | None = Field(None, min_length=1, max_length=100)
    email: EmailStr | None = None


class UserResponse(UserBase):
    """Schema de respuesta (sin password)."""
    id: int
    created_at: datetime
    is_active: bool = True

    model_config = {"from_attributes": True}
```

## Dependency Injection

```python
# dependencies.py
from typing import AsyncGenerator, Annotated
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials

security = HTTPBearer()


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """Yield database session."""
    async with async_session_maker() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def get_current_user(
    credentials: Annotated[HTTPAuthorizationCredentials, Depends(security)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> UserResponse:
    """Validate token and return current user."""
    token = credentials.credentials
    user = await verify_token(token, db)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authentication credentials",
        )
    return user
```

## Main App

```python
# main.py
from fastapi import FastAPI
from .routers import users, items, health

app = FastAPI(
    title="My API",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

# Registrar routers
app.include_router(health.router)
app.include_router(users.router, prefix="/api/v1")
app.include_router(items.router, prefix="/api/v1")
```

## Error Handling

```python
from fastapi import Request
from fastapi.responses import JSONResponse

@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError) -> JSONResponse:
    return JSONResponse(
        status_code=400,
        content={"detail": str(exc)},
    )
```

## Testing

```python
# tests/test_users.py
import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app

@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c

@pytest.mark.asyncio
async def test_create_user(client: AsyncClient):
    response = await client.post("/api/v1/users", json={
        "name": "Alice",
        "email": "alice@example.com",
        "password": "securepass123",
    })
    assert response.status_code == 201
    assert response.json()["name"] == "Alice"
```

## Recursos

- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [Pydantic V2](https://docs.pydantic.dev/)
- [Microsoft REST API Guidelines](https://github.com/microsoft/api-guidelines)
