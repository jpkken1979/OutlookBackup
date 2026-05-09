#!/usr/bin/env python3
"""Antigravity MCP & Skills Security Auditor.

Escanea servidores MCP y skills del ecosistema en busca de vulnerabilidades:
- Prompt injections ocultas en descripciones de herramientas
- Tool poisoning attacks
- Secretos hardcodeados en archivos SKILL.md
- Payloads maliciosos en lenguaje natural
- Manejo inseguro de datos sensibles

Uso:
    python audit_mcp.py                    # Escaneo completo
    python audit_mcp.py --skills-only      # Solo skills
    python audit_mcp.py --mcp-only         # Solo servidores MCP
    python audit_mcp.py --report json      # Salida en JSON
    python audit_mcp.py --verbose          # Modo detallado
"""

import argparse
import json
import logging
import re
import sys
from dataclasses import dataclass, field
from datetime import datetime, UTC
from pathlib import Path

# Evita crashes por encoding en consolas Windows cp932/cp1252.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

# Configuración de logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("antigravity.audit_mcp")

# =============================================================================
# CONSTANTS
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent
SKILLS_DIR = PROJECT_ROOT / ".agent" / "skills"
AGENTS_DIR = PROJECT_ROOT / ".agent" / "agents"
MCP_DIR = PROJECT_ROOT / ".agent" / "mcp"
MCP_SERVER_DIR = PROJECT_ROOT / "mcp-server"
LOGS_DIR = PROJECT_ROOT / ".agent" / "logs"
NON_BLOCKING_SKILL_PREFIX = ".agent/skills/"
DOC_FILE_EXTENSIONS = {".md", ".markdown", ".rst", ".txt"}

# Patrones sospechosos de prompt injection
PROMPT_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"ignore\s+(previous|all|above)\s+instructions", re.IGNORECASE),
    re.compile(r"disregard\s+(previous|all|your)\s+instructions", re.IGNORECASE),
    re.compile(r"forget\s+(everything|all|previous)", re.IGNORECASE),
    re.compile(r"you\s+are\s+now\s+a", re.IGNORECASE),
    re.compile(r"new\s+system\s+prompt", re.IGNORECASE),
    re.compile(r"override\s+(system|safety|guardrails)", re.IGNORECASE),
    re.compile(r"<\s*system\s*>", re.IGNORECASE),
    re.compile(r"\[SYSTEM\]", re.IGNORECASE),
    re.compile(r"IMPORTANT:\s*ignore", re.IGNORECASE),
    re.compile(r"do\s+not\s+follow\s+any\s+other", re.IGNORECASE),
    re.compile(r"act\s+as\s+if\s+you\s+have\s+no\s+restrictions", re.IGNORECASE),
    re.compile(r"jailbreak", re.IGNORECASE),
    re.compile(r"DAN\s+mode", re.IGNORECASE),
]

# Patrones de secretos/tokens hardcodeados
SECRET_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"sk-[a-zA-Z0-9]{20,}"),  # OpenAI API keys
    re.compile(r"sk-ant-[a-zA-Z0-9]{20,}"),  # Anthropic API keys
    re.compile(r"ghp_[a-zA-Z0-9]{36,}"),  # GitHub personal access tokens
    re.compile(r"gho_[a-zA-Z0-9]{36,}"),  # GitHub OAuth tokens
    re.compile(r"AKIA[0-9A-Z]{16}"),  # AWS access keys
    re.compile(r"(?i)password\s*[=:]\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"(?i)api[_-]?key\s*[=:]\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"(?i)token\s*[=:]\s*['\"][^'\"]{16,}['\"]"),
    re.compile(r"(?i)secret\s*[=:]\s*['\"][^'\"]{8,}['\"]"),
    re.compile(r"Bearer\s+[a-zA-Z0-9._-]{20,}"),
]

# Patrones de shell injection
SHELL_INJECTION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"subprocess\.run\([^)]*shell\s*=\s*True", re.IGNORECASE),
    re.compile(r"os\.system\s*\(", re.IGNORECASE),
    re.compile(r"os\.popen\s*\(", re.IGNORECASE),
    re.compile(r"(?<![\w.])eval\s*\(", re.IGNORECASE),
    re.compile(r"(?<![\w.])exec\s*\(", re.IGNORECASE),
    re.compile(r"\$\([^)]+\)"),  # Subshell execution
]

# Patrones de exfiltración de datos
EXFILTRATION_PATTERNS: list[re.Pattern[str]] = [
    re.compile(r"curl\s+.*-d\s+.*\$", re.IGNORECASE),
    re.compile(r"wget\s+.*--post-data", re.IGNORECASE),
    re.compile(r"fetch\s*\(['\"]https?://[^'\"]*\.\w{2,}['\"]", re.IGNORECASE),
    re.compile(r"requests?\.(post|put)\s*\(", re.IGNORECASE),
    re.compile(r"httpx?\.(post|put)\s*\(", re.IGNORECASE),
]

# Severidad
SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_LOW = "LOW"
SEVERITY_INFO = "INFO"


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class Finding:
    """Representa un hallazgo de seguridad."""

    severity: str
    category: str
    file_path: str
    line_number: int
    description: str
    matched_text: str = ""
    recommendation: str = ""
    ci_blocking: bool = True
    classification: str = "runtime_risk"


@dataclass
class AuditResult:
    """Resultado completo de la auditoría."""

    timestamp: str = ""
    total_skills_scanned: int = 0
    total_agents_scanned: int = 0
    total_mcp_servers_scanned: int = 0
    total_python_files_scanned: int = 0
    findings: list[Finding] = field(default_factory=list)
    summary: dict[str, int] = field(default_factory=dict)
    summary_blocking: dict[str, int] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.timestamp:
            self.timestamp = datetime.now(tz=UTC).isoformat()

    @property
    def has_critical(self) -> bool:
        """Retorna True si hay hallazgos críticos."""
        return any(f.severity == SEVERITY_CRITICAL for f in self.findings)

    @property
    def has_high(self) -> bool:
        """Retorna True si hay hallazgos de alta severidad."""
        return any(f.severity == SEVERITY_HIGH for f in self.findings)

    @property
    def has_critical_blocking(self) -> bool:
        """Retorna True si hay hallazgos críticos que bloquean CI."""
        return any(f.severity == SEVERITY_CRITICAL and f.ci_blocking for f in self.findings)

    @property
    def has_high_blocking(self) -> bool:
        """Retorna True si hay hallazgos HIGH que bloquean CI."""
        return any(f.severity == SEVERITY_HIGH and f.ci_blocking for f in self.findings)

    def add_finding(self, finding: Finding) -> None:
        """Añade un hallazgo y actualiza el resumen."""
        self.findings.append(finding)
        self.summary[finding.severity] = self.summary.get(finding.severity, 0) + 1
        if finding.ci_blocking:
            self.summary_blocking[finding.severity] = (
                self.summary_blocking.get(finding.severity, 0) + 1
            )

    def to_dict(self) -> dict:
        """Convierte el resultado a diccionario."""
        return {
            "timestamp": self.timestamp,
            "stats": {
                "skills_scanned": self.total_skills_scanned,
                "agents_scanned": self.total_agents_scanned,
                "mcp_servers_scanned": self.total_mcp_servers_scanned,
                "python_files_scanned": self.total_python_files_scanned,
            },
            "summary": self.summary,
            "summary_blocking": self.summary_blocking,
            "total_findings": len(self.findings),
            "total_blocking_findings": sum(1 for f in self.findings if f.ci_blocking),
            "findings": [
                {
                    "severity": f.severity,
                    "category": f.category,
                    "file": f.file_path,
                    "line": f.line_number,
                    "description": f.description,
                    "matched_text": f.matched_text[:100] if f.matched_text else "",
                    "recommendation": f.recommendation,
                    "ci_blocking": f.ci_blocking,
                    "classification": f.classification,
                }
                for f in self.findings
            ],
        }


# =============================================================================
# SCANNER FUNCTIONS
# =============================================================================


def classify_finding_for_ci(
    relative_path: str,
    strict_content: bool = False,
) -> tuple[bool, str]:
    """Clasifica un hallazgo como bloqueante o pedagógico.

    Regla base:
    - Modo estricto: todo hallazgo es bloqueante.
    - Contenido bajo `.agent/skills/` se marca como pedagógico/no bloqueante.
    - Riesgo en runtime (agentes, mcp, server) se mantiene bloqueante.
    """
    if strict_content:
        return True, "runtime_risk"

    normalized = relative_path.replace("\\", "/")
    suffix = Path(normalized).suffix.lower()

    if normalized.startswith(NON_BLOCKING_SKILL_PREFIX):
        if suffix in DOC_FILE_EXTENSIONS:
            return False, "pedagogical_doc_example"
        return False, "skill_reference_content"

    return True, "runtime_risk"


def scan_file_for_patterns(
    file_path: Path,
    patterns: list[re.Pattern[str]],
    category: str,
    severity: str,
    recommendation: str = "",
    strict_content: bool = False,
) -> list[Finding]:
    """Escanea un archivo buscando patrones regex peligrosos.

    Args:
        file_path: Ruta al archivo a escanear.
        patterns: Lista de patrones compilados.
        category: Categoría del hallazgo.
        severity: Severidad del hallazgo.
        recommendation: Recomendación de remediación.

    Returns:
        Lista de hallazgos encontrados.
    """
    findings: list[Finding] = []
    try:
        relative_path = str(file_path.relative_to(PROJECT_ROOT))
        ci_blocking, classification = classify_finding_for_ci(
            relative_path=relative_path,
            strict_content=strict_content,
        )
        content = file_path.read_text(encoding="utf-8", errors="replace")
        lines = content.splitlines()

        for line_num, line in enumerate(lines, start=1):
            for pattern in patterns:
                match = pattern.search(line)
                if match:
                    findings.append(
                        Finding(
                            severity=severity,
                            category=category,
                            file_path=relative_path,
                            line_number=line_num,
                            description=f"Patrón sospechoso detectado: {pattern.pattern}",
                            matched_text=match.group(0),
                            recommendation=recommendation,
                            ci_blocking=ci_blocking,
                            classification=classification,
                        )
                    )
    except Exception as e:
        logger.warning(f"Error leyendo {file_path}: {e}")

    return findings


def scan_skills(result: AuditResult, strict_content: bool = False) -> None:
    """Escanea todas las skills del ecosistema.

    Args:
        result: Objeto AuditResult donde se acumulan los hallazgos.
    """
    logger.info("Escaneando skills...")

    if not SKILLS_DIR.exists():
        logger.warning(f"Directorio de skills no encontrado: {SKILLS_DIR}")
        return

    skill_dirs = [d for d in SKILLS_DIR.iterdir() if d.is_dir() and not d.name.startswith("_")]

    for skill_dir in skill_dirs:
        result.total_skills_scanned += 1
        skill_md = skill_dir / "SKILL.md"

        if not skill_md.exists():
            result.add_finding(
                Finding(
                    severity=SEVERITY_LOW,
                    category="missing_skill_md",
                    file_path=str(skill_dir.relative_to(PROJECT_ROOT)),
                    line_number=0,
                    description=f"Skill '{skill_dir.name}' no tiene SKILL.md",
                    recommendation="Añadir un archivo SKILL.md con metadatos YAML.",
                )
            )
            continue

        # Escanear prompt injections en SKILL.md
        findings = scan_file_for_patterns(
            skill_md,
            PROMPT_INJECTION_PATTERNS,
            "prompt_injection",
            SEVERITY_CRITICAL,
            "Revisar manualmente el contenido sospechoso. "
            "Eliminar instrucciones que intenten sobreescribir el sistema.",
            strict_content=strict_content,
        )
        for f in findings:
            result.add_finding(f)

        # Escanear secretos hardcodeados en SKILL.md
        findings = scan_file_for_patterns(
            skill_md,
            SECRET_PATTERNS,
            "hardcoded_secret",
            SEVERITY_HIGH,
            "Mover secretos a variables de entorno. "
            "Nunca incluir tokens/claves en archivos de skill.",
            strict_content=strict_content,
        )
        for f in findings:
            result.add_finding(f)

        # Escanear scripts Python dentro de la skill
        scripts_dir = skill_dir / "scripts"
        if scripts_dir.exists():
            for py_file in scripts_dir.rglob("*.py"):
                result.total_python_files_scanned += 1

                # Buscar shell injections
                findings = scan_file_for_patterns(
                    py_file,
                    SHELL_INJECTION_PATTERNS,
                    "shell_injection",
                    SEVERITY_HIGH,
                    "Usar shlex.split() + shell=False en lugar de shell=True. "
                    "Evitar eval()/exec() con input no sanitizado.",
                    strict_content=strict_content,
                )
                for f in findings:
                    result.add_finding(f)

                # Buscar secretos hardcodeados
                findings = scan_file_for_patterns(
                    py_file,
                    SECRET_PATTERNS,
                    "hardcoded_secret",
                    SEVERITY_HIGH,
                    "Mover secretos a variables de entorno (.env).",
                    strict_content=strict_content,
                )
                for f in findings:
                    result.add_finding(f)

                # Buscar exfiltración de datos
                findings = scan_file_for_patterns(
                    py_file,
                    EXFILTRATION_PATTERNS,
                    "data_exfiltration",
                    SEVERITY_MEDIUM,
                    "Verificar que las llamadas HTTP externas son intencionales "
                    "y no envían datos sensibles.",
                    strict_content=strict_content,
                )
                for f in findings:
                    result.add_finding(f)

    logger.info(f"  → {result.total_skills_scanned} skills escaneadas")


def scan_agents(result: AuditResult, strict_content: bool = False) -> None:
    """Escanea los agentes del ecosistema.

    Args:
        result: Objeto AuditResult donde se acumulan los hallazgos.
    """
    logger.info("Escaneando agentes...")

    if not AGENTS_DIR.exists():
        logger.warning(f"Directorio de agentes no encontrado: {AGENTS_DIR}")
        return

    agent_dirs = [d for d in AGENTS_DIR.iterdir() if d.is_dir() and not d.name.startswith("_")]

    for agent_dir in agent_dirs:
        result.total_agents_scanned += 1
        identity_md = agent_dir / "IDENTITY.md"

        if identity_md.exists():
            # Escanear prompt injections en IDENTITY.md
            findings = scan_file_for_patterns(
                identity_md,
                PROMPT_INJECTION_PATTERNS,
                "prompt_injection",
                SEVERITY_CRITICAL,
                "Revisar manualmente el contenido de IDENTITY.md del agente.",
                strict_content=strict_content,
            )
            for f in findings:
                result.add_finding(f)

        # Escanear scripts del agente
        scripts_dir = agent_dir / "scripts"
        if scripts_dir.exists():
            for py_file in scripts_dir.rglob("*.py"):
                result.total_python_files_scanned += 1

                findings = scan_file_for_patterns(
                    py_file,
                    SHELL_INJECTION_PATTERNS,
                    "shell_injection",
                    SEVERITY_HIGH,
                    "Usar shlex.split() + shell=False.",
                    strict_content=strict_content,
                )
                for f in findings:
                    result.add_finding(f)

                findings = scan_file_for_patterns(
                    py_file,
                    SECRET_PATTERNS,
                    "hardcoded_secret",
                    SEVERITY_HIGH,
                    "Mover secretos a variables de entorno.",
                    strict_content=strict_content,
                )
                for f in findings:
                    result.add_finding(f)

    logger.info(f"  → {result.total_agents_scanned} agentes escaneados")


def scan_mcp_servers(result: AuditResult, strict_content: bool = False) -> None:
    """Escanea los servidores MCP del ecosistema.

    Args:
        result: Objeto AuditResult donde se acumulan los hallazgos.
    """
    logger.info("Escaneando servidores MCP...")

    mcp_dirs = [MCP_DIR, MCP_SERVER_DIR]

    for mcp_dir in mcp_dirs:
        if not mcp_dir.exists():
            continue

        for py_file in mcp_dir.glob("*.py"):
            result.total_mcp_servers_scanned += 1
            result.total_python_files_scanned += 1

            # Shell injections
            findings = scan_file_for_patterns(
                py_file,
                SHELL_INJECTION_PATTERNS,
                "shell_injection",
                SEVERITY_CRITICAL,
                "Servidores MCP son puntos de entrada expuestos. NUNCA usar shell=True ni eval().",
                strict_content=strict_content,
            )
            for f in findings:
                result.add_finding(f)

            # Secretos hardcodeados
            findings = scan_file_for_patterns(
                py_file,
                SECRET_PATTERNS,
                "hardcoded_secret",
                SEVERITY_CRITICAL,
                "Servidores MCP expuestos no deben contener secretos. Usar variables de entorno.",
                strict_content=strict_content,
            )
            for f in findings:
                result.add_finding(f)

            # Exfiltración
            findings = scan_file_for_patterns(
                py_file,
                EXFILTRATION_PATTERNS,
                "data_exfiltration",
                SEVERITY_HIGH,
                "Verificar que las llamadas HTTP desde servidores MCP son intencionales y seguras.",
                strict_content=strict_content,
            )
            for f in findings:
                result.add_finding(f)

    logger.info(f"  → {result.total_mcp_servers_scanned} servidores MCP escaneados")


# =============================================================================
# PRINTER
# =============================================================================


def print_report_text(result: AuditResult) -> None:
    """Imprime el reporte en formato texto legible.

    Args:
        result: Resultado de la auditoría.
    """
    try:
        from rich.console import Console
        from rich.table import Table
        from rich.panel import Panel

        console = Console()

        # Encabezado
        console.print()
        console.print(
            Panel(
                "[bold]Antigravity MCP & Skills Security Audit[/bold]\n"
                f"Timestamp: {result.timestamp}",
                title="🔒 Auditoría de Seguridad",
                border_style="cyan",
            )
        )

        # Estadísticas
        stats_table = Table(title="Estadísticas del Escaneo", show_header=False)
        stats_table.add_column("Métrica", style="cyan")
        stats_table.add_column("Valor", style="white")
        stats_table.add_row("Skills escaneadas", str(result.total_skills_scanned))
        stats_table.add_row("Agentes escaneados", str(result.total_agents_scanned))
        stats_table.add_row("Servidores MCP escaneados", str(result.total_mcp_servers_scanned))
        stats_table.add_row("Archivos Python escaneados", str(result.total_python_files_scanned))
        stats_table.add_row("Total hallazgos", str(len(result.findings)))
        blocking_count = sum(1 for f in result.findings if f.ci_blocking)
        stats_table.add_row("Hallazgos bloqueantes CI", str(blocking_count))
        stats_table.add_row("Hallazgos no bloqueantes", str(len(result.findings) - blocking_count))
        console.print(stats_table)

        # Resumen por severidad
        if result.summary:
            severity_colors = {
                SEVERITY_CRITICAL: "red bold",
                SEVERITY_HIGH: "red",
                SEVERITY_MEDIUM: "yellow",
                SEVERITY_LOW: "blue",
                SEVERITY_INFO: "dim",
            }
            console.print("\n[bold]Resumen por Severidad:[/bold]")
            for sev in [
                SEVERITY_CRITICAL,
                SEVERITY_HIGH,
                SEVERITY_MEDIUM,
                SEVERITY_LOW,
                SEVERITY_INFO,
            ]:
                count = result.summary.get(sev, 0)
                if count > 0:
                    style = severity_colors.get(sev, "white")
                    console.print(f"  [{style}]{sev}: {count}[/{style}]")

        if result.summary_blocking:
            console.print("\n[bold]Resumen Bloqueante CI:[/bold]")
            for sev in [
                SEVERITY_CRITICAL,
                SEVERITY_HIGH,
                SEVERITY_MEDIUM,
                SEVERITY_LOW,
                SEVERITY_INFO,
            ]:
                count = result.summary_blocking.get(sev, 0)
                if count > 0:
                    style = severity_colors.get(sev, "white")
                    console.print(f"  [{style}]{sev}: {count}[/{style}]")

        # Hallazgos detallados
        if result.findings:
            console.print("\n[bold]Hallazgos Detallados:[/bold]\n")
            findings_table = Table(show_header=True, header_style="bold magenta")
            findings_table.add_column("#", style="dim", width=4)
            findings_table.add_column("Sev", width=8)
            findings_table.add_column("Categoría", width=18)
            findings_table.add_column("Archivo", width=40)
            findings_table.add_column("Línea", width=6)
            findings_table.add_column("CI", width=10)
            findings_table.add_column("Texto", width=30)

            severity_colors_plain = {
                SEVERITY_CRITICAL: "red",
                SEVERITY_HIGH: "red",
                SEVERITY_MEDIUM: "yellow",
                SEVERITY_LOW: "blue",
                SEVERITY_INFO: "dim",
            }

            for i, f in enumerate(result.findings, start=1):
                sev_color = severity_colors_plain.get(f.severity, "white")
                findings_table.add_row(
                    str(i),
                    f"[{sev_color}]{f.severity}[/{sev_color}]",
                    f.category,
                    f.file_path,
                    str(f.line_number),
                    "BLOCK" if f.ci_blocking else "NO-BLOCK",
                    f.matched_text[:30] if f.matched_text else "-",
                )

            console.print(findings_table)
        else:
            console.print("\n[bold green]✅ No se encontraron hallazgos de seguridad.[/bold green]")

        # Resultado final
        console.print()
        if result.has_critical_blocking:
            console.print(
                "[bold red]❌ AUDITORÍA FALLIDA — Hallazgos CRITICAL bloqueantes encontrados[/bold red]"
            )
        elif result.has_high_blocking:
            console.print(
                "[bold yellow]⚠️  AUDITORÍA CON ADVERTENCIAS — Hallazgos HIGH bloqueantes encontrados[/bold yellow]"
            )
        else:
            console.print(
                "[bold green]✅ AUDITORÍA EXITOSA — Sin hallazgos bloqueantes críticos[/bold green]"
            )
        console.print()

    except ImportError:
        # Fallback sin rich
        print(f"\n{'=' * 60}")
        print("Antigravity MCP & Skills Security Audit")
        print(f"{'=' * 60}")
        print(f"Skills: {result.total_skills_scanned} | Agentes: {result.total_agents_scanned}")
        print(
            f"MCP Servers: {result.total_mcp_servers_scanned} | Python files: {result.total_python_files_scanned}"
        )
        print(f"Hallazgos: {len(result.findings)}")
        print(f"Hallazgos bloqueantes CI: {sum(1 for f in result.findings if f.ci_blocking)}")
        if result.summary:
            print(f"Resumen: {result.summary}")
        if result.summary_blocking:
            print(f"Resumen bloqueante CI: {result.summary_blocking}")
        for i, f in enumerate(result.findings, start=1):
            print(
                f"  [{f.severity}] [{'BLOCK' if f.ci_blocking else 'NO-BLOCK'}] "
                f"{f.category} — {f.file_path}:{f.line_number} — {f.matched_text[:50]}"
            )
        print()


def print_report_json(result: AuditResult) -> None:
    """Imprime el reporte en formato JSON.

    Args:
        result: Resultado de la auditoría.
    """
    print(json.dumps(result.to_dict(), indent=2, ensure_ascii=False))


# =============================================================================
# MAIN
# =============================================================================


def run_audit(
    skills: bool = True,
    agents: bool = True,
    mcp: bool = True,
    report_format: str = "text",
    strict_content: bool = False,
) -> AuditResult:
    """Ejecuta la auditoría completa.

    Args:
        skills: Escanear skills.
        agents: Escanear agentes.
        mcp: Escanear servidores MCP.
        report_format: Formato de salida ('text' o 'json').
        strict_content: Si True, trata todo hallazgo como bloqueante de CI.

    Returns:
        Resultado completo de la auditoría.
    """
    result = AuditResult()

    logger.info("Iniciando auditoría de seguridad del ecosistema Antigravity...")
    logger.info(f"Directorio raíz: {PROJECT_ROOT}")

    if skills:
        scan_skills(result, strict_content=strict_content)

    if agents:
        scan_agents(result, strict_content=strict_content)

    if mcp:
        scan_mcp_servers(result, strict_content=strict_content)

    # Imprimir resultado
    if report_format == "json":
        print_report_json(result)
    else:
        print_report_text(result)

    # Guardar log
    LOGS_DIR.mkdir(parents=True, exist_ok=True)
    log_file = LOGS_DIR / f"audit_{datetime.now(tz=UTC).strftime('%Y%m%d_%H%M%S')}.json"
    log_file.write_text(
        json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    logger.info(f"Reporte guardado en: {log_file}")

    return result


def main() -> None:
    """Entry point del script."""
    parser = argparse.ArgumentParser(
        description="Antigravity MCP & Skills Security Auditor",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--skills-only",
        action="store_true",
        help="Solo escanear skills",
    )
    parser.add_argument(
        "--mcp-only",
        action="store_true",
        help="Solo escanear servidores MCP",
    )
    parser.add_argument(
        "--agents-only",
        action="store_true",
        help="Solo escanear agentes",
    )
    parser.add_argument(
        "--report",
        choices=["text", "json"],
        default="text",
        help="Formato del reporte (default: text)",
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Modo detallado",
    )
    parser.add_argument(
        "--fail-on-high",
        action="store_true",
        help="Retornar exit code 1 si hay hallazgos HIGH o CRITICAL (para CI)",
    )
    parser.add_argument(
        "--strict-content",
        action="store_true",
        help=("Tratar hallazgos en contenido de skills/documentación como bloqueantes de CI."),
    )

    args = parser.parse_args()

    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # Determinar qué escanear
    scan_skills_flag = True
    scan_agents_flag = True
    scan_mcp_flag = True

    if args.skills_only:
        scan_agents_flag = False
        scan_mcp_flag = False
    elif args.mcp_only:
        scan_skills_flag = False
        scan_agents_flag = False
    elif args.agents_only:
        scan_skills_flag = False
        scan_mcp_flag = False

    result = run_audit(
        skills=scan_skills_flag,
        agents=scan_agents_flag,
        mcp=scan_mcp_flag,
        report_format=args.report,
        strict_content=args.strict_content,
    )

    # Exit code para CI
    if args.fail_on_high and (result.has_critical_blocking or result.has_high_blocking):
        sys.exit(1)
    elif result.has_critical_blocking:
        sys.exit(2)


if __name__ == "__main__":
    main()
