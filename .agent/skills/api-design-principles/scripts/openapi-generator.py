#!/usr/bin/env python3
"""
OpenAPI 3.0 Schema Generator.

Generates OpenAPI specifications from FastAPI applications or Python API definitions.
Supports REST APIs with comprehensive documentation, security definitions, and examples.

Usage:
    python openapi-generator.py --help
    python openapi-generator.py --app app.py
    python openapi-generator.py --schema schema.json --output openapi.json
    python openapi-generator.py --validate openapi.json
"""

import argparse
import json
import sys
from dataclasses import dataclass, asdict
from pathlib import Path
from typing import Any, TypeAlias
import logging

logger = logging.getLogger(__name__)

# Type aliases
JSONType: TypeAlias = dict[str, Any] | list[Any] | str | int | float | bool | None


@dataclass
class Contact:
    """API contact information."""

    name: str
    url: str | None = None
    email: str | None = None


@dataclass
class License:
    """API license information."""

    name: str
    url: str | None = None


@dataclass
class Info:
    """OpenAPI info object."""

    title: str
    version: str
    description: str | None = None
    terms_of_service: str | None = None
    contact: Contact | None = None
    license: License | None = None


@dataclass
class Server:
    """OpenAPI server object."""

    url: str
    description: str | None = None
    variables: dict[str, Any] | None = None


@dataclass
class Parameter:
    """OpenAPI parameter object."""

    name: str
    param_in: str  # 'query', 'path', 'header', 'cookie'
    required: bool = False
    description: str | None = None
    schema: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to OpenAPI dict."""
        result: dict[str, Any] = {
            "name": self.name,
            "in": self.param_in,
            "required": self.required,
        }
        if self.description:
            result["description"] = self.description
        if self.schema:
            result["schema"] = self.schema
        return result


@dataclass
class Response:
    """OpenAPI response object."""

    status_code: str  # '200', '404', etc.
    description: str
    content_type: str = "application/json"
    schema: dict[str, Any] | None = None
    examples: dict[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        """Convert to OpenAPI dict."""
        result: dict[str, Any] = {"description": self.description}

        if self.schema or self.examples:
            result["content"] = {
                self.content_type: {
                    "schema": self.schema or {},
                    **({"examples": self.examples} if self.examples else {}),
                }
            }

        return result


class OpenAPIGenerator:
    """Generate OpenAPI 3.0 specifications."""

    def __init__(self, info: Info, servers: list[Server] | None = None):
        """Initialize generator.

        Args:
            info: API information.
            servers: List of servers.
        """
        self.info = info
        self.servers = servers or [Server(url="http://localhost:8000")]
        self.paths: dict[str, dict[str, Any]] = {}
        self.components: dict[str, Any] = {
            "schemas": {},
            "securitySchemes": {},
        }

    def add_path(
        self,
        path: str,
        method: str,
        operation_id: str,
        summary: str,
        description: str | None = None,
        parameters: list[Parameter] | None = None,
        request_body: dict[str, Any] | None = None,
        responses: dict[str, Response] | None = None,
        tags: list[str] | None = None,
        security: list[dict[str, list[str]]] | None = None,
    ) -> None:
        """Add endpoint to OpenAPI spec.

        Args:
            path: API path (e.g., '/users', '/users/{id}').
            method: HTTP method (e.g., 'get', 'post').
            operation_id: Unique operation ID.
            summary: Short endpoint summary.
            description: Detailed description.
            parameters: Query/path/header parameters.
            request_body: Request body schema.
            responses: Response schemas by status code.
            tags: Endpoint tags for grouping.
            security: Security requirements.
        """
        if path not in self.paths:
            self.paths[path] = {}

        operation: dict[str, Any] = {
            "operationId": operation_id,
            "summary": summary,
            "tags": tags or [],
        }

        if description:
            operation["description"] = description

        if parameters:
            operation["parameters"] = [p.to_dict() for p in parameters]

        if request_body:
            operation["requestBody"] = request_body

        if responses:
            operation["responses"] = {code: resp.to_dict() for code, resp in responses.items()}
        else:
            operation["responses"] = {"200": Response("200", "Success").to_dict()}

        if security:
            operation["security"] = security

        self.paths[path][method.lower()] = operation

    def add_schema(self, name: str, schema: dict[str, Any]) -> None:
        """Add reusable schema component.

        Args:
            name: Schema name (e.g., 'User', 'Error').
            schema: Schema definition.
        """
        self.components["schemas"][name] = schema

    def add_security_scheme(self, name: str, scheme_type: str, **kwargs: Any) -> None:
        """Add security scheme.

        Args:
            name: Scheme name (e.g., 'Bearer', 'ApiKey').
            scheme_type: 'http', 'apiKey', 'oauth2', 'openIdConnect'.
            **kwargs: Scheme-specific properties.
        """
        scheme: dict[str, Any] = {"type": scheme_type, **kwargs}
        self.components["securitySchemes"][name] = scheme

    def generate(self) -> dict[str, Any]:
        """Generate OpenAPI specification.

        Returns:
            OpenAPI 3.0 specification dict.
        """
        spec: dict[str, Any] = {
            "openapi": "3.0.0",
            "info": {
                "title": self.info.title,
                "version": self.info.version,
            },
        }

        if self.info.description:
            spec["info"]["description"] = self.info.description
        if self.info.terms_of_service:
            spec["info"]["termsOfService"] = self.info.terms_of_service
        if self.info.contact:
            spec["info"]["contact"] = {
                k: v for k, v in asdict(self.info.contact).items() if v is not None
            }
        if self.info.license:
            spec["info"]["license"] = {
                k: v for k, v in asdict(self.info.license).items() if v is not None
            }

        spec["servers"] = [
            {
                "url": server.url,
                **({"description": server.description} if server.description else {}),
            }
            for server in self.servers
        ]

        spec["paths"] = self.paths

        if self.components["schemas"] or self.components["securitySchemes"]:
            spec["components"] = self.components

        return spec

    def to_json(self, indent: int = 2) -> str:
        """Generate JSON specification.

        Args:
            indent: JSON indentation level.

        Returns:
            JSON string.
        """
        return json.dumps(self.generate(), indent=indent)

    @staticmethod
    def validate_spec(spec: dict[str, Any]) -> tuple[bool, list[str]]:
        """Validate OpenAPI specification.

        Args:
            spec: OpenAPI spec dict.

        Returns:
            Tuple of (is_valid, list_of_errors).
        """
        errors: list[str] = []

        # Check required fields
        if "openapi" not in spec:
            errors.append("Missing required field: 'openapi'")
        if "info" not in spec:
            errors.append("Missing required field: 'info'")
        if "paths" not in spec:
            errors.append("Missing required field: 'paths'")

        # Validate info
        if "info" in spec:
            info = spec["info"]
            if "title" not in info:
                errors.append("Missing required field: 'info.title'")
            if "version" not in info:
                errors.append("Missing required field: 'info.version'")

        # Validate paths
        if "paths" in spec and spec["paths"]:
            for path, methods in spec["paths"].items():
                if not isinstance(methods, dict):
                    errors.append(f"Path '{path}' value must be an object")
                    continue

                for method, operation in methods.items():
                    if method.startswith("x-"):
                        continue  # Skip extensions
                    if method not in [
                        "get",
                        "post",
                        "put",
                        "patch",
                        "delete",
                        "options",
                        "head",
                        "trace",
                    ]:
                        errors.append(f"Invalid HTTP method: {method}")

                    if isinstance(operation, dict):
                        if "responses" not in operation:
                            errors.append(f"Operation '{method} {path}' missing responses")

        return len(errors) == 0, errors


def create_example_spec() -> OpenAPIGenerator:
    """Create example OpenAPI specification for documentation.

    Returns:
        Configured OpenAPIGenerator instance.
    """
    info = Info(
        title="User Management API",
        version="1.0.0",
        description="Simple REST API for managing users",
        contact=Contact(name="API Support", email="support@example.com"),
    )

    generator = OpenAPIGenerator(info)

    # Add security scheme
    generator.add_security_scheme(
        "BearerAuth",
        "http",
        scheme="bearer",
        bearerFormat="JWT",
    )

    # Define schemas
    generator.add_schema(
        "User",
        {
            "type": "object",
            "required": ["id", "email", "name"],
            "properties": {
                "id": {"type": "string", "example": "user-123"},
                "email": {"type": "string", "format": "email"},
                "name": {"type": "string"},
                "status": {
                    "type": "string",
                    "enum": ["active", "inactive", "suspended"],
                },
                "created_at": {"type": "string", "format": "date-time"},
                "updated_at": {"type": "string", "format": "date-time"},
            },
        },
    )

    generator.add_schema(
        "UserCreate",
        {
            "type": "object",
            "required": ["email", "name", "password"],
            "properties": {
                "email": {"type": "string", "format": "email"},
                "name": {"type": "string", "minLength": 1, "maxLength": 100},
                "password": {"type": "string", "minLength": 8},
                "status": {
                    "type": "string",
                    "enum": ["active", "inactive"],
                    "default": "active",
                },
            },
        },
    )

    generator.add_schema(
        "PaginatedUsers",
        {
            "type": "object",
            "required": ["items", "total", "page", "page_size", "pages"],
            "properties": {
                "items": {"type": "array", "items": {"$ref": "#/components/schemas/User"}},
                "total": {"type": "integer"},
                "page": {"type": "integer"},
                "page_size": {"type": "integer"},
                "pages": {"type": "integer"},
            },
        },
    )

    generator.add_schema(
        "Error",
        {
            "type": "object",
            "required": ["error", "message"],
            "properties": {
                "error": {"type": "string"},
                "message": {"type": "string"},
                "details": {"type": "object"},
            },
        },
    )

    # Add endpoints
    generator.add_path(
        "/api/users",
        "get",
        "list_users",
        "List all users",
        description="Retrieve paginated list of users with optional filtering",
        parameters=[
            Parameter("page", "query", False, "Page number", {"type": "integer", "default": 1}),
            Parameter(
                "page_size",
                "query",
                False,
                "Items per page",
                {"type": "integer", "default": 20, "maximum": 100},
            ),
            Parameter(
                "status",
                "query",
                False,
                "Filter by status",
                {"type": "string", "enum": ["active", "inactive", "suspended"]},
            ),
        ],
        responses={
            "200": Response(
                "200",
                "Successful response",
                schema={"$ref": "#/components/schemas/PaginatedUsers"},
            ),
            "401": Response("401", "Unauthorized"),
        },
        tags=["Users"],
        security=[{"BearerAuth": []}],
    )

    generator.add_path(
        "/api/users",
        "post",
        "create_user",
        "Create a new user",
        request_body={
            "required": True,
            "content": {
                "application/json": {"schema": {"$ref": "#/components/schemas/UserCreate"}}
            },
        },
        responses={
            "201": Response(
                "201",
                "User created successfully",
                schema={"$ref": "#/components/schemas/User"},
            ),
            "400": Response("400", "Invalid input", schema={"$ref": "#/components/schemas/Error"}),
            "409": Response("409", "User already exists"),
        },
        tags=["Users"],
        security=[{"BearerAuth": []}],
    )

    generator.add_path(
        "/api/users/{user_id}",
        "get",
        "get_user",
        "Get user by ID",
        parameters=[Parameter("user_id", "path", True, "User ID", {"type": "string"})],
        responses={
            "200": Response(
                "200",
                "User found",
                schema={"$ref": "#/components/schemas/User"},
            ),
            "404": Response("404", "User not found"),
        },
        tags=["Users"],
        security=[{"BearerAuth": []}],
    )

    generator.add_path(
        "/api/users/{user_id}",
        "patch",
        "update_user",
        "Update user",
        parameters=[Parameter("user_id", "path", True, "User ID", {"type": "string"})],
        request_body={
            "required": True,
            "content": {
                "application/json": {
                    "schema": {
                        "type": "object",
                        "properties": {
                            "email": {"type": "string", "format": "email"},
                            "name": {"type": "string"},
                            "status": {"type": "string", "enum": ["active", "inactive"]},
                        },
                    }
                }
            },
        },
        responses={
            "200": Response(
                "200",
                "User updated",
                schema={"$ref": "#/components/schemas/User"},
            ),
            "404": Response("404", "User not found"),
        },
        tags=["Users"],
        security=[{"BearerAuth": []}],
    )

    generator.add_path(
        "/api/users/{user_id}",
        "delete",
        "delete_user",
        "Delete user",
        parameters=[Parameter("user_id", "path", True, "User ID", {"type": "string"})],
        responses={
            "204": Response("204", "User deleted successfully"),
            "404": Response("404", "User not found"),
        },
        tags=["Users"],
        security=[{"BearerAuth": []}],
    )

    return generator


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="OpenAPI 3.0 Schema Generator",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Generate example OpenAPI spec
  %(prog)s --output openapi.json

  # Validate existing spec
  %(prog)s --validate openapi.json

  # Pretty print spec
  %(prog)s --output openapi.json --pretty
        """,
    )

    parser.add_argument(
        "-o",
        "--output",
        type=str,
        help="Output file for generated spec (default: print to stdout)",
    )
    parser.add_argument(
        "-v",
        "--validate",
        type=str,
        metavar="FILE",
        help="Validate existing OpenAPI spec",
    )
    parser.add_argument(
        "--pretty",
        action="store_true",
        help="Pretty print JSON output",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose logging",
    )

    args = parser.parse_args()

    if args.verbose:
        logging.basicConfig(level=logging.DEBUG)
    else:
        logging.basicConfig(level=logging.INFO)

    # Validate mode
    if args.validate:
        validate_file = Path(args.validate)
        if not validate_file.exists():
            logger.error(f"File not found: {args.validate}")
            return 1

        try:
            with open(validate_file) as f:
                spec = json.load(f)
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON: {e}")
            return 1

        is_valid, errors = OpenAPIGenerator.validate_spec(spec)
        if is_valid:
            print(f"✓ Valid OpenAPI specification: {args.validate}")
            return 0
        else:
            print("✗ Invalid OpenAPI specification:")
            for error in errors:
                print(f"  - {error}")
            return 1

    # Generate mode
    generator = create_example_spec()
    spec_json = generator.to_json(indent=2 if args.pretty else None)

    if args.output:
        output_path = Path(args.output)
        output_path.write_text(spec_json, encoding="utf-8")
        print(f"OpenAPI spec generated: {args.output}")
    else:
        print(spec_json)

    return 0


if __name__ == "__main__":
    sys.exit(main())
