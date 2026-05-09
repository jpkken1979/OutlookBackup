#!/usr/bin/env python3
"""
API Design Complete - Validador y Generador de APIs
Herramientas para diseñar y validar APIs RESTful.
"""

import logging
import re
import json
from dataclasses import dataclass, field
from enum import Enum

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class HttpMethod(Enum):
    GET = "GET"
    POST = "POST"
    PUT = "PUT"
    PATCH = "PATCH"
    DELETE = "DELETE"


class HttpStatus(Enum):
    # 2xx Success
    OK = 200
    CREATED = 201
    ACCEPTED = 202
    NO_CONTENT = 204

    # 4xx Client Errors
    BAD_REQUEST = 400
    UNAUTHORIZED = 401
    FORBIDDEN = 403
    NOT_FOUND = 404
    METHOD_NOT_ALLOWED = 405
    CONFLICT = 409
    UNPROCESSABLE_ENTITY = 422
    TOO_MANY_REQUESTS = 429

    # 5xx Server Errors
    INTERNAL_SERVER_ERROR = 500
    BAD_GATEWAY = 502
    SERVICE_UNAVAILABLE = 503


@dataclass
class ApiEndpoint:
    """Representa un endpoint de API."""

    path: str
    method: HttpMethod
    description: str
    request_body: dict | None = None
    response_schema: dict | None = None
    path_params: list[str] = field(default_factory=list)
    query_params: list[str] = field(default_factory=list)
    auth_required: bool = True
    rate_limit: int | None = None


@dataclass
class ValidationResult:
    """Resultado de validación de API."""

    is_valid: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    suggestions: list[str] = field(default_factory=list)


class ApiDesignValidator:
    """Validador de diseño de API REST."""

    # Patrones RESTful
    RESOURCE_PATTERN = r"^/[a-z][a-z0-9-]*(/\{[a-z_]+\})?(/[a-z][a-z0-9-]*(/\{[a-z_]+\})?)*$"

    # Verbos HTTP y sus usos correctos
    METHOD_SEMANTICS = {
        HttpMethod.GET: {
            "idempotent": True,
            "safe": True,
            "cacheable": True,
            "request_body": False,
            "success_status": [HttpStatus.OK],
        },
        HttpMethod.POST: {
            "idempotent": False,
            "safe": False,
            "cacheable": False,
            "request_body": True,
            "success_status": [HttpStatus.CREATED, HttpStatus.OK, HttpStatus.ACCEPTED],
        },
        HttpMethod.PUT: {
            "idempotent": True,
            "safe": False,
            "cacheable": False,
            "request_body": True,
            "success_status": [HttpStatus.OK, HttpStatus.NO_CONTENT],
        },
        HttpMethod.PATCH: {
            "idempotent": False,
            "safe": False,
            "cacheable": False,
            "request_body": True,
            "success_status": [HttpStatus.OK, HttpStatus.NO_CONTENT],
        },
        HttpMethod.DELETE: {
            "idempotent": True,
            "safe": False,
            "cacheable": False,
            "request_body": False,
            "success_status": [HttpStatus.OK, HttpStatus.NO_CONTENT, HttpStatus.ACCEPTED],
        },
    }

    def validate_endpoint(self, endpoint: ApiEndpoint) -> ValidationResult:
        """Valida un endpoint de API."""
        result = ValidationResult(is_valid=True)

        self._validate_path(endpoint, result)
        self._validate_method_semantics(endpoint, result)
        self._validate_naming(endpoint, result)
        self._validate_versioning(endpoint, result)

        result.is_valid = len(result.errors) == 0
        return result

    def _validate_path(self, endpoint: ApiEndpoint, result: ValidationResult) -> None:
        """Valida la estructura del path."""
        path = endpoint.path

        # Verificar formato RESTful
        if not re.match(self.RESOURCE_PATTERN, path):
            result.warnings.append(f"Path '{path}' may not follow RESTful conventions")

        # No usar verbos en el path
        verbs = ["get", "create", "update", "delete", "fetch", "save", "remove"]
        path_parts = path.lower().split("/")
        for verb in verbs:
            if verb in path_parts:
                result.errors.append(
                    f"Avoid verbs in path: '{verb}' found. Use HTTP methods instead"
                )

        # Usar plurales para colecciones
        for part in path_parts:
            if part and not part.startswith("{"):
                if part.endswith("y") and not part.endswith("ey"):
                    result.suggestions.append(
                        f"Consider using plural form for '{part}' (e.g., '{part[:-1]}ies')"
                    )

    def _validate_method_semantics(self, endpoint: ApiEndpoint, result: ValidationResult) -> None:
        """Valida semántica del método HTTP."""
        method = endpoint.method
        semantics = self.METHOD_SEMANTICS[method]

        # Verificar body en métodos que no lo soportan
        if endpoint.request_body and not semantics["request_body"]:
            result.errors.append(f"{method.value} requests should not have a request body")

        # Verificar body en métodos que lo requieren
        if semantics["request_body"] and not endpoint.request_body:
            result.warnings.append(f"{method.value} requests typically include a request body")

    def _validate_naming(self, endpoint: ApiEndpoint, result: ValidationResult) -> None:
        """Valida convenciones de nomenclatura."""
        path = endpoint.path

        # Usar kebab-case, no snake_case ni camelCase
        if "_" in path and "{" not in path.split("_")[0]:
            result.warnings.append(
                "Use kebab-case (hyphens) instead of snake_case (underscores) in paths"
            )

        if re.search(r"[A-Z]", path):
            result.errors.append("Use lowercase in paths. Found uppercase characters")

    def _validate_versioning(self, endpoint: ApiEndpoint, result: ValidationResult) -> None:
        """Valida estrategia de versionamiento."""
        path = endpoint.path

        # Verificar si hay versionamiento
        version_patterns = [r"^/v\d+/", r"^/api/v\d+/"]
        has_version = any(re.match(p, path) for p in version_patterns)

        if not has_version:
            result.suggestions.append(
                "Consider adding API versioning (e.g., /v1/users or /api/v1/users)"
            )


class OpenApiGenerator:
    """Generador de especificaciones OpenAPI."""

    def generate(self, endpoints: list[ApiEndpoint], info: dict) -> dict:
        """Genera especificación OpenAPI 3.0."""
        spec = {
            "openapi": "3.0.0",
            "info": {
                "title": info.get("title", "API"),
                "version": info.get("version", "1.0.0"),
                "description": info.get("description", ""),
            },
            "paths": {},
            "components": {
                "securitySchemes": {
                    "bearerAuth": {"type": "http", "scheme": "bearer", "bearerFormat": "JWT"}
                }
            },
        }

        for endpoint in endpoints:
            if endpoint.path not in spec["paths"]:
                spec["paths"][endpoint.path] = {}

            operation = {
                "summary": endpoint.description,
                "responses": {"200": {"description": "Successful response"}},
            }

            if endpoint.auth_required:
                operation["security"] = [{"bearerAuth": []}]

            if endpoint.request_body:
                operation["requestBody"] = {
                    "required": True,
                    "content": {"application/json": {"schema": endpoint.request_body}},
                }

            if endpoint.path_params:
                operation["parameters"] = [
                    {"name": param, "in": "path", "required": True, "schema": {"type": "string"}}
                    for param in endpoint.path_params
                ]

            if endpoint.query_params:
                if "parameters" not in operation:
                    operation["parameters"] = []
                operation["parameters"].extend(
                    [
                        {
                            "name": param,
                            "in": "query",
                            "required": False,
                            "schema": {"type": "string"},
                        }
                        for param in endpoint.query_params
                    ]
                )

            spec["paths"][endpoint.path][endpoint.method.value.lower()] = operation

        return spec


# =============================================================================
# DEMO
# =============================================================================


def main() -> None:
    """Demostración del validador y generador de APIs."""
    print("\n" + "=" * 60)
    print("API DESIGN COMPLETE - Validador y Generador")
    print("=" * 60)

    validator = ApiDesignValidator()
    generator = OpenApiGenerator()

    # Endpoints de ejemplo
    endpoints = [
        ApiEndpoint(
            path="/v1/users",
            method=HttpMethod.GET,
            description="List all users",
            query_params=["page", "limit", "sort"],
        ),
        ApiEndpoint(
            path="/v1/users",
            method=HttpMethod.POST,
            description="Create a new user",
            request_body={
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "email": {"type": "string", "format": "email"},
                },
                "required": ["name", "email"],
            },
        ),
        ApiEndpoint(
            path="/v1/users/{user_id}",
            method=HttpMethod.GET,
            description="Get user by ID",
            path_params=["user_id"],
        ),
        ApiEndpoint(
            path="/v1/users/{user_id}",
            method=HttpMethod.PUT,
            description="Update user",
            path_params=["user_id"],
            request_body={
                "type": "object",
                "properties": {"name": {"type": "string"}, "email": {"type": "string"}},
            },
        ),
        ApiEndpoint(
            path="/v1/users/{user_id}",
            method=HttpMethod.DELETE,
            description="Delete user",
            path_params=["user_id"],
        ),
    ]

    # Endpoints con problemas para demostrar validación
    bad_endpoints = [
        ApiEndpoint(
            path="/getUsers",  # Verbo en path + camelCase
            method=HttpMethod.GET,
            description="Bad: verb in path",
        ),
        ApiEndpoint(
            path="/user_data",  # snake_case
            method=HttpMethod.POST,
            description="Bad: snake_case in path",
        ),
        ApiEndpoint(
            path="/users",  # Sin versionamiento
            method=HttpMethod.GET,
            description="Missing versioning",
            request_body={"invalid": "body"},  # GET con body
        ),
    ]

    # Validar endpoints buenos
    print("\n--- VALIDATING GOOD ENDPOINTS ---")
    for ep in endpoints:
        result = validator.validate_endpoint(ep)
        status = "VALID" if result.is_valid else "INVALID"
        print(f"[{status}] {ep.method.value} {ep.path}")
        for error in result.errors:
            print(f"  ERROR: {error}")
        for warning in result.warnings:
            print(f"  WARNING: {warning}")
        for suggestion in result.suggestions:
            print(f"  SUGGESTION: {suggestion}")

    # Validar endpoints malos
    print("\n--- VALIDATING BAD ENDPOINTS ---")
    for ep in bad_endpoints:
        result = validator.validate_endpoint(ep)
        status = "VALID" if result.is_valid else "INVALID"
        print(f"[{status}] {ep.method.value} {ep.path}")
        for error in result.errors:
            print(f"  ERROR: {error}")
        for warning in result.warnings:
            print(f"  WARNING: {warning}")

    # Generar OpenAPI spec
    print("\n--- GENERATED OPENAPI SPEC ---")
    spec = generator.generate(
        endpoints,
        {
            "title": "User Management API",
            "version": "1.0.0",
            "description": "API for managing users",
        },
    )
    print(json.dumps(spec, indent=2))

    print("\n" + "=" * 60)
    print("API design validation complete")
    print("=" * 60)


if __name__ == "__main__":
    main()
