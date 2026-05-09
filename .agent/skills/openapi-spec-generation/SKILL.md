---
name: openapi-spec-generation
description: "Master OpenAPI 3.1 specification generation and maintenance with design-first and code-first approaches. Covers generating specs from FastAPI/Flask/Express, design-first workflow with tools (Swagger Editor, Stoplight), schema versioning, authentication documentation (OAuth2, API keys, JWT), validation against specs, contract testing, SDK generation (OpenAPI Generator, Swagger Codegen), and documentation portals (Swagger UI, ReDoc). Includes patterns for request/response examples, error response documentation, rate limit specifications, and API versioning strategies. Use when creating API documentation, enforcing API contracts, generating client libraries, design-first API development, or implementing API-driven development."
type: feature
---

# OpenAPI 3.1 Specification Generation & Documentation

Master creating, maintaining, and enforcing API contracts with OpenAPI specifications.

---

## OpenAPI Structure Overview

```yaml
openapi: 3.1.0
info:
  title: Pet Store API
  version: 1.0.0
  description: API for managing pets

servers:
  - url: https://api.example.com/v1
    description: Production
  - url: http://localhost:8000/v1
    description: Development

paths:
  /pets:
    get:
      summary: List all pets
      tags: [Pets]
      parameters:
        - name: limit
          in: query
          required: false
          schema:
            type: integer
      responses:
        '200':
          description: A list of pets
        '400':
          description: Invalid parameters

components:
  schemas:
    Pet:
      type: object
      required: [id, name]
      properties:
        id:
          type: integer
        name:
          type: string
        status:
          type: string
          enum: [available, sold, pending]
```

---

## Pattern 1: Code-First (FastAPI Auto-Generation)

### Auto-Generate OpenAPI from Python Code

```python
from fastapi import FastAPI, Query, HTTPException
from pydantic import BaseModel, Field
from typing import Optional

app = FastAPI(
    title="Pet Store API",
    description="API for managing pets",
    version="1.0.0",
)

class Pet(BaseModel):
    """Pet model."""
    id: int = Field(..., description="Unique pet identifier")
    name: str = Field(..., min_length=1, description="Pet name")
    species: str = Field(..., description="Pet species (dog, cat, bird)")
    status: str = Field(
        default="available",
        description="Pet availability status"
    )

    class Config:
        json_schema_extra = {
            "example": {
                "id": 1,
                "name": "Fluffy",
                "species": "cat",
                "status": "available"
            }
        }

@app.get(
    "/pets",
    response_model=list[Pet],
    summary="List all pets",
    tags=["Pets"],
)
async def list_pets(
    limit: int = Query(
        10,
        ge=1,
        le=100,
        description="Maximum number of pets to return"
    ),
    status: Optional[str] = Query(
        None,
        description="Filter by status"
    ),
) -> list[Pet]:
    """
    Retrieve a list of pets.

    - **limit**: Maximum results (1-100)
    - **status**: Filter by availability status
    """
    return await pet_service.list_pets(limit, status)

@app.post("/pets", response_model=Pet, status_code=201, tags=["Pets"])
async def create_pet(pet: Pet) -> Pet:
    """Create a new pet."""
    return await pet_service.create_pet(pet)

@app.get("/pets/{pet_id}", response_model=Pet, tags=["Pets"])
async def get_pet(pet_id: int) -> Pet:
    """Get pet by ID."""
    pet = await pet_service.get_pet(pet_id)
    if not pet:
        raise HTTPException(status_code=404, detail="Pet not found")
    return pet

# OpenAPI spec automatically available at /openapi.json
# Documentation at /docs and /redoc
```

---

## Pattern 2: Design-First Workflow

### Creating Spec Before Code (Stoplight/Swagger Editor)

```yaml
# specs/api.yaml (Design-first specification)

openapi: 3.1.0
info:
  title: Pet Store API
  version: 1.0.0

paths:
  /pets:
    get:
      summary: List pets
      operationId: listPets
      parameters:
        - name: limit
          in: query
          required: false
          schema:
            type: integer
            default: 10
            minimum: 1
            maximum: 100
        - name: status
          in: query
          required: false
          schema:
            type: string
            enum: [available, sold, pending]
      responses:
        '200':
          description: List of pets
          content:
            application/json:
              schema:
                type: array
                items:
                  $ref: '#/components/schemas/Pet'
        '400':
          description: Invalid parameters
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Error'

    post:
      summary: Create a pet
      operationId: createPet
      requestBody:
        required: true
        content:
          application/json:
            schema:
              $ref: '#/components/schemas/PetCreate'
      responses:
        '201':
          description: Pet created
          content:
            application/json:
              schema:
                $ref: '#/components/schemas/Pet'
        '400':
          description: Validation error

components:
  schemas:
    Pet:
      type: object
      required: [id, name, species]
      properties:
        id:
          type: integer
          description: Unique identifier
        name:
          type: string
          minLength: 1
          maxLength: 100
        species:
          type: string
          enum: [dog, cat, bird, fish]
        age:
          type: integer
          minimum: 0
          maximum: 150
        status:
          type: string
          enum: [available, sold, pending]
          default: available

    PetCreate:
      type: object
      required: [name, species]
      properties:
        name:
          type: string
        species:
          type: string
        age:
          type: integer

    Error:
      type: object
      required: [code, message]
      properties:
        code:
          type: string
          enum: [VALIDATION_ERROR, NOT_FOUND, INTERNAL_ERROR]
        message:
          type: string
        details:
          type: object
```

---

## Pattern 3: Authentication & Security

### Documenting API Security

```python
from fastapi import FastAPI, Security, HTTPException
from fastapi.security import HTTPBearer, HTTPAuthCredentials

app = FastAPI()

# Define security scheme in OpenAPI
security_scheme = {
    "type": "http",
    "scheme": "bearer",
    "bearerFormat": "JWT",
}

# Apply to endpoints
@app.get(
    "/protected",
    security=[{"bearerAuth": []}],  # Mark as requiring auth
)
async def protected_endpoint(credentials: HTTPAuthCredentials = Security(HTTPBearer())):
    """Endpoint requiring Bearer token authentication."""
    token = credentials.credentials
    user = await verify_token(token)
    return {"user": user}

# Multiple auth methods
app = FastAPI(
    openapi_extra={
        "components": {
            "securitySchemes": {
                "bearerAuth": {
                    "type": "http",
                    "scheme": "bearer",
                    "bearerFormat": "JWT",
                    "description": "JWT Bearer token"
                },
                "apiKey": {
                    "type": "apiKey",
                    "in": "header",
                    "name": "X-API-Key",
                    "description": "API key authentication"
                },
                "oauth2": {
                    "type": "oauth2",
                    "flows": {
                        "authorizationCode": {
                            "authorizationUrl": "https://auth.example.com/oauth/authorize",
                            "tokenUrl": "https://auth.example.com/oauth/token",
                            "scopes": {
                                "read": "Read access",
                                "write": "Write access"
                            }
                        }
                    }
                }
            }
        }
    }
)
```

---

## Pattern 4: Contract Testing

### Validating API Against Spec

```python
import openapi_spec_validator

# Validate spec is valid OpenAPI
def validate_spec(spec_path: str) -> bool:
    """Validate OpenAPI specification."""
    from openapi_spec_validator import validate_spec
    from openapi_spec_validator.validation.decorators import (
        OpenAPIV30SpecValidator,
    )

    spec = yaml.safe_load(open(spec_path))
    try:
        validate_spec(spec)
        print("✓ Spec is valid OpenAPI")
        return True
    except Exception as e:
        print(f"✗ Invalid spec: {e}")
        return False

# Test that API matches spec
import pytest
from openapi_spec_validator import validate_v30_spec
from hypothesis import given, strategies as st

class TestAPIContract:
    """Contract tests against OpenAPI spec."""

    @pytest.fixture
    def spec(self):
        with open("specs/api.yaml") as f:
            return yaml.safe_load(f)

    def test_list_pets_response(self, client, spec):
        """Response matches spec."""
        response = client.get("/pets?limit=10")

        assert response.status_code == 200
        # Validate response against schema
        pets_schema = spec["components"]["schemas"]["Pet"]
        for pet in response.json():
            assert validate_against_schema(pet, pets_schema)

    def test_create_pet_validation(self, client, spec):
        """Request validation against spec."""
        # Missing required field should fail
        response = client.post("/pets", json={"species": "dog"})
        assert response.status_code == 400

        # Valid request should succeed
        response = client.post(
            "/pets",
            json={"name": "Fluffy", "species": "cat"}
        )
        assert response.status_code == 201
```

---

## Pattern 5: SDK Generation

### Auto-Generate Clients from Spec

```bash
# Using OpenAPI Generator
openapi-generator-cli generate \
  -i specs/api.yaml \
  -g python \
  -o generated/python-client \
  --package-name pet_store_client

openapi-generator-cli generate \
  -i specs/api.yaml \
  -g typescript-fetch \
  -o generated/typescript-client

# Using Swagger Codegen
swagger-codegen generate \
  -i specs/api.yaml \
  -l python \
  -o client/python

# Using QuickType (simple JSON schema)
quicktype -o Pet.ts specs/schemas.json
```

### Using Generated Client

```python
# Python client auto-generated from spec
from pet_store_client import PetStoreApi, Pet

api = PetStoreApi()

# Type-safe, auto-documented
pets = api.list_pets(limit=20)
for pet in pets:
    print(f"{pet.name} ({pet.species})")

# Create with validation
new_pet = Pet(name="Buddy", species="dog")
created = api.create_pet(new_pet)

# TypeScript
import { DefaultApi, Pet } from './generated/typescript-client';

const api = new DefaultApi();

// Auto-complete, type checking
const pets = await api.listPets({ limit: 20 });
pets.forEach(pet => console.log(`${pet.name} (${pet.species})`));
```

---

## Pattern 6: API Versioning in OpenAPI

### Supporting Multiple API Versions

```python
from fastapi import FastAPI, APIRouter

# Version in URL path
app = FastAPI(title="Pet Store API")

# v1 endpoints
v1_router = APIRouter(prefix="/v1", tags=["v1"])

@v1_router.get("/pets")
async def list_pets_v1():
    """List pets (v1 format)."""
    return {"pets": [...]}

# v2 endpoints with breaking changes
v2_router = APIRouter(prefix="/v2", tags=["v2"])

@v2_router.get("/pets")
async def list_pets_v2():
    """List pets (v2 format - improved)."""
    return {
        "data": [...],
        "pagination": {"total": 100, "limit": 10}
    }

app.include_router(v1_router)
app.include_router(v2_router)

# Separate OpenAPI specs
def custom_openapi():
    if app.openapi_schema:
        return app.openapi_schema

    openapi_schema = get_openapi(
        title="Pet Store API",
        version="2.0.0",  # Mark as v2
        routes=app.routes,
    )

    # Deprecation notice
    openapi_schema["info"]["x-api-lifecycle"] = {
        "deprecated": False,
        "sunset": "2026-12-31",  # When v1 will be removed
        "deprecation": "Use /v2 endpoints"
    }

    app.openapi_schema = openapi_schema
    return app.openapi_schema

app.openapi = custom_openapi
```

---

## Best Practices Checklist

| Practice | Why | How |
|----------|-----|-----|
| **Keep spec in sync** | Single source of truth | Code-first or design-first, not both |
| **Version your API** | Backward compatibility | Use /v1, /v2 in paths |
| **Document security** | Clear requirements | Define securitySchemes |
| **Include examples** | Better developer experience | Add x-examples to schemas |
| **Validate against spec** | Prevent drift | Use contract tests |
| **Generate clients** | Reduce manual work | OpenAPI Generator, Swagger Codegen |
| **Test spec validity** | Catch errors early | Validate in CI/CD |

---

## Implementation Checklist

- [ ] Choose approach (code-first or design-first)
- [ ] Create or generate OpenAPI spec
- [ ] Document all endpoints (summary, description)
- [ ] Define request/response schemas
- [ ] Document authentication methods
- [ ] Add error response documentation
- [ ] Include request/response examples
- [ ] Set up API documentation portal (Swagger UI / ReDoc)
- [ ] Validate spec in CI/CD
- [ ] Generate client SDKs
- [ ] Set up contract testing
- [ ] Document API versioning strategy
