#!/usr/bin/env python3
"""Higher-level NotebookLM workflows for slash commands.

The raw `nlm` CLI is powerful, but daily agent use needs guardrails:
project notebook lookup, safe uploads, and one-command ask/add flows.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[2]
SCRIPT_DIR = Path(__file__).resolve().parent
REGISTRY_PATH = ROOT / ".agent" / "notebooklm" / "projects.json"
POLICY_PATH = ROOT / ".agent" / "notebooklm" / "policy.json"

sys.path.insert(0, str(SCRIPT_DIR))
import notebooklm_bridge as bridge  # noqa: E402


SECRET_EXTENSIONS = {
    ".env",
    ".key",
    ".p12",
    ".pfx",
    ".pem",
}

PRIVATE_BUSINESS_EXTENSIONS = {
    ".accdb",
    ".bak",
    ".db",
    ".db-journal",
    ".db-shm",
    ".db-wal",
    ".mdb",
    ".sqlite",
    ".sqlite3",
    ".xls",
    ".xlsm",
    ".xlsx",
}

BLOCKED_PATH_PARTS = {
    ".codex",
    ".git",
    ".notebooklm-mcp-cli",
    ".venv",
    ".venv-mcp",
    "__pycache__",
    "artifacts",
    "data",
    "dist",
    "node_modules",
    "output",
    "outputs",
}

SECRET_NAME_PATTERNS = [
    ".env",
    "secret",
    "token",
    "credential",
    "cookie",
    "password",
    "settings.local",
]

PRIVATE_BUSINESS_NAME_PATTERNS = [
    "社員台帳",
    "給与",
    "勤怠",
    "口座",
    "マイナンバー",
    "源泉",
    "扶養",
    "年末調整",
    "payroll",
]

SECRET_CONTENT_PATTERNS = [
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\b(?:OPENAI|ANTHROPIC|GITHUB|GOOGLE|MINIMAX|ZAI|OPENROUTER)_API_KEY\b"),
    re.compile(r"\b(?:access_token|refresh_token|client_secret|private_key)\b", re.I),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
]

DEFAULT_POLICY: dict[str, Any] = {
    "version": 1,
    "profile": "private_repo_trusted",
    "allow_private_business_documents": True,
    "quiet_business_warnings": True,
    "hard_block_secrets": True,
}


@dataclass
class SafetyResult:
    allowed: bool
    reasons: list[str]


def configure_utf8_output() -> None:
    os.environ.setdefault("PYTHONIOENCODING", "utf-8")
    for stream in (sys.stdout, sys.stderr):
        if hasattr(stream, "reconfigure"):
            stream.reconfigure(encoding="utf-8", errors="replace")


def now_iso() -> str:
    return datetime.now(UTC).isoformat()


def default_project_key(cwd: Path | None = None) -> str:
    return (cwd or ROOT).resolve().name


def load_registry(path: Path = REGISTRY_PATH) -> dict[str, Any]:
    if not path.exists():
        return {"version": 1, "active_project": default_project_key(), "projects": {}}
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid registry shape: {path}")
    data.setdefault("version", 1)
    data.setdefault("active_project", default_project_key())
    data.setdefault("projects", {})
    return data


def save_registry(data: dict[str, Any], path: Path = REGISTRY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def load_policy(path: Path = POLICY_PATH) -> dict[str, Any]:
    if not path.exists():
        return DEFAULT_POLICY.copy()
    with path.open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, dict):
        raise ValueError(f"Invalid policy shape: {path}")
    merged = DEFAULT_POLICY.copy()
    merged.update(data)
    return merged


def save_policy(data: dict[str, Any], path: Path = POLICY_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")


def set_project(
    project: str,
    notebook_id: str,
    *,
    title: str = "",
    path: Path = REGISTRY_PATH,
) -> dict[str, Any]:
    data = load_registry(path)
    projects = data.setdefault("projects", {})
    current = projects.get(project, {})
    current.update(
        {
            "project": project,
            "notebook_id": notebook_id,
            "title": title or current.get("title") or project,
            "updated_at": now_iso(),
        }
    )
    if not current.get("root") and project == default_project_key():
        current["root"] = str(ROOT)
    current.setdefault("sources", [])
    projects[project] = current
    data["active_project"] = project
    save_registry(data, path)
    return current


def resolve_notebook_id(
    *,
    notebook_id: str | None,
    project: str | None,
    registry_path: Path = REGISTRY_PATH,
) -> tuple[str, str]:
    if notebook_id:
        return notebook_id, project or default_project_key()

    data = load_registry(registry_path)
    project_key = project or data.get("active_project") or default_project_key()
    project_entry = data.get("projects", {}).get(project_key)
    if isinstance(project_entry, dict) and project_entry.get("notebook_id"):
        return str(project_entry["notebook_id"]), project_key

    raise ValueError('No hay notebook asociado. Usa --new "Titulo" o --notebook-id NOTEBOOK_ID.')


def looks_like_url(value: str) -> bool:
    return value.startswith(("http://", "https://"))


def is_youtube_url(value: str) -> bool:
    return "youtube.com/" in value or "youtu.be/" in value


def classify_source(target: str, *, text_mode: bool = False) -> str:
    if text_mode:
        return "text"
    if looks_like_url(target):
        return "youtube" if is_youtube_url(target) else "url"
    if Path(target).exists():
        return "file"
    return "text"


def _read_probe(path: Path, limit: int = 128_000) -> str:
    try:
        with path.open("r", encoding="utf-8", errors="ignore") as handle:
            return handle.read(limit)
    except OSError:
        return ""


def check_upload_safety(
    target: str,
    *,
    source_type: str,
    policy: dict[str, Any] | None = None,
) -> SafetyResult:
    reasons: list[str] = []
    if source_type not in {"file", "text"}:
        return SafetyResult(True, reasons)

    active_policy = policy or load_policy()
    allow_private_business = bool(active_policy.get("allow_private_business_documents", False))

    if source_type == "file":
        path = Path(target)
        suffixes = {suffix.lower() for suffix in path.suffixes}
        secret_extensions = suffixes & SECRET_EXTENSIONS
        if secret_extensions:
            reasons.append(f"extension de credencial: {', '.join(sorted(secret_extensions))}")

        private_extensions = suffixes & PRIVATE_BUSINESS_EXTENSIONS
        if private_extensions and not allow_private_business:
            reasons.append(f"extension privada: {', '.join(sorted(private_extensions))}")

        lowered_parts = {part.lower() for part in path.parts}
        blocked_parts = lowered_parts & BLOCKED_PATH_PARTS
        if blocked_parts:
            reasons.append(f"ruta sensible: {', '.join(sorted(blocked_parts))}")

        lowered_name = path.name.lower()
        for pattern in SECRET_NAME_PATTERNS:
            if pattern.lower() in lowered_name:
                reasons.append(f"nombre de credencial: {pattern}")
        if not allow_private_business:
            for pattern in PRIVATE_BUSINESS_NAME_PATTERNS:
                if pattern.lower() in lowered_name:
                    reasons.append(f"nombre privado: {pattern}")

        if path.exists() and path.stat().st_size <= 2_000_000:
            probe = _read_probe(path)
            for pattern in SECRET_CONTENT_PATTERNS:
                if pattern.search(probe):
                    reasons.append(f"contenido parece secreto: {pattern.pattern}")
    else:
        for pattern in SECRET_CONTENT_PATTERNS:
            if pattern.search(target):
                reasons.append(f"texto parece secreto: {pattern.pattern}")

    return SafetyResult(not reasons, reasons)


def extract_json_object(text: str) -> dict[str, Any]:
    decoder = json.JSONDecoder()
    for index, char in enumerate(text):
        if char != "{":
            continue
        try:
            parsed, _ = decoder.raw_decode(text[index:])
        except json.JSONDecodeError:
            continue
        if isinstance(parsed, dict):
            return parsed
    raise ValueError("No se pudo extraer JSON de la salida de nlm.")


def run_nlm_capture(args: list[str]) -> subprocess.CompletedProcess[str]:
    nlm = bridge.ensure_mcp_cli()
    return bridge.capture([str(nlm), *args])


def run_nlm_stream(args: list[str]) -> int:
    nlm = bridge.ensure_mcp_cli()
    return bridge.run([str(nlm), *args], check=False).returncode


def git_command() -> str:
    candidates = [
        "git",
        r"C:\Program Files\Git\cmd\git.exe",
        r"C:\Program Files\Git\bin\git.exe",
    ]
    for candidate in candidates:
        try:
            result = subprocess.run(
                [candidate, "--version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                check=False,
            )
        except OSError:
            continue
        if result.returncode == 0:
            return candidate
    return "git"


def create_notebook(title: str) -> str:
    result = run_nlm_capture(["notebook", "create", title, "--json"])
    if result.returncode != 0:
        raise RuntimeError(result.stderr or result.stdout)
    payload = extract_json_object(result.stdout)
    notebook_id = payload.get("notebookId") or payload.get("id") or payload.get("notebook_id")
    if not notebook_id:
        raise ValueError(f"nlm no devolvio notebook_id: {result.stdout}")
    return str(notebook_id)


def add_source_to_notebook(
    notebook_id: str,
    *,
    target: str,
    source_type: str,
    title: str | None,
    wait: bool,
    dry_run: bool,
) -> int:
    command = ["source", "add", notebook_id]
    if source_type == "file":
        command.extend(["--file", target])
    elif source_type == "url":
        command.extend(["--url", target])
    elif source_type == "youtube":
        command.extend(["--youtube", target])
    elif source_type == "text":
        command.extend(["--text", target])
    else:
        raise ValueError(f"Tipo de fuente no soportado: {source_type}")

    if title:
        command.extend(["--title", title])
    if wait:
        command.append("--wait")

    if dry_run:
        print("DRY RUN: nlm " + " ".join(command))
        return 0
    return run_nlm_stream(command)


def record_source(
    project: str,
    *,
    notebook_id: str,
    target: str,
    source_type: str,
    title: str | None = None,
    registry_path: Path = REGISTRY_PATH,
) -> None:
    """Registra (o refresca) una fuente en el registry del proyecto.

    Dedupe por ``target``: si la fuente ya estaba registrada se actualiza su
    ``added_at`` (y ``title``) en lugar de apilar entradas duplicadas — el
    ``added_at`` es lo que ``resync`` compara contra el mtime del archivo.

    Args:
        project: Clave del proyecto en el registry.
        notebook_id: Notebook asociado.
        target: Path/URL/texto subido.
        source_type: Tipo de fuente (file/url/youtube/text).
        title: Titulo usado al subir (para poder reemplazar la fuente remota).
        registry_path: Override del path del registry (tests).
    """
    data = load_registry(registry_path)
    project_entry = data.setdefault("projects", {}).setdefault(
        project,
        {
            "project": project,
            "notebook_id": notebook_id,
            "title": project,
            "sources": [],
        },
    )
    project_entry["notebook_id"] = notebook_id
    sources = project_entry.setdefault("sources", [])
    entry = next((s for s in sources if s.get("target") == target), None)
    if entry is None:
        entry = {"target": target, "type": source_type}
        sources.append(entry)
    entry["type"] = source_type
    entry["added_at"] = now_iso()
    if title:
        entry["title"] = title
    project_entry["updated_at"] = now_iso()
    data["active_project"] = project
    save_registry(data, registry_path)


def derive_source_title(target: str) -> str:
    """Deriva el titulo canonico de una fuente file (path con guiones, sin .md).

    Mismo criterio que las subidas batch: ``docs/dev-reference.md`` ->
    ``docs-dev-reference``. Permite reencontrar la fuente remota por titulo
    aunque el registry no lo tenga guardado (fuentes previas al campo title).
    """
    title = target.replace("\\", "/").strip("/").replace("/", "-")
    return title[:-3] if title.lower().endswith(".md") else title


def list_notebook_sources(notebook_id: str) -> list[dict[str, Any]]:
    """Lista las fuentes remotas de un notebook via ``nlm source list --json``.

    Returns:
        Lista de dicts con ``id`` y ``title``; vacia ante cualquier fallo
        (el caller degrada a re-agregar sin borrar la fuente vieja).
    """
    result = run_nlm_capture(["source", "list", notebook_id, "--json"])
    if result.returncode != 0:
        return []
    try:
        data = json.loads(result.stdout[result.stdout.index("[") :])
    except (ValueError, json.JSONDecodeError):
        return []
    return [s for s in data if isinstance(s, dict)] if isinstance(data, list) else []


def delete_notebook_sources(source_ids: list[str]) -> bool:
    """Borra fuentes remotas por id (``nlm source delete ... --confirm``)."""
    if not source_ids:
        return True
    result = run_nlm_capture(["source", "delete", *source_ids, "--confirm"])
    return result.returncode == 0


def resync_command(args: argparse.Namespace) -> int:
    """Re-sube las fuentes file cuyo archivo local cambio desde la ultima subida.

    Las sources de NotebookLM son snapshots: los archivos vivos
    (ESTADO_PROYECTO.md, MEMORY.md, ...) driftean. Este comando compara el
    mtime local contra el ``added_at`` del registry y reemplaza (borra + re-sube)
    solo las fuentes vencidas. Con ``--all`` re-sube todas las file sources.

    Returns:
        0 si todo OK (o nada para hacer), 1 si alguna re-subida fallo.
    """
    project = args.project or default_project_key()
    notebook_id, project = resolve_notebook_id(notebook_id=None, project=project)
    if not notebook_id:
        print(f"NotebookLM: proyecto '{project}' sin notebook asociado.")
        return 1

    data = load_registry()
    sources = data.get("projects", {}).get(project, {}).get("sources", [])
    # Dedupe por target preservando el added_at mas nuevo (registries viejos
    # apilaban duplicados antes del dedupe de record_source).
    by_target: dict[str, dict[str, Any]] = {}
    for src in sources:
        if src.get("type") == "file" and src.get("target"):
            by_target[str(src["target"])] = src

    stale: list[tuple[str, dict[str, Any]]] = []
    for target, src in sorted(by_target.items()):
        path = Path(target)
        if not path.exists():
            print(f"- omitido (no existe): {target}")
            continue
        added_raw = str(src.get("added_at", ""))
        try:
            added_ts = datetime.fromisoformat(added_raw).timestamp()
        except ValueError:
            added_ts = 0.0
        if args.all or path.stat().st_mtime > added_ts:
            stale.append((target, src))

    if not stale:
        print("NotebookLM: todas las fuentes file estan al dia.")
        return 0

    if args.dry_run:
        for target, _ in stale:
            print(f"DRY RUN: re-subiria {target}")
        return 0

    remote = list_notebook_sources(notebook_id)
    failures = 0
    for target, src in stale:
        safety = check_upload_safety(target, source_type="file")
        if not safety.allowed and not args.force_sensitive:
            print(f"- omitido (guard de sensibilidad, usar --force-sensitive): {target}")
            continue
        title = str(src.get("title") or derive_source_title(target))
        base = Path(target).name
        old_ids = [
            str(s["id"])
            for s in remote
            if s.get("id") and str(s.get("title", "")) in {title, base, Path(base).stem}
        ]
        if old_ids and not delete_notebook_sources(old_ids):
            print(f"- aviso: no se pudo borrar la version vieja de {target} (quedara duplicada)")
        rc = add_source_to_notebook(
            notebook_id,
            target=target,
            source_type="file",
            title=title,
            wait=False,
            dry_run=False,
        )
        if rc == 0:
            record_source(
                project, notebook_id=notebook_id, target=target, source_type="file", title=title
            )
            print(f"- re-subido: {target}")
        else:
            failures += 1
            print(f"- FALLO re-subida: {target}")
    return 1 if failures else 0


def add_command(args: argparse.Namespace) -> int:
    source_type = classify_source(args.target, text_mode=args.text)
    safety = check_upload_safety(args.target, source_type=source_type)
    if not safety.allowed and not args.force_sensitive:
        print("NotebookLM: subida bloqueada por credenciales o archivos tecnicos locales.")
        for reason in safety.reasons:
            print(f"- {reason}")
        print("Si realmente queres subirlo, reintenta con --force-sensitive.")
        return 3

    project = args.project or default_project_key()
    notebook_id = args.notebook_id
    if args.new:
        if args.dry_run:
            notebook_id = "DRY-RUN-NOTEBOOK-ID"
            print(f"DRY RUN: nlm notebook create {args.new!r} --json")
        else:
            notebook_id = create_notebook(args.new)
            set_project(project, notebook_id, title=args.new)
        action = "se asociaria a" if args.dry_run else "asociado a"
        print(f"Proyecto '{project}' {action} notebook {notebook_id}")
    else:
        notebook_id, project = resolve_notebook_id(notebook_id=notebook_id, project=args.project)
        if args.notebook_id and not args.dry_run:
            set_project(project, notebook_id, title=args.project or project)

    if not notebook_id:
        raise ValueError("No se pudo resolver notebook_id.")

    rc = add_source_to_notebook(
        notebook_id,
        target=args.target,
        source_type=source_type,
        title=args.title,
        wait=not args.no_wait,
        dry_run=args.dry_run,
    )
    if rc == 0 and not args.dry_run:
        record_source(
            project,
            notebook_id=notebook_id,
            target=args.target,
            source_type=source_type,
            title=args.title,
        )
        print(f"NotebookLM: fuente registrada en proyecto '{project}' ({notebook_id}).")
    elif rc == 0:
        print(f"NotebookLM: dry-run OK para proyecto '{project}' ({notebook_id}).")
    return rc


def ask_command(args: argparse.Namespace) -> int:
    question = " ".join(args.question).strip()
    if not question:
        raise ValueError("Falta la pregunta.")
    notebook_id, project = resolve_notebook_id(notebook_id=args.notebook_id, project=args.project)
    command = ["notebook", "query", notebook_id, question, "--timeout", str(args.timeout)]
    if args.json:
        command.append("--json")
    print(f"NotebookLM project: {project}")
    print(f"NotebookLM notebook: {notebook_id}")
    return run_nlm_stream(command)


def project_command(args: argparse.Namespace) -> int:
    if args.project_command == "set":
        set_project(args.project, args.notebook_id, title=args.title or args.project)
        print(f"Proyecto '{args.project}' asociado a notebook {args.notebook_id}.")
        return 0

    data = load_registry()
    if args.project_command == "active":
        project = args.project or data.get("active_project") or default_project_key()
        if project not in data.get("projects", {}):
            raise ValueError(f"Proyecto sin notebook asociado: {project}")
        data["active_project"] = project
        save_registry(data)
        print(f"Proyecto activo: {project}")
        return 0

    projects = data.get("projects", {})
    if not projects:
        print("No hay proyectos asociados todavia.")
        return 0
    print("NotebookLM project registry:")
    print(f"Active: {data.get('active_project')}")
    for name, entry in sorted(projects.items()):
        marker = "*" if name == data.get("active_project") else "-"
        print(f"{marker} {name}: {entry.get('notebook_id')} ({entry.get('title', name)})")
    return 0


def validate_json_file(path: Path) -> tuple[bool, str]:
    try:
        with path.open("r", encoding="utf-8") as handle:
            json.load(handle)
        return True, "OK"
    except Exception as exc:  # noqa: BLE001 - diagnostic boundary
        return False, str(exc)


def doctor_command(_: argparse.Namespace) -> int:
    rc = 0
    print("NotebookLM unified doctor")
    print()

    auth = run_nlm_capture(["login", "--check"])
    print("Auth:")
    print(auth.stdout.strip() or auth.stderr.strip())
    if auth.returncode != 0:
        rc = 1

    notebooks = run_nlm_capture(["notebook", "list", "--quiet"])
    notebook_ids = [line for line in notebooks.stdout.splitlines() if line.strip()]
    print()
    print(f"Notebooks accesibles: {len(notebook_ids)}")
    if notebooks.returncode != 0:
        print(notebooks.stderr or notebooks.stdout)
        rc = 1

    setup = run_nlm_capture(["setup", "list"])
    print()
    print("Clientes MCP:")
    print(setup.stdout.strip() or setup.stderr.strip())
    if setup.returncode != 0:
        rc = 1

    print()
    print("JSON MCP:")
    for path in [
        ROOT / ".mcp.json",
        ROOT / ".vscode" / "mcp.json",
        ROOT / ".cursor" / "mcp.json",
        ROOT / ".vscode" / "cline_mcp_settings.json",
    ]:
        ok, message = validate_json_file(path)
        print(f"- {path}: {message}")
        if not ok:
            rc = 1

    data = load_registry()
    policy = load_policy()
    print()
    print(f"Registry: {REGISTRY_PATH}")
    print(f"Active project: {data.get('active_project')}")
    print(f"Projects: {len(data.get('projects', {}))}")
    print(f"Policy: {policy.get('profile')}")
    print(f"Private business docs: {policy.get('allow_private_business_documents')}")
    return rc


def candidates_command(_: argparse.Namespace) -> int:
    result = subprocess.run(
        [git_command(), "status", "--short"],
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    if result.returncode != 0:
        print(result.stderr.strip())
        return result.returncode

    candidates: list[str] = []
    for line in result.stdout.splitlines():
        path_text = line[3:].strip()
        if " -> " in path_text:
            path_text = path_text.split(" -> ", 1)[1]
        path = ROOT / path_text
        source_type = "file" if path.exists() else "text"
        if path.suffix.lower() in {
            ".docx",
            ".md",
            ".pdf",
            ".pptx",
            ".txt",
            ".xls",
            ".xlsm",
            ".xlsx",
        }:
            safety = check_upload_safety(str(path), source_type=source_type)
            if safety.allowed:
                candidates.append(path_text)

    if not candidates:
        print("No hay candidatos seguros obvios para NotebookLM.")
        return 0
    print("Candidatos seguros para ofrecer en /finalize:")
    for path in candidates:
        print(f"- {path}")
    return 0


NOTEBOOKLM_COMMAND_FILES = [
    "notebooklm-add.md",
    "notebooklm-ask.md",
    "notebooklm-doctor.md",
    "notebooklm-project.md",
]

AUTO_RECALL_HOOK_COMMAND = (
    'cd "${CLAUDE_PROJECT_DIR:-.}" && python -X utf8 ".agent/scripts/notebooklm_auto_recall.py"'
)

FINALIZE_NOTEBOOKLM_BLOCK = """\

<!-- NOTEBOOKLM-FINALIZE-START -->
## NotebookLM opcional

Si la tarea produjo documentacion, reportes, PDFs, specs o resumenes utiles,
ofrece subirlos al notebook del proyecto. En este repo privado se permiten
documentos internos de negocio; solo evita credenciales tecnicas reales como
tokens, cookies, claves privadas o archivos de entorno.

```bash
python .agent/scripts/notebooklm_workflow.py candidates
python .agent/scripts/notebooklm_workflow.py add --project <proyecto> <archivo>
```
<!-- NOTEBOOKLM-FINALIZE-END -->
"""


def copy_if_changed(source: Path, target: Path) -> bool:
    target.parent.mkdir(parents=True, exist_ok=True)
    source_bytes = source.read_bytes()
    if target.exists() and target.read_bytes() == source_bytes:
        return False
    target.write_bytes(source_bytes)
    shutil.copystat(source, target, follow_symlinks=True)
    return True


def patch_finalize_command(target_root: Path) -> bool:
    finalize = target_root / ".claude" / "commands" / "finalize.md"
    if not finalize.exists():
        return False
    text = finalize.read_text(encoding="utf-8", errors="replace")
    if "NOTEBOOKLM-FINALIZE-START" in text:
        return False
    finalize.write_text(
        text.rstrip() + FINALIZE_NOTEBOOKLM_BLOCK + "\n", encoding="utf-8", newline="\n"
    )
    return True


def patch_claude_settings_auto_recall(target_root: Path) -> bool:
    settings = target_root / ".claude" / "settings.json"
    data: dict[str, Any]
    if settings.exists():
        with settings.open("r", encoding="utf-8") as handle:
            loaded = json.load(handle)
        if not isinstance(loaded, dict):
            raise ValueError(f"Invalid Claude settings shape: {settings}")
        data = loaded
    else:
        data = {}

    hooks = data.setdefault("hooks", {})
    if not isinstance(hooks, dict):
        raise ValueError(f"Invalid hooks shape: {settings}")
    entries = hooks.setdefault("UserPromptSubmit", [])
    if not isinstance(entries, list):
        raise ValueError(f"Invalid UserPromptSubmit hooks shape: {settings}")

    for entry in entries:
        if not isinstance(entry, dict):
            continue
        for hook in entry.get("hooks", []):
            command = str(hook.get("command", "")) if isinstance(hook, dict) else ""
            if "notebooklm_auto_recall.py" in command or "user_prompt_submit.py" in command:
                return False

    entries.append(
        {
            "matcher": "",
            "hooks": [
                {
                    "type": "command",
                    "command": AUTO_RECALL_HOOK_COMMAND,
                    "timeout": 35000,
                }
            ],
        }
    )
    settings.parent.mkdir(parents=True, exist_ok=True)
    with settings.open("w", encoding="utf-8", newline="\n") as handle:
        json.dump(data, handle, ensure_ascii=False, indent=2)
        handle.write("\n")
    return True


def inject_command(args: argparse.Namespace) -> int:
    target_root = Path(args.target).expanduser().resolve()
    if not target_root.exists() or not target_root.is_dir():
        raise ValueError(f"Target no es un directorio valido: {target_root}")

    copied: list[str] = []
    unchanged: list[str] = []
    created: list[str] = []

    script_files = [
        SCRIPT_DIR / "notebooklm_workflow.py",
        SCRIPT_DIR / "notebooklm_bridge.py",
        SCRIPT_DIR / "notebooklm_auto_recall.py",
    ]
    for source in script_files:
        target = target_root / ".agent" / "scripts" / source.name
        changed = copy_if_changed(source, target)
        (copied if changed else unchanged).append(str(target.relative_to(target_root)))

    for name in NOTEBOOKLM_COMMAND_FILES:
        source = ROOT / ".claude" / "commands" / name
        target = target_root / ".claude" / "commands" / name
        changed = copy_if_changed(source, target)
        (copied if changed else unchanged).append(str(target.relative_to(target_root)))

    policy_target = target_root / ".agent" / "notebooklm" / "policy.json"
    if not policy_target.exists():
        save_policy(load_policy(), policy_target)
        created.append(str(policy_target.relative_to(target_root)))
    else:
        unchanged.append(str(policy_target.relative_to(target_root)))

    registry_target = target_root / ".agent" / "notebooklm" / "projects.json"
    if not registry_target.exists():
        save_registry(
            {
                "version": 1,
                "active_project": target_root.name,
                "projects": {},
            },
            registry_target,
        )
        created.append(str(registry_target.relative_to(target_root)))
    else:
        unchanged.append(str(registry_target.relative_to(target_root)))

    finalize_patched = patch_finalize_command(target_root)
    if finalize_patched:
        copied.append(".claude/commands/finalize.md")

    auto_recall_patched = patch_claude_settings_auto_recall(target_root)
    if auto_recall_patched:
        copied.append(".claude/settings.json")

    payload = {
        "success": True,
        "target": str(target_root),
        "copied": copied,
        "created": created,
        "unchanged": unchanged,
        "finalize_patched": finalize_patched,
        "auto_recall_patched": auto_recall_patched,
        "policy": load_policy().get("profile"),
    }
    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(f"NotebookLM injector OK: {target_root}")
        print(f"Copiados/actualizados: {len(copied)}")
        print(f"Creados: {len(created)}")
        print(f"Sin cambios: {len(unchanged)}")
        print(f"Finalize parcheado: {'si' if finalize_patched else 'no'}")
        print(f"Auto-recall parcheado: {'si' if auto_recall_patched else 'no'}")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="NotebookLM guarded workflows.")
    subparsers = parser.add_subparsers(dest="command", required=True)

    add = subparsers.add_parser("add", help="Upload a file/URL/text to a project notebook")
    add.add_argument("target", help="File path, URL, YouTube URL, or text")
    add.add_argument("--new", help="Create a new notebook with this title first")
    add.add_argument("--project", help="Project key for registry lookup")
    add.add_argument("--notebook-id", help="Use a specific notebook ID")
    add.add_argument("--title", help="Source title")
    add.add_argument("--text", action="store_true", help="Treat target as copied text")
    add.add_argument("--no-wait", action="store_true", help="Do not wait for source processing")
    add.add_argument("--force-sensitive", action="store_true", help="Override safety guard")
    add.add_argument("--dry-run", action="store_true", help="Print nlm commands without uploading")
    add.set_defaults(func=add_command)

    resync = subparsers.add_parser(
        "resync", help="Re-upload file sources whose local file changed since last upload"
    )
    resync.add_argument("--project", help="Project key for registry lookup")
    resync.add_argument("--all", action="store_true", help="Re-upload every file source")
    resync.add_argument("--dry-run", action="store_true", help="List stale sources only")
    resync.add_argument("--force-sensitive", action="store_true", help="Override safety guard")
    resync.set_defaults(func=resync_command)

    ask = subparsers.add_parser("ask", help="Ask a project notebook")
    ask.add_argument("question", nargs=argparse.REMAINDER, help="Question to ask")
    ask.add_argument("--project", help="Project key for registry lookup")
    ask.add_argument("--notebook-id", help="Use a specific notebook ID")
    ask.add_argument("--timeout", type=float, default=120)
    ask.add_argument("--json", action="store_true")
    ask.set_defaults(func=ask_command)

    project = subparsers.add_parser("project", help="Manage project registry")
    project_sub = project.add_subparsers(dest="project_command", required=True)
    project_sub.add_parser("list").set_defaults(func=project_command)
    active = project_sub.add_parser("active")
    active.add_argument("project", nargs="?")
    active.set_defaults(func=project_command)
    set_parser = project_sub.add_parser("set")
    set_parser.add_argument("project")
    set_parser.add_argument("notebook_id")
    set_parser.add_argument("--title")
    set_parser.set_defaults(func=project_command)

    doctor = subparsers.add_parser("doctor", help="Unified NotebookLM health check")
    doctor.set_defaults(func=doctor_command)

    candidates = subparsers.add_parser("candidates", help="List safe finalize upload candidates")
    candidates.set_defaults(func=candidates_command)

    inject = subparsers.add_parser("inject", help="Install NotebookLM commands into a target repo")
    inject.add_argument("--target", required=True, help="Target repository/app directory")
    inject.add_argument("--json", action="store_true", help="Emit machine-readable JSON")
    inject.set_defaults(func=inject_command)

    return parser


def main(argv: list[str] | None = None) -> int:
    configure_utf8_output()
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except Exception as exc:  # noqa: BLE001 - CLI boundary
        print(f"NotebookLM workflow error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
