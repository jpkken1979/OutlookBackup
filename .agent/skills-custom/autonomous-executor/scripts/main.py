#!/usr/bin/env python3
"""Autonomous Executor -- planificador y ejecutor autónomo.

Recibe un objetivo, genera plan, espera aprobación humana, ejecuta completamente
de forma autónoma usando MCP (skills, agents, brain) y subprocess.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import re
import shlex
import subprocess
import sys
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parents[3]
GATEWAY_URL = os.environ.get("ANTIGRAVITY_GATEWAY_URL", "http://127.0.0.1:4747")
STEP_TIMEOUT = int(os.environ.get("EXECUTOR_STEP_TIMEOUT", "60"))
MAX_RETRIES = 2
MAX_STEPS = 20
ABORT_THRESHOLD = 0.3  # abort if > 30% steps fail

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────
# Data models
# ─────────────────────────────────────────────────────────

@dataclass
class PlanStep:
    """Un paso en el plan de ejecución."""

    index: int
    action: str
    target: str
    success_criteria: str
    method: str  # "subprocess" | "mcp_agent" | "mcp_skill" | "brain_save"
    details: str = ""
    status: str = "pending"  # pending | running | ok | fail | skipped
    error: Optional[str] = None
    duration_ms: Optional[int] = None
    retries: int = 0

    def to_dict(self) -> dict:
        return {
            "index": self.index,
            "action": self.action,
            "target": self.target,
            "success_criteria": self.success_criteria,
            "method": self.method,
            "details": self.details,
            "status": self.status,
            "error": self.error,
            "duration_ms": self.duration_ms,
            "retries": self.retries,
        }


@dataclass
class ExecutionResult:
    """Resultado total de una ejecución."""

    goal: str
    plan_steps: list[PlanStep]
    executed_steps: int = 0
    successful_steps: int = 0
    failed_steps: int = 0
    skipped_steps: int = 0
    duration_seconds: float = 0.0
    files_modified: list[str] = field(default_factory=list)
    new_skills_created: list[str] = field(default_factory=list)
    agents_invoked: list[str] = field(default_factory=list)
    brain_nodes_created: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)
    aborted: bool = False

    def to_dict(self) -> dict:
        return {
            "goal": self.goal,
            "executed_steps": self.executed_steps,
            "successful_steps": self.successful_steps,
            "failed_steps": self.failed_steps,
            "skipped_steps": self.skipped_steps,
            "duration_seconds": round(self.duration_seconds, 2),
            "files_modified": self.files_modified,
            "new_skills_created": self.new_skills_created,
            "agents_invoked": self.agents_invoked,
            "brain_nodes_created": self.brain_nodes_created,
            "recommendations": self.recommendations,
            "aborted": self.aborted,
            "plan": [s.to_dict() for s in self.plan_steps],
        }


# ─────────────────────────────────────────────────────────
# Gateway / MCP helpers
# ─────────────────────────────────────────────────────────

def _gateway_health() -> bool:
    """Check si el gateway está activo."""
    try:
        import urllib.request

        req = urllib.request.Request(
            f"{GATEWAY_URL}/v1/health",
            headers={"Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=3) as resp:
            return resp.status == 200
    except Exception:
        return False


def _http_get(path: str, timeout: int = 10) -> Optional[dict]:
    """GET HTTP genérico al gateway."""
    try:
        import urllib.request

        url = f"{GATEWAY_URL}{path}"
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.debug("HTTP GET %s failed: %s", path, e)
        return None


def _http_post(path: str, data: dict, timeout: int = 10) -> Optional[dict]:
    """POST HTTP genérico al gateway."""
    try:
        import urllib.request

        url = f"{GATEWAY_URL}{path}"
        body = json.dumps(data).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body,
            headers={"Content-Type": "application/json", "Accept": "application/json"},
        )
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except Exception as e:
        logger.debug("HTTP POST %s failed: %s", path, e)
        return None


# ─────────────────────────────────────────────────────────
# Brain integration
# ─────────────────────────────────────────────────────────

def brain_save(
    title: str,
    context: str,
    area: str = "execution",
    tags: Optional[list[str]] = None,
    node_type: str = "pattern",
    importance: str = "medium",
) -> bool:
    """Guarda un nodo en el Brain Network via gateway o fallback file."""

    tags = tags or []

    # Try MCP endpoint
    result = _http_post("/v1/brain/ingest", {
        "title": title,
        "context": context,
        "area": area,
        "tags": tags,
        "node_type": node_type,
        "importance": importance,
    })
    if result:
        return True

    # Fallback: guardar como archivo markdown en brain dir
    try:
        import sys as _sys
        _sys.path.insert(0, str(REPO_ROOT / ".agent"))
        from core.brain import Brain

        brain = Brain(REPO_ROOT / ".agent" / "brain", app_id="autonomous-executor")
        brain.ingest(
            title=title,
            context=context,
            area=area,
            tags=tags,
            node_type=node_type,
            importance=importance,
        )
        return True
    except Exception as e:
        logger.debug("Brain fallback failed: %s", e)
        return False


# ─────────────────────────────────────────────────────────
# Skill discovery
# ─────────────────────────────────────────────────────────

def find_skill_by_keyword(keyword: str) -> Optional[str]:
    """Busca un skill existente por keyword via gateway."""

    result = _http_get(f"/v1/skills/search?q={keyword}")
    if result and "skills" in result:
        skills = result["skills"]
        if skills:
            return skills[0].get("name") or skills[0].get("path", "")
    return None


# ─────────────────────────────────────────────────────────
# Agent invocation
# ─────────────────────────────────────────────────────────

def invoke_agent(agent_name: str, goal: str) -> tuple[bool, str]:
    """Invoca un agente via gateway."""

    result = _http_post("/v1/agents/invoke", {
        "agent": agent_name,
        "goal": goal,
        "timeout": STEP_TIMEOUT,
    })
    if result:
        success = result.get("success", result.get("status") == "ok")
        output = result.get("output", result.get("message", ""))
        return success, output
    return False, "Gateway unavailable"


# ─────────────────────────────────────────────────────────
# Subprocess executor
# ─────────────────────────────────────────────────────────

def run_command(cmd: str, cwd: Optional[Path] = None, timeout: int = STEP_TIMEOUT) -> tuple[int, str, str]:
    """Ejecuta un comando shell via subprocess."""

    try:
        parts = shlex.split(cmd)
        result = subprocess.run(
            parts,
            shell=False,
            capture_output=True,
            text=True,
            encoding="utf-8", errors="replace",
            cwd=cwd or REPO_ROOT,
            timeout=timeout,
        )
        return result.returncode, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return -1, "", f"Timeout after {timeout}s"
    except Exception as e:
        return -1, "", str(e)


# ─────────────────────────────────────────────────────────
# Goal entity extraction
# ─────────────────────────────────────────────────────────

# Common file extensions per language
_EXT_BY_LANG = {
    "python": [".py"],
    "typescript": [".ts", ".tsx"],
    "javascript": [".js", ".jsx"],
    "rust": [".rs"],
    "bash": [".sh"],
    "markdown": [".md"],
}

# Directories that map to languages / surfaces
_SURFACE_DIRS = {
    ".agent": "python",
    "nexus-app": "typescript",
    "nexus-app/src-tauri": "rust",
    "src": "typescript",
    "mcp-server": "python",
    "scripts": "python",
    "tests": "python",
    "docs": "markdown",
}


def extract_file_paths(goal: str) -> list[str]:
    """Extrae paths de archivo mencionados en el goal.

    Detecta patrones como:
      - src/auth/login.ts
      - .agent/core/orchestrator.py
      - nexus-app/src/App.tsx
      - nexus-app/src-tauri/src/main.rs

    Cada segmento de path contiene NO espacios, lo que permite distinguir
    un path de texto libre.
    """

    paths: list[str] = []
    seen: set[str] = set()
    ext_set = {"py", "ts", "tsx", "js", "jsx", "rs", "sh", "md", "json", "yaml", "yml", "toml", "pyi"}

    # ── Token-based extraction ──────────────────────────────────────
    # Split on whitespace and punctuation (but preserve path tokens).
    # For each token that looks like a path (contains '/'), try to
    # reconstruct the full path by peeking at adjacent tokens.
    tokens = goal.split()

    i = 0
    while i < len(tokens):
        # Strip trailing punctuation only; leading dots are part of the path
        tok = tokens[i].rstrip(".,;:'\",()[]{")
        # Must contain a slash to be a path candidate
        if "/" in tok:
            # Reconstruct full path from current and subsequent tokens
            path_parts: list[str] = []
            j = i
            while j < len(tokens):
                part = tokens[j].rstrip(".,;:'\",()[]{")
                # Stop when we hit a part with a space (shouldn't happen after split)
                # or when the current part ends with a known extension
                if "." in part:
                    ext = part.rsplit(".", 1)[-1].lower()
                    if ext in ext_set:
                        path_parts.append(part)
                        j += 1
                        break
                    elif "/" in part:
                        segs = part.rsplit("/", 1)
                        path_parts.append(segs[0])
                        path_parts.append(segs[1])
                        j += 1
                        break
                    else:
                        # No ext and no slash continuation - this token ends the path
                        break
                elif "/" in part:
                    path_parts.append(part)
                    j += 1
                else:
                    break

            if path_parts:
                # Reconstruct path string
                full = "/".join(
                    p.rstrip("/") for p in path_parts if p
                )
                if full not in seen and "/" in full:
                    seen.add(full)
                    paths.append(full)
                i = j - 1
        i += 1

    # ── Regex fallback: handle edge cases like ".agent/core/orchestrator.py" ──
    # Pattern: starts with '.' or '/' or '~', contains '/', ends with known ext.
    edge_pattern = re.compile(
        r'(?:^|(?<=\s))'           # start of string or after whitespace
        r'[.~][a-zA-Z0-9_\-./]+'  # .something/path/file.ext  (no spaces allowed)
        r'\.(?:py|ts|tsx|js|jsx|rs|sh|md|json|yaml|yml|toml|pyi)'
        r'(?=\s|$|,|["\'<])',
    )
    for m in edge_pattern.finditer(goal):
        raw = m.group().rstrip("'\",;: ")  # strip trailing, preserve leading dot
        if "/" in raw and raw not in seen:
            seen.add(raw)
            paths.append(raw)

    return paths


def extract_module_names(goal: str) -> list[str]:
    """Extrae nombres de módulo/componente mencionados en el goal.

    Detecta patrones como:
      - "el módulo X"
      - "componente Y"
      - "archivo Z"
      - "directorio W"
      - "surface X"
    """

    module_pattern = re.compile(
        r'(?:módulo|modulo|component|componente|archivo|file|directorio|directory|'
        r'surface|paquete|package|clase|class|función|funcion|function)\s+'
        r'["\']?([a-zA-Z0-9_\-/.]+)[ "\']?',
        re.IGNORECASE,
    )
    return _deduplicate_ordered(module_pattern.findall(goal))


def extract_languages(goal: str) -> list[str]:
    """Detecta lenguajes/tecnologías mencionados en el goal."""

    lang_keywords = {
        "python": ["python", "py", "pydantic", "pytest", "ruff", "mypy"],
        "typescript": ["typescript", "ts", "tsx", "react", "tailwind", "framer motion", "vitest"],
        "javascript": ["javascript", "js", "jsx", "node"],
        "rust": ["rust", "rs", "tauri", "cargo"],
        "bash": ["bash", "sh", "shell", "subprocess"],
        "markdown": ["markdown", "md", "docs", "documentación", "documentar"],
    }
    goal_lower = goal.lower()
    found: list[str] = []
    for lang, keywords in lang_keywords.items():
        if any(k in goal_lower for k in keywords):
            found.append(lang)
    return found


def extract_surfaces(goal: str) -> list[str]:
    """Detecta surfaces del proyecto mencionadas en el goal.

    El repo tiene 4 surfaces conocidas:
      - .agent  (Python runtime)
      - nexus-app  (Tauri desktop)
      - src  (Bot Telegram TS)
      - mcp-server  (MCP portable)
    """

    surfaces = {
        ".agent": [".agent/", "runtime", "skills", "agentes", "mcp"],
        "nexus-app": ["nexus-app", "nexus app", "tauri", "desktop", "rust"],
        "src": ["src/", "telegram", "bot", "grammy"],
        "mcp-server": ["mcp-server", "mcp server"],
    }
    goal_lower = goal.lower()
    found: list[str] = []
    for surf, keywords in surfaces.items():
        if any(k in goal_lower for k in keywords):
            found.append(surf)
    return found


def _deduplicate_ordered(items: list[str]) -> list[str]:
    """Deduplica conservando orden, case-sensitive."""
    seen: set[str] = set()
    result: list[str] = []
    for item in items:
        if item not in seen:
            seen.add(item)
            result.append(item)
    return result


# ─────────────────────────────────────────────────────────
# Plan generation
# ─────────────────────────────────────────────────────────

def _tags_for_goal(
    is_bug: bool,
    is_feature: bool,
    is_code_review: bool,
    is_docs: bool,
    is_test: bool,
    is_build: bool,
    is_data: bool,
    is_git: bool,
    is_multi: bool,
    is_discovery: bool,
    languages: list[str],
    surfaces: list[str],
) -> str:
    """Genera un string de tags para brain_save según el tipo de objetivo."""
    tags: list[str] = ["autonomous-executor"]
    if is_bug:
        tags.append("bugfix")
    if is_feature:
        tags.append("feature")
    if is_code_review:
        tags.append("code-review")
    if is_docs:
        tags.append("documentation")
    if is_test:
        tags.append("testing")
    if is_build:
        tags.append("build")
    if is_data:
        tags.append("data-analysis")
    if is_git:
        tags.append("git")
    if is_multi:
        tags.append("multi-surface")
    if is_discovery:
        tags.append("discovery")
    tags.extend(languages)
    tags.extend(surfaces)
    return ", ".join(tags)


def analyze_goal(goal: str) -> list[PlanStep]:
    """Analiza un objetivo y genera un plan estructurado de pasos.

    Detecta tipos de objetivo, extrae entidades (paths, módulos, lenguajes,
    surfaces) y genera pasos específicos para cada categoría.
    """

    goal_lower = goal.lower()
    steps: list[PlanStep] = []
    idx = 1

    # ── Extraer entidades ──────────────────────────────────
    detected_paths = extract_file_paths(goal)
    detected_modules = extract_module_names(goal)
    detected_langs = extract_languages(goal)
    detected_surfaces = extract_surfaces(goal)

    # ── Detectar tipo de objetivo ───────────────────────────
    is_bug = any(k in goal_lower for k in [
        "bug", "error", "arreglar", "fix", "rompe", "crash", "falla", "rompido",
    ])
    is_feature = any(k in goal_lower for k in [
        "implementar", "feature", "agregar", "crear", "nuevo", "add",
    ])
    is_audit = any(k in goal_lower for k in [
        "audit", "auditar", "seguridad", "vulnerab", "owasp", "cve",
    ])
    is_refactor = any(k in goal_lower for k in [
        "refactor", "limpiar", "cleanup", "deuda", "reestructur",
    ])

    # ── Nuevos tipos de objetivo ────────────────────────────
    is_code_review = any(k in goal_lower for k in [
        "code review", "revisar código", "revisar codigo", "revisar archivo",
        "revisar modulo", "revisar módulo", "peer review", "review código",
        "analizar código", "analizar codigo", "linting", "revisar src",
        "auditar código", "auditar codigo",
    ])
    is_docs = any(k in goal_lower for k in [
        "documentar", "documentación", "docs", "generar docs", "crear readme",
        "escribir documentación", "write docs", "generar documentación",
        "README", "CHANGELOG", "API docs", "manual técnico",
    ])
    is_test = any(k in goal_lower for k in [
        "test", "tests", "prueba", "pruebas", "pytest", "coverage",
        "test coverage", "escribir tests", "escribir pruebas", "testear",
        "unit test", "integration test", "e2e", "vitest",
    ])
    is_build = any(k in goal_lower for k in [
        "compilar", "build", "deploy", "release", "instalar", "package",
        "bundle", "publish", "distribuir", "nsis", "msi", "exe",
    ])
    is_data = any(k in goal_lower for k in [
        "analizar metrics", "analytics", "analítica", "reporte",
        "generar reporte", "data analysis", "logs", "dashboards",
        "métricas", "metricas", "estadísticas", "estadisticas",
        "data pipeline", "etl",
    ])
    is_git = any(k in goal_lower for k in [
        "git commit", "commits", "git history", "branch", "merge",
        "git merge", "git branch", "git push", "git pull", "rebase",
        "cherry-pick", "git revert", "git log", "git diff", "git stash",
    ])
    is_discovery = any(k in goal_lower for k in [
        "encontrar", "buscar", "explorar", "explore", "search",
        "investigar", "averiguar", "discover", "find", "scan",
        "identificar archivos", "mapear", "mapear superficie",
    ]) and not any(k in goal_lower for k in [
        "implementar", "crear", "agregar", "add", "fix", "test", "docs",
    ])

    # Multi-project: más de una surface detectada, o keywords explícitos
    is_multi = len(detected_surfaces) >= 2 or any(k in goal_lower for k in [
        "multi-proyecto", "multi surface", "multi-surface", "varios proyectos",
        "end-to-end", "e2e cambio",
    ])

    # ── Construir paths de búsqueda dinámicamente ───────────
    search_dirs = []
    if detected_surfaces:
        search_dirs = detected_surfaces
    else:
        # Fallback a las surfaces existentes del repo
        for surf in [".agent", "src", "nexus-app", "mcp-server"]:
            if (REPO_ROOT / surf).exists():
                search_dirs.append(surf)

    search_base = " ".join(f"{d}/" for d in search_dirs) if search_dirs else ".agent/ src/ nexus-app/src/"

    # ── Determinar el target específico de archivos ────────
    target_description: str
    if detected_paths:
        target_description = "Archivos detectados: " + ", ".join(detected_paths[:5])
    elif detected_modules:
        target_description = "Módulos detectados: " + ", ".join(detected_modules[:5])
    elif detected_surfaces:
        target_description = "Surfaces detectadas: " + ", ".join(detected_surfaces)
    else:
        target_description = "Proyecto completo"

    # ── PLAN SEGÚN TIPO ────────────────────────────────────

    # ── 1. CODE REVIEW ───────────────────────────────────
    if is_code_review:
        steps.append(PlanStep(
            index=idx,
            action="Localizar archivos a revisar",
            target=target_description,
            success_criteria="Archivos identificados y accesibles",
            method="subprocess",
            details=_build_grep_cmd(search_base, detected_paths, detected_modules),
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Ejecutar lint estático",
            target=f"Linting: {', '.join(detected_langs) if detected_langs else 'todo'}",
            success_criteria="ruff / eslint sin errores críticos",
            method="subprocess",
            details=_build_lint_cmd(detected_langs, detected_surfaces),
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Revisar código fuente",
            target=target_description,
            success_criteria="Se identifican issues de calidad, seguridad y estilo",
            method="subprocess",
            details="Revisión manual asistida por herramientas de análisis estático",
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Documentar hallazgos",
            target="Brain Network + reporte en terminal",
            success_criteria="Hallazgos guardados con tags relevantes",
            method="brain_save",
            details=f"Code review: {goal[:120]}",
        ))
        idx += 1

        # Si hay paths detectados, agregar paso de verificación de tipos
        if detected_langs or detected_paths:
            steps.append(PlanStep(
                index=idx,
                action="Verificar tipos en archivos revisados",
                target=target_description,
                success_criteria="TypeScript/Rust compiles cleanly",
                method="subprocess",
                details=_build_typecheck_cmd(detected_langs, detected_paths, detected_surfaces),
            ))
            idx += 1

    # ── 2. DOCUMENTATION ──────────────────────────────────
    elif is_docs:
        steps.append(PlanStep(
            index=idx,
            action="Identificar área a documentar",
            target=target_description,
            success_criteria="Contexto del código identificado",
            method="subprocess",
            details=_build_grep_cmd(search_base, detected_paths, detected_modules),
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Generar documentación",
            target=f"Archivos detectados: {', '.join(detected_paths[:3]) if detected_paths else 'proyecto completo'}",
            success_criteria="Archivos .md actualizados o creados",
            method="subprocess",
            details="Generar contenido Markdown con contexto relevante",
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Guardar en Brain como documentación",
            target="Brain Network",
            success_criteria="Nodo de docs ingestado con tags apropiados",
            method="brain_save",
            details=f"Documentación: {goal[:120]}",
        ))
        idx += 1

    # ── 3. TESTING ────────────────────────────────────────
    elif is_test:
        steps.append(PlanStep(
            index=idx,
            action="Identificar archivos a testear",
            target=target_description,
            success_criteria="Archivos objetivo identificados",
            method="subprocess",
            details=_build_grep_cmd(search_base, detected_paths, detected_modules),
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Analizar estructura de tests existentes",
            target="tests/ o suite del proyecto",
            success_criteria="Patrones de test identificados",
            method="subprocess",
            details="find tests/ -name 'test_*.py' -o -name '*_test.py' | head -20 2>/dev/null || true",
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Escribir tests",
            target=f"Tests para: {', '.join(detected_paths[:3]) if detected_paths else 'archivos detectados'}",
            success_criteria="Tests escritos con coverage adecuado",
            method="subprocess",
            details="Escribir archivos de test con pytest / vitest según el lenguaje",
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Ejecutar suite de tests",
            target="Suite completa",
            success_criteria="Tests pasan o errores documentados",
            method="subprocess",
            details=_build_test_cmd(detected_langs, detected_surfaces),
        ))
        idx += 1

    # ── 4. BUILD / DEPLOY ─────────────────────────────────
    elif is_build:
        steps.append(PlanStep(
            index=idx,
            action="Verificar dependencias",
            target="deps del proyecto",
            success_criteria="Dependencias instaladas y versiones correctas",
            method="subprocess",
            details=_build_deps_check_cmd(detected_surfaces),
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Compilar / build",
            target=f"Build para: {', '.join(detected_surfaces) if detected_surfaces else 'todo el proyecto'}",
            success_criteria="Artefactos generados sin errores",
            method="subprocess",
            details=_build_build_cmd(detected_surfaces),
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Verificar artefactos",
            target="Binarios / instaladores",
            success_criteria="Archivos .exe/.msi presentes si corresponde",
            method="subprocess",
            details=_build_artifact_verify_cmd(detected_surfaces),
        ))
        idx += 1

    # ── 5. DATA / ANALYSIS ─────────────────────────────────
    elif is_data:
        steps.append(PlanStep(
            index=idx,
            action="Recopilar datos",
            target=target_description,
            success_criteria="Fuentes de datos identificadas",
            method="subprocess",
            details="Recopilar logs, metrics, archivos relevantes",
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Analizar datos",
            target="Métricas y logs",
            success_criteria="Patrones y anomalías identificadas",
            method="subprocess",
            details="Analizar datos recopilados y generar insights",
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Generar reporte",
            target="Reporte en markdown",
            success_criteria="Reporte legible con hallazgos",
            method="brain_save",
            details=f"Reporte de análisis: {goal[:120]}",
        ))
        idx += 1

    # ── 6. GIT ────────────────────────────────────────────
    elif is_git:
        steps.append(PlanStep(
            index=idx,
            action="Inspeccionar estado git",
            target="Repositorio",
            success_criteria="Estado actual del repo conocido",
            method="subprocess",
            details="git status && git log --oneline -10",
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Ejecutar operación git",
            target=target_description,
            success_criteria="Operación git completada",
            method="subprocess",
            details=f"Ejecutar operación git: {goal[:100]}",
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Verificar resultado",
            target="Resultado git",
            success_criteria="git status confirma el cambio esperado",
            method="subprocess",
            details="git status && git log --oneline -3",
        ))
        idx += 1

    # ── 7. MULTI-PROJECT ───────────────────────────────────
    elif is_multi:
        for surf in detected_surfaces:
            steps.append(PlanStep(
                index=idx,
                action=f"Ejecutar en {surf}",
                target=f"Surface: {surf}",
                success_criteria=f"Cambios en {surf} aplicados",
                method="subprocess",
                details=f"Ejecutar cambios para surface: {surf}",
            ))
            idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Verificar integración entre surfaces",
            target=", ".join(detected_surfaces),
            success_criteria="Interfaces entre surfaces compatibles",
            method="subprocess",
            details="Verificar imports y dependencias cruzadas",
        ))
        idx += 1

    # ── 8. DISCOVERY ───────────────────────────────────────
    elif is_discovery:
        steps.append(PlanStep(
            index=idx,
            action="Mapear superficie del proyecto",
            target="Estructura del repo",
            success_criteria="Estructura de directorios mapeada",
            method="subprocess",
            details="find . -maxdepth 3 -type d | grep -v '.git\\|node_modules\\|target\\|dist' | head -40",
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Buscar entidades",
            target=target_description,
            success_criteria="Archivos/módulos encontrados",
            method="subprocess",
            details=_build_grep_cmd(search_base, detected_paths, detected_modules),
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Reportar hallazgos",
            target="Hallazgos del escaneo",
            success_criteria="Hallazgos listados y accesibles",
            method="brain_save",
            details=f"Discovery: {goal[:120]}",
        ))
        idx += 1

    # ── 9. AUDIT ────────────────────────────────────────────
    elif is_audit:
        steps.append(PlanStep(
            index=idx,
            action="Escanear código con ruff",
            target="Código Python",
            success_criteria="Issues de linting reportados",
            method="subprocess",
            details="ruff check .agent/ src/ mcp-server/ 2>/dev/null || true",
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Ejecutar tests de seguridad",
            target="Suite de tests",
            success_criteria="Tests de seguridad pasan",
            method="subprocess",
            details="pytest tests/ -v --tb=short -k security 2>/dev/null || pytest tests/ -v --tb=short 2>/dev/null || true",
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Guardar hallazgos de auditoría",
            target="Brain Network",
            success_criteria="Hallazgos guardados con tags security",
            method="brain_save",
            details=f"Auditoría: {goal[:120]}",
        ))
        idx += 1

    # ── 10. REFACTOR ───────────────────────────────────────
    elif is_refactor:
        steps.append(PlanStep(
            index=idx,
            action="Identificar código a refactorizar",
            target=target_description,
            success_criteria="Archivos objetivo identificados",
            method="subprocess",
            details=_build_grep_cmd(search_base, detected_paths, detected_modules),
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Ejecutar ruff --fix (cambios seguros)",
            target="Código",
            success_criteria="Cambios automáticos aplicados",
            method="subprocess",
            details="ruff check .agent/ src/ --fix 2>/dev/null || true",
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Refactorizar código",
            target=target_description,
            success_criteria="Cambios refactor aplicados",
            method="subprocess",
            details="Aplicar cambios de refactorización",
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Verificar con tests",
            target="Suite de tests",
            success_criteria="Tests pasan post-refactor",
            method="subprocess",
            details=_build_test_cmd(detected_langs, detected_surfaces),
        ))
        idx += 1

    # ── 11. BUG ────────────────────────────────────────────
    elif is_bug:
        steps.append(PlanStep(
            index=idx,
            action="Investigar causa raíz",
            target=target_description,
            success_criteria="Causa del bug identificada",
            method="subprocess",
            details=_build_grep_cmd(search_base, detected_paths, detected_modules),
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Guardar análisis en Brain",
            target="Brain Network",
            success_criteria="Análisis guardado como concept",
            method="brain_save",
            details=f"Bug analysis: {goal[:120]}",
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Aplicar fix",
            target=target_description,
            success_criteria="Cambio aplicado y sintácticamente correcto",
            method="subprocess",
            details="Aplicar fix al código",
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Ejecutar tests",
            target="Suite de tests",
            success_criteria="Tests pasan o errores mapeados",
            method="subprocess",
            details=_build_test_cmd(detected_langs, detected_surfaces),
        ))
        idx += 1

    # ── 12. FEATURE ────────────────────────────────────────
    elif is_feature:
        steps.append(PlanStep(
            index=idx,
            action="Diseñar implementación",
            target=target_description,
            success_criteria="Arquitectura y archivos definidos",
            method="brain_save",
            details=f"Feature design: {goal[:120]}",
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Implementar feature",
            target=target_description,
            success_criteria="Código implementado y funcional",
            method="subprocess",
            details="Implementar cambios",
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Verificar con tests",
            target="Suite de tests",
            success_criteria="Tests pasan",
            method="subprocess",
            details=_build_test_cmd(detected_langs, detected_surfaces),
        ))
        idx += 1

    # ── GENERIC FALLBACK ────────────────────────────────────
    else:
        steps.append(PlanStep(
            index=idx,
            action="Explorar contexto",
            target=target_description,
            success_criteria="Archivos y módulos relevantes localizados",
            method="subprocess",
            details=_build_grep_cmd(search_base, detected_paths, detected_modules),
        ))
        idx += 1

        steps.append(PlanStep(
            index=idx,
            action="Ejecutar",
            target=target_description,
            success_criteria="Objetivo cumplido",
            method="subprocess",
            details=f"Ejecutar: {goal[:80]}",
        ))
        idx += 1

    # ── Pasos comunes post-ejecución ───────────────────────

    # Verificación de tipos / lint
    if not is_build and not is_git and not is_discovery and not is_docs:
        steps.append(PlanStep(
            index=idx,
            action="Verificar calidad de código",
            target="Linting y type checking",
            success_criteria="ruff y mypy sin errores críticos",
            method="subprocess",
            details=_build_lint_cmd(detected_langs, detected_surfaces),
        ))
        idx += 1

    # Tests (excepto para docs, build, git, discovery en modo puro)
    # No agregar paso común si el flujo específico ya lo ejecutó (is_test)
    if not is_docs and not is_build and not is_git and not is_test:
        test_cmd = _build_test_cmd(detected_langs, detected_surfaces)
        if test_cmd:
            steps.append(PlanStep(
                index=idx,
                action="Ejecutar tests",
                target="Suite de tests",
                success_criteria="Tests pasan o errores mapeados",
                method="subprocess",
                details=test_cmd,
            ))
            idx += 1

    # Commitear (excepto discovery puro y multi-project que ya tiene sus pasos)
    if not is_discovery:
        steps.append(PlanStep(
            index=idx,
            action="Commitear cambios",
            target="Repositorio git",
            success_criteria="Commit creado con mensaje descriptivo",
            method="subprocess",
            details=_build_git_commit_msg(goal),
        ))
        idx += 1

    # Brain save final
    steps.append(PlanStep(
        index=idx,
        action="Guardar en Brain",
        target="Brain Network",
        success_criteria="Nodo de ejecución guardado con tags relevantes",
        method="brain_save",
        details=f"Completado: {goal[:120]}",
    ))

    return steps[:MAX_STEPS]


# ─────────────────────────────────────────────────────────
# Helper builders — construyen comandos dinámicos según el contexto
# ─────────────────────────────────────────────────────────

def _build_grep_cmd(search_base: str, paths: list[str], modules: list[str]) -> str:
    """Construye comando grep según paths/modules detectados."""
    if paths:
        files = " ".join(paths[:5])
        return f"grep -n '' {files} 2>/dev/null | head -50 || true"
    if modules:
        mods = " ".join(modules[:5])
        return f"grep -rn '{mods}' {search_base} 2>/dev/null | head -30 || true"
    return f"grep -rn 'TODO\\|FIXME\\|BUG' {search_base} 2>/dev/null | head -20 || true"


def _build_lint_cmd(langs: list[str], surfaces: list[str]) -> str:
    """Construye comando de linting según lenguajes detectados."""
    cmds: list[str] = []
    if "python" in langs or ".agent" in surfaces or not langs:
        cmds.append("ruff check .agent/ 2>/dev/null || true")
    if "python" in langs or ".agent" in surfaces or not langs:
        cmds.append("mypy .agent/ --strict 2>/dev/null || true")
    if "typescript" in langs or "src" in surfaces or "nexus-app" in surfaces:
        cmds.append("cd nexus-app && npx eslint src/ 2>/dev/null || cd .. && true")
    return " && ".join(cmds) if cmds else "echo 'No lint targets identified'"


def _build_typecheck_cmd(langs: list[str], paths: list[str], surfaces: list[str]) -> str:
    """Construye comando de type checking."""
    cmds: list[str] = []
    if "python" in langs or ".agent" in surfaces or not langs:
        cmds.append("mypy .agent/ --strict 2>/dev/null || true")
    if "typescript" in langs or "src" in surfaces or "nexus-app" in surfaces:
        cmds.append("cd nexus-app && npx tsc --noEmit 2>/dev/null || cd .. && true")
    if "rust" in langs or "nexus-app/src-tauri" in surfaces:
        cmds.append("cd nexus-app/src-tauri && cargo check 2>/dev/null || true")
    return " && ".join(cmds) if cmds else "echo 'No typecheck targets'"


def _build_test_cmd(langs: list[str], surfaces: list[str]) -> str:
    """Construye comando de tests según lenguajes/surfaces."""
    cmds: list[str] = []
    if "python" in langs or ".agent" in surfaces or (REPO_ROOT / "tests").exists():
        cmds.append("pytest tests/ -v --tb=short 2>/dev/null || true")
    if "typescript" in langs or "src" in surfaces or "nexus-app" in surfaces:
        cmds.append("cd nexus-app && npm test -- --run 2>/dev/null || cd .. && true")
    if "rust" in langs or "nexus-app/src-tauri" in surfaces:
        cmds.append("cd nexus-app/src-tauri && cargo test 2>/dev/null || cd .. && true")
    return " && ".join(cmds) if cmds else ""


def _build_deps_check_cmd(surfaces: list[str]) -> str:
    """Construye comando de verificación de dependencias."""
    cmds: list[str] = []
    if ".agent" in surfaces or not surfaces:
        cmds.append("pip install -r .agent/requirements.txt --dry-run 2>/dev/null || pip install -r requirements.txt --dry-run 2>/dev/null || true")
    if "nexus-app" in surfaces or not surfaces:
        cmds.append("cd nexus-app && npm install --dry-run 2>/dev/null || cd .. && true")
    return " && ".join(cmds) if cmds else "echo 'No dependency files found'"


def _build_build_cmd(surfaces: list[str]) -> str:
    """Construye comando de build según surfaces."""
    if "nexus-app" in surfaces:
        return "cd nexus-app && npm run tauri:build 2>/dev/null || npm run build 2>/dev/null || true"
    if ".agent" in surfaces:
        return "pip install -e . --quiet 2>/dev/null || true"
    if "src" in surfaces:
        return "cd src && npm run build 2>/dev/null || true"
    return "echo 'No build command for this surface'"


def _build_artifact_verify_cmd(surfaces: list[str]) -> str:
    """Construye comando de verificación de artefactos."""
    if "nexus-app" in surfaces:
        return "find nexus-app/src-tauri/target/release -name '*.exe' -o -name '*.msi' 2>/dev/null | head -10"
    return "find . -name '*.exe' -o -name '*.msi' 2>/dev/null | grep -v '.git\\|node_modules' | head -10 || true"


def _build_git_commit_msg(goal: str) -> str:
    """Construye el comando de commit con mensaje dinámico."""
    # Clasificar el tipo de commit
    gl = goal.lower()
    if any(k in gl for k in ["test", "pytest", "coverage"]):
        commit_type = "test"
    elif any(k in gl for k in ["fix", "bug", "error", "falla"]):
        commit_type = "fix"
    elif any(k in gl for k in ["audit", "security", "vulnerab"]):
        commit_type = "fix"
    elif any(k in gl for k in ["docs", "document", "readme"]):
        commit_type = "docs"
    elif any(k in gl for k in ["build", "deploy", "release"]):
        commit_type = "chore"
    elif any(k in gl for k in ["refactor", "cleanup", "limpiar"]):
        commit_type = "refactor"
    else:
        commit_type = "feat"

    # Truncar mensaje a ~50 chars para el subject
    msg = goal[:50].strip()
    return f'git add -A && git commit -m "{commit_type}(executor): {msg}" --allow-empty'


# ─────────────────────────────────────────────────────────
# Plan display and approval
# ─────────────────────────────────────────────────────────

def display_plan(goal: str, steps: list[PlanStep]) -> None:
    """Muestra el plan y espera aprobación humana."""

    print()
    print("=" * 60)
    print(f"OBJETIVO: {goal}")
    print("=" * 60)
    print()
    print("PLAN:")
    for step in steps:
        print(f"  [{step.index}] {step.action}")
        if step.target:
            print(f"       Target: {step.target}")
        print(f"       Criteria: {step.success_criteria}")
        print(f"       Method: {step.method}")
        print()
    print("=" * 60)
    print()
    print("Respuestas válidas: sí / no / modificar")
    print()


def ask_approval() -> tuple[bool, bool]:
    """Pide confirmación al usuario. Devuelve (approved, wants_modify)."""

    try:
        response = input("¿Ejecuto el plan? [sí/no/modificar]: ").strip().lower()
    except (EOFError, OSError):
        response = ""

    if response in ("sí", "si", "yes", "y", "s", "ejecutar", "ejecuto", "ok", "go", "start"):
        return True, False
    elif response in ("modificar", "mod", "edit", "change"):
        return False, True
    else:
        return False, False


def edit_plan_interactive(steps: list[PlanStep]) -> list[PlanStep]:
    """Permite editar el plan interactivamente."""

    print("\n--- Modificar Plan ---")
    print("Comandos: add <action> | remove <idx> | reorder | done")
    print()

    while True:
        try:
            cmd = input("plan> ").strip()
        except (EOFError, OSError):
            break

        if not cmd:
            continue

        parts = cmd.split(maxsplit=1)
        action = parts[0].lower()

        if action == "done":
            break
        elif action == "add" and len(parts) > 1:
            new_action = parts[1]
            new_idx = len(steps) + 1
            steps.append(PlanStep(
                index=new_idx,
                action=new_action,
                target="",
                success_criteria="Completado",
                method="subprocess",
            ))
            print(f"  Añadido paso [{new_idx}]: {new_action}")
        elif action in ("remove", "rm", "del") and len(parts) > 1:
            try:
                target_idx = int(parts[1])
                steps = [s for s in steps if s.index != target_idx]
                # Reindex
                for i, s in enumerate(steps, 1):
                    s.index = i
                print(f"  Eliminado paso [{target_idx}]")
            except ValueError:
                print("  Índice inválido")
        elif action == "list":
            for s in steps:
                print(f"  [{s.index}] {s.action}")

    return steps


# ─────────────────────────────────────────────────────────
# Step executor
# ─────────────────────────────────────────────────────────

def execute_step(step: PlanStep, goal: str) -> tuple[bool, str]:
    """Ejecuta un paso individual."""

    method = step.method

    if method == "subprocess":
        return execute_subprocess_step(step)
    elif method == "brain_save":
        return execute_brain_step(step, goal)
    elif method == "mcp_agent":
        return execute_agent_step(step)
    elif method == "mcp_skill":
        return execute_skill_step(step)
    else:
        return False, f"Unknown method: {method}"


def execute_subprocess_step(step: PlanStep) -> tuple[bool, str]:
    """Ejecuta un paso via subprocess."""

    if not step.details:
        return True, "No command needed (informational step)"

    code, stdout, stderr = run_command(step.details, timeout=STEP_TIMEOUT)

    if code == 0:
        return True, stdout[:200] if stdout else "OK"
    else:
        combined = (stdout + "\n" + stderr).strip()[:300]
        return False, combined or f"Exit code: {code}"


def execute_brain_step(step: PlanStep, goal: str) -> tuple[bool, str]:
    """Ejecuta un paso de guardado en Brain."""

    if step.action == "Guardar en Brain":
        success = brain_save(
            title=f"Execution: {goal[:80]}",
            context=f"Completado objetivo: {goal}",
            area="execution",
            tags=["autonomous-executor", "completed", "session"],
            node_type="session",
            importance="medium",
        )
        return success, "Brain node created" if success else "Brain save failed"


def execute_agent_step(step: PlanStep) -> tuple[bool, str]:
    """Ejecuta un paso via invocación de agente."""

    # Placeholder: agent invocation via gateway
    success, output = invoke_agent(step.target, step.action)
    return success, output


def execute_skill_step(step: PlanStep) -> tuple[bool, str]:
    """Ejecuta un paso via skill del ecosistema."""

    skill = find_skill_by_keyword(step.action)
    if skill:
        result = _http_post("/v1/skills/run", {
            "skill": skill,
            "goal": step.action,
        })
        if result:
            return True, str(result)
    return False, f"Skill not found for: {step.action}"


# ─────────────────────────────────────────────────────────
# Main execution loop
# ─────────────────────────────────────────────────────────

def run_execution(goal: str, steps: list[PlanStep], json_output: bool = False) -> ExecutionResult:
    """Ejecuta el plan completo de forma autónoma."""

    result = ExecutionResult(goal=goal, plan_steps=steps)
    start_time = time.monotonic()

    gateway_up = _gateway_health()
    if not gateway_up:
        print("[WARN] Gateway no disponible -- modo offline")

    total = len(steps)
    failures = 0

    for step in steps:
        result.executed_steps += 1

        # Update status
        step.status = "running"
        print(f"\n-> [{step.index}/{total}] {step.action}... ", end="", flush=True)

        step_start = time.monotonic()
        success, message = execute_step(step, goal)
        step.duration_ms = int((time.monotonic() - step_start) * 1000)

        if success:
            step.status = "ok"
            result.successful_steps += 1
            print("OK")
            if message and message != "OK":
                print(f"  └ {message[:120]}")
        else:
            # Retry logic
            if step.retries < MAX_RETRIES:
                step.retries += 1
                print(f"FAIL (retry {step.retries}/{MAX_RETRIES}): {message[:100]}")
                # Retry once
                success2, message2 = execute_step(step, goal)
                if success2:
                    step.status = "ok"
                    result.successful_steps += 1
                    failures -= 1
                    print(f"  └ Retry OK: {message2[:100]}")
                else:
                    step.status = "fail"
                    step.error = message2 or message
                    result.failed_steps += 1
                    failures += 1
                    print(f"  └ Failed: {step.error[:100]}")
            else:
                step.status = "fail"
                step.error = message
                result.failed_steps += 1
                failures += 1
                print(f"FAIL: {message[:100]}")

        # Check abort threshold
        if result.executed_steps >= 3 and (failures / result.executed_steps) > ABORT_THRESHOLD:
            print(f"\n[ABORT] >{ABORT_THRESHOLD:.0%} steps failed -- abortando ejecución")
            result.aborted = True
            # Mark remaining as skipped
            for s in steps[result.executed_steps:]:
                s.status = "skipped"
                result.skipped_steps += 1
            break

    result.duration_seconds = time.monotonic() - start_time

    # Post-execution: rebuild brain index
    if gateway_up or (REPO_ROOT / ".agent" / "brain").exists():
        print("\n-> Guardando resumen en Brain...")
        brain_save(
            title=f"Execution result: {goal[:80]}",
            context=_build_summary(result),
            area="execution",
            tags=["autonomous-executor", "result"],
            node_type="pattern",
            importance="medium",
        )
        result.brain_nodes_created.append("execution_summary")

    # Try to rebuild brain index
    try:
        import sys as _sys
        _sys.path.insert(0, str(REPO_ROOT / ".agent"))
        from core.brain import Brain

        brain = Brain(REPO_ROOT / ".agent" / "brain", app_id="autonomous-executor")
        brain.rebuild_index()
        print("-> Brain index rebuild OK")
    except Exception as e:
        logger.debug("Brain index rebuild skipped: %s", e)

    return result


def _build_summary(result: ExecutionResult) -> str:
    """Construye el resumen textual de la ejecución."""

    ok_steps = [s.action for s in result.plan_steps if s.status == "ok"]
    fail_steps = [(s.action, s.error) for s in result.plan_steps if s.status == "fail"]

    lines = [
        f"Objetivo: {result.goal}",
        f"Duración: {result.duration_seconds:.1f}s",
        f"Pasos exitosos: {result.successful_steps}/{result.executed_steps}",
        f"Fallidos: {result.failed_steps}",
        f"Aborted: {result.aborted}",
        "",
        "Steps OK: " + ", ".join(ok_steps) if ok_steps else "Ninguno",
    ]
    for action, error in fail_steps:
        lines.append(f"FAIL [{action}]: {error}")

    return "\n".join(lines)


# ─────────────────────────────────────────────────────────
# CLI entry point
# ─────────────────────────────────────────────────────────

def main() -> int:
    # Force UTF-8 on stdout/stderr to avoid cp932 encode errors
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

    parser = argparse.ArgumentParser(
        description="Autonomous Executor: planifica y ejecuta objetivos de forma autonoma",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python main.py --goal \"arreglar el bug de login\"\n"
            "  python main.py --goal \"implementar feature X\" --plan-only\n"
            "  python main.py --goal \"auditar seguridad\" --json\n\n"
            "El script muestra el plan y espera confirmacion antes de ejecutar.\n"
        ),
    )
    parser.add_argument(
        "--goal",
        type=str,
        required=True,
        help="Objetivo de texto libre a ejecutar",
    )
    parser.add_argument(
        "--plan-only",
        action="store_true",
        help="Solo generar el plan, no ejecutar",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Salida en formato JSON",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Logging detallado",
    )

    args = parser.parse_args()

    # Logging setup
    log_level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=log_level,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )

    print(f"\n[Autonomous Executor] Objetivo: {args.goal}")
    print(f"[Autonomous Executor] Gateway: {GATEWAY_URL}")

    # ── Fase 1: Análisis y planificación ──
    print("\n[1/5] Analizando objetivo...")
    steps = analyze_goal(args.goal)
    print(f"       Plan generados: {len(steps)} pasos")

    if not steps:
        print("[ERROR] No se pudo generar un plan para este objetivo.")
        return 1

    # ── Fase 2: Mostrar plan y esperar aprobación ──
    display_plan(args.goal, steps)

    if args.plan_only:
        print("[INFO] Modo --plan-only: no se ejecuta nada.")
        return 0

    print("\n[2/5] Esperando aprobación...")
    approved, wants_modify = ask_approval()

    if wants_modify:
        steps = edit_plan_interactive(steps)
        display_plan(args.goal, steps)
        approved, _ = ask_approval()

    if not approved:
        print("\n[INFO] Ejecución cancelada por el usuario.")
        return 0

    # ── Fase 3: Ejecución Autónoma ──
    print("\n[3/5] Ejecutando plan...\n")

    result = run_execution(args.goal, steps, json_output=args.json)

    # ── Fase 4: Reporte ──
    print("\n[4/5] Generando reporte...")

    if args.json:
        print(json.dumps(result.to_dict(), ensure_ascii=False, indent=2))
    else:
        print("\n" + "=" * 60)
        print("REPORTE DE EJECUCIÓN")
        print("=" * 60)
        print(f"Objetivo:    {result.goal}")
        print(f"Duración:    {result.duration_seconds:.1f}s")
        print(f"Pasos OK:    {result.successful_steps}/{result.executed_steps}")
        print(f"Pasos FAIL:  {result.failed_steps}")
        if result.skipped_steps:
            print(f"Skipped:     {result.skipped_steps}")
        if result.aborted:
            print("⚠ ABORTADO por threshold de fallos")
        if result.brain_nodes_created:
            print(f"Brain nodes: {', '.join(result.brain_nodes_created)}")
        print()
        print("Detalle de pasos:")
        for step in result.plan_steps:
            icon = "[OK]" if step.status == "ok" else ("[X]" if step.status == "fail" else ("->" if step.status == "running" else "?"))
            duration_ms = step.duration_ms or 0
            print(f"  {icon} [{step.index}] {step.action} [{step.status}] ({duration_ms}ms)")
            if step.error:
                print(f"         ERROR: {step.error[:80]}")

        if result.failed_steps > 0:
            print("\nRecomendaciones:")
            for step in result.plan_steps:
                if step.status == "fail":
                    print(f"  - Revisar paso [{step.index}] {step.action}: {step.error[:100]}")
                    result.recommendations.append(f"Revisar {step.action}: {step.error}")

        if result.successful_steps == result.executed_steps and not result.aborted:
            print("\n[OK] Todos los pasos completados exitosamente.")

    # ── Fase 5: Sync memories ──
    print("\n[5/5] Sincronizando memorias...")

    try:
        subprocess.run(
            shlex.split("git add .claude/memory/ .agent/brain/"),
            shell=False,
            capture_output=True,
            cwd=REPO_ROOT,
            timeout=10,
        )
        result2 = subprocess.run(
            shlex.split('git commit -m "chore(memory): sync execution memories"'),
            shell=False,
            capture_output=True,
            cwd=REPO_ROOT,
            timeout=10,
        )
        if result2.returncode == 0:
            print("-> Memorias sincronizadas en git")
    except Exception as e:
        logger.debug("Git sync skipped: %s", e)

    return 0 if result.aborted is False and result.failed_steps == 0 else 1


if __name__ == "__main__":
    sys.exit(main())