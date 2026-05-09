#!/usr/bin/env python3
"""Sync curated OpenAI Codex skills into $CODEX_HOME/skills.

Instala skills desde https://github.com/openai/skills para que Codex
las tenga disponibles globalmente. Puede seleccionar un subconjunto
"smart" según el stack detectado del proyecto.
"""

from __future__ import annotations

import argparse
import json
import logging
import os
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("sync_codex_skills")

OPENAI_SKILLS_REPO = "openai/skills"
OPENAI_SKILLS_REF = "main"
OPENAI_SKILLS_CURATED_ROOT = "skills/.curated"
GITHUB_API_ROOT = f"https://api.github.com/repos/{OPENAI_SKILLS_REPO}/contents"
DEFAULT_TIMEOUT_SECONDS = 20
DEFAULT_BASE_SKILLS = (
    "doc",
    "openai-docs",
    "security-best-practices",
)

try:
    from app_intelligence_pipeline import quick_analyze

    INTELLIGENCE_AVAILABLE = True
except ImportError:
    INTELLIGENCE_AVAILABLE = False


def _read_json_url(url: str) -> Any:
    request = Request(
        url,
        headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": "Antigravity-Codex-Skill-Sync",
        },
    )
    with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:  # noqa: S310
        return json.loads(response.read().decode("utf-8"))


def _download_bytes(url: str) -> bytes:
    request = Request(url, headers={"User-Agent": "Antigravity-Codex-Skill-Sync"})
    with urlopen(request, timeout=DEFAULT_TIMEOUT_SECONDS) as response:  # noqa: S310
        return response.read()


def get_codex_home(explicit_home: str | None = None) -> Path:
    """Resuelve el CODEX_HOME efectivo."""
    if explicit_home:
        return Path(explicit_home).expanduser().resolve()
    env_home = os.environ.get("CODEX_HOME")
    if env_home:
        return Path(env_home).expanduser().resolve()
    return (Path.home() / ".codex").resolve()


def _safe_stack(target_dir: Path) -> dict[str, Any]:
    """Detecta stack usando la pipeline existente o un fallback simple."""
    stack: dict[str, Any] = {
        "language": "unknown",
        "framework": "",
        "testing": [],
        "ci": "",
        "containerization": "",
    }

    if INTELLIGENCE_AVAILABLE:
        try:
            profile = quick_analyze(target_dir)
            if isinstance(profile.stack, dict):
                stack.update(profile.stack)
        except Exception as exc:
            logger.warning(f"⚠️  [Codex Skills] quick_analyze falló, usando fallback: {exc}")

    if stack["language"] == "unknown":
        if (target_dir / "pyproject.toml").exists() or (target_dir / "requirements.txt").exists():
            stack["language"] = "python"
        if (target_dir / "package.json").exists():
            stack["language"] = "mixed" if stack["language"] != "unknown" else "typescript"
    if not stack["ci"] and (target_dir / ".github" / "workflows").is_dir():
        stack["ci"] = "github-actions"
    if not stack["containerization"] and (
        (target_dir / "Dockerfile").exists() or (target_dir / "docker-compose.yml").exists()
    ):
        stack["containerization"] = "docker"
    if not isinstance(stack.get("testing"), list):
        stack["testing"] = []
    return stack


def list_curated_skills(ref: str = OPENAI_SKILLS_REF) -> list[str]:
    """Lista las skills curadas disponibles en openai/skills."""
    url = f"{GITHUB_API_ROOT}/{OPENAI_SKILLS_CURATED_ROOT}?ref={ref}"
    data = _read_json_url(url)
    if not isinstance(data, list):
        raise ValueError("Respuesta inválida del API de GitHub para skills curadas")
    return sorted(item["name"] for item in data if item.get("type") == "dir")


def recommend_skills(target_dir: Path, curated_skills: set[str], profile: str) -> list[str]:
    """Selecciona skills de Codex según el stack del proyecto."""
    if profile == "none":
        return []
    if profile == "all-curated":
        return sorted(curated_skills)

    stack = _safe_stack(target_dir)
    language = str(stack.get("language", "")).lower()
    framework = str(stack.get("framework", "")).lower()
    testing = {str(item).lower() for item in stack.get("testing", [])}
    ci = str(stack.get("ci", "")).lower()

    recommended: set[str] = set(DEFAULT_BASE_SKILLS)

    if language in {"javascript", "typescript", "mixed"} or framework:
        recommended.add("frontend-skill")

    if "playwright" in testing:
        recommended.update({"playwright", "playwright-interactive"})

    if framework.startswith("next") or (target_dir / "vercel.json").exists():
        recommended.add("vercel-deploy")
    if (target_dir / "wrangler.toml").exists():
        recommended.add("cloudflare-deploy")
    if (target_dir / "render.yaml").exists() or (target_dir / "render.yml").exists():
        recommended.add("render-deploy")

    if ci == "github-actions":
        recommended.update({"gh-address-comments", "gh-fix-ci", "yeet"})

    has_dotnet = any(target_dir.glob("*.sln")) or any(target_dir.rglob("*.csproj"))
    if has_dotnet:
        recommended.add("aspnet-core")
    if any("winui" in path.name.lower() for path in target_dir.rglob("*.csproj")):
        recommended.add("winui-app")

    return sorted(skill for skill in recommended if skill in curated_skills)


def _download_directory(api_path: str, destination: Path, ref: str) -> None:
    """Descarga recursivamente un directorio desde GitHub Contents API."""
    url = f"{GITHUB_API_ROOT}/{api_path}?ref={ref}"
    entries = _read_json_url(url)
    if not isinstance(entries, list):
        raise ValueError(f"Respuesta inválida para {api_path}")

    destination.mkdir(parents=True, exist_ok=True)
    for entry in entries:
        entry_type = entry.get("type")
        entry_name = entry.get("name")
        if not entry_name:
            continue
        target = destination / entry_name

        if entry_type == "dir":
            path = entry.get("path")
            if not isinstance(path, str):
                continue
            _download_directory(path, target, ref)
            continue

        if entry_type != "file":
            continue

        download_url = entry.get("download_url")
        if not isinstance(download_url, str):
            continue
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(_download_bytes(download_url))


def write_sync_manifest(
    target_dir: Path,
    *,
    codex_home: Path,
    profile: str,
    stack: dict[str, Any],
    selected: list[str],
    installed: list[str],
    skipped: list[str],
    errors: list[str],
) -> Path:
    """Guarda un manifiesto del resultado para trazabilidad de la inyección."""
    manifest_path = target_dir / ".antigravity" / "codex-skills.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "source": f"https://github.com/{OPENAI_SKILLS_REPO}",
        "ref": OPENAI_SKILLS_REF,
        "profile": profile,
        "installedAt": datetime.now(UTC).isoformat(),
        "codexHome": str(codex_home),
        "stack": stack,
        "selected": selected,
        "installed": installed,
        "skipped": skipped,
        "errors": errors,
    }
    manifest_path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")
    return manifest_path


def sync_codex_skills(
    target_dir: Path,
    *,
    codex_home: str | None = None,
    profile: str = "smart",
    dry_run: bool = False,
    requested_skills: list[str] | None = None,
    write_manifest: bool = True,
) -> dict[str, Any]:
    """Instala skills curadas de openai/skills para Codex."""
    codex_home_path = get_codex_home(codex_home)
    skills_root = codex_home_path / "skills"
    curated = set(list_curated_skills())

    if requested_skills:
        selected = sorted(skill for skill in requested_skills if skill in curated)
        missing = sorted(skill for skill in requested_skills if skill not in curated)
    else:
        selected = recommend_skills(target_dir, curated, profile)
        missing = []

    installed: list[str] = []
    skipped: list[str] = []
    errors: list[str] = []

    if not dry_run:
        skills_root.mkdir(parents=True, exist_ok=True)

    for skill_name in selected:
        destination = skills_root / skill_name
        if destination.exists():
            skipped.append(skill_name)
            continue
        if dry_run:
            installed.append(skill_name)
            continue
        try:
            _download_directory(
                api_path=f"{OPENAI_SKILLS_CURATED_ROOT}/{skill_name}",
                destination=destination,
                ref=OPENAI_SKILLS_REF,
            )
            installed.append(skill_name)
        except (HTTPError, URLError, ValueError, OSError) as exc:
            errors.append(f"{skill_name}: {exc}")
            logger.error(f"❌ [Codex Skills] Error instalando {skill_name}: {exc}")

    stack = _safe_stack(target_dir)
    if missing:
        errors.extend(f"{skill}: no existe en openai/skills/.curated" for skill in missing)

    manifest_path: str | None = None
    if write_manifest and not dry_run:
        manifest = write_sync_manifest(
            target_dir,
            codex_home=codex_home_path,
            profile=profile,
            stack=stack,
            selected=selected,
            installed=installed,
            skipped=skipped,
            errors=errors,
        )
        manifest_path = str(manifest)

    return {
        "profile": profile,
        "codex_home": str(codex_home_path),
        "selected": selected,
        "installed": installed,
        "skipped": skipped,
        "errors": errors,
        "manifest": manifest_path,
        "stack": stack,
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Sync curated openai/skills into $CODEX_HOME/skills for Codex"
    )
    parser.add_argument("target_dir", help="Project directory used for smart skill selection")
    parser.add_argument(
        "--codex-home",
        help="Override CODEX_HOME (default: env CODEX_HOME or ~/.codex)",
    )
    parser.add_argument(
        "--profile",
        choices=["smart", "all-curated", "none"],
        default="smart",
        help="Skill selection profile (default: smart)",
    )
    parser.add_argument(
        "--only",
        help="Comma-separated curated skill names to install explicitly",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be installed without writing files",
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output result as JSON",
    )
    args = parser.parse_args()

    target_dir = Path(args.target_dir).resolve()
    if not target_dir.exists():
        logger.error(f"❌ Target directory does not exist: {target_dir}")
        sys.exit(1)

    requested = (
        [item.strip() for item in args.only.split(",") if item.strip()] if args.only else None
    )

    try:
        result = sync_codex_skills(
            target_dir=target_dir,
            codex_home=args.codex_home,
            profile=args.profile,
            dry_run=args.dry_run,
            requested_skills=requested,
        )
    except (HTTPError, URLError, ValueError, OSError) as exc:
        logger.error(f"❌ [Codex Skills] Sync falló: {exc}")
        sys.exit(1)

    if args.json:
        print(json.dumps(result, indent=2, ensure_ascii=False))
        return

    logger.info("")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    logger.info(f"✅ Skills seleccionadas: {len(result['selected'])}")
    logger.info(f"   Instaladas: {len(result['installed'])}")
    logger.info(f"   Omitidas (ya existían): {len(result['skipped'])}")
    logger.info(f"   Errores: {len(result['errors'])}")
    logger.info(f"   CODEX_HOME: {result['codex_home']}")
    logger.info("━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━")
    if result["installed"]:
        logger.info("")
        logger.info("Reinicia Codex para que detecte las nuevas skills.")


if __name__ == "__main__":
    main()
