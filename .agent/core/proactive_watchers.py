"""Proactive Watchers — agentes que observan y sugieren sin ser invocados.

Sistema de watchers que monitorean el proyecto en busca de:
- Secrets expuestos en código
- Vulnerabilidades en dependencias
- Código duplicado detectado en observaciones
- Tasks pendientes acumulándose
"""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class WatcherAlert:
    """Alerta generada por un watcher."""

    watcher: str
    severity: str  # "critical" | "high" | "medium" | "low"
    title: str
    detail: str
    file_path: str = ""
    line_number: int = 0
    suggestion: str = ""

    def to_dict(self) -> dict[str, Any]:
        """Serializa la alerta a dict."""
        return {
            "watcher": self.watcher,
            "severity": self.severity,
            "title": self.title,
            "detail": self.detail,
            "file_path": self.file_path,
            "line_number": self.line_number,
            "suggestion": self.suggestion,
        }


@dataclass
class WatcherReport:
    """Reporte consolidado de todos los watchers."""

    alerts: list[WatcherAlert] = field(default_factory=list)
    watchers_run: int = 0
    scan_duration_ms: float = 0.0

    @property
    def critical_count(self) -> int:
        """Número de alertas críticas."""
        return sum(1 for a in self.alerts if a.severity == "critical")

    @property
    def high_count(self) -> int:
        """Número de alertas altas."""
        return sum(1 for a in self.alerts if a.severity == "high")

    def to_dict(self) -> dict[str, Any]:
        """Serializa el reporte a dict."""
        return {
            "alerts": [a.to_dict() for a in self.alerts],
            "summary": {
                "total": len(self.alerts),
                "critical": self.critical_count,
                "high": self.high_count,
                "watchers_run": self.watchers_run,
                "scan_duration_ms": self.scan_duration_ms,
            },
        }


# ---- Patterns de secrets comunes ----

SECRET_PATTERNS: list[tuple[str, str]] = [
    (r'(?i)(api[_-]?key|apikey)\s*[=:]\s*["\']([A-Za-z0-9_\-]{20,})["\']', "API Key expuesta"),
    (
        r'(?i)(secret|password|passwd|pwd)\s*[=:]\s*["\']([^\s"\']{8,})["\']',
        "Secret/password hardcodeado",
    ),
    (r'(?i)(token)\s*[=:]\s*["\']([A-Za-z0-9_\-\.]{20,})["\']', "Token hardcodeado"),
    (r'(?i)(aws_access_key_id)\s*[=:]\s*["\']?(AKIA[A-Z0-9]{16})["\']?', "AWS Access Key"),
    (r'(?i)(aws_secret_access_key)\s*[=:]\s*["\']?([A-Za-z0-9/+=]{40})["\']?', "AWS Secret Key"),
    (r"sk-[A-Za-z0-9]{40,}", "OpenAI API Key"),
    (r"ghp_[A-Za-z0-9]{36}", "GitHub Personal Token"),
    (r"gho_[A-Za-z0-9]{36}", "GitHub OAuth Token"),
    (r"ghu_[A-Za-z0-9]{36}", "GitHub User-to-Server Token"),
    (r"ghs_[A-Za-z0-9]{36}", "GitHub Server-to-Server Token"),
    (r"-----BEGIN (RSA |EC )?PRIVATE KEY-----", "Clave privada"),
]

# Archivos a ignorar en escaneo de secrets
IGNORE_PATTERNS = {
    ".env.example",
    ".env.template",
    ".env.sample",
    "package-lock.json",
    "yarn.lock",
    "pnpm-lock.yaml",
    "Cargo.lock",
    "poetry.lock",
}

IGNORE_DIRS = {
    "node_modules",
    ".git",
    "dist",
    "build",
    "__pycache__",
    ".venv",
    "venv",
    ".tox",
    ".mypy_cache",
    ".ruff_cache",
    "target",
    ".next",
    ".nuxt",
}

CODE_EXTENSIONS = {
    ".py",
    ".ts",
    ".tsx",
    ".js",
    ".jsx",
    ".rs",
    ".go",
    ".java",
    ".kt",
    ".rb",
    ".php",
    ".yaml",
    ".yml",
    ".toml",
    ".json",
    ".sh",
    ".bash",
    ".env",
}


def _should_scan_file(path: Path) -> bool:
    """Determina si un archivo debe ser escaneado."""
    if path.name in IGNORE_PATTERNS:
        return False
    if path.suffix not in CODE_EXTENSIONS:
        return False
    return all(part not in IGNORE_DIRS for part in path.parts)


class SecurityWatcher:
    """Detecta secrets y credenciales expuestas en el código."""

    name = "security-watcher"

    def scan(self, project_dir: str | Path, *, max_files: int = 500) -> list[WatcherAlert]:
        """Escanea el proyecto en busca de secrets expuestos.

        Args:
            project_dir: Directorio del proyecto.
            max_files: Límite de archivos a escanear.

        Returns:
            Lista de alertas de seguridad.
        """
        alerts: list[WatcherAlert] = []
        root = Path(project_dir)
        files_scanned = 0

        try:
            for filepath in root.rglob("*"):
                if files_scanned >= max_files:
                    break
                if not filepath.is_file() or not _should_scan_file(filepath):
                    continue

                files_scanned += 1
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                except (OSError, PermissionError):
                    continue

                for line_num, line in enumerate(content.splitlines(), 1):
                    # Skip commented lines
                    stripped = line.lstrip()
                    if stripped.startswith(("#", "//", "*", "/*")):
                        continue

                    for pattern, description in SECRET_PATTERNS:
                        if re.search(pattern, line):
                            # Verificar que no sea un placeholder
                            if any(
                                placeholder in line.lower()
                                for placeholder in (
                                    "your_",
                                    "xxx",
                                    "placeholder",
                                    "example",
                                    "change_me",
                                    "todo",
                                    "fixme",
                                    "env.",
                                    "process.env",
                                    "os.environ",
                                    "os.getenv",
                                )
                            ):
                                continue

                            alerts.append(
                                WatcherAlert(
                                    watcher=self.name,
                                    severity="critical",
                                    title=description,
                                    detail=f"Posible {description.lower()} en línea {line_num}",
                                    file_path=str(filepath.relative_to(root)),
                                    line_number=line_num,
                                    suggestion="Mover a variable de entorno y agregar archivo a .gitignore",
                                )
                            )
                            break  # Una alerta por línea
        except PermissionError:
            pass

        logger.info(
            "SecurityWatcher: escaneados %d archivos, %d alertas",
            files_scanned,
            len(alerts),
        )
        return alerts


class DependencyWatcher:
    """Detecta señales de dependencias potencialmente problemáticas."""

    name = "dependency-watcher"

    def scan(self, project_dir: str | Path) -> list[WatcherAlert]:
        """Escanea archivos de dependencias en busca de problemas.

        Args:
            project_dir: Directorio del proyecto.

        Returns:
            Lista de alertas sobre dependencias.
        """
        alerts: list[WatcherAlert] = []
        root = Path(project_dir)

        # Check package.json for known problematic patterns
        pkg_json = root / "package.json"
        if pkg_json.exists():
            alerts.extend(self._check_npm(pkg_json))

        # Check pyproject.toml for unpinned deps
        pyproject = root / "pyproject.toml"
        if pyproject.exists():
            alerts.extend(self._check_python(pyproject))

        # Check for missing lock files
        if pkg_json.exists() and not any(
            (root / lock).exists()
            for lock in ("package-lock.json", "yarn.lock", "pnpm-lock.yaml", "bun.lockb")
        ):
            alerts.append(
                WatcherAlert(
                    watcher=self.name,
                    severity="medium",
                    title="Sin archivo lock de npm",
                    detail="package.json existe pero no hay lock file",
                    file_path="package.json",
                    suggestion="Ejecutar npm install para generar package-lock.json",
                )
            )

        return alerts

    def _check_npm(self, pkg_path: Path) -> list[WatcherAlert]:
        """Verifica dependencias npm."""
        import json

        alerts: list[WatcherAlert] = []
        try:
            data = json.loads(pkg_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return alerts

        deps = {**data.get("dependencies", {}), **data.get("devDependencies", {})}

        # Check for wildcard versions
        for dep_name, version in deps.items():
            if version in ("*", "latest"):
                alerts.append(
                    WatcherAlert(
                        watcher=self.name,
                        severity="high",
                        title=f"Dependencia sin versión fija: {dep_name}",
                        detail=f"{dep_name}@{version} puede causar builds no reproducibles",
                        file_path="package.json",
                        suggestion=f"Fijar la versión de {dep_name}",
                    )
                )

        return alerts

    def _check_python(self, pyproject_path: Path) -> list[WatcherAlert]:
        """Verifica dependencias Python."""
        alerts: list[WatcherAlert] = []
        try:
            content = pyproject_path.read_text(encoding="utf-8")
        except OSError:
            return alerts

        # Simple check: dependencies without version constraints
        in_deps = False
        for line in content.splitlines():
            stripped = line.strip()
            if stripped.startswith("dependencies"):
                in_deps = True
                continue
            if in_deps and stripped.startswith("]"):
                in_deps = False
                continue
            if in_deps and stripped.startswith('"'):
                dep = stripped.strip('",')
                # Check if there's a version constraint
                if dep and not any(c in dep for c in (">=", "<=", "==", "~=", ">", "<", "^")):
                    alerts.append(
                        WatcherAlert(
                            watcher=self.name,
                            severity="medium",
                            title=f"Dependencia sin versión: {dep}",
                            detail=f"{dep} no tiene constraint de versión",
                            file_path="pyproject.toml",
                            suggestion=f"Agregar versión mínima a {dep}",
                        )
                    )

        return alerts


class PatternWatcher:
    """Detecta patrones problemáticos en el código."""

    name = "pattern-watcher"

    # Anti-patterns to detect
    ANTI_PATTERNS: list[tuple[str, str, str, str]] = [
        (
            r"shell\s*=\s*True",
            "subprocess con shell=True",
            "high",
            "Usar shlex.split() + shell=False",
        ),
        (
            r"eval\s*\(",
            "Uso de eval()",
            "high",
            "Reemplazar eval() con alternativa segura (ast.literal_eval o JSON parsing)",
        ),
        (
            r"exec\s*\(",
            "Uso de exec()",
            "medium",
            "Evaluar si exec() es realmente necesario",
        ),
        (
            r"# ?TODO|# ?FIXME|# ?HACK|# ?XXX",
            "Marcador de deuda técnica",
            "low",
            "Resolver o crear issue para este TODO",
        ),
    ]

    def scan(self, project_dir: str | Path, *, max_files: int = 300) -> list[WatcherAlert]:
        """Escanea en busca de anti-patterns.

        Args:
            project_dir: Directorio del proyecto.
            max_files: Límite de archivos.

        Returns:
            Lista de alertas de patrones.
        """
        alerts: list[WatcherAlert] = []
        root = Path(project_dir)
        files_scanned = 0

        try:
            for filepath in root.rglob("*"):
                if files_scanned >= max_files:
                    break
                if not filepath.is_file():
                    continue
                if filepath.suffix not in (".py", ".ts", ".tsx", ".js", ".jsx"):
                    continue
                if any(p in filepath.parts for p in IGNORE_DIRS):
                    continue

                files_scanned += 1
                try:
                    content = filepath.read_text(encoding="utf-8", errors="ignore")
                except (OSError, PermissionError):
                    continue

                rel_path = str(filepath.relative_to(root))
                for line_num, line in enumerate(content.splitlines(), 1):
                    for pattern, title, severity, suggestion in self.ANTI_PATTERNS:
                        if re.search(pattern, line):
                            alerts.append(
                                WatcherAlert(
                                    watcher=self.name,
                                    severity=severity,
                                    title=title,
                                    detail=f"Detectado en {rel_path}:{line_num}",
                                    file_path=rel_path,
                                    line_number=line_num,
                                    suggestion=suggestion,
                                )
                            )
                            break
        except PermissionError:
            pass

        return alerts


# ---- Registry de watchers ----

_WATCHERS: list[Any] = [  # type: ignore[list-item]
    SecurityWatcher(),
    DependencyWatcher(),
    PatternWatcher(),
]


def run_all_watchers(
    project_dir: str | Path,
    *,
    watchers: list[str] | None = None,
) -> WatcherReport:
    """Ejecuta todos los watchers (o los seleccionados) sobre un proyecto.

    Args:
        project_dir: Directorio del proyecto a escanear.
        watchers: Nombres de watchers específicos a ejecutar (None = todos).

    Returns:
        WatcherReport con alertas consolidadas.
    """
    import time

    start = time.monotonic()
    report = WatcherReport()

    for watcher in _WATCHERS:
        if watchers and watcher.name not in watchers:
            continue
        try:
            alerts = watcher.scan(project_dir)
            report.alerts.extend(alerts)
            report.watchers_run += 1
        except Exception as e:
            logger.warning("Watcher %s falló: %s", watcher.name, e)

    report.scan_duration_ms = (time.monotonic() - start) * 1000

    # Sort by severity
    severity_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    report.alerts.sort(key=lambda a: severity_order.get(a.severity, 99))

    logger.info(
        "Watchers completados: %d ejecutados, %d alertas en %.0fms",
        report.watchers_run,
        len(report.alerts),
        report.scan_duration_ms,
    )
    return report
