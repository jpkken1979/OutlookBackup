#!/usr/bin/env python3
"""Normaliza IDENTITY.md de los 116 agentes del ecosistema.

Garantiza:
1. Frontmatter YAML estandarizado con: name, tier (numerico 1-12), description,
   tools, model, category, capabilities
2. Tier numerico segun el sistema de 12 tiers del ecosistema
3. Seccion "Capacidades del Ecosistema" agregada al final con tools relevantes
   segun categoria (Brain, Watcher, Delta Reader, Context Engine, Memory,
   magic-21st para ui-ux, etc.)
4. Preserva todo el contenido textual existente del agente

Uso:
    py .agent/scripts/normalize_agents.py --dry-run    # ver cambios sin aplicar
    py .agent/scripts/normalize_agents.py --apply      # aplicar cambios

v1.0 - 2026-05-17
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from typing import Any

# yaml es opcional; si no esta, usamos un formatter manual
try:
    import yaml  # type: ignore[import-not-found]

    HAS_YAML = True
except ImportError:
    HAS_YAML = False

REPO_ROOT = Path(__file__).resolve().parents[2]
AGENTS_DIR = REPO_ROOT / ".agent" / "agents"

# Sistema de 12 tiers del ecosistema
TIER_MAP: dict[str, int] = {
    "orchestration": 1,
    "core dev": 2,
    "core development": 2,
    "core-dev": 2,
    "quality": 3,
    "security": 4,
    "devops": 5,
    "specialized": 6,
    "uns": 7,
    "uns enterprise": 7,
    "intelligence": 8,
    "system": 9,
    "data": 10,
    "data & ml": 10,
    "data-ml": 10,
    "desktop": 11,
    "content": 12,
}

# Categoria por agente (manualmente curada para corregir inferencia automatica)
AGENT_CATEGORY: dict[str, str] = {
    # Orchestration
    "agent-composer": "orchestration",
    "analyst": "orchestration",
    "architect": "orchestration",
    "critic": "orchestration",
    "explorer": "orchestration",
    "finalizer": "orchestration",
    "intent-router": "orchestration",
    "planner": "orchestration",
    "ralph": "orchestration",
    "stuck": "orchestration",
    "activator": "orchestration",
    "local-executor": "orchestration",
    "inteligente-shain-agent": "orchestration",
    "skill-architect": "orchestration",
    # Core dev
    "api-designer": "core-dev",
    "backend-specialist": "core-dev",
    "feature-dev": "core-dev",
    "frontend-specialist": "core-dev",
    "react-specialist": "core-dev",
    "refactor": "core-dev",
    "migrator": "core-dev",
    "app-creator": "core-dev",
    "debugger": "core-dev",
    "interactive-debugger": "core-dev",
    "schema-mapper": "core-dev",
    "self-improver": "core-dev",
    "tracer": "core-dev",
    # Quality
    "a11y": "quality",
    "code-reviewer": "quality",
    "performance-checker": "quality",
    "performance-optimizer": "quality",
    "quality-scorer": "quality",
    "regression-detector": "quality",
    "self-verifier": "quality",
    "test-engineer": "quality",
    "test-runner": "quality",
    "verifier": "quality",
    "api-tester": "quality",
    "load-testing-engineer": "quality",
    "code-archaeologist": "quality",
    # Security
    "app-auditor": "security",
    "ce-security-sentinel": "security",
    "compliance-auditor": "security",
    "dependency-auditor": "security",
    "penetration-tester": "security",
    "security-auditor": "security",
    "security-scanner": "security",
    # DevOps
    "cost-optimizer": "devops",
    "cost-predictor": "devops",
    "dead-code-finder": "devops",
    "debate-facilitator": "devops",
    "devops-engineer": "devops",
    "file-organizer": "devops",
    "git-analyst": "devops",
    "git-orchestrator": "devops",
    "health-monitor": "devops",
    "infrastructure-architect": "devops",
    "observability-engineer": "devops",
    "report-generator": "devops",
    # Specialized (genuinos: integraciones, frameworks especificos)
    "api-gateway-specialist": "specialized",
    "dependency": "specialized",
    "graphql-specialist": "specialized",
    "integration-hub": "specialized",
    "mcp-integrator": "specialized",
    "realtime-specialist": "specialized",
    "serverless-architect": "specialized",
    # Core-dev reclassificados (mobile/game dev son codigo core)
    "mobile-developer": "core-dev",
    "game-developer": "core-dev",
    # DevOps reclassificados (operations)
    "notification-manager": "devops",
    # UNS reclassificados (scheduler es para dispatch team UNS)
    "scheduler": "uns",
    # Intelligence reclassificados
    "prompt-optimizer": "intelligence",
    # Content reclassificados (UI/UX, docs, i18n, SEO)
    "magic-21st-specialist": "content",
    "cli-designer": "content",
    "design-system-architect": "content",
    "documentation-writer": "content",
    "doc-generator": "content",
    "docusaurus-expert": "content",
    "i18n": "content",
    "seo-specialist": "content",
    # UNS Enterprise (dispatch japones, HR, kobetsu, etc.)
    "haken-document-specialist": "uns",
    "haken-system-architect": "uns",
    "japanese-ocr-extractor": "uns",
    "uns-hr-specialist": "uns",
    "face-photo-detector": "uns",
    # Intelligence
    "brain-curator": "intelligence",
    "mem0-manager": "intelligence",
    "cognitive-analyst": "intelligence",
    "context-guardian": "intelligence",
    "context-keeper": "intelligence",
    "emotion-responder": "intelligence",
    "feedback-refiner": "intelligence",
    "learning-engine": "intelligence",
    "mentor": "intelligence",
    "user-preference-learner": "intelligence",
    "plan-optimizer": "intelligence",
    "multi-file-coordinator": "intelligence",
    "bot-optimizer": "intelligence",
    "content-curator": "intelligence",
    "content-improver": "intelligence",
    # System
    "ce-demo-reel": "system",
    "repo-analyzer": "system",
    # Data & ML
    "data-engineer": "data",
    "data-sync": "data",
    "database-architect": "data",
    "ml-engineer": "data",
    "sqlite-persister": "data",
    # Desktop (Nexus + Tauri + Vite)
    "tauri-architect": "desktop",
    "tauri-backend": "desktop",
    "tauri-frontend": "desktop",
    "vite-architect": "desktop",
    "vite-performance": "desktop",
    "vite-plugin-developer": "desktop",
    # Content / Docs / UI/UX
    "ce-figma-design-sync": "content",
    "ui-orchestrator": "content",
    "ui-ux-designer": "content",
    "excel-parser": "content",
    "excel-specialist": "content",
    "document-processor": "content",
    "product-manager": "content",
}

# Tools especificos por categoria (suplementan los base Read/Glob/Grep/Task)
TOOLS_BY_CATEGORY: dict[str, list[str]] = {
    "orchestration": ["Read", "Glob", "Grep", "Task", "WebSearch"],
    "core-dev": ["Read", "Write", "Edit", "Glob", "Grep", "Bash", "Task"],
    "quality": ["Read", "Glob", "Grep", "Bash", "Task"],
    "security": ["Read", "Glob", "Grep", "WebSearch", "Bash", "Task"],
    "devops": ["Read", "Write", "Edit", "Glob", "Grep", "Bash", "Task"],
    "specialized": ["Read", "Glob", "Grep", "WebSearch", "Task"],
    "uns": ["Read", "Write", "Edit", "Glob", "Grep", "Task"],
    "intelligence": ["Read", "Glob", "Grep", "Task", "WebSearch"],
    "system": ["Read", "Glob", "Grep", "Bash", "Task"],
    "data": ["Read", "Write", "Edit", "Glob", "Grep", "Bash", "Task"],
    "desktop": ["Read", "Write", "Edit", "Glob", "Grep", "Bash", "Task"],
    "content": ["Read", "Write", "Edit", "Glob", "Grep", "WebSearch", "Task"],
}

# Mapeo categoria -> tier numerico
CATEGORY_TO_TIER: dict[str, int] = {
    "orchestration": 1,
    "core-dev": 2,
    "quality": 3,
    "security": 4,
    "devops": 5,
    "specialized": 6,
    "uns": 7,
    "intelligence": 8,
    "system": 9,
    "data": 10,
    "desktop": 11,
    "content": 12,
}

# Capacidades del ecosistema universales (todos los agentes pueden usarlas)
ECOSYSTEM_CAPABILITIES_UNIVERSAL = """## Capacidades del Ecosistema

### Memoria y conocimiento
- **Brain Network** (`.agent/brain/`): `brain.query()`, `brain.ingest()`, cross-refs y decay temporal
- **Memoria mem0** (gateway `:4747`): `/v1/mem0/recall`, `/v1/mem0/store` para recall semantico
- **Memoria markdown** (`.claude/memory/*.md`): decisiones, bugfixes, patrones versionados en git

### Lectura eficiente
- **Delta Reader** (`antigravity-delta-reader` MCP): para archivos >50 lineas que se releen
- **Context Engine** (`ANTIGRAVITY_CONTEXT_ENGINE`): brain_aware, delta_aware, composite, summarizing

### Procesos y monitoreo
- **Watcher** (`antigravity-watcher` MCP): `watch_spawn` para procesos largos con matching reactivo
- **Gateway local** (`http://127.0.0.1:4747`): observabilidad, metricas, SSE stream
"""

# Capacidades adicionales por categoria
ECOSYSTEM_CAPABILITIES_BY_CATEGORY: dict[str, str] = {
    "content": """
### Stack UI/UX (categoria content)
- **magic-21st** MCP: generador de componentes UI con IA (requiere `MAGIC_21ST_API_KEY`)
- **ui-ux-pro-max** skill: 85 styles, 161 paletas, 25 chart types data-driven
- **shadcn-ui-components** skill + Tailwind v4 + Framer Motion
- Slash `/ui` orquesta el stack completo
""",
    "data": """
### Data & ML
- **antigravity-excel** MCP: lectura y escritura Excel
- **excel-engine** skills custom: openpyxl backend + edge cases
- **SQLite WAL mode** estandar para concurrencia
""",
    "desktop": """
### Desktop (Tauri 2 + React 19 + Vite 8)
- **antigravity-ui** MCP: inspector UI del ecosistema
- Tauri commands en `nexus-app/src-tauri/src/commands/`
- TypeScript strict + Tailwind v4 + Framer Motion
- ESLint flat config + Vitest
""",
    "security": """
### Security
- **secrets-scanner** skill: 19 patterns + Shannon entropy + pre-commit hooks
- **bandit** + custom MCP scanners via `make scan-mcp`
- OWASP Top 10 baseline + threat modeling
""",
    "quality": """
### Quality
- **react-doctor** skill (`/jpread`): a11y, memory leaks, motion, paleta
- **mutmut** mutation testing + **Hypothesis** property-based
- `make test-cov`, `make test-property`, `make test-mutant`
""",
    "orchestration": """
### Orchestration
- **Agentes y skills** via MCP: `antigravity-agents`, `antigravity-skills`
- **Slash commands**: `/sdd`, `/autonomous`, `/team-plan`, `/ralph`, `/ultrawork`
- **Brain ingest automatico** en `/finalize`
""",
    "uns": """
### UNS Enterprise (mercado japones)
- **Dispatch (派遣) workflows**: contratos `個別契約書`, `履歴書`, kintai, yukyu
- **Japanese OCR** y manejo de PDFs oficiales (MLIT, ministerios)
- Datos sensibles UNS solo en env vars (`UNS_BANK_*`, `UNS_DISPATCH_LICENSE`)
""",
    "intelligence": """
### Intelligence
- **antigravity-intelligence** MCP: cross-app reasoning
- **Context engines** pluggables: brain_aware, delta_aware, composite
- **User profile** y feedback adaptativo via `user-preference-learner`
""",
    "core-dev": """
### Core Development
- **TypeScript strict** en `nexus-app/` (sin `any`)
- **Python**: type hints obligatorios, ruff + mypy strict
- **Refactoring** seguro via `refactor` agent + tests guards
""",
    "devops": """
### DevOps
- **GitHub Actions**: 13 workflows en `.github/workflows/`
- **make** targets: `test-gates`, `scan-mcp`, `health`
- **git-orchestrator** + commits convencionales en espanol
""",
    "specialized": """
### Specialized
- Integraciones via **MCP**: context7 (docs), playwright (browser), chrome-devtools
- **CLI tools**: scaffold-generator, autonomous-executor, log-analyzer
- Skills externos via `npx skills find/add`
""",
    "system": """
### System
- **Repo crawler** (`.agent/scripts/repo_crawler.py`): auto-ingest docs al Brain
- **Demo reel** y screenshots de marketing via Playwright retina 2x
- **Status** y inventory via `make status`
""",
}


def parse_frontmatter(content: str) -> tuple[dict[str, Any] | None, str]:
    """Parsea frontmatter YAML del inicio del archivo.

    Returns:
        (metadata_dict, body) si hay frontmatter valido
        (None, content) si no hay frontmatter
    """
    if not content.startswith("---\n"):
        return None, content
    parts = content.split("---\n", 2)
    if len(parts) < 3:
        return None, content
    if not HAS_YAML:
        return {}, parts[2]
    try:
        data = yaml.safe_load(parts[1])
        if not isinstance(data, dict):
            return None, content
        return data, parts[2]
    except yaml.YAMLError:
        return None, content


def extract_from_plain(content: str, name: str) -> dict[str, Any]:
    """Extrae metadatos de IDENTITY.md sin frontmatter, usando patrones markdown.

    Patrones soportados:
        - **Name:** value
        - **Nombre:** value
        - **Tier:** value
        - **Role:** value
        - **Rol:** value
    """
    metadata: dict[str, Any] = {"name": name}

    patterns = {
        "tier": r"\*\*Tier:?\*\*\s*[:\-]?\s*([^\n]+)",
        "role": r"\*\*Rol(?:e)?:?\*\*\s*[:\-]?\s*([^\n]+)",
        "purpose": r"\*\*(?:Prop[oó]sito|Purpose):?\*\*\s*[:\-]?\s*([^\n]+)",
    }
    for key, pattern in patterns.items():
        match = re.search(pattern, content, re.IGNORECASE)
        if match:
            metadata[key] = match.group(1).strip()

    # Description: estrategias en orden de preferencia
    # 1) Linea inline "**Description:**" o "**Descripcion:**"
    desc_inline = re.search(
        r"\*\*(?:Description|Descripci[oó]n|Descripcion):?\*\*\s*[:\-]?\s*([^\n]+)",
        content,
        re.IGNORECASE,
    )
    if desc_inline:
        desc = desc_inline.group(1).strip()
        # Limpiar marcadores residuales tipo "**Name:** xyz **Tier:** ..."
        desc = re.sub(r"\*\*[^*]+:?\*\*\s*[^*]+", "", desc).strip()
        if len(desc) > 20:
            metadata["description"] = desc[:280]
            return metadata

    # 2) Primera oracion que empiece con "You are" / "Eres" / "Soy" / "I am"
    persona_match = re.search(
        r"^((?:You are|Eres|Soy|I am)\s+\*?\*?[A-Z][^.\n]{15,250}[.\n])",
        content,
        re.MULTILINE,
    )
    if persona_match:
        desc = persona_match.group(1).strip().rstrip(".")
        desc = re.sub(r"\*+", "", desc)  # quitar asteriscos markdown
        metadata["description"] = re.sub(r"\s+", " ", desc).strip()[:280]
        return metadata

    # 3) "Soy/Eres" tipico de agentes en espanol
    intro_es = re.search(
        r"(?:Soy|Eres|Mi misi[oó]n|Especialidad en?)\s+[^.\n]{10,250}\.",
        content,
        re.IGNORECASE,
    )
    if intro_es:
        desc = intro_es.group(0).strip().rstrip(".")
        desc = re.sub(r"\*+", "", desc)
        metadata["description"] = re.sub(r"\s+", " ", desc).strip()[:280]
        return metadata

    # 4) Primer parrafo no-header, no-table, no-bullet despues del primer #
    first_h1 = re.search(r"^#\s+(.+)$", content, re.MULTILINE)
    if first_h1:
        after = content[first_h1.end() :]
        # Saltar headers H2/H3 hasta encontrar un parrafo de texto real
        for para_match in re.finditer(r"\n\n([^\n#|*\-`].+?)(?:\n\n|\n#)", after, re.DOTALL):
            candidate = para_match.group(1)
            # Skip si parece tabla, codigo, lista bullets
            if "|" in candidate or candidate.startswith(("    ", "\t", "```")):
                continue
            desc = re.sub(r"\s+", " ", candidate).strip()
            if len(desc) >= 30:
                metadata["description"] = desc[:280]
                return metadata

    return metadata


def normalize_tier(tier_raw: Any, category: str) -> int:
    """Convierte tier a numero 1-12 segun el sistema canonico."""
    if isinstance(tier_raw, int) and 1 <= tier_raw <= 12:
        return tier_raw
    if isinstance(tier_raw, str):
        cleaned = tier_raw.lower().strip()
        # "2 (Quality)" -> 2
        match = re.match(r"^(\d+)", cleaned)
        if match:
            n = int(match.group(1))
            if 1 <= n <= 12:
                return n
        # Match por nombre
        for tier_name, tier_num in TIER_MAP.items():
            if tier_name in cleaned:
                return tier_num
    # Fallback: usar categoria
    return CATEGORY_TO_TIER.get(category, 6)  # 6 = specialized si no se sabe


def build_frontmatter(metadata: dict[str, Any]) -> str:
    """Construye bloque de frontmatter YAML estandarizado."""
    name = metadata.get("name", "unknown")
    tier = metadata.get("tier", 6)
    description = metadata.get("description", "").strip()
    # Heuristica: si la description detectada parece ser tabla markdown
    # (varios `|` o `---|---`), no es realmente descripcion. Fallback.
    if description.count("|") > 3 or "---|" in description or "→" in description:
        description = ""
    if not description:
        description = f"Agente {name} del ecosistema Antigravity"
    # Escape para YAML single-quoted scalar: solo hay que escapar comillas
    # simples duplicandolas. Sin newlines/tabs en single-line.
    description = description.replace("\n", " ").replace("\r", " ").replace("\t", " ")
    description = re.sub(r"\s+", " ", description).strip()[:280]
    # YAML single-quoted: ' -> ''
    description_yaml = description.replace("'", "''")
    category = metadata.get("category", "specialized")
    model = metadata.get("model", "sonnet")
    tools = metadata.get("tools", ["Read", "Glob", "Grep", "Task"])
    if isinstance(tools, str):
        tools_str = tools
    else:
        tools_str = ", ".join(tools)

    return (
        "---\n"
        f"name: {name}\n"
        f"tier: {tier}\n"
        f"category: {category}\n"
        f"description: '{description_yaml}'\n"
        f"model: {model}\n"
        f"tools: {tools_str}\n"
        "---\n"
    )


def has_capabilities_section(body: str) -> bool:
    return "## Capacidades del Ecosistema" in body


def build_capabilities_block(category: str) -> str:
    """Construye el bloque de capacidades del ecosistema para una categoria."""
    extra = ECOSYSTEM_CAPABILITIES_BY_CATEGORY.get(category, "")
    return "\n\n" + ECOSYSTEM_CAPABILITIES_UNIVERSAL + extra + "\n"


def normalize_agent(agent_dir: Path, dry_run: bool) -> dict[str, Any]:
    """Normaliza un IDENTITY.md. Devuelve dict con accion realizada."""
    name = agent_dir.name
    identity_file = agent_dir / "IDENTITY.md"
    if not identity_file.exists():
        return {"name": name, "action": "skip-no-identity"}

    original = identity_file.read_text(encoding="utf-8")
    metadata, body = parse_frontmatter(original)
    had_frontmatter = metadata is not None
    if metadata is None:
        metadata = extract_from_plain(original, name)
        body = original  # preservar TODO el contenido

    # Inferir categoria si no esta en mapeo
    in_curated_map = name in AGENT_CATEGORY
    category = AGENT_CATEGORY.get(name, metadata.get("category", "specialized"))
    metadata["category"] = category

    # Normalizar tier: si el agente esta en el mapeo curado, el tier deriva
    # de la categoria (mas confiable que el valor escrito hace meses).
    # Si no esta en el mapeo, respetamos el tier_raw del archivo o fallback.
    if in_curated_map:
        metadata["tier"] = CATEGORY_TO_TIER[category]
    else:
        metadata["tier"] = normalize_tier(metadata.get("tier"), category)

    # Garantizar name
    metadata["name"] = name

    # Description: si no hay, usar default razonable
    if not metadata.get("description"):
        metadata["description"] = (
            f"Agente {name} del ecosistema Antigravity (categoria: {category})"
        )

    # Model default si falta o invalido
    valid_models = {"opus", "sonnet", "haiku"}
    current_model = metadata.get("model")
    if current_model not in valid_models:
        # tier 1-3 (orchestration, core-dev, quality) merecen opus por defecto;
        # tier 4-8 sonnet; tier 9-12 haiku (mas baratos para tareas content/system)
        if metadata["tier"] <= 3:
            metadata["model"] = "opus"
        elif metadata["tier"] <= 8:
            metadata["model"] = "sonnet"
        else:
            metadata["model"] = "sonnet"  # haiku no esta probado, conservamos sonnet

    # Tools por categoria: prefiero el mapeo curado vs el viejo del archivo,
    # porque queremos consistencia. Si el agente ya tenia tools especificos
    # mas amplios, los mergeamos.
    category_tools = TOOLS_BY_CATEGORY.get(metadata["category"], ["Read", "Glob", "Grep", "Task"])
    existing_tools = metadata.get("tools", [])
    if isinstance(existing_tools, str):
        existing_tools = [t.strip() for t in existing_tools.split(",")]
    if not isinstance(existing_tools, list):
        existing_tools = []
    # Merge preservando los del archivo si son utiles, agregando los de categoria
    merged = list(dict.fromkeys([*existing_tools, *category_tools]))  # dedup ordenado
    # Filtrar solo tools validos (los conocidos del ecosistema)
    valid_tools = {
        "Read",
        "Write",
        "Edit",
        "Glob",
        "Grep",
        "Bash",
        "Task",
        "WebSearch",
        "WebFetch",
        "NotebookEdit",
    }
    merged = [t for t in merged if t in valid_tools]
    metadata["tools"] = merged or category_tools

    new_frontmatter = build_frontmatter(metadata)

    # Construir nuevo body: si no tenia frontmatter, preservar todo el original
    # Si tenia, usar el body extraido
    if had_frontmatter:
        new_body = body
    else:
        # Quitar lineas tipo "**Name:** ...", "**Tier:** ..." del comienzo (redundantes con frontmatter)
        cleaned_body = re.sub(
            r"^[-*]?\s*\*\*(?:Name|Nombre|Tier|Role|Rol|Categor[íi]a|Vers[ií]on):?\*\*[^\n]*\n",
            "",
            body,
            flags=re.MULTILINE,
        )
        new_body = cleaned_body

    # Agregar seccion Capacidades del Ecosistema al final si no esta
    if not has_capabilities_section(new_body):
        new_body = new_body.rstrip() + build_capabilities_block(category)

    new_content = new_frontmatter + new_body

    action = "updated" if new_content != original else "unchanged"
    bytes_before = len(original.encode("utf-8"))
    bytes_after = len(new_content.encode("utf-8"))

    if action == "updated" and not dry_run:
        identity_file.write_text(new_content, encoding="utf-8")

    return {
        "name": name,
        "action": action,
        "had_frontmatter": had_frontmatter,
        "tier": metadata["tier"],
        "category": category,
        "model": metadata["model"],
        "bytes_before": bytes_before,
        "bytes_after": bytes_after,
        "delta": bytes_after - bytes_before,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Normaliza IDENTITY.md de los 116 agentes.")
    parser.add_argument(
        "--apply", action="store_true", help="Aplicar cambios. Sin esto, solo dry-run."
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Mostrar cambios sin aplicar (default)."
    )
    args = parser.parse_args()

    dry_run = not args.apply
    mode = "DRY-RUN" if dry_run else "APPLY"
    print(f"[normalize_agents] {mode} - escaneando {AGENTS_DIR}")

    results: list[dict[str, Any]] = []
    skipped = {"_docs", ".backup-2026-05-17", "__pycache__"}

    for child in sorted(AGENTS_DIR.iterdir()):
        if not child.is_dir():
            continue
        if child.name.startswith(".") or child.name in skipped:
            continue
        result = normalize_agent(child, dry_run)
        results.append(result)

    # Reporte
    updated = [r for r in results if r["action"] == "updated"]
    unchanged = [r for r in results if r["action"] == "unchanged"]
    skipped_results = [r for r in results if r["action"].startswith("skip")]

    print(f"\n=== Resumen {mode} ===")
    print(f"Total procesados: {len(results)}")
    print(f"  Actualizados: {len(updated)}")
    print(f"  Sin cambios: {len(unchanged)}")
    print(f"  Skipped: {len(skipped_results)}")

    # Distribucion por tier
    tier_dist: dict[int, int] = {}
    for r in results:
        t = r.get("tier", 0)
        tier_dist[t] = tier_dist.get(t, 0) + 1
    print("\nDistribucion por tier (despues):")
    for tier in sorted(tier_dist.keys()):
        print(f"  Tier {tier}: {tier_dist[tier]} agentes")

    # Conversiones plain->yaml
    converted = [r for r in updated if not r["had_frontmatter"]]
    print(f"\nConvertidos de plain a YAML frontmatter: {len(converted)}")

    # Detectar agrupaciones que podrian ser duplicados/solapamiento
    print("\n=== Posibles duplicados / solapamientos ===")
    suspect_groups = [
        ["ui-ux-designer", "ui-orchestrator"],
        ["test-engineer", "test-runner", "api-tester", "load-testing-engineer"],
        ["debugger", "interactive-debugger", "tracer"],
        [
            "security-auditor",
            "security-scanner",
            "penetration-tester",
            "compliance-auditor",
            "app-auditor",
            "ce-security-sentinel",
            "dependency-auditor",
        ],
        ["doc-generator", "documentation-writer", "docusaurus-expert"],
        ["data-engineer", "data-sync", "database-architect"],
        [
            "tauri-architect",
            "tauri-backend",
            "tauri-frontend",
            "vite-architect",
            "vite-performance",
            "vite-plugin-developer",
        ],
        ["context-guardian", "context-keeper"],
        ["frontend-specialist", "react-specialist", "tauri-frontend"],
        ["backend-specialist", "tauri-backend", "serverless-architect"],
        ["dependency", "dependency-auditor"],
        ["self-improver", "self-verifier"],
        ["finalizer", "stuck"],
        ["agent-composer", "intent-router", "skill-architect"],
        ["cost-optimizer", "cost-predictor"],
    ]
    existing_names = {r["name"] for r in results}
    for group in suspect_groups:
        present = [g for g in group if g in existing_names]
        if len(present) >= 2:
            print(f"  - {', '.join(present)}")

    if dry_run:
        print("\n(dry-run: ningun archivo modificado. Correr con --apply para aplicar)")

    return 0


if __name__ == "__main__":
    sys.exit(main())
