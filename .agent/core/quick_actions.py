"""
Quick Actions - Acciones rápidas que uso constantemente

Este módulo proporciona atajos para las acciones más comunes.
No quiero pensar "¿qué agente invoco?" - quiero hacer la acción directamente.
"""
# mypy: ignore-errors

import json
import os
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any


@dataclass
class ActionResult:
    """Resultado de una acción rápida."""

    success: bool
    data: Any
    message: str
    duration_ms: int = 0


class QuickActions:
    """
    Acciones rápidas para tareas comunes.

    Estas son las cosas que hago TODO EL TIEMPO:
    - Explorar el proyecto
    - Verificar mi código
    - Recordar algo importante
    - Ver preferencias del usuario
    - Comprimir contexto
    - Hacer commit
    - Buscar en el código
    """

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()

    # ==================== EXPLORACIÓN ====================

    def explore_project(self) -> ActionResult:
        """
        Exploración rápida del proyecto.

        Returns:
            Resumen del proyecto
        """
        import time

        start = time.time()

        result = {
            "name": self.project_root.name,
            "path": str(self.project_root),
        }

        # Stack tecnológico
        result["stack"] = self._detect_stack()

        # Estructura
        result["structure"] = self._get_structure()

        # Git status
        result["git"] = self._get_git_info()

        # Archivos importantes
        result["key_files"] = self._find_key_files()

        # Tamaño
        result["stats"] = self._get_project_stats()

        duration = int((time.time() - start) * 1000)

        return ActionResult(
            success=True,
            data=result,
            message=f"Project explored: {result['name']} ({result['stack']['language']})",
            duration_ms=duration,
        )

    def _detect_stack(self) -> dict:
        """Detecta stack tecnológico.

        Returns:
            Diccionario con lenguaje, framework y herramientas detectadas.
        """
        stack = {"language": "unknown", "framework": None, "tools": []}

        if (self.project_root / "pyproject.toml").exists() or (
            self.project_root / "requirements.txt"
        ).exists():
            self._detect_python_stack(stack)
        elif (self.project_root / "package.json").exists():
            self._detect_js_stack(stack)
        elif (self.project_root / "Cargo.toml").exists():
            stack["language"] = "rust"

        return stack

    def _detect_python_stack(self, stack: dict) -> None:
        """Detecta framework y herramientas de un proyecto Python.

        Args:
            stack: Diccionario de stack a mutar in-place.
        """
        stack["language"] = "python"
        framework_map = {"fastapi": "FastAPI", "django": "Django", "flask": "Flask"}

        for file in ["pyproject.toml", "requirements.txt"]:
            path = self.project_root / file
            if not path.exists():
                continue
            content = path.read_text(encoding="utf-8").lower()
            for needle, name in framework_map.items():
                if needle in content:
                    stack["framework"] = name
                    break
            for tool in ["pytest", "ruff", "mypy"]:
                if tool in content:
                    stack["tools"].append(tool)

    def _detect_js_stack(self, stack: dict) -> None:
        """Detecta lenguaje y framework de un proyecto JavaScript/TypeScript.

        Args:
            stack: Diccionario de stack a mutar in-place.
        """
        try:
            pkg = json.loads((self.project_root / "package.json").read_text(encoding="utf-8"))
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
        except (OSError, json.JSONDecodeError, ValueError):
            stack["language"] = "javascript"
            return

        stack["language"] = "typescript" if "typescript" in deps else "javascript"
        framework_map = {"next": "Next.js", "react": "React", "vue": "Vue"}
        for needle, name in framework_map.items():
            if needle in deps:
                stack["framework"] = name
                break

    def _get_structure(self) -> dict:
        """Obtiene estructura del proyecto."""
        structure = {"directories": [], "depth": 0}

        # Directorios principales (1 nivel)
        for item in self.project_root.iterdir():
            if item.is_dir() and not item.name.startswith("."):
                structure["directories"].append(item.name)

        structure["directories"] = sorted(structure["directories"])[:15]
        return structure

    def _get_git_info(self) -> dict:
        """Obtiene información de git."""
        info = {"is_repo": False}

        try:
            # Branch
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=5,
            )
            if result.returncode == 0:
                info["is_repo"] = True
                info["branch"] = result.stdout.strip()

            # Status
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=5,
            )
            if result.returncode == 0:
                lines = [l for l in result.stdout.strip().split("\n") if l]
                info["changes"] = len(lines)
                info["clean"] = len(lines) == 0

            # Remote
            result = subprocess.run(
                ["git", "remote", "get-url", "origin"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=5,
            )
            if result.returncode == 0:
                info["remote"] = result.stdout.strip()

        except Exception:
            pass

        return info

    def _find_key_files(self) -> list[str]:
        """Encuentra archivos clave."""
        key_files = []
        patterns = [
            "README.md",
            "CLAUDE.md",
            "package.json",
            "pyproject.toml",
            "Cargo.toml",
            "docker-compose.yml",
            "Dockerfile",
            "tsconfig.json",
            ".env.example",
        ]

        for pattern in patterns:
            if (self.project_root / pattern).exists():
                key_files.append(pattern)

        return key_files

    def _get_project_stats(self) -> dict:
        """Obtiene estadísticas del proyecto."""
        stats = {"files": 0, "lines": 0}

        extensions = {".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go"}
        excluded_dirs = {
            ".git",
            ".venv",
            "venv",
            "node_modules",
            "dist",
            "build",
            "target",
            "coverage",
            ".pytest_cache",
            ".mypy_cache",
            ".ruff_cache",
            "__pycache__",
        }

        for root, dirs, files in os.walk(self.project_root):
            dirs[:] = [d for d in dirs if d not in excluded_dirs and not d.startswith(".")]

            for filename in files:
                file_path = Path(root) / filename
                if file_path.suffix not in extensions:
                    continue

                stats["files"] += 1
                try:
                    content = file_path.read_text(encoding="utf-8", errors="ignore")
                    stats["lines"] += len(content.splitlines())
                except (OSError, UnicodeDecodeError):
                    continue

        return stats

    # ==================== VERIFICACIÓN ====================

    def verify_code(self, code: str, language: str = "python") -> ActionResult:
        """
        Verifica código rápidamente.

        Args:
            code: Código a verificar
            language: Lenguaje

        Returns:
            Resultado de verificación
        """
        import time

        start = time.time()

        issues = []

        if language == "python":
            # Syntax check
            try:
                import ast

                ast.parse(code)
            except SyntaxError as e:
                issues.append(
                    {"severity": "critical", "message": f"Syntax error: {e.msg}", "line": e.lineno}
                )

            # Basic checks
            lines = code.split("\n")
            for i, line in enumerate(lines, 1):
                if len(line) > 120:
                    issues.append(
                        {
                            "severity": "warning",
                            "message": f"Line too long ({len(line)})",
                            "line": i,
                        }
                    )

                if "print(" in line and "debug" not in line.lower():
                    issues.append(
                        {"severity": "info", "message": "print() found - debug code?", "line": i}
                    )

        # Security checks (all languages)
        import re

        security_patterns = [
            (r'password\s*=\s*["\'][^"\']+["\']', "Hardcoded password"),
            (r'api_key\s*=\s*["\'][^"\']+["\']', "Hardcoded API key"),
            (r"\beval\s*\(", "eval() is dangerous"),
        ]

        for pattern, message in security_patterns:
            if re.search(pattern, code, re.IGNORECASE):
                issues.append({"severity": "error", "message": message})

        duration = int((time.time() - start) * 1000)

        passed = not any(i["severity"] == "critical" for i in issues)

        return ActionResult(
            success=passed,
            data={
                "passed": passed,
                "issues_count": len(issues),
                "issues": issues[:10],  # Primeros 10
            },
            message=f"Verification {'passed' if passed else 'failed'} with {len(issues)} issues",
            duration_ms=duration,
        )

    # ==================== MEMORIA ====================

    def remember(self, key: str, value: Any, category: str = "note") -> ActionResult:
        """
        Guarda algo en memoria.

        Args:
            key: Identificador
            value: Valor a guardar
            category: Categoría (note, decision, preference, error)

        Returns:
            Resultado
        """
        memory_path = self.project_root / ".agent" / "memory" / "quick_memory.json"
        memory_path.parent.mkdir(parents=True, exist_ok=True)

        # Cargar existente
        memory = {}
        if memory_path.exists():
            try:
                memory = json.loads(memory_path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError, ValueError):
                pass

        # Agregar nuevo
        if category not in memory:
            memory[category] = {}

        memory[category][key] = {"value": value, "timestamp": datetime.now().isoformat()}

        # Guardar
        memory_path.write_text(json.dumps(memory, indent=2))

        return ActionResult(
            success=True, data={"key": key, "category": category}, message=f"Remembered: {key}"
        )

    def recall(self, key: str | None = None, category: str | None = None) -> ActionResult:
        """
        Recupera algo de memoria.

        Args:
            key: Identificador específico
            category: Categoría

        Returns:
            Lo que recordé
        """
        memory_path = self.project_root / ".agent" / "memory" / "quick_memory.json"

        if not memory_path.exists():
            return ActionResult(success=False, data=None, message="No memory found")

        try:
            memory = json.loads(memory_path.read_text(encoding="utf-8"))

            if category and key:
                value = memory.get(category, {}).get(key)
                return ActionResult(
                    success=value is not None,
                    data=value,
                    message=f"Recalled: {key}" if value else f"Not found: {key}",
                )
            elif category:
                data = memory.get(category, {})
                return ActionResult(
                    success=True, data=data, message=f"Category {category}: {len(data)} items"
                )
            else:
                # Todo
                return ActionResult(
                    success=True,
                    data=memory,
                    message=f"Total: {sum(len(v) for v in memory.values())} items",
                )

        except Exception as e:
            return ActionResult(success=False, data=None, message=f"Error: {e}")

    # ==================== GIT ====================

    def git_status(self) -> ActionResult:
        """Estado rápido de git."""
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=5,
            )

            if result.returncode != 0:
                return ActionResult(success=False, data=None, message="Not a git repository")

            lines = [l for l in result.stdout.strip().split("\n") if l]

            modified = [l[3:] for l in lines if l.startswith(" M")]
            added = [l[3:] for l in lines if l.startswith("??")]
            staged = [l[3:] for l in lines if l.startswith("M ") or l.startswith("A ")]

            return ActionResult(
                success=True,
                data={
                    "clean": len(lines) == 0,
                    "modified": modified,
                    "untracked": added,
                    "staged": staged,
                    "total_changes": len(lines),
                },
                message="Clean" if not lines else f"{len(lines)} changes",
            )

        except Exception as e:
            return ActionResult(success=False, data=None, message=f"Error: {e}")

    def git_quick_commit(self, message: str) -> ActionResult:
        """Commit rápido."""
        try:
            # Add all
            subprocess.run(["git", "add", "-A"], cwd=self.project_root, timeout=10)

            # Commit
            result = subprocess.run(
                ["git", "commit", "-m", message],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=30,
            )

            if result.returncode == 0:
                return ActionResult(
                    success=True, data={"message": message}, message=f"Committed: {message[:50]}"
                )
            else:
                return ActionResult(
                    success=False, data={"error": result.stderr}, message="Commit failed"
                )

        except Exception as e:
            return ActionResult(success=False, data=None, message=f"Error: {e}")

    # ==================== BÚSQUEDA ====================

    def find_in_code(self, pattern: str, file_type: str = "*") -> ActionResult:
        """
        Búsqueda rápida en código.

        Args:
            pattern: Patrón a buscar
            file_type: Tipo de archivo (py, js, ts, *)

        Returns:
            Resultados
        """
        import time

        start = time.time()

        results = []
        extensions = {
            "py": [".py"],
            "js": [".js", ".jsx"],
            "ts": [".ts", ".tsx"],
            "*": [".py", ".js", ".ts", ".tsx", ".jsx", ".rs", ".go"],
        }

        exts = extensions.get(file_type, extensions["*"])

        for ext in exts:
            for file in self.project_root.rglob(f"*{ext}"):
                if ".git" in str(file) or "node_modules" in str(file):
                    continue

                try:
                    content = file.read_text(encoding="utf-8")
                    for i, line in enumerate(content.split("\n"), 1):
                        if pattern.lower() in line.lower():
                            results.append(
                                {
                                    "file": str(file.relative_to(self.project_root)),
                                    "line": i,
                                    "content": line.strip()[:100],
                                }
                            )

                            if len(results) >= 50:
                                break
                except Exception:
                    pass

                if len(results) >= 50:
                    break

        duration = int((time.time() - start) * 1000)

        return ActionResult(
            success=True,
            data={
                "pattern": pattern,
                "matches": len(results),
                "results": results[:20],  # Primeros 20
            },
            message=f"Found {len(results)} matches for '{pattern}'",
            duration_ms=duration,
        )

    # ==================== CONTEXTO ====================

    def check_context_health(self, current_tokens: int, max_tokens: int = 200000) -> ActionResult:
        """
        Verifica salud del contexto.

        Args:
            current_tokens: Tokens actuales
            max_tokens: Máximo

        Returns:
            Estado y recomendaciones
        """
        usage_percent = (current_tokens / max_tokens) * 100

        if usage_percent < 50:
            status = "healthy"
            recommendations = []
        elif usage_percent < 70:
            status = "moderate"
            recommendations = ["Consider summarizing old context"]
        elif usage_percent < 85:
            status = "warning"
            recommendations = [
                "Archive completed task context",
                "Summarize long outputs",
                "Remove redundant information",
            ]
        elif usage_percent < 95:
            status = "critical"
            recommendations = [
                "URGENT: Compress context now",
                "Keep only current task",
                "Remove all non-essential context",
            ]
        else:
            status = "overflow"
            recommendations = [
                "CRITICAL: Context will overflow",
                "Aggressive compression needed",
                "Consider starting new session",
            ]

        return ActionResult(
            success=usage_percent < 85,
            data={
                "current_tokens": current_tokens,
                "max_tokens": max_tokens,
                "usage_percent": round(usage_percent, 1),
                "status": status,
                "recommendations": recommendations,
            },
            message=f"Context: {usage_percent:.1f}% ({status})",
        )


# ==================== FUNCIONES DE ACCESO RÁPIDO ====================

_actions: QuickActions | None = None


def get_quick_actions(project_root: str = ".") -> QuickActions:
    """Obtiene instancia."""
    global _actions
    if _actions is None:
        _actions = QuickActions(project_root)
    return _actions


# Shortcuts
def explore() -> ActionResult:
    """Explorar proyecto."""
    return get_quick_actions().explore_project()


def verify(code: str, language: str = "python") -> ActionResult:
    """Verificar código."""
    return get_quick_actions().verify_code(code, language)


def remember(key: str, value: Any, category: str = "note") -> ActionResult:
    """Recordar algo."""
    return get_quick_actions().remember(key, value, category)


def recall(key: str | None = None, category: str | None = None) -> ActionResult:
    """Recordar algo."""
    return get_quick_actions().recall(key, category)


def search(pattern: str, file_type: str = "*") -> ActionResult:
    """Buscar en código."""
    return get_quick_actions().find_in_code(pattern, file_type)


def git_status() -> ActionResult:
    """Estado de git."""
    return get_quick_actions().git_status()


if __name__ == "__main__":
    # Test
    actions = QuickActions()

    print("=== Explore Project ===")
    result = actions.explore_project()
    print(json.dumps(result.data, indent=2))

    print("\n=== Git Status ===")
    result = actions.git_status()
    print(result.message)

    print("\n=== Search ===")
    result = actions.find_in_code("def ", "py")
    print(f"Found {result.data['matches']} matches")
