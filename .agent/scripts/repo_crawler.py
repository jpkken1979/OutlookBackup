"""Repo crawler para ingesta de documentos markdown al Brain Network.

Recorre una whitelist de documentos canonicos del repo OpenAntigravity,
detecta tags semanticos (apps UNS, componentes del ecosistema, etc.) y
los ingesta al Brain Network con `app_origin='repo-crawler'`.

El brain.ingest() ya se encarga del cross-linking automatico via
`_detect_related()`, que matchea nodos con tags solapados. Este script
solo tiene que generar buenos tags; el grafo se construye solo.

Dedup por SHA256 del contenido raw, almacenado en el campo `source_notes`
con formato `sha256:XXXX\norigin:repo-crawler`.

Uso:
    python .agent/scripts/repo_crawler.py               # dry-run
    python .agent/scripts/repo_crawler.py --apply       # ejecuta
    python .agent/scripts/repo_crawler.py --path X.md   # un solo archivo
    python .agent/scripts/repo_crawler.py --apply -v    # verbose
"""

from __future__ import annotations

import argparse
import hashlib
import logging
import re
import sys
from dataclasses import dataclass, field
from fnmatch import fnmatch
from pathlib import Path

import yaml

# Hacer importable el modulo core del brain
AGENT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(AGENT_ROOT))

from core.brain import Brain, BrainNode  # noqa: E402

logger = logging.getLogger("repo_crawler")

# ---------------------------------------------------------------------------
# Configuracion
# ---------------------------------------------------------------------------

REPO_ROOT = AGENT_ROOT.parent  # /.../OpenAntigravity26.3.30
BRAIN_DIR = AGENT_ROOT / "brain"
APP_ORIGIN = "repo-crawler"

MAX_TAGS_PER_NODE = 12
MIN_CONTENT_CHARS = 300
CONTEXT_MAX_CHARS = 3500
CONTENT_SCAN_CHARS = 5000  # Cantidad de chars iniciales para detectar tags

# Whitelist de patterns (glob) — relativos a REPO_ROOT
WHITELIST_PATTERNS: list[str] = [
    "CLAUDE.md",
    "RULES.md",
    "BRAIN_README.md",
    "BUILD.md",
    "ESTADO_PROYECTO.md",
    "WORKFLOW_RULES.md",
    "README.md",
    ".claude/rules/*.md",
    ".claude/memory/*.md",
    ".claude/commands/*.md",
    "docs/**/*.md",
    "nexus-app/CLAUDE.md",
    "nexus-app/README.md",
    "nexus-app/docs/**/*.md",
    "src/**/README.md",
    "mcp-server/**/*.md",
    ".antigravity/rules.md",
    ".antigravity/README.md",
]

# Blacklist CRITICA — nunca ingestar
BLACKLIST_PATTERNS: list[str] = [
    ".agent/brain/**",
    ".agent/brain-backups/**",
    ".git/**",
    "node_modules/**",
    "target/**",
    "dist/**",
    "build/**",
    ".claude/worktrees/**",
    "**/CHANGELOG.md",
    "**/*.test.md",
]


# ---------------------------------------------------------------------------
# Tag detectors
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TagRule:
    """Una regla de deteccion de tags.

    Args:
        pattern: Regex a aplicar.
        tags: Tags a asignar si matchea.
        case_sensitive: Si True, respeta caja. Default: False.
    """

    pattern: str
    tags: tuple[str, ...]
    case_sensitive: bool = False


# Reglas por path (se aplican sobre rel_path con separadores forward slash)
PATH_RULES: list[TagRule] = [
    TagRule(r"nexus-app/", ("nexus", "tauri", "desktop")),
    TagRule(r"^src/", ("telegram", "bot", "typescript")),
    TagRule(r"mcp-server/", ("mcp", "server-portable")),
    TagRule(r"\.claude/rules/", ("rules", "convention")),
    TagRule(r"\.claude/memory/", ("memory-local",)),
    TagRule(r"\.claude/commands/", ("slash-command",)),
    TagRule(r"docs/", ("docs",)),
]

# Reglas por filename exacto (case-sensitive en nombre)
FILENAME_RULES: dict[str, tuple[str, ...]] = {
    "CLAUDE.md": ("claude-code", "project-instructions"),
    "README.md": ("readme",),
    "RULES.md": ("rules",),
    "BUILD.md": ("build",),
    "ESTADO_PROYECTO.md": ("estado", "historial"),
    "WORKFLOW_RULES.md": ("workflow",),
    "BRAIN_README.md": ("brain",),
}

# Reglas por contenido (primeros CONTENT_SCAN_CHARS chars)
CONTENT_RULES: list[TagRule] = [
    TagRule(r"\bARARI\b", ("arari",), case_sensitive=True),
    TagRule(r"kobetsu|個別契約", ("kobetsu",)),
    TagRule(r"rirekisho|履歴書", ("rirekisho",)),
    TagRule(r"\bkintai\b|勤怠", ("kintai",)),
    TagRule(r"\byukyu\b|有給", ("yukyu",)),
    TagRule(r"\bchingi\b|賃金", ("chingi",)),
    TagRule(r"apartments-opus|apartment\.opus", ("apartments",)),
    TagRule(r"\bpaginaweb\b|uns-web", ("paginaweb",)),
    TagRule(r"kintaiflow", ("kintaiflow",)),
    TagRule(r"haken|派遣", ("uns-dispatch",)),
    TagRule(r"\bNexus\b", ("nexus",), case_sensitive=True),
    TagRule(r"\btauri\b", ("tauri",)),
    TagRule(r"\bReact\b", ("react",)),
    TagRule(r"\brust\b", ("rust",)),
    TagRule(r"FastAPI", ("fastapi",)),
    TagRule(r"Pydantic", ("pydantic",)),
    TagRule(r":4747|gateway local", ("gateway",)),
    TagRule(r"watch_spawn|process_watcher", ("watcher",)),
    TagRule(r"context engine|prepare_context", ("context-engine",)),
    TagRule(r"brain\.ingest|brain network", ("brain",)),
    TagRule(r"delta_read|delta_reader", ("delta-reader",)),
    TagRule(r"mem0|antigravity-memory", ("mem0",)),
    TagRule(r"\bMCP\b", ("mcp",), case_sensitive=True),
]

# UNS apps para decidir area "business"
UNS_APP_TAGS = {
    "arari",
    "kobetsu",
    "rirekisho",
    "kintai",
    "yukyu",
    "chingi",
    "apartments",
    "paginaweb",
    "kintaiflow",
}

# Areas validas que un frontmatter puede pisar al area heuristico (mismo set que brain)
VALID_FRONTMATTER_AREAS = {
    "dev",
    "ops",
    "ux",
    "business",
    "security",
    "testing",
    "architecture",
    "data",
    "infra",
    "docs",
    "general",
    "nexus",
    "memory",
    "governance",
    "ecosystem",
    "telegram",
}

# Importancias validas (mismo set que brain.VALID_STATUSES de importance)
VALID_FRONTMATTER_IMPORTANCE = {"low", "normal", "high", "critical"}


# ---------------------------------------------------------------------------
# Resultado del scan
# ---------------------------------------------------------------------------


@dataclass
class ScanResult:
    """Resultado del scan de un archivo."""

    rel_path: str
    title: str
    tags: list[str]
    area: str
    context: str
    sha256: str
    node_type: str
    importance: str
    action: str = "pending"  # pending | new | updated | skip | too_small | blacklisted
    reason: str = ""
    existing_slug: str = ""


@dataclass
class CrawlerStats:
    """Estadisticas agregadas del crawler."""

    found: int = 0
    to_ingest: int = 0
    to_update: int = 0
    unchanged: int = 0
    too_small: int = 0
    blacklisted: int = 0
    archived: int = 0
    archived_pending: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _matches_any(rel_path: str, patterns: list[str]) -> bool:
    """Verifica si rel_path matchea algun glob de patterns.

    Args:
        rel_path: Path relativo con separador forward slash.
        patterns: Lista de globs.

    Returns:
        True si matchea al menos uno.
    """
    return any(fnmatch(rel_path, pattern) for pattern in patterns)


def _strip_frontmatter(content: str) -> str:
    """Remueve frontmatter YAML del inicio del markdown si existe.

    Args:
        content: Contenido raw del markdown.

    Returns:
        Contenido sin el frontmatter.
    """
    match = re.match(r"^---\n.*?\n---\n?", content, re.DOTALL)
    if match:
        return content[match.end():]
    return content


def _extract_frontmatter_block(content: str) -> str | None:
    """Extrae el bloque YAML interno del frontmatter, si existe.

    Args:
        content: Contenido raw del markdown.

    Returns:
        Texto interno del frontmatter (sin los `---`) o None si no hay.
    """
    if not content.startswith("---\n"):
        return None
    # Buscar el cierre `\n---\n` o `\n---` al final
    end_match = re.search(r"\n---(?:\n|$)", content[4:])
    if not end_match:
        return None
    return content[4 : 4 + end_match.start()]


def _parse_frontmatter(content: str) -> dict[str, object]:
    """Parsea el frontmatter YAML del markdown.

    Maneja errores de parseo silenciosamente (devuelve dict vacio).

    Args:
        content: Contenido raw del markdown.

    Returns:
        Dict con las claves del frontmatter, o vacio si no hay/no parsea.
    """
    block = _extract_frontmatter_block(content)
    if block is None:
        return {}

    try:
        data = yaml.safe_load(block)
    except yaml.YAMLError:
        return {}

    if not isinstance(data, dict):
        return {}
    return data


def _extract_frontmatter_tags(content: str) -> list[str]:
    """Extrae tags del frontmatter YAML normalizados a lowercase.

    Args:
        content: Contenido raw del markdown.

    Returns:
        Lista de tags strings, lowercased y deduplicados. Vacia si no hay.
    """
    data = _parse_frontmatter(content)
    raw_tags = data.get("tags")
    if not isinstance(raw_tags, list):
        return []

    cleaned: list[str] = []
    seen: set[str] = set()
    for item in raw_tags:
        if not isinstance(item, str):
            continue
        norm = item.strip().lower()
        if not norm or norm in seen:
            continue
        seen.add(norm)
        cleaned.append(norm)
    return cleaned


def _extract_frontmatter_overrides(content: str) -> dict[str, str]:
    """Extrae overrides opcionales (title, area, importance) del frontmatter.

    Solo devuelve campos cuyos valores son validos. Campos faltantes o invalidos
    no aparecen en el resultado para que el caller use el default heuristico.

    Args:
        content: Contenido raw del markdown.

    Returns:
        Dict con subset de {"title", "area", "importance"} segun lo que sea valido.
    """
    data = _parse_frontmatter(content)
    overrides: dict[str, str] = {}

    title = data.get("title")
    if isinstance(title, str) and title.strip():
        overrides["title"] = title.strip()

    area = data.get("area")
    if isinstance(area, str) and area.strip().lower() in VALID_FRONTMATTER_AREAS:
        overrides["area"] = area.strip().lower()

    importance = data.get("importance")
    if (
        isinstance(importance, str)
        and importance.strip().lower() in VALID_FRONTMATTER_IMPORTANCE
    ):
        overrides["importance"] = importance.strip().lower()

    return overrides


def _extract_title(content: str, fallback: str) -> str:
    """Extrae el primer `# Heading` o usa fallback.

    Args:
        content: Contenido sin frontmatter.
        fallback: Titulo por default si no encuentra.

    Returns:
        Titulo extraido o fallback.
    """
    for line in content.split("\n"):
        stripped = line.strip()
        if stripped.startswith("# ") and not stripped.startswith("##"):
            return stripped.lstrip("# ").strip()
    return fallback


def _detect_tags(rel_path: str, filename: str, content_preview: str) -> list[str]:
    """Detecta tags semanticos aplicando las reglas de path, filename y contenido.

    Args:
        rel_path: Path relativo del archivo (forward slash).
        filename: Nombre del archivo sin directorio.
        content_preview: Primeros N chars del contenido.

    Returns:
        Lista de tags unicos, ordenada alfabeticamente, max MAX_TAGS_PER_NODE.
    """
    tags: set[str] = {"auto-ingested"}

    # Path rules
    for rule in PATH_RULES:
        flags = 0 if rule.case_sensitive else re.IGNORECASE
        if re.search(rule.pattern, rel_path, flags):
            tags.update(rule.tags)

    # Filename rules
    if filename in FILENAME_RULES:
        tags.update(FILENAME_RULES[filename])

    # Content rules
    for rule in CONTENT_RULES:
        flags = 0 if rule.case_sensitive else re.IGNORECASE
        if re.search(rule.pattern, content_preview, flags):
            tags.update(rule.tags)

    sorted_tags = sorted(tags)
    return sorted_tags[:MAX_TAGS_PER_NODE]


def _infer_area(tags: list[str]) -> str:
    """Infiere el area del nodo segun sus tags.

    Args:
        tags: Tags detectados.

    Returns:
        Area inferida.
    """
    tag_set = set(tags)
    if "nexus" in tag_set:
        return "nexus"
    if tag_set & UNS_APP_TAGS:
        return "business"
    if "brain" in tag_set or "memory-local" in tag_set:
        return "memory"
    if tag_set & {"rules", "convention", "workflow"}:
        return "governance"
    if "mcp" in tag_set or "gateway" in tag_set:
        return "ecosystem"
    if "telegram" in tag_set:
        return "telegram"
    if "docs" in tag_set:
        return "docs"
    return "general"


def _infer_node_type(filename: str) -> str:
    """Decide session vs concept segun el filename.

    Args:
        filename: Nombre del archivo sin directorio.

    Returns:
        'session' para sesiones historicas, 'concept' para docs de referencia.
    """
    if filename.startswith("session_") or filename == "ESTADO_PROYECTO.md":
        return "session"
    return "concept"


def _infer_importance(rel_path: str, filename: str) -> str:
    """Decide critical/high/normal segun el path y filename.

    Args:
        rel_path: Path relativo.
        filename: Nombre del archivo.

    Returns:
        Nivel de importancia.
    """
    critical_roots = {"CLAUDE.md", "RULES.md", "BRAIN_README.md", "WORKFLOW_RULES.md"}
    # Solo los de la raiz del repo cuentan como critical
    if rel_path in critical_roots:
        return "critical"

    if rel_path.startswith(".claude/rules/") and filename.endswith(".md"):
        return "high"
    if rel_path == "nexus-app/CLAUDE.md":
        return "high"
    if rel_path == "BUILD.md":
        return "high"

    return "normal"


def _compute_sha(content: str) -> str:
    """Computa SHA256 hex truncado del contenido.

    Args:
        content: Contenido raw.

    Returns:
        Primeros 16 chars del hash hex.
    """
    return hashlib.sha256(content.encode("utf-8")).hexdigest()[:16]


def _parse_source_notes(source_notes: str) -> dict[str, str]:
    """Parsea el campo source_notes a un dict.

    Formato esperado: lineas "clave:valor".

    Args:
        source_notes: Texto del campo source_notes.

    Returns:
        Dict con las claves parseadas.
    """
    result: dict[str, str] = {}
    for line in source_notes.splitlines():
        line = line.strip()
        if ":" not in line:
            continue
        key, _, value = line.partition(":")
        result[key.strip().lower()] = value.strip()
    return result


# ---------------------------------------------------------------------------
# Crawler core
# ---------------------------------------------------------------------------


def find_candidate_files(filter_path: str | None = None) -> list[Path]:
    """Encuentra archivos que matchean whitelist y no blacklist.

    Args:
        filter_path: Si se pasa, solo devuelve ese path (si matchea whitelist).

    Returns:
        Lista de Paths absolutos a procesar.
    """
    seen: set[Path] = set()
    candidates: list[Path] = []

    if filter_path:
        target = REPO_ROOT / filter_path
        if not target.exists() or not target.is_file():
            logger.error("Path no existe: %s", filter_path)
            return []
        rel = str(target.relative_to(REPO_ROOT)).replace("\\", "/")
        if not _matches_any(rel, WHITELIST_PATTERNS):
            logger.error("Path no esta en whitelist: %s", rel)
            return []
        if _matches_any(rel, BLACKLIST_PATTERNS):
            logger.error("Path esta en blacklist: %s", rel)
            return []
        return [target]

    for pattern in WHITELIST_PATTERNS:
        for path in REPO_ROOT.glob(pattern):
            if not path.is_file():
                continue
            if path in seen:
                continue
            seen.add(path)
            candidates.append(path)

    return sorted(candidates)


def scan_file(abs_path: Path) -> ScanResult | None:
    """Escanea un archivo y produce un ScanResult con tags y metadata.

    Args:
        abs_path: Path absoluto al archivo.

    Returns:
        ScanResult o None si hubo error de lectura.
    """
    rel_path = str(abs_path.relative_to(REPO_ROOT)).replace("\\", "/")

    if _matches_any(rel_path, BLACKLIST_PATTERNS):
        return ScanResult(
            rel_path=rel_path,
            title="",
            tags=[],
            area="general",
            context="",
            sha256="",
            node_type="concept",
            importance="normal",
            action="blacklisted",
            reason="match blacklist",
        )

    try:
        raw = abs_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError) as e:
        logger.warning("No se pudo leer %s: %s", rel_path, e)
        return None

    body = _strip_frontmatter(raw)
    if len(body.strip()) < MIN_CONTENT_CHARS:
        return ScanResult(
            rel_path=rel_path,
            title="",
            tags=[],
            area="general",
            context="",
            sha256="",
            node_type="concept",
            importance="normal",
            action="too_small",
            reason=f"contenido util < {MIN_CONTENT_CHARS} chars",
        )

    filename = abs_path.name

    # Frontmatter overrides (si el .md trae YAML valido)
    frontmatter_tags = _extract_frontmatter_tags(raw)
    overrides = _extract_frontmatter_overrides(raw)

    content_preview = body[:CONTENT_SCAN_CHARS]
    detected_tags = _detect_tags(rel_path, filename, content_preview)

    # Merge: frontmatter tags + detected tags, lowercased + dedup, max MAX_TAGS_PER_NODE
    merged_tag_set: set[str] = set()
    for tag in frontmatter_tags + detected_tags:
        norm = tag.strip().lower()
        if norm:
            merged_tag_set.add(norm)
    tags = sorted(merged_tag_set)[:MAX_TAGS_PER_NODE]

    # Title: frontmatter > primer H1 > filename
    title = overrides.get("title") or _extract_title(body, fallback=filename.replace(".md", ""))

    # Area: frontmatter > inferencia heuristica
    area = overrides.get("area") or _infer_area(tags)

    # Importance: frontmatter > heuristica por path
    importance = overrides.get("importance") or _infer_importance(rel_path, filename)

    node_type = _infer_node_type(filename)
    sha256 = _compute_sha(raw)

    context = f"Archivo: {rel_path}\n\n{body[:CONTEXT_MAX_CHARS]}"

    return ScanResult(
        rel_path=rel_path,
        title=title,
        tags=tags,
        area=area,
        context=context,
        sha256=sha256,
        node_type=node_type,
        importance=importance,
    )


def build_existing_index(brain: Brain) -> dict[str, tuple[str, str]]:
    """Construye dict rel_path -> (slug, sha256) para nodos del crawler.

    Args:
        brain: Instancia del Brain.

    Returns:
        Dict con los nodos existentes creados por este crawler.
    """
    existing: dict[str, tuple[str, str]] = {}

    for md_file in brain._all_node_files():  # type: ignore[attr-defined]
        try:
            content = md_file.read_text(encoding="utf-8")
            node = BrainNode.from_frontmatter(content, md_file)
        except (ValueError, OSError):
            continue

        if node.app_origin != APP_ORIGIN:
            continue

        notes = _parse_source_notes(node.source_notes)
        sha = notes.get("sha256", "")
        # rel_path viene del primer elemento de sources
        rel = node.sources[0] if node.sources else ""
        if rel:
            existing[rel] = (node.slug, sha)

    return existing


def _is_safe_relative_repo_path(path_str: str) -> bool:
    """Verifica que el path sea relativo al repo (no absoluto ni con `..`).

    Solo archivamos nodos cuyo `sources` apunte a un path relativo al repo.
    Si la fuente es absoluta o sale del repo, no podemos asegurar que el
    archivo realmente desaparecio — puede ser un path externo intencional.

    Args:
        path_str: Path a validar.

    Returns:
        True si el path es relativo y queda dentro del repo.
    """
    if not path_str:
        return False
    candidate = Path(path_str)
    if candidate.is_absolute():
        return False
    if ".." in candidate.parts:
        return False
    return True


def find_orphan_nodes(
    brain: Brain,
    existing: dict[str, tuple[str, str]],
) -> list[tuple[str, str]]:
    """Busca nodos del crawler cuyo path original ya no existe en el repo.

    Solo considera nodos con `sources: [path]` donde path es relativo al repo.
    Excluye nodos ya `status="archived"` para mantener idempotencia.

    Args:
        brain: Instancia del Brain.
        existing: Index de nodos existentes (rel_path -> (slug, sha)).

    Returns:
        Lista de (rel_path, slug) a archivar.
    """
    orphans: list[tuple[str, str]] = []

    for rel_path, (slug, _sha) in existing.items():
        if not _is_safe_relative_repo_path(rel_path):
            continue
        if (REPO_ROOT / rel_path).exists():
            continue

        # Verificar status actual para idempotencia
        try:
            node = brain.get_node(slug, track_access=False)
        except (FileNotFoundError, ValueError):
            continue
        if node.status == "archived":
            continue

        orphans.append((rel_path, slug))

    return orphans


def apply_changes(
    brain: Brain,
    result: ScanResult,
    existing: dict[str, tuple[str, str]],
) -> str:
    """Aplica el cambio correspondiente al brain (ingest o update).

    Args:
        brain: Instancia del Brain.
        result: ScanResult del archivo.
        existing: Index de nodos existentes del crawler.

    Returns:
        Accion realizada: 'new', 'updated' o 'unchanged'.
    """
    if result.rel_path not in existing:
        # Nuevo nodo
        brain.ingest(
            title=result.title,
            context=result.context,
            area=result.area,
            tags=result.tags,
            sources=[result.rel_path],
            node_type=result.node_type,
            source_notes=f"sha256:{result.sha256}\norigin:{APP_ORIGIN}",
            importance=result.importance,
        )
        return "new"

    slug, old_sha = existing[result.rel_path]
    if old_sha == result.sha256:
        return "unchanged"

    # Actualizar nodo existente (context + tags)
    brain.update_node(
        slug,
        context=result.context,
        tags=result.tags,
    )

    # Como update_node no permite cambiar source_notes, lo reescribimos a mano
    try:
        node = brain.get_node(slug, track_access=False)
        node.source_notes = f"sha256:{result.sha256}\norigin:{APP_ORIGIN}"
        node_path = brain._find_node_file(slug)  # type: ignore[attr-defined]
        node_path.write_text(node.to_frontmatter(), encoding="utf-8")
    except (FileNotFoundError, ValueError) as e:
        logger.warning("No se pudo refrescar source_notes de %s: %s", slug, e)

    return "updated"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _parse_args() -> argparse.Namespace:
    """Parsea argumentos de linea de comando.

    Returns:
        Namespace con los args.
    """
    parser = argparse.ArgumentParser(
        description="Ingesta documentos markdown del repo al Brain Network.",
    )
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Aplicar cambios reales. Sin este flag corre en dry-run.",
    )
    parser.add_argument(
        "--path",
        type=str,
        default=None,
        help="Procesar solo ese path (relativo al repo).",
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Loguear cada archivo procesado.",
    )
    parser.add_argument(
        "--no-cleanup",
        action="store_true",
        help="Saltar la pasada de cleanup que archiva nodos huerfanos.",
    )
    return parser.parse_args()


def _configure_logging(verbose: bool) -> None:
    """Configura el logger segun el nivel verbose.

    Args:
        verbose: Si True, nivel DEBUG.
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="[%(asctime)s] [%(levelname)s] %(message)s",
        datefmt="%H:%M:%S",
    )


def main() -> int:
    """Entry point del crawler.

    Returns:
        0 si fue exitoso, 1 en error.
    """
    args = _parse_args()
    _configure_logging(args.verbose)

    mode = "APPLY" if args.apply else "DRY-RUN"
    logger.info("[repo-crawler] modo=%s repo=%s", mode, REPO_ROOT)

    if not BRAIN_DIR.exists():
        logger.error("Brain dir no existe: %s", BRAIN_DIR)
        return 1

    brain = Brain(BRAIN_DIR, app_id=APP_ORIGIN)
    existing = build_existing_index(brain)
    logger.info("[repo-crawler] nodos previos del crawler: %d", len(existing))

    candidates = find_candidate_files(filter_path=args.path)
    logger.info("[repo-crawler] archivos candidatos: %d", len(candidates))

    stats = CrawlerStats()
    results: list[ScanResult] = []

    for abs_path in candidates:
        stats.found += 1
        result = scan_file(abs_path)
        if result is None:
            stats.errors.append(str(abs_path))
            continue

        results.append(result)

        if result.action == "blacklisted":
            stats.blacklisted += 1
            if args.verbose:
                logger.debug("[skip:blacklist] %s", result.rel_path)
            continue

        if result.action == "too_small":
            stats.too_small += 1
            if args.verbose:
                logger.debug("[skip:small] %s (%s)", result.rel_path, result.reason)
            continue

        # Clasificar new vs update vs unchanged
        if result.rel_path not in existing:
            result.action = "new"
            stats.to_ingest += 1
            if args.verbose:
                logger.debug(
                    "[new] %s tags=%s area=%s",
                    result.rel_path,
                    result.tags,
                    result.area,
                )
        else:
            slug, old_sha = existing[result.rel_path]
            result.existing_slug = slug
            if old_sha == result.sha256:
                result.action = "unchanged"
                stats.unchanged += 1
                if args.verbose:
                    logger.debug("[unchanged] %s slug=%s", result.rel_path, slug)
            else:
                result.action = "updated"
                stats.to_update += 1
                if args.verbose:
                    logger.debug("[update] %s slug=%s", result.rel_path, slug)

        # Apply si corresponde
        if args.apply and result.action in {"new", "updated"}:
            try:
                applied = apply_changes(brain, result, existing)
                logger.info("[%s] %s", applied, result.rel_path)
            except Exception as e:  # noqa: BLE001
                logger.error("Error procesando %s: %s", result.rel_path, e)
                stats.errors.append(f"{result.rel_path}: {e}")

    # Pasada de cleanup: archivar nodos huerfanos cuyo source ya no existe
    if args.no_cleanup:
        if args.verbose:
            logger.debug("[cleanup] saltado por --no-cleanup")
    elif args.path:
        # Si se proceso un solo path, no hacer cleanup global
        if args.verbose:
            logger.debug("[cleanup] saltado: corrida con --path solo")
    else:
        orphans = find_orphan_nodes(brain, existing)
        stats.archived_pending = [rel for rel, _slug in orphans]

        if not args.apply:
            for rel_path, slug in orphans:
                logger.info("[orphan:dry-run] %s slug=%s", rel_path, slug)
        else:
            for rel_path, slug in orphans:
                try:
                    brain.update_node(slug, status="archived")
                    stats.archived += 1
                    logger.info("[archived] %s slug=%s", rel_path, slug)
                except (FileNotFoundError, ValueError) as e:
                    logger.error("Error archivando %s (slug=%s): %s", rel_path, slug, e)
                    stats.errors.append(f"{rel_path} (archive): {e}")

    # Reporte final
    print()
    print("[repo-crawler] scan complete")
    print(f"  archivos encontrados:    {stats.found}")
    print(f"  a ingestar (nuevos):     {stats.to_ingest}")
    print(f"  a actualizar (cambios):  {stats.to_update}")
    print(f"  sin cambios (skip):      {stats.unchanged}")
    print(f"  excluidos (blacklist):   {stats.blacklisted}")
    print(f"  muy chicos (skip):       {stats.too_small}")

    if args.apply:
        print(f"  huerfanos archivados:    {stats.archived}")
    else:
        pending = len(stats.archived_pending)
        print(f"  huerfanos detectados:    {pending} (dry-run, no archivados)")
        if pending and args.verbose:
            for rel in stats.archived_pending[:10]:
                print(f"    - {rel}")

    if stats.errors:
        print(f"  errores:                 {len(stats.errors)}")
        for err in stats.errors[:5]:
            print(f"    - {err}")

    if not args.apply and (
        stats.to_ingest or stats.to_update or stats.archived_pending
    ):
        print()
        print("[repo-crawler] dry-run: usa --apply para ejecutar")

    return 1 if stats.errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
