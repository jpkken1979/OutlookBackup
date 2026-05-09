#!/usr/bin/env python3
"""
Documentation Writing Skill

Genera documentación técnica de alta calidad para proyectos de software.
"""

import argparse
import json
import re
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


@dataclass
class ProjectInfo:
    """Información extraída del proyecto."""

    name: str = ""
    description: str = ""
    version: str = "1.0.0"
    language: str = "unknown"
    framework: str = ""
    dependencies: list = field(default_factory=list)
    scripts: dict = field(default_factory=dict)
    has_tests: bool = False
    has_docker: bool = False
    has_ci: bool = False
    license: str = ""
    author: str = ""


def detect_project_info(project_path: Path) -> ProjectInfo:
    """Detecta información del proyecto analizando archivos."""
    info = ProjectInfo()

    # Detectar package.json (Node.js)
    package_json = project_path / "package.json"
    if package_json.exists():
        try:
            with open(package_json) as f:
                pkg = json.load(f)
            info.name = pkg.get("name", "")
            info.description = pkg.get("description", "")
            info.version = pkg.get("version", "1.0.0")
            info.language = "javascript/typescript"
            info.scripts = pkg.get("scripts", {})
            info.author = pkg.get("author", "")
            info.license = pkg.get("license", "")

            deps = list(pkg.get("dependencies", {}).keys())
            dev_deps = list(pkg.get("devDependencies", {}).keys())
            info.dependencies = deps + dev_deps

            # Detectar framework
            if "next" in deps:
                info.framework = "Next.js"
            elif "react" in deps:
                info.framework = "React"
            elif "vue" in deps:
                info.framework = "Vue.js"
            elif "express" in deps:
                info.framework = "Express"
            elif "@nestjs/core" in deps:
                info.framework = "NestJS"
        except Exception:
            pass

    # Detectar pyproject.toml (Python)
    pyproject = project_path / "pyproject.toml"
    if pyproject.exists():
        info.language = "python"
        try:
            content = pyproject.read_text()
            if "fastapi" in content.lower():
                info.framework = "FastAPI"
            elif "django" in content.lower():
                info.framework = "Django"
            elif "flask" in content.lower():
                info.framework = "Flask"

            # Extraer nombre
            match = re.search(r'name\s*=\s*"([^"]+)"', content)
            if match:
                info.name = match.group(1)

            # Extraer versión
            match = re.search(r'version\s*=\s*"([^"]+)"', content)
            if match:
                info.version = match.group(1)
        except Exception:
            pass

    # Detectar Cargo.toml (Rust)
    cargo = project_path / "Cargo.toml"
    if cargo.exists():
        info.language = "rust"
        try:
            content = cargo.read_text()
            match = re.search(r'name\s*=\s*"([^"]+)"', content)
            if match:
                info.name = match.group(1)
            if "tauri" in content.lower():
                info.framework = "Tauri"
            elif "actix" in content.lower():
                info.framework = "Actix"
            elif "rocket" in content.lower():
                info.framework = "Rocket"
        except Exception:
            pass

    # Detectar tests
    info.has_tests = (
        (project_path / "tests").exists()
        or (project_path / "test").exists()
        or (project_path / "__tests__").exists()
        or (project_path / "spec").exists()
    )

    # Detectar Docker
    info.has_docker = (
        (project_path / "Dockerfile").exists()
        or (project_path / "docker-compose.yml").exists()
        or (project_path / "docker-compose.yaml").exists()
    )

    # Detectar CI
    info.has_ci = (
        (project_path / ".github" / "workflows").exists()
        or (project_path / ".gitlab-ci.yml").exists()
        or (project_path / "Jenkinsfile").exists()
    )

    # Usar nombre del directorio si no se detectó
    if not info.name:
        info.name = project_path.name

    return info


def generate_readme(project_path: Path, info: ProjectInfo, language: str = "en") -> str:
    """Genera un README.md completo."""

    templates = {
        "en": {
            "title": info.name,
            "badges": generate_badges(info),
            "description": info.description or f"A {info.language} project",
            "features_title": "Features",
            "install_title": "Installation",
            "usage_title": "Usage",
            "dev_title": "Development",
            "test_title": "Testing",
            "docker_title": "Docker",
            "license_title": "License",
            "contributing_title": "Contributing",
        },
        "es": {
            "title": info.name,
            "badges": generate_badges(info),
            "description": info.description or f"Un proyecto en {info.language}",
            "features_title": "Características",
            "install_title": "Instalación",
            "usage_title": "Uso",
            "dev_title": "Desarrollo",
            "test_title": "Tests",
            "docker_title": "Docker",
            "license_title": "Licencia",
            "contributing_title": "Contribuir",
        },
        "ja": {
            "title": info.name,
            "badges": generate_badges(info),
            "description": info.description or f"{info.language}プロジェクト",
            "features_title": "機能",
            "install_title": "インストール",
            "usage_title": "使用方法",
            "dev_title": "開発",
            "test_title": "テスト",
            "docker_title": "Docker",
            "license_title": "ライセンス",
            "contributing_title": "貢献",
        },
    }

    t = templates.get(language, templates["en"])

    sections = []

    # Header
    sections.append(f"# {t['title']}\n")
    if t["badges"]:
        sections.append(t["badges"] + "\n")
    sections.append(f"{t['description']}\n")

    # Features
    sections.append(f"## {t['features_title']}\n")
    sections.append("- Feature 1\n- Feature 2\n- Feature 3\n")

    # Installation
    sections.append(f"## {t['install_title']}\n")
    sections.append(generate_install_instructions(info))

    # Usage
    sections.append(f"## {t['usage_title']}\n")
    sections.append(generate_usage_instructions(info))

    # Development
    if info.scripts:
        sections.append(f"## {t['dev_title']}\n")
        sections.append(generate_dev_instructions(info))

    # Testing
    if info.has_tests:
        sections.append(f"## {t['test_title']}\n")
        sections.append(generate_test_instructions(info))

    # Docker
    if info.has_docker:
        sections.append(f"## {t['docker_title']}\n")
        sections.append(generate_docker_instructions(info))

    # License
    if info.license:
        sections.append(f"## {t['license_title']}\n")
        sections.append(f"This project is licensed under the {info.license} License.\n")

    return "\n".join(sections)


def generate_badges(info: ProjectInfo) -> str:
    """Genera badges para el README."""
    badges = []

    if info.version:
        badges.append(f"![Version](https://img.shields.io/badge/version-{info.version}-blue)")

    if info.license:
        badges.append(f"![License](https://img.shields.io/badge/license-{info.license}-green)")

    if info.language == "javascript/typescript":
        badges.append("![Node.js](https://img.shields.io/badge/Node.js-18+-green)")
    elif info.language == "python":
        badges.append("![Python](https://img.shields.io/badge/Python-3.11+-blue)")
    elif info.language == "rust":
        badges.append("![Rust](https://img.shields.io/badge/Rust-1.70+-orange)")

    if info.has_tests:
        badges.append("![Tests](https://img.shields.io/badge/tests-passing-brightgreen)")

    if info.has_docker:
        badges.append("![Docker](https://img.shields.io/badge/docker-ready-blue)")

    return " ".join(badges)


def generate_install_instructions(info: ProjectInfo) -> str:
    """Genera instrucciones de instalación."""
    instructions = []

    instructions.append("```bash")
    instructions.append(f"git clone https://github.com/user/{info.name}.git")
    instructions.append(f"cd {info.name}")

    if info.language == "javascript/typescript":
        instructions.append("npm install")
    elif info.language == "python":
        instructions.append("pip install -e .")
    elif info.language == "rust":
        instructions.append("cargo build")

    instructions.append("```\n")

    return "\n".join(instructions)


def generate_usage_instructions(info: ProjectInfo) -> str:
    """Genera instrucciones de uso."""
    instructions = []

    instructions.append("```bash")

    if info.language == "javascript/typescript":
        if "start" in info.scripts:
            instructions.append("npm start")
        elif "dev" in info.scripts:
            instructions.append("npm run dev")
        else:
            instructions.append("npm start")
    elif info.language == "python":
        if info.framework == "FastAPI":
            instructions.append("uvicorn main:app --reload")
        elif info.framework == "Django":
            instructions.append("python manage.py runserver")
        else:
            instructions.append(f"python -m {info.name}")
    elif info.language == "rust":
        instructions.append("cargo run")

    instructions.append("```\n")

    return "\n".join(instructions)


def generate_dev_instructions(info: ProjectInfo) -> str:
    """Genera instrucciones de desarrollo."""
    instructions = []

    if info.scripts:
        instructions.append("Available scripts:\n")
        instructions.append("```bash")
        for script, cmd in list(info.scripts.items())[:5]:
            instructions.append(f"npm run {script}  # {cmd[:50]}...")
        instructions.append("```\n")

    return "\n".join(instructions)


def generate_test_instructions(info: ProjectInfo) -> str:
    """Genera instrucciones de testing."""
    instructions = []

    instructions.append("```bash")

    if info.language == "javascript/typescript":
        if "test" in info.scripts:
            instructions.append("npm test")
        else:
            instructions.append("npm test")
    elif info.language == "python":
        instructions.append("pytest tests/ -v")
    elif info.language == "rust":
        instructions.append("cargo test")

    instructions.append("```\n")

    return "\n".join(instructions)


def generate_docker_instructions(info: ProjectInfo) -> str:
    """Genera instrucciones de Docker."""
    instructions = []

    instructions.append("```bash")
    instructions.append(f"docker build -t {info.name} .")
    instructions.append(f"docker run -p 3000:3000 {info.name}")
    instructions.append("```\n")

    return "\n".join(instructions)


def generate_api_docs(project_path: Path, info: ProjectInfo) -> str:
    """Genera documentación de API en formato OpenAPI."""
    openapi = {
        "openapi": "3.0.0",
        "info": {
            "title": f"{info.name} API",
            "version": info.version,
            "description": info.description or f"API documentation for {info.name}",
        },
        "servers": [{"url": "http://localhost:3000", "description": "Development server"}],
        "paths": {
            "/health": {
                "get": {
                    "summary": "Health check",
                    "responses": {"200": {"description": "Service is healthy"}},
                }
            },
            "/api/v1/items": {
                "get": {
                    "summary": "List items",
                    "parameters": [
                        {
                            "name": "limit",
                            "in": "query",
                            "schema": {"type": "integer", "default": 10},
                        }
                    ],
                    "responses": {"200": {"description": "List of items"}},
                },
                "post": {
                    "summary": "Create item",
                    "requestBody": {
                        "required": True,
                        "content": {
                            "application/json": {
                                "schema": {
                                    "type": "object",
                                    "properties": {
                                        "name": {"type": "string"},
                                        "value": {"type": "string"},
                                    },
                                }
                            }
                        },
                    },
                    "responses": {"201": {"description": "Item created"}},
                },
            },
        },
    }

    return json.dumps(openapi, indent=2)


def generate_changelog(project_path: Path, info: ProjectInfo) -> str:
    """Genera un CHANGELOG.md."""
    today = datetime.now().strftime("%Y-%m-%d")

    changelog = f"""# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
- Initial project structure
- Basic functionality

## [{info.version}] - {today}

### Added
- First release
- Core features implemented
- Documentation

### Changed
- N/A

### Deprecated
- N/A

### Removed
- N/A

### Fixed
- N/A

### Security
- N/A
"""

    return changelog


def generate_architecture_doc(project_path: Path, info: ProjectInfo) -> str:
    """Genera documentación de arquitectura (ADR)."""

    adr = f"""# Architecture Decision Record

## ADR-001: Project Structure

### Status
Accepted

### Context
We need to establish a clear project structure for {info.name}.

### Decision
We will use the following structure:

```
{info.name}/
├── src/           # Source code
├── tests/         # Test files
├── docs/          # Documentation
├── config/        # Configuration files
└── scripts/       # Utility scripts
```

### Consequences
- Clear separation of concerns
- Easy to navigate
- Standard structure familiar to developers

---

## ADR-002: Technology Stack

### Status
Accepted

### Context
We need to choose the technology stack for {info.name}.

### Decision
- **Language**: {info.language}
- **Framework**: {info.framework or "N/A"}
- **Database**: PostgreSQL (recommended)
- **Cache**: Redis (recommended)

### Consequences
- Modern, well-supported stack
- Good developer experience
- Strong community support

---

## ADR-003: Testing Strategy

### Status
Accepted

### Context
We need a testing strategy for {info.name}.

### Decision
- Unit tests for business logic
- Integration tests for APIs
- E2E tests for critical flows
- Target: 80% code coverage

### Consequences
- High confidence in code quality
- Safe refactoring
- Documentation through tests
"""

    return adr


def main():
    parser = argparse.ArgumentParser(
        description="Documentation Writing Skill - Genera documentación técnica"
    )
    parser.add_argument(
        "project_path", nargs="?", default=".", help="Ruta al proyecto (default: directorio actual)"
    )
    parser.add_argument(
        "--type",
        "-t",
        choices=["readme", "api", "changelog", "architecture", "all"],
        default="readme",
        help="Tipo de documentación a generar",
    )
    parser.add_argument(
        "--language",
        "-l",
        choices=["en", "es", "ja"],
        default="en",
        help="Idioma de la documentación",
    )
    parser.add_argument("--output", "-o", help="Archivo de salida (default: stdout)")
    parser.add_argument("--json", action="store_true", help="Output en formato JSON")

    args = parser.parse_args()
    project_path = Path(args.project_path).resolve()

    if not project_path.exists():
        print(f"Error: Path '{project_path}' does not exist")
        return 1

    # Detectar información del proyecto
    info = detect_project_info(project_path)

    # Generar documentación según tipo
    docs = {}

    if args.type in ["readme", "all"]:
        docs["readme"] = generate_readme(project_path, info, args.language)

    if args.type in ["api", "all"]:
        docs["api"] = generate_api_docs(project_path, info)

    if args.type in ["changelog", "all"]:
        docs["changelog"] = generate_changelog(project_path, info)

    if args.type in ["architecture", "all"]:
        docs["architecture"] = generate_architecture_doc(project_path, info)

    # Output
    if args.json:
        result = {
            "project": {
                "name": info.name,
                "version": info.version,
                "language": info.language,
                "framework": info.framework,
            },
            "documentation": docs,
        }
        print(json.dumps(result, indent=2))
    else:
        if args.type == "all":
            for doc_type, content in docs.items():
                print(f"\n{'=' * 60}")
                print(f" {doc_type.upper()}")
                print(f"{'=' * 60}\n")
                print(content)
        else:
            content = docs.get(args.type, "")
            if args.output:
                with open(args.output, "w") as f:
                    f.write(content)
                print(f"Documentation written to {args.output}")
            else:
                print(content)

    return 0


if __name__ == "__main__":
    exit(main())
