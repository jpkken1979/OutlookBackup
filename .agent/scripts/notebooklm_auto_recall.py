#!/usr/bin/env python3
"""Selective NotebookLM recall for prompt hooks and IDE agents.

The goal is intentionally narrow: detect project-memory prompts, resolve the
right project notebook, query NotebookLM with a short budget, and emit compact
context. Normal coding prompts should not pay the cost.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import time
import unicodedata
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
REGISTRY_PATH = ROOT / ".agent" / "notebooklm" / "projects.json"
WORKFLOW_PATH = ROOT / ".agent" / "scripts" / "notebooklm_workflow.py"

DEFAULT_TIMEOUT_SECONDS = 15.0
MAX_PROMPT_CHARS = 500
MAX_CONTEXT_CHARS = 3200

# Circuit breaker: si NotebookLM viene fallando (timeouts por device-binding de
# Google, auth caida, red), dejamos de pagar el costo en CADA prompt y
# reintentamos recien despues del cooldown. Estado fuera del repo (no churn git).
BREAKER_PATH = Path.home() / ".antigravity" / "notebooklm" / "auto_recall_breaker.json"
BREAKER_THRESHOLD = 3
BREAKER_COOLDOWN_SECONDS = 6 * 3600.0

DIRECT_MEMORY_TERMS = {
    "memoria",
    "notebook",
    "notebooklm",
    "recall",
    "recuerda",
    "recorda",
    "recordas",
    "recordar",
    "referencia",
    "referencias",
    "historial",
    "contexto",
}

PROJECT_CONTEXT_TERMS = {
    "arquitectura",
    "auditoria",
    "auditar",
    "bug",
    "bugfix",
    "decision",
    "decisiones",
    "docs",
    "documentacion",
    "estado",
    "falta",
    "faltan",
    "manual",
    "pendiente",
    "pendientes",
    "produccion",
    "recomendacion",
    "recomendaciones",
    "regla",
    "reglas",
    "resumen",
    "roadmap",
    "workflow",
    "workflows",
}

QUESTION_HINTS = {
    "como",
    "cual",
    "cuales",
    "cuando",
    "dime",
    "explica",
    "por que",
    "que",
    "segun",
}

SKIP_PREFIXES = (
    "/cuota",
    "/notebooklm",
    "/notebooklm-add",
    "/notebooklm-ask",
    "/notebooklm-doctor",
    "/notebooklm-project",
    "/notebooklm-sync",
)


@dataclass(frozen=True)
class ProjectMatch:
    project: str
    notebook_id: str
    title: str
    reason: str


@dataclass(frozen=True)
class RecallDecision:
    should_query: bool
    reason: str
    score: int
    project: str = ""
    notebook_id: str = ""
    title: str = ""


def normalize_text(value: str) -> str:
    normalized = unicodedata.normalize("NFKD", value)
    ascii_text = "".join(ch for ch in normalized if not unicodedata.combining(ch))
    return ascii_text.casefold()


def extract_prompt(data: dict[str, Any]) -> str:
    for key in ("prompt", "message", "input", "user_message", "text"):
        value = data.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return ""


def sanitize_prompt(prompt: str) -> str:
    cleaned = re.sub(r"<private>.*?</private>", "", prompt, flags=re.IGNORECASE | re.DOTALL)
    return cleaned.strip()[:MAX_PROMPT_CHARS]


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "active_project": "", "projects": {}}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"version": 1, "active_project": "", "projects": {}}
    if not isinstance(data, dict):
        return {"version": 1, "active_project": "", "projects": {}}
    data.setdefault("projects", {})
    return data


def _path_from_source_root(target: Path) -> Path | None:
    parts = [normalize_text(part) for part in target.parts]
    for marker in (".claude", ".agent", "docs", "src", "server", "tests"):
        if marker in parts:
            idx = parts.index(marker)
            if idx > 0:
                return Path(*target.parts[:idx])

    if target.name in {"AGENTS.md", "CLAUDE.md", "README.md", "ESTADO_PROYECTO.md"}:
        return target.parent
    return None


def project_roots(entry: dict[str, Any]) -> list[Path]:
    roots: list[Path] = []
    for key in ("root", "path"):
        value = entry.get(key)
        if isinstance(value, str) and value.strip():
            roots.append(Path(value))

    values = entry.get("roots")
    if isinstance(values, list):
        roots.extend(Path(str(value)) for value in values if str(value).strip())

    sources = entry.get("sources")
    if isinstance(sources, list):
        for source in sources:
            if not isinstance(source, dict):
                continue
            target = str(source.get("target", "")).strip()
            if not target:
                continue
            root = _path_from_source_root(Path(target))
            if root is not None:
                roots.append(root)

    unique: list[Path] = []
    seen: set[str] = set()
    for root in roots:
        marker = str(root.resolve(strict=False)).casefold()
        if marker not in seen:
            seen.add(marker)
            unique.append(root)
    return unique


def _cwd_matches_project(cwd: Path, entry: dict[str, Any]) -> bool:
    cwd_text = str(cwd.resolve(strict=False)).casefold()
    for root in project_roots(entry):
        root_text = str(root.resolve(strict=False)).casefold()
        if cwd_text == root_text or cwd_text.startswith(root_text + os.sep):
            return True
    return False


def _project_named_in_prompt(prompt_norm: str, project: str, entry: dict[str, Any]) -> bool:
    candidates = [project, str(entry.get("title", ""))]
    aliases = entry.get("aliases")
    if isinstance(aliases, list):
        candidates.extend(str(value) for value in aliases if str(value).strip())
    return any(normalize_text(candidate) in prompt_norm for candidate in candidates if candidate)


def resolve_project(prompt: str, cwd: Path, registry: dict[str, Any]) -> ProjectMatch | None:
    projects = registry.get("projects", {})
    if not isinstance(projects, dict):
        return None

    prompt_norm = normalize_text(prompt)
    matches: list[ProjectMatch] = []
    for project, raw_entry in projects.items():
        if not isinstance(raw_entry, dict):
            continue
        notebook_id = str(raw_entry.get("notebook_id", "")).strip()
        if not notebook_id:
            continue
        title = str(raw_entry.get("title", project)).strip() or str(project)
        project_key = str(project)
        if _project_named_in_prompt(prompt_norm, project_key, raw_entry):
            matches.append(ProjectMatch(project_key, notebook_id, title, "prompt_project_match"))
            continue
        if _cwd_matches_project(cwd, raw_entry):
            matches.append(ProjectMatch(project_key, notebook_id, title, "cwd_project_match"))

    if matches:
        return matches[0]

    # ponytail: active fallback is deliberately limited to direct memory asks;
    # if this grows into multi-project routing, store explicit project roots.
    active = str(registry.get("active_project", "")).strip()
    active_entry = projects.get(active) if active else None
    if isinstance(active_entry, dict) and _has_direct_memory_term(prompt_norm):
        notebook_id = str(active_entry.get("notebook_id", "")).strip()
        if notebook_id:
            title = str(active_entry.get("title", active)).strip() or active
            return ProjectMatch(active, notebook_id, title, "active_memory_fallback")
    return None


def _has_direct_memory_term(prompt_norm: str) -> bool:
    return any(term in prompt_norm for term in DIRECT_MEMORY_TERMS)


def should_query_notebook(prompt: str, project_match: ProjectMatch | None) -> RecallDecision:
    prompt_norm = normalize_text(prompt)
    stripped = prompt_norm.strip()
    if not stripped or any(stripped.startswith(prefix) for prefix in SKIP_PREFIXES):
        return RecallDecision(False, "skip_command_or_empty", 0)
    if project_match is None:
        return RecallDecision(False, "no_project_notebook", 0)

    direct_hits = sum(1 for term in DIRECT_MEMORY_TERMS if term in prompt_norm)
    context_hits = sum(1 for term in PROJECT_CONTEXT_TERMS if term in prompt_norm)
    question_hits = sum(
        1 for term in QUESTION_HINTS if prompt_norm.startswith(term) or f" {term} " in prompt_norm
    )
    question_signal = 1 if "?" in prompt or "¿" in prompt or question_hits else 0
    project_signal = 1 if project_match.reason == "prompt_project_match" else 0
    score = (direct_hits * 3) + (context_hits * 2) + question_signal + project_signal

    if direct_hits and score >= 4:
        return RecallDecision(
            True,
            f"{project_match.reason}:direct_memory",
            score,
            project_match.project,
            project_match.notebook_id,
            project_match.title,
        )
    if project_signal and context_hits and score >= 4:
        return RecallDecision(
            True,
            f"{project_match.reason}:project_context",
            score,
            project_match.project,
            project_match.notebook_id,
            project_match.title,
        )
    if project_match.reason == "cwd_project_match" and context_hits >= 2 and question_signal:
        return RecallDecision(
            True,
            f"{project_match.reason}:cwd_context",
            score,
            project_match.project,
            project_match.notebook_id,
            project_match.title,
        )
    return RecallDecision(False, "low_signal", score)


def build_decision(prompt: str, cwd: Path, registry_path: Path = REGISTRY_PATH) -> RecallDecision:
    clean_prompt = sanitize_prompt(prompt)
    registry = load_registry(registry_path)
    project_match = resolve_project(clean_prompt, cwd, registry)
    return should_query_notebook(clean_prompt, project_match)


def load_breaker(path: Path = BREAKER_PATH) -> dict[str, Any]:
    """Lee el estado del circuit breaker; corrupto o ausente = cerrado."""
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {"consecutive_failures": 0, "last_failure_at": 0.0}
    if not isinstance(data, dict):
        return {"consecutive_failures": 0, "last_failure_at": 0.0}
    return {
        "consecutive_failures": int(data.get("consecutive_failures", 0) or 0),
        "last_failure_at": float(data.get("last_failure_at", 0.0) or 0.0),
    }


def breaker_is_open(state: dict[str, Any], now: float | None = None) -> bool:
    """Abierto = N fallos consecutivos y todavia dentro del cooldown."""
    if state.get("consecutive_failures", 0) < BREAKER_THRESHOLD:
        return False
    now = time.time() if now is None else now
    return (now - float(state.get("last_failure_at", 0.0))) < BREAKER_COOLDOWN_SECONDS


def _write_breaker(path: Path, state: dict[str, Any]) -> None:
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(state), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass  # best-effort: el breaker nunca debe romper el hook


def bump_breaker_failure(path: Path = BREAKER_PATH, now: float | None = None) -> None:
    """Registra un fallo ANTES de consultar (pesimista): si el hook nos mata
    por timeout, el intento igual queda contado."""
    state = load_breaker(path)
    state["consecutive_failures"] = state.get("consecutive_failures", 0) + 1
    state["last_failure_at"] = time.time() if now is None else now
    _write_breaker(path, state)


def record_breaker_success(path: Path = BREAKER_PATH) -> None:
    _write_breaker(path, {"consecutive_failures": 0, "last_failure_at": 0.0})


def query_notebook(prompt: str, decision: RecallDecision, timeout: float) -> tuple[str, bool]:
    """Consulta el notebook. Devuelve (texto, ok) para alimentar el breaker."""
    workflow_timeout = max(5.0, timeout - 2.0)
    command = [
        sys.executable,
        str(WORKFLOW_PATH),
        "ask",
        "--project",
        decision.project,
        "--timeout",
        str(int(workflow_timeout)),
        prompt,
    ]
    try:
        result = subprocess.run(
            command,
            cwd=str(ROOT),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=timeout,
            check=False,
        )
    except subprocess.TimeoutExpired:
        return (
            f"NotebookLM project: {decision.project}\n"
            f"NotebookLM notebook: {decision.notebook_id}\n"
            f"Consulta cancelada por timeout local ({int(timeout)}s).",
            False,
        )
    except Exception as exc:  # noqa: BLE001
        return f"NotebookLM no disponible para auto-recall: {exc}", False

    output = (result.stdout or "").strip()
    if result.returncode == 0 and output:
        return output, True

    details = (result.stderr or output or "sin salida").strip()
    if "Authentication expired" in details or "re-authenticate" in details:
        return (
            "NotebookLM auth expirada. Ejecuta `/notebooklm-sync login` o "
            "`python .agent/scripts/notebooklm_bridge.py login` y vuelve a preguntar.",
            False,
        )
    return f"NotebookLM auto-recall fallo ({result.returncode}): {details[:900]}", False


def format_context(prompt: str, decision: RecallDecision, notebook_output: str) -> str:
    body = notebook_output.strip()
    if len(body) > MAX_CONTEXT_CHARS:
        body = body[: MAX_CONTEXT_CHARS - 80].rstrip() + "\n...[recortado por auto-recall]"

    return "\n".join(
        [
            "[NotebookLM Auto-Recall]",
            f"Proyecto: {decision.project}",
            f"Notebook: {decision.title or decision.notebook_id}",
            f"Motivo: {decision.reason} (score={decision.score})",
            f"Prompt: {prompt[:160]}",
            "",
            body,
            "",
            "Usa este bloque como contexto auxiliar. Si contradice archivos locales actuales, verifica el repo.",
        ]
    )


def _input_payload(args: argparse.Namespace) -> tuple[str, Path]:
    if args.prompt:
        return sanitize_prompt(args.prompt), Path(args.cwd or os.getcwd())

    raw = sys.stdin.read()
    data = json.loads(raw) if raw.strip() else {}
    if not isinstance(data, dict):
        return "", Path(args.cwd or os.getcwd())
    prompt = sanitize_prompt(extract_prompt(data))
    cwd = Path(str(data.get("cwd") or args.cwd or os.getcwd()))
    return prompt, cwd


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Selective NotebookLM auto-recall.")
    parser.add_argument("--prompt", help="Prompt text. If omitted, reads Claude hook JSON stdin.")
    parser.add_argument("--cwd", help="Prompt workspace cwd. Defaults to current directory.")
    parser.add_argument("--registry", type=Path, default=REGISTRY_PATH)
    parser.add_argument("--timeout", type=float, default=DEFAULT_TIMEOUT_SECONDS)
    parser.add_argument(
        "--breaker", type=Path, default=BREAKER_PATH, help="Circuit breaker state file."
    )
    parser.add_argument("--dry-run", action="store_true", help="Do not query NotebookLM.")
    parser.add_argument("--json", action="store_true", help="Emit decision JSON.")
    args = parser.parse_args(argv)

    if os.getenv("ANTIGRAVITY_NOTEBOOKLM_AUTO_RECALL", "").strip().lower() in {
        "0",
        "false",
        "no",
        "off",
    }:
        return 0

    prompt, cwd = _input_payload(args)
    decision = build_decision(prompt, cwd, args.registry)

    if args.json:
        print(json.dumps(asdict(decision), ensure_ascii=False, indent=2))
        return 0

    if not decision.should_query:
        return 0

    if args.dry_run:
        print(format_context(prompt, decision, "Dry-run: NotebookLM query skipped."))
        return 0

    if breaker_is_open(load_breaker(args.breaker)):
        # NotebookLM viene fallando: silencio total para no bloquear ni
        # ensuciar el prompt. Se reintenta solo al expirar el cooldown.
        return 0

    # Pesimista: contamos el fallo antes de consultar; si el hook nos mata por
    # timeout, el intento igual queda registrado. El exito lo resetea.
    bump_breaker_failure(args.breaker)
    output, ok = query_notebook(prompt, decision, args.timeout)
    if ok:
        record_breaker_success(args.breaker)
    print(format_context(prompt, decision, output))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
