#!/usr/bin/env python3
"""
Project Structure Validator
Valida que un proyecto siga las mejores prácticas de estructura.
"""

import os
import sys
import json
import logging
from pathlib import Path
from dataclasses import dataclass, field
from enum import Enum

logging.basicConfig(level=logging.INFO, format="[%(asctime)s] [%(levelname)s] %(message)s")
logger = logging.getLogger(__name__)


class ProjectType(Enum):
    FRONTEND = "frontend"
    BACKEND = "backend"
    FULLSTACK = "fullstack"
    UNKNOWN = "unknown"


class Severity(Enum):
    ERROR = "error"
    WARNING = "warning"
    INFO = "info"


@dataclass
class ValidationIssue:
    """Problema encontrado en la validación."""

    severity: Severity
    category: str
    message: str
    path: str | None = None
    suggestion: str | None = None


@dataclass
class ValidationResult:
    """Resultado de la validación."""

    project_path: str
    project_type: ProjectType
    issues: list[ValidationIssue] = field(default_factory=list)
    score: int = 100

    @property
    def passed(self) -> bool:
        return not any(i.severity == Severity.ERROR for i in self.issues)

    def add_issue(self, issue: ValidationIssue) -> None:
        self.issues.append(issue)
        if issue.severity == Severity.ERROR:
            self.score -= 10
        elif issue.severity == Severity.WARNING:
            self.score -= 5
        self.score = max(0, self.score)


class ProjectStructureValidator:
    """Validador de estructura de proyectos."""

    # Carpetas esperadas por tipo de proyecto
    FRONTEND_FOLDERS = {
        "required": ["src", "public"],
        "recommended": [
            "src/components",
            "src/pages",
            "src/hooks",
            "src/services",
            "src/utils",
            "src/types",
            "src/assets",
        ],
    }

    BACKEND_FOLDERS = {
        "required": ["src"],
        "recommended": [
            "src/config",
            "src/models",
            "src/routes",
            "src/controllers",
            "src/services",
            "src/middlewares",
            "src/utils",
        ],
    }

    # Archivos de configuración esperados
    CONFIG_FILES = {
        "required": [".gitignore", "package.json"],
        "recommended": ["README.md", "tsconfig.json", ".env.example"],
        "frontend": ["vite.config.ts", "next.config.js", "eslint.config.js"],
        "backend": ["Dockerfile", "docker-compose.yml"],
    }

    # Patrones de nombres incorrectos
    BAD_PATTERNS = [
        ("utils.ts", "Archivo genérico 'utils.ts' - dividir por funcionalidad"),
        ("helpers.ts", "Archivo genérico 'helpers.ts' - ser más específico"),
        ("index.tsx", "Evitar 'index.tsx' como componente - usar nombre descriptivo"),
        ("data.ts", "Archivo genérico 'data.ts' - ser más específico"),
    ]

    def __init__(self, project_path: str):
        self.project_path = Path(project_path)
        self.result = ValidationResult(
            project_path=str(self.project_path), project_type=ProjectType.UNKNOWN
        )

    def detect_project_type(self) -> ProjectType:
        """Detecta el tipo de proyecto."""
        package_json = self.project_path / "package.json"

        if not package_json.exists():
            return ProjectType.UNKNOWN

        try:
            with open(package_json) as f:
                pkg = json.load(f)
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

                has_frontend = any(k in deps for k in ["react", "vue", "next", "vite", "svelte"])
                has_backend = any(k in deps for k in ["express", "fastify", "nestjs", "koa"])

                if has_frontend and has_backend:
                    return ProjectType.FULLSTACK
                elif has_frontend:
                    return ProjectType.FRONTEND
                elif has_backend:
                    return ProjectType.BACKEND

        except Exception as e:
            logger.warning(f"Error reading package.json: {e}")

        return ProjectType.UNKNOWN

    def validate_folders(self) -> None:
        """Valida la estructura de carpetas."""
        if self.result.project_type == ProjectType.FRONTEND:
            folders = self.FRONTEND_FOLDERS
        elif self.result.project_type == ProjectType.BACKEND:
            folders = self.BACKEND_FOLDERS
        else:
            folders = {"required": ["src"], "recommended": []}

        # Carpetas requeridas
        for folder in folders["required"]:
            folder_path = self.project_path / folder
            if not folder_path.exists():
                self.result.add_issue(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        category="structure",
                        message=f"Carpeta requerida '{folder}' no existe",
                        path=folder,
                        suggestion=f"Crear carpeta: mkdir -p {folder}",
                    )
                )

        # Carpetas recomendadas
        for folder in folders["recommended"]:
            folder_path = self.project_path / folder
            if not folder_path.exists():
                self.result.add_issue(
                    ValidationIssue(
                        severity=Severity.WARNING,
                        category="structure",
                        message=f"Carpeta recomendada '{folder}' no existe",
                        path=folder,
                        suggestion=f"Considerar crear: mkdir -p {folder}",
                    )
                )

    def validate_config_files(self) -> None:
        """Valida archivos de configuración."""
        # Archivos requeridos
        for file in self.CONFIG_FILES["required"]:
            file_path = self.project_path / file
            if not file_path.exists():
                self.result.add_issue(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        category="config",
                        message=f"Archivo requerido '{file}' no existe",
                        path=file,
                    )
                )

        # Archivos recomendados
        for file in self.CONFIG_FILES["recommended"]:
            file_path = self.project_path / file
            if not file_path.exists():
                self.result.add_issue(
                    ValidationIssue(
                        severity=Severity.WARNING,
                        category="config",
                        message=f"Archivo recomendado '{file}' no existe",
                        path=file,
                    )
                )

        # Archivos específicos por tipo
        type_key = self.result.project_type.value
        if type_key in self.CONFIG_FILES:
            for file in self.CONFIG_FILES[type_key]:
                file_path = self.project_path / file
                if not file_path.exists():
                    self.result.add_issue(
                        ValidationIssue(
                            severity=Severity.INFO,
                            category="config",
                            message=f"Archivo típico de {type_key} '{file}' no existe",
                            path=file,
                        )
                    )

    def validate_naming_conventions(self) -> None:
        """Valida convenciones de nombres."""
        src_path = self.project_path / "src"
        if not src_path.exists():
            return

        for root, _dirs, files in os.walk(src_path):
            for file in files:
                # Verificar patrones incorrectos
                for bad_pattern, message in self.BAD_PATTERNS:
                    if file == bad_pattern:
                        self.result.add_issue(
                            ValidationIssue(
                                severity=Severity.WARNING,
                                category="naming",
                                message=message,
                                path=os.path.join(root, file),
                            )
                        )

                # Verificar componentes React
                if file.endswith((".tsx", ".jsx")) and "components" in root:
                    if file[0].islower() and file != "index.tsx":
                        self.result.add_issue(
                            ValidationIssue(
                                severity=Severity.WARNING,
                                category="naming",
                                message=f"Componente '{file}' debe usar PascalCase",
                                path=os.path.join(root, file),
                                suggestion=f"Renombrar a: {file[0].upper() + file[1:]}",
                            )
                        )

    def validate_barrel_exports(self) -> None:
        """Valida que existan barrel exports (index.ts)."""
        src_path = self.project_path / "src"
        if not src_path.exists():
            return

        important_folders = ["components", "hooks", "services", "utils", "types"]

        for folder in important_folders:
            folder_path = src_path / folder
            if folder_path.exists() and folder_path.is_dir():
                index_file = folder_path / "index.ts"
                index_file_tsx = folder_path / "index.tsx"

                if not index_file.exists() and not index_file_tsx.exists():
                    self.result.add_issue(
                        ValidationIssue(
                            severity=Severity.INFO,
                            category="exports",
                            message=f"Falta barrel export en '{folder}'",
                            path=str(folder_path),
                            suggestion=f"Crear {folder}/index.ts con exports",
                        )
                    )

    def validate_env_security(self) -> None:
        """Valida que .env no esté en git."""
        env_file = self.project_path / ".env"
        gitignore = self.project_path / ".gitignore"

        if env_file.exists():
            if gitignore.exists():
                with open(gitignore) as f:
                    content = f.read()
                    if ".env" not in content:
                        self.result.add_issue(
                            ValidationIssue(
                                severity=Severity.ERROR,
                                category="security",
                                message=".env existe pero NO está en .gitignore",
                                path=".env",
                                suggestion="Añadir '.env' a .gitignore INMEDIATAMENTE",
                            )
                        )
            else:
                self.result.add_issue(
                    ValidationIssue(
                        severity=Severity.ERROR,
                        category="security",
                        message=".env existe sin .gitignore",
                        suggestion="Crear .gitignore con '.env'",
                    )
                )

    def validate(self) -> ValidationResult:
        """Ejecuta todas las validaciones."""
        logger.info(f"Validando proyecto: {self.project_path}")

        # Detectar tipo de proyecto
        self.result.project_type = self.detect_project_type()
        logger.info(f"Tipo de proyecto detectado: {self.result.project_type.value}")

        # Ejecutar validaciones
        self.validate_folders()
        self.validate_config_files()
        self.validate_naming_conventions()
        self.validate_barrel_exports()
        self.validate_env_security()

        return self.result

    def print_report(self) -> None:
        """Imprime reporte de validación."""
        print("\n" + "=" * 60)
        print("PROJECT STRUCTURE VALIDATION REPORT")
        print("=" * 60)
        print(f"\nProyecto: {self.result.project_path}")
        print(f"Tipo: {self.result.project_type.value}")
        print(f"Score: {self.result.score}/100")
        print(f"Estado: {'✅ PASSED' if self.result.passed else '❌ FAILED'}")

        if not self.result.issues:
            print("\n✅ No se encontraron problemas")
        else:
            # Agrupar por severidad
            errors = [i for i in self.result.issues if i.severity == Severity.ERROR]
            warnings = [i for i in self.result.issues if i.severity == Severity.WARNING]
            infos = [i for i in self.result.issues if i.severity == Severity.INFO]

            if errors:
                print(f"\n❌ ERRORES ({len(errors)}):")
                for issue in errors:
                    print(f"  [{issue.category}] {issue.message}")
                    if issue.path:
                        print(f"    → {issue.path}")
                    if issue.suggestion:
                        print(f"    💡 {issue.suggestion}")

            if warnings:
                print(f"\n⚠️  ADVERTENCIAS ({len(warnings)}):")
                for issue in warnings:
                    print(f"  [{issue.category}] {issue.message}")
                    if issue.suggestion:
                        print(f"    💡 {issue.suggestion}")

            if infos:
                print(f"\n📝 SUGERENCIAS ({len(infos)}):")
                for issue in infos:
                    print(f"  [{issue.category}] {issue.message}")

        print("\n" + "=" * 60)


def main():
    """Punto de entrada."""
    if len(sys.argv) < 2:
        print("Uso: python validate_structure.py <ruta-proyecto>")
        print("\nEjemplo:")
        print("  python validate_structure.py /path/to/my-app")
        sys.exit(1)

    project_path = sys.argv[1]

    if not os.path.exists(project_path):
        print(f"Error: El directorio '{project_path}' no existe")
        sys.exit(1)

    validator = ProjectStructureValidator(project_path)
    result = validator.validate()
    validator.print_report()

    sys.exit(0 if result.passed else 1)


if __name__ == "__main__":
    main()
