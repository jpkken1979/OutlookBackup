"""
Session Bootstrap - Carga automática de contexto al iniciar sesión

Este módulo es CRÍTICO. Resuelve mi problema de "amnesia" entre sesiones.
Al iniciar, cargo todo lo que necesito para ser útil inmediatamente.
"""

import json
import logging
import subprocess
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ProjectContext:
    """Contexto del proyecto cargado."""

    name: str
    path: str
    language: str
    framework: str | None = None
    git_branch: str | None = None
    git_status: str | None = None
    recent_commits: list[str] = field(default_factory=list)
    key_files: list[str] = field(default_factory=list)
    dependencies: dict = field(default_factory=dict)


@dataclass
class UserPreferences:
    """Preferencias del usuario cargadas."""

    language: str = "spanish"  # Idioma de comunicación
    code_style: dict = field(default_factory=dict)
    commit_style: str = "conventional"
    verbosity: str = "balanced"
    auto_verify: bool = True
    auto_test: bool = True


@dataclass
class SessionMemory:
    """Memoria de sesiones anteriores."""

    decisions: list[dict] = field(default_factory=list)
    errors_fixed: list[dict] = field(default_factory=list)
    user_corrections: list[dict] = field(default_factory=list)
    important_notes: list[str] = field(default_factory=list)
    learned_patterns: list[dict] = field(default_factory=list)


@dataclass
class BootstrapResult:
    """Resultado del bootstrap de sesión."""

    project: ProjectContext
    preferences: UserPreferences
    memory: SessionMemory
    warnings: list[str] = field(default_factory=list)
    load_time_ms: int = 0
    ready: bool = True


class SessionBootstrap:
    """
    Bootstrap automático de sesión.

    Al iniciar cualquier sesión, este módulo:
    1. Detecta el proyecto actual
    2. Carga memoria persistente
    3. Carga preferencias del usuario
    4. Prepara contexto crítico
    5. Me hace útil INMEDIATAMENTE
    """

    MEMORY_PATH = Path(".agent/memory")
    PREFERENCES_PATH = Path(".agent/memory/user_preferences.json")
    SESSION_MEMORY_PATH = Path(".agent/memory/session_memory.json")
    PROJECT_CACHE_PATH = Path(".agent/memory/project_cache.json")

    def __init__(self, project_root: str = "."):
        self.project_root = Path(project_root).resolve()
        self.memory_path = self.project_root / self.MEMORY_PATH
        self.memory_path.mkdir(parents=True, exist_ok=True)

    def _read_text_utf8(self, path: Path) -> str:
        """Lee texto de forma robusta usando UTF-8."""
        try:
            return path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            # Evita romper bootstrap por locales del sistema (cp932/cp1252, etc.)
            return path.read_text(encoding="utf-8", errors="replace")

    def _write_text_utf8(self, path: Path, content: str) -> None:
        """Escribe texto en UTF-8 de forma consistente."""
        path.write_text(content, encoding="utf-8")

    def bootstrap(self) -> BootstrapResult:
        """
        Ejecuta bootstrap completo de sesión.

        Returns:
            BootstrapResult con todo el contexto cargado
        """
        import time

        start = time.time()

        warnings = []

        # 1. Cargar contexto del proyecto
        project = self._load_project_context()

        # 2. Cargar preferencias del usuario
        preferences = self._load_preferences()

        # 3. Cargar memoria de sesiones anteriores
        memory = self._load_session_memory()

        # 4. Verificar estado
        if not project.git_branch:
            warnings.append("No git repository detected")

        if not memory.decisions:
            warnings.append("No previous session memory found")

        load_time = int((time.time() - start) * 1000)

        return BootstrapResult(
            project=project,
            preferences=preferences,
            memory=memory,
            warnings=warnings,
            load_time_ms=load_time,
            ready=True,
        )

    def _load_project_context(self) -> ProjectContext:
        """Carga contexto del proyecto."""
        name = self.project_root.name

        # Detectar lenguaje y framework
        language, framework = self._detect_stack()

        # Git info
        git_branch = self._get_git_branch()
        git_status = self._get_git_status_summary()
        recent_commits = self._get_recent_commits(5)

        # Archivos clave
        key_files = self._find_key_files()

        # Dependencias
        dependencies = self._load_dependencies()

        return ProjectContext(
            name=name,
            path=str(self.project_root),
            language=language,
            framework=framework,
            git_branch=git_branch,
            git_status=git_status,
            recent_commits=recent_commits,
            key_files=key_files,
            dependencies=dependencies,
        )

    def _detect_stack(self) -> tuple[str, str | None]:
        """Detecta lenguaje y framework del proyecto."""
        # Python
        if (self.project_root / "pyproject.toml").exists():
            return "python", self._detect_python_framework()
        if (self.project_root / "requirements.txt").exists():
            return "python", self._detect_python_framework()
        if (self.project_root / "setup.py").exists():
            return "python", self._detect_python_framework()

        # JavaScript/TypeScript
        if (self.project_root / "package.json").exists():
            return self._detect_js_stack()

        # Rust
        if (self.project_root / "Cargo.toml").exists():
            return "rust", self._detect_rust_framework()

        # Go
        if (self.project_root / "go.mod").exists():
            return "go", None

        return "unknown", None

    def _detect_python_framework(self) -> str | None:
        """Detecta framework Python."""
        # Buscar en requirements o pyproject
        indicators = {
            "fastapi": "FastAPI",
            "django": "Django",
            "flask": "Flask",
            "pytest": "pytest",
            "anthropic": "Anthropic SDK",
        }

        req_file = self.project_root / "requirements.txt"
        if req_file.exists():
            content = self._read_text_utf8(req_file).lower()
            for key, framework in indicators.items():
                if key in content:
                    return framework

        pyproject = self.project_root / "pyproject.toml"
        if pyproject.exists():
            content = self._read_text_utf8(pyproject).lower()
            for key, framework in indicators.items():
                if key in content:
                    return framework

        return None

    def _detect_js_stack(self) -> tuple[str, str | None]:
        """Detecta stack JavaScript/TypeScript."""
        package_json = self.project_root / "package.json"
        if not package_json.exists():
            return "javascript", None

        try:
            pkg = json.loads(self._read_text_utf8(package_json))
            deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}

            # TypeScript?
            lang = "typescript" if "typescript" in deps else "javascript"

            # Framework
            if "next" in deps:
                return lang, "Next.js"
            if "react" in deps:
                return lang, "React"
            if "vue" in deps:
                return lang, "Vue"
            if "svelte" in deps:
                return lang, "Svelte"
            if "express" in deps:
                return lang, "Express"
            if "@tauri-apps/api" in deps:
                return lang, "Tauri"

            return lang, None
        except Exception:
            return "javascript", None

    def _detect_rust_framework(self) -> str | None:
        """Detecta framework Rust."""
        cargo = self.project_root / "Cargo.toml"
        if cargo.exists():
            content = self._read_text_utf8(cargo).lower()
            if "tauri" in content:
                return "Tauri"
            if "actix" in content:
                return "Actix"
            if "axum" in content:
                return "Axum"
            if "rocket" in content:
                return "Rocket"
        return None

    def _get_git_branch(self) -> str | None:
        """Obtiene branch actual de git."""
        try:
            result = subprocess.run(
                ["git", "branch", "--show-current"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=5,
            )
            if result.returncode == 0:
                return result.stdout.strip()
        except Exception as e:
            logger.debug("Bootstrap data load skipped: %s", e)
        return None

    def _get_git_status_summary(self) -> str | None:
        """Obtiene resumen del estado de git."""
        try:
            result = subprocess.run(
                ["git", "status", "--short"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=5,
            )
            if result.returncode == 0:
                lines = result.stdout.strip().split("\n")
                if not lines or lines == [""]:
                    return "clean"
                modified = sum(1 for l in lines if l.startswith(" M") or l.startswith("M "))
                added = sum(1 for l in lines if l.startswith("A ") or l.startswith("??"))
                deleted = sum(1 for l in lines if l.startswith(" D") or l.startswith("D "))
                return f"{modified} modified, {added} untracked, {deleted} deleted"
        except Exception as e:
            logger.debug("Bootstrap data load skipped: %s", e)
        return None

    def _get_recent_commits(self, count: int = 5) -> list[str]:
        """Obtiene commits recientes."""
        try:
            result = subprocess.run(
                ["git", "log", f"-{count}", "--oneline"],
                capture_output=True,
                text=True,
                cwd=self.project_root,
                timeout=5,
            )
            if result.returncode == 0:
                return [l.strip() for l in result.stdout.strip().split("\n") if l.strip()]
        except Exception as e:
            logger.debug("Bootstrap data load skipped: %s", e)
        return []

    def _find_key_files(self) -> list[str]:
        """Encuentra archivos clave del proyecto."""
        key_patterns = [
            "README.md",
            "CLAUDE.md",
            "package.json",
            "pyproject.toml",
            "Cargo.toml",
            "docker-compose.yml",
            "Dockerfile",
            ".env.example",
            "tsconfig.json",
            "src/main.*",
            "src/index.*",
            "src/app.*",
        ]

        found: list[str] = []
        for pattern in key_patterns:
            if "*" in pattern:
                matches = list(self.project_root.glob(pattern))
                found.extend(str(m.relative_to(self.project_root)) for m in matches[:3])
            else:
                path = self.project_root / pattern
                if path.exists():
                    found.append(pattern)

        return found[:15]  # Limitar a 15 archivos

    def _load_dependencies(self) -> dict:
        """Carga dependencias principales."""
        deps = {}

        # Python
        req_file = self.project_root / "requirements.txt"
        if req_file.exists():
            lines = self._read_text_utf8(req_file).split("\n")
            for line in lines[:20]:  # Primeras 20
                if line.strip() and not line.startswith("#"):
                    name = line.split("==")[0].split(">=")[0].split("[")[0].strip()
                    if name:
                        deps[name] = "python"

        # JavaScript
        package_json = self.project_root / "package.json"
        if package_json.exists():
            try:
                pkg = json.loads(self._read_text_utf8(package_json))
                for dep in list(pkg.get("dependencies", {}).keys())[:15]:
                    deps[dep] = "npm"
            except (OSError, json.JSONDecodeError, ValueError) as e:
                logger.debug("Bootstrap data load skipped: %s", e)

        return deps

    def _load_preferences(self) -> UserPreferences:
        """Carga preferencias del usuario."""
        pref_file = self.project_root / self.PREFERENCES_PATH

        if pref_file.exists():
            try:
                data = json.loads(self._read_text_utf8(pref_file))
                return UserPreferences(
                    language=data.get("language", "spanish"),
                    code_style=data.get("code_style", {}),
                    commit_style=data.get("commit_style", "conventional"),
                    verbosity=data.get("verbosity", "balanced"),
                    auto_verify=data.get("auto_verify", True),
                    auto_test=data.get("auto_test", True),
                )
            except (OSError, json.JSONDecodeError, ValueError) as e:
                logger.debug("Bootstrap data load skipped: %s", e)

        return UserPreferences()

    def _load_session_memory(self) -> SessionMemory:
        """Carga memoria de sesiones anteriores."""
        memory_file = self.project_root / self.SESSION_MEMORY_PATH

        if memory_file.exists():
            try:
                data = json.loads(self._read_text_utf8(memory_file))
                return SessionMemory(
                    decisions=data.get("decisions", [])[-50:],  # Últimas 50
                    errors_fixed=data.get("errors_fixed", [])[-30:],
                    user_corrections=data.get("user_corrections", [])[-30:],
                    important_notes=data.get("important_notes", [])[-20:],
                    learned_patterns=data.get("learned_patterns", [])[-20:],
                )
            except (OSError, json.JSONDecodeError, ValueError) as e:
                logger.debug("Bootstrap data load skipped: %s", e)

        return SessionMemory()

    def save_preferences(self, preferences: UserPreferences):
        """Guarda preferencias del usuario."""
        pref_file = self.project_root / self.PREFERENCES_PATH
        pref_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "language": preferences.language,
            "code_style": preferences.code_style,
            "commit_style": preferences.commit_style,
            "verbosity": preferences.verbosity,
            "auto_verify": preferences.auto_verify,
            "auto_test": preferences.auto_test,
            "updated_at": datetime.now().isoformat(),
        }

        self._write_text_utf8(pref_file, json.dumps(data, indent=2))

    def save_to_memory(
        self,
        decision: dict | None = None,
        error_fixed: dict | None = None,
        user_correction: dict | None = None,
        important_note: str | None = None,
        learned_pattern: dict | None = None,
    ):
        """Guarda algo en la memoria de sesión."""
        memory = self._load_session_memory()

        if decision:
            decision["timestamp"] = datetime.now().isoformat()
            memory.decisions.append(decision)

        if error_fixed:
            error_fixed["timestamp"] = datetime.now().isoformat()
            memory.errors_fixed.append(error_fixed)

        if user_correction:
            user_correction["timestamp"] = datetime.now().isoformat()
            memory.user_corrections.append(user_correction)

        if important_note:
            memory.important_notes.append(f"[{datetime.now().isoformat()}] {important_note}")

        if learned_pattern:
            learned_pattern["timestamp"] = datetime.now().isoformat()
            memory.learned_patterns.append(learned_pattern)

        # Guardar
        memory_file = self.project_root / self.SESSION_MEMORY_PATH
        memory_file.parent.mkdir(parents=True, exist_ok=True)

        data = {
            "decisions": memory.decisions[-50:],
            "errors_fixed": memory.errors_fixed[-30:],
            "user_corrections": memory.user_corrections[-30:],
            "important_notes": memory.important_notes[-20:],
            "learned_patterns": memory.learned_patterns[-20:],
            "last_updated": datetime.now().isoformat(),
        }

        self._write_text_utf8(memory_file, json.dumps(data, indent=2))

    def get_quick_context(self) -> str:
        """Genera contexto rapido del proyecto para inyeccion.

        Returns:
            String con contexto del proyecto formateado
        """
        result = self.bootstrap()

        lines = [
            f"**Proyecto:** {result.project.name}",
            f"**Stack:** {result.project.language}"
            + (f" ({result.project.framework})" if result.project.framework else ""),
            f"**Branch:** {result.project.git_branch or 'N/A'}",
        ]

        if result.memory.decisions:
            lines.append("\n**Decisiones recientes:**")
            for d in result.memory.decisions[-5:]:
                desc = d.get("description", d.get("what", str(d)))
                lines.append(f"- {desc}")

        if result.memory.learned_patterns:
            lines.append("\n**Patrones aprendidos:**")
            for p in result.memory.learned_patterns[-3:]:
                desc = p.get("description", p.get("pattern", str(p)))
                lines.append(f"- {desc}")

        return "\n".join(lines)

    def get_historical_context(self, max_tokens: int = 3000) -> str:
        """Genera contexto historico desde ObservationPipeline y SessionSummarizer.

        Combina:
        - Observaciones recientes de sesiones anteriores
        - Resumenes AI de sesiones
        - Decisiones y patrones aprendidos

        Args:
            max_tokens: Maximo aproximado de tokens (4 chars = 1 token)

        Returns:
            String con contexto historico para inyeccion
        """
        sections: list[str] = []
        max_chars = max_tokens * 4
        current_chars = 0

        # 1. Observaciones del pipeline
        try:
            from .observation_pipeline import get_observation_pipeline

            pipeline = get_observation_pipeline(str(self.project_root))
            obs_context = pipeline.get_context_for_injection(
                max_observations=10, max_tokens=max_tokens // 2
            )
            if obs_context.strip():
                sections.append(obs_context)
                current_chars += len(obs_context)
        except Exception as e:
            logger.debug("Bootstrap data load skipped: %s", e)

        # 2. Resumenes de sesiones
        remaining_tokens = (max_chars - current_chars) // 4
        if remaining_tokens > 200:
            try:
                from .session_summarizer import get_session_summarizer

                summarizer = get_session_summarizer(str(self.project_root))
                summaries = summarizer.get_recent_summaries_context(
                    max_sessions=3, max_tokens=remaining_tokens
                )
                if summaries.strip():
                    sections.append(summaries)
                    current_chars += len(summaries)
            except Exception as e:
                logger.debug("Bootstrap data load skipped: %s", e)

        # 3. Errores recurrentes desde ProjectMemory
        remaining_chars = max_chars - current_chars
        if remaining_chars > 200:
            try:
                from .project_memory import get_project_memory

                pm = get_project_memory(str(self.project_root))
                errors_context = pm.get_relevant_errors()  # type: ignore[attr-defined]  # dynamic ProjectMemory API
                if errors_context and len(errors_context) < remaining_chars:
                    sections.append(f"## Errores Conocidos\n{errors_context}")
            except Exception as e:
                logger.debug("Bootstrap data load skipped: %s", e)

        if not sections:
            return ""

        return "\n\n".join(sections)

    def get_summary(self) -> str:
        """Obtiene resumen legible del bootstrap."""
        result = self.bootstrap()

        lines = [
            "=" * 50,
            "SESSION BOOTSTRAP COMPLETE",
            "=" * 50,
            "",
            f"Project: {result.project.name}",
            f"Path: {result.project.path}",
            f"Stack: {result.project.language}"
            + (f" ({result.project.framework})" if result.project.framework else ""),
            f"Branch: {result.project.git_branch or 'N/A'}",
            f"Git Status: {result.project.git_status or 'N/A'}",
            "",
            "Recent Commits:",
        ]

        for commit in result.project.recent_commits[:3]:
            lines.append(f"  - {commit}")

        lines.extend(
            [
                "",
                f"User Language: {result.preferences.language}",
                f"Auto-verify: {result.preferences.auto_verify}",
                f"Commit Style: {result.preferences.commit_style}",
                "",
                f"Memory: {len(result.memory.decisions)} decisions, {len(result.memory.learned_patterns)} patterns",
                "",
            ]
        )

        if result.warnings:
            lines.append("Warnings:")
            for w in result.warnings:
                lines.append(f"  - {w}")

        lines.extend(
            [
                "",
                f"Load time: {result.load_time_ms}ms",
                "=" * 50,
            ]
        )

        return "\n".join(lines)


# Singleton y función de acceso rápido
_bootstrap: SessionBootstrap | None = None


def get_session_bootstrap(project_root: str = ".") -> SessionBootstrap:
    """Obtiene instancia del bootstrap."""
    global _bootstrap
    if _bootstrap is None:
        _bootstrap = SessionBootstrap(project_root)
    return _bootstrap


def quick_bootstrap() -> BootstrapResult:
    """Bootstrap rápido de sesión."""
    return get_session_bootstrap().bootstrap()


if __name__ == "__main__":
    # Test
    bootstrap = SessionBootstrap()
    print(bootstrap.get_summary())
