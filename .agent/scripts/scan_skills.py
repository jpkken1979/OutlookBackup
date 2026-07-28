#!/usr/bin/env python3
"""Skill & Plugin Static Scanner — Análisis de código peligroso.

Inspirado en el SkillScanner de OpenClaw que analiza código de
skills/plugins buscando patrones peligrosos a nivel de línea
y de fuente completa.

Severidades:
  CRITICAL — Ejecución arbitraria, crypto-mining, exfiltración masiva
  HIGH     — Shell injection, env harvesting + network send
  WARN     — Código ofuscado, WebSocket a puertos no-estándar

Escanea:
  - Archivos Python (.py) en skills/, plugins/, agents/
  - Detección de eval/exec, subprocess con shell=True
  - Crypto-mining references (crypto, mining, hashrate)
  - Exfiltración: lectura de archivos + envío por red
  - Ofuscación: hex/base64 encoding sospechoso
  - Reverse shells

Uso:
    python .agent/scripts/scan_skills.py
    python .agent/scripts/scan_skills.py --json
    python .agent/scripts/scan_skills.py --dir .agent/plugins
    python .agent/scripts/scan_skills.py --severity critical

v1.0.0 - 2026-02-27 — Inspirado en OpenClaw SkillScanner
"""

from __future__ import annotations

import json
import logging
import io
import re
import sys
import tokenize
from dataclasses import dataclass, field
from pathlib import Path

# Evita crashes por encoding en consolas Windows cp932/cp1252.
for _stream in (sys.stdout, sys.stderr):
    if hasattr(_stream, "reconfigure"):
        try:
            _stream.reconfigure(encoding="utf-8", errors="replace")
        except (OSError, ValueError):
            pass

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("antigravity.scan_skills")

# =============================================================================
# CONSTANTS
# =============================================================================

PROJECT_ROOT = Path(__file__).parent.parent.parent

# =============================================================================
# SEVERITY LEVELS
# =============================================================================

SEVERITY_CRITICAL = "CRITICAL"
SEVERITY_HIGH = "HIGH"
SEVERITY_WARN = "WARN"
SEVERITY_INFO = "INFO"

SEVERITY_ORDER = {
    SEVERITY_CRITICAL: 0,
    SEVERITY_HIGH: 1,
    SEVERITY_WARN: 2,
    SEVERITY_INFO: 3,
}


# =============================================================================
# SCAN RULES — Patrones por línea
# =============================================================================


@dataclass
class ScanRule:
    """Regla de escaneo con patrón regex."""

    id: str
    pattern: re.Pattern[str]
    severity: str
    description: str
    category: str  # "exec", "shell", "crypto", "exfil", "obfuscation", "network"
    code_context_only: bool = (
        False  # Si True, no dispara cuando el match está dentro de un string literal
    )


LINE_RULES: list[ScanRule] = [
    # CRITICAL — Ejecución arbitraria
    ScanRule(
        id="EXEC-001",
        pattern=re.compile(r"\beval\s*\(", re.IGNORECASE),
        severity=SEVERITY_CRITICAL,
        description="eval() — arbitrary code execution",
        category="exec",
        code_context_only=True,
    ),
    ScanRule(
        id="EXEC-002",
        pattern=re.compile(r"\bexec\s*\(", re.IGNORECASE),
        severity=SEVERITY_CRITICAL,
        description="exec() — arbitrary code execution",
        category="exec",
        code_context_only=True,
    ),
    ScanRule(
        id="EXEC-003",
        pattern=re.compile(r"\bcompile\s*\(.+,\s*['\"]exec", re.IGNORECASE),
        severity=SEVERITY_CRITICAL,
        description="compile() with exec mode — dynamic code generation",
        category="exec",
        # No code_context_only: el patrón incluye el literal 'exec' como arg del compile,
        # por lo que necesita ver el contenido original de la línea para detectarlo.
    ),
    ScanRule(
        id="EXEC-004",
        pattern=re.compile(r"__import__\s*\("),
        severity=SEVERITY_HIGH,
        description="__import__() — dynamic module loading",
        category="exec",
        code_context_only=True,
    ),
    # CRITICAL — Shell injection
    ScanRule(
        id="SHELL-001",
        pattern=re.compile(r"subprocess\.\w+\(.+shell\s*=\s*True", re.DOTALL),
        severity=SEVERITY_CRITICAL,
        description="subprocess with shell=True — command injection risk",
        category="shell",
        code_context_only=True,
    ),
    ScanRule(
        id="SHELL-002",
        pattern=re.compile(r"\bos\.system\s*\("),
        severity=SEVERITY_CRITICAL,
        description="os.system() — shell command execution",
        category="shell",
        code_context_only=True,
    ),
    ScanRule(
        id="SHELL-003",
        pattern=re.compile(r"\bos\.popen\s*\("),
        severity=SEVERITY_HIGH,
        description="os.popen() — shell command execution",
        category="shell",
        code_context_only=True,
    ),
    # CRITICAL — Crypto-mining
    ScanRule(
        id="CRYPTO-001",
        pattern=re.compile(r"\b(hashrate|stratum|xmrig|monero|coinminer)\b", re.IGNORECASE),
        severity=SEVERITY_CRITICAL,
        description="Crypto-mining reference detected",
        category="crypto",
    ),
    ScanRule(
        id="CRYPTO-002",
        pattern=re.compile(r"\b(cryptonight|randomx|ethash|equihash|scrypt)\b", re.IGNORECASE),
        severity=SEVERITY_CRITICAL,
        description="Mining algorithm reference detected",
        category="crypto",
    ),
    # HIGH — Exfiltración potencial
    ScanRule(
        id="EXFIL-001",
        pattern=re.compile(
            r"(requests|httpx|urllib|aiohttp)\.(post|put|patch)\s*\(", re.IGNORECASE
        ),
        severity=SEVERITY_WARN,
        description="HTTP write operation — verify not sending sensitive data",
        category="exfil",
        code_context_only=True,
    ),
    ScanRule(
        id="EXFIL-002",
        pattern=re.compile(r"socket\.connect\s*\("),
        severity=SEVERITY_HIGH,
        description="Raw socket connection — potential data exfiltration",
        category="exfil",
        code_context_only=True,
    ),
    # HIGH — Reverse shell patterns
    ScanRule(
        id="RSHELL-001",
        pattern=re.compile(
            r"(socket|subprocess).*(/bin/sh|/bin/bash|cmd\.exe|powershell)", re.IGNORECASE
        ),
        severity=SEVERITY_CRITICAL,
        description="Possible reverse shell pattern",
        category="shell",
        code_context_only=True,
    ),
    ScanRule(
        id="RSHELL-002",
        pattern=re.compile(r"pty\.spawn\s*\("),
        severity=SEVERITY_CRITICAL,
        description="pty.spawn() — often used in reverse shells",
        category="shell",
        code_context_only=True,
    ),
    # WARN — Ofuscación
    ScanRule(
        id="OBFUSC-001",
        pattern=re.compile(r"\\x[0-9a-f]{2}.*\\x[0-9a-f]{2}.*\\x[0-9a-f]{2}", re.IGNORECASE),
        severity=SEVERITY_WARN,
        description="Hex-encoded string chain — possible obfuscation",
        category="obfuscation",
    ),
    ScanRule(
        id="OBFUSC-002",
        pattern=re.compile(r"base64\.b64decode\s*\(.{50,}\)"),
        severity=SEVERITY_WARN,
        description="Long base64 decode — possible obfuscated payload",
        category="obfuscation",
    ),
    ScanRule(
        id="OBFUSC-003",
        pattern=re.compile(r"codecs\.decode\s*\(.+,\s*['\"]rot", re.IGNORECASE),
        severity=SEVERITY_WARN,
        description="ROT encoding — possible obfuscation",
        category="obfuscation",
    ),
    # WARN — Red
    ScanRule(
        id="NET-001",
        pattern=re.compile(r"websocket.*connect.*:\d{4,5}", re.IGNORECASE),
        severity=SEVERITY_WARN,
        description="WebSocket connection to non-standard port",
        category="network",
    ),
    # HIGH — Environment harvesting
    ScanRule(
        id="ENV-001",
        pattern=re.compile(r"os\.environ\b(?!\.get\()"),
        severity=SEVERITY_WARN,
        description="Full os.environ access — verify not harvesting all env vars",
        category="exfil",
    ),
    ScanRule(
        id="ENV-002",
        pattern=re.compile(r"dict\(os\.environ\)"),
        severity=SEVERITY_HIGH,
        description="Copying entire environment — possible env harvesting",
        category="exfil",
    ),
    # HIGH — File system
    ScanRule(
        id="FS-001",
        pattern=re.compile(r"shutil\.rmtree\s*\(\s*['\"]?/", re.IGNORECASE),
        severity=SEVERITY_CRITICAL,
        description="Recursive delete from root path — destructive operation",
        category="exec",
    ),
    ScanRule(
        id="FS-002",
        pattern=re.compile(r"pathlib.*unlink.*missing_ok|os\.remove.*\.\.", re.IGNORECASE),
        severity=SEVERITY_WARN,
        description="File deletion with path traversal risk",
        category="exec",
    ),
]


# =============================================================================
# SOURCE-LEVEL RULES — Análisis de archivo completo
# =============================================================================


@dataclass
class SourceRule:
    """Regla que analiza el archivo completo (multi-línea)."""

    id: str
    severity: str
    description: str
    category: str
    check: str  # Nombre del método de verificación


def _check_file_read_plus_network(source: str) -> bool:
    """Detecta patrón: lee archivos + envía por red."""
    has_file_read = bool(
        re.search(r"(open\s*\(|Path.*read_text|Path.*read_bytes|\.read\(\))", source)
    )
    has_network_write = bool(
        re.search(r"(requests\.post|httpx\.post|urllib\.request\.urlopen|aiohttp.*post)", source)
    )
    return has_file_read and has_network_write


def _check_env_harvest_plus_network(source: str) -> bool:
    """Detecta patrón: recolecta env + envía por red."""
    has_env_access = bool(re.search(r"(os\.environ|dict\(os\.environ\))", source))
    has_network = bool(re.search(r"(requests\.|httpx\.|urllib\.|aiohttp\.|socket\.)", source))
    return has_env_access and has_network


def _check_excessive_imports(source: str) -> bool:
    """Detecta exceso de imports sospechosos (>5 imports de red/sistema)."""
    suspicious = re.findall(
        r"\bimport\s+(socket|subprocess|ctypes|multiprocessing|threading|http\.server)",
        source,
    )
    return len(suspicious) >= 4


SOURCE_RULES: list[SourceRule] = [
    SourceRule(
        id="SRC-001",
        severity=SEVERITY_HIGH,
        description="File read + network write — potential data exfiltration",
        category="exfil",
        check="file_read_plus_network",
    ),
    SourceRule(
        id="SRC-002",
        severity=SEVERITY_CRITICAL,
        description="Environment harvesting + network send — credential theft pattern",
        category="exfil",
        check="env_harvest_plus_network",
    ),
    SourceRule(
        id="SRC-003",
        severity=SEVERITY_WARN,
        description="Excessive system/network imports — suspicious module loading",
        category="obfuscation",
        check="excessive_imports",
    ),
]

_SOURCE_CHECKS = {
    "file_read_plus_network": _check_file_read_plus_network,
    "env_harvest_plus_network": _check_env_harvest_plus_network,
    "excessive_imports": _check_excessive_imports,
}


# =============================================================================
# DATA MODELS
# =============================================================================


@dataclass
class Finding:
    """Un hallazgo de seguridad."""

    rule_id: str
    severity: str
    file: str
    line: int | None  # None para source-level findings
    category: str
    description: str
    snippet: str = ""

    def to_dict(self) -> dict:
        """Serializa a diccionario."""
        result: dict = {
            "rule_id": self.rule_id,
            "severity": self.severity,
            "file": self.file,
            "category": self.category,
            "description": self.description,
        }
        if self.line is not None:
            result["line"] = self.line
        if self.snippet:
            result["snippet"] = self.snippet
        return result


@dataclass
class ScanReport:
    """Reporte de escaneo completo."""

    findings: list[Finding] = field(default_factory=list)
    files_scanned: int = 0
    directories_scanned: list[str] = field(default_factory=list)

    @property
    def critical_count(self) -> int:
        """Número de findings CRITICAL."""
        return sum(1 for f in self.findings if f.severity == SEVERITY_CRITICAL)

    @property
    def high_count(self) -> int:
        """Número de findings HIGH."""
        return sum(1 for f in self.findings if f.severity == SEVERITY_HIGH)

    def to_dict(self) -> dict:
        """Serializa a diccionario."""
        return {
            "files_scanned": self.files_scanned,
            "directories_scanned": self.directories_scanned,
            "total_findings": len(self.findings),
            "by_severity": {
                "critical": self.critical_count,
                "high": self.high_count,
                "warn": sum(1 for f in self.findings if f.severity == SEVERITY_WARN),
                "info": sum(1 for f in self.findings if f.severity == SEVERITY_INFO),
            },
            "findings": [f.to_dict() for f in self.findings],
        }


# =============================================================================
# SCANNER ENGINE
# =============================================================================

# Archivos seguros que se excluyen del escaneo
_SAFE_PATTERNS = {
    "test_",
    "_test.py",
    "conftest.py",
    "__pycache__",
    ".pyc",
    "_deprecated",
    # Codigo archivado (no activo): no debe gatear CI, igual que _deprecated.
    "_archive",
    # Resultados de benchmarks científicos (HumanEval, SWE-bench)
    # eval() es parte de las soluciones generadas, no código de producción
    "benchmarks/results",
}

# Rutas específicas con falsos positivos documentados.
# Cada entrada es un fragmento de ruta (posix, lowercase) y una justificación.
_ALLOWLIST_PATHS: dict[str, str] = {
    # soffice.py: os.environ.copy() pasa el entorno al proceso LibreOffice
    # vía subprocess. socket se usa solo para detectar si AF_UNIX está bloqueado.
    # No hay envío de datos por red — el socket nunca se conecta a un host externo.
    "skills/docx-v2/scripts/office/soffice.py": "env passed to soffice subprocess, no network exfil",
    "skills/pptx-v2/scripts/office/soffice.py": "env passed to soffice subprocess, no network exfil",
    "skills/xlsx/scripts/office/soffice.py": "env passed to soffice subprocess, no network exfil",
    # remote_control.py: os.environ.copy() pasa env al subprocess Python del MCP server.
    # urllib.request se usa únicamente para health check GET /health.
    "skills/remote-control/scripts/remote_control.py": "env passed to mcp server subprocess, urllib for health check only",
    # oauth_demo.py: os.environ.get() para secrets (patrón correcto).
    # Las llamadas HTTP reales están comentadas; el demo no envía datos de entorno.
    "skills/oauth-social-auth/scripts/oauth_demo.py": "demo file, env vars via .get(), no real http calls",
    # shopify_graphql.py: os.environ.get() para credenciales Shopify (patrón correcto).
    # urllib.request se usa para llamadas a la Shopify GraphQL API con el token del usuario.
    "skills/shopify-development/scripts/shopify_graphql.py": "env vars via .get(), shopify api client",
    # mega_upgrade.py: os.environ.get() para LINE_NOTIFY_TOKEN y otros tokens.
    # urllib.request envía notificaciones al webhook configurado por el usuario.
    "skills/uns-mega-upgrade/scripts/mega_upgrade.py": "env vars via .get(), user-configured notification webhooks",
    # visa_tracker.py: os.environ.get() para LINE_NOTIFY_TOKEN.
    # urllib.request envía notificaciones de vencimiento de visados al webhook del usuario.
    "skills/uns-visa-tracker-upgrade/scripts/visa_tracker.py": "env vars via .get(), user-configured line notify webhook",
    # egov_api.py: open() lee certificados digitales del usuario (電子証明書) necesarios
    # para la firma electrónica ante la API e-Gov japonesa. Uso legítimo de file+network.
    "skills/haken-saas/integrations/egov_api.py": "reads user cert files for e-gov digital signature, legitimate file+network pattern",
    # Falsos positivos de la heuristica file/env + network (SRC-001/SRC-002):
    # agentes del ecosistema que leen config ANTIGRAVITY_* (o credenciales del
    # servicio destino) y hablan con el gateway LOCAL :4747 o con la API
    # intencionada. No hay exfiltracion — es el patron normal agente->gateway/API.
    # _agent_utils.py: lee ANTIGRAVITY_LLM_* y urllib al Ollama/gateway local.
    "agents/_agent_utils.py": "reads ANTIGRAVITY_LLM_* config, urllib to local ollama/gateway",
    # excel-specialist: lee ANTIGRAVITY_GATEWAY/API_KEY, urllib al gateway local.
    "agents/excel-specialist/scripts/main.py": "reads ANTIGRAVITY_* config, urllib to local gateway",
    # api-tester: su proposito ES hacer HTTP requests de prueba a URLs dadas.
    "agents/api-tester/scripts/main.py": "api testing agent — http requests are its purpose",
    # content-curator: lee ANTIGRAVITY_GATEWAY_URL, urllib al gateway local + RSS.
    "agents/content-curator/scripts/monitor.py": "reads ANTIGRAVITY_GATEWAY_URL, local gateway + rss feeds",
    "agents/content-curator/scripts/scheduler.py": "reads ANTIGRAVITY_GATEWAY_URL, local gateway health check",
    # scheduler: integracion Google Calendar — httpx al OAuth/API de Google con
    # GOOGLE_CALENDAR_* del usuario. Uso intencional del servicio, no exfiltracion.
    "agents/scheduler/scripts/scheduler.py": "google calendar integration, oauth+api with user GOOGLE_CALENDAR_* creds",
}


# Patrones que aplican SOLO al nombre del archivo.
# Usamos esto para evitar que directorios temporales de pytest (p.ej.
# "test_scan_recursive0/") hagan que se salten archivos legítimos dentro.
_FILENAME_SAFE_PATTERNS = {"test_", "_test.py", "conftest.py", ".pyc"}
# Patrones que aplican al PATH COMPLETO (marcadores de directorio o extensión).
_PATH_SAFE_PATTERNS = {"__pycache__", "_deprecated", "_archive", "benchmarks/results"}

# Regexp para enmascarar strings de una línea antes de aplicar reglas code_context_only.
_INLINE_STRING_RE = re.compile(
    r"""(?:r|b|rb|br|f|fr|rf)?(?:"[^"\\\n]*(?:\\.[^"\\\n]*)*"|'[^'\\\n]*(?:\\.[^'\\\n]*)*')"""
)


def _mask_inline_strings(line: str) -> str:
    """Reemplaza el contenido de string literals de una línea con 'X'.

    Permite que el regex del patrón vea la estructura de la línea (nombres de
    función, paréntesis) pero no el contenido de los strings, evitando falsos
    positivos cuando 'eval()' aparece como texto dentro de un string literal.
    """

    def _mask(m: re.Match) -> str:
        s = m.group(0)
        for i, c in enumerate(s):
            if c in ('"', "'"):
                return s[: i + 1] + "X" * (len(s) - i - 2) + s[-1]
        return s

    return _INLINE_STRING_RE.sub(_mask, line)


def _should_skip(file_path: Path) -> bool:
    """Determina si un archivo debe saltarse."""
    # _FILENAME_SAFE_PATTERNS aplica solo al nombre del archivo.
    # Evita que directorios temporales de pytest (p.ej. test_scan_recursive0/)
    # hagan que se salten archivos legítimos dentro de ellos.
    filename = file_path.name.lower()
    if any(pattern in filename for pattern in _FILENAME_SAFE_PATTERNS):
        return True
    # _PATH_SAFE_PATTERNS aplica al path completo (marcadores de directorio).
    path_text = file_path.as_posix().lower()
    if any(pattern in path_text for pattern in _PATH_SAFE_PATTERNS):
        return True
    # _ALLOWLIST_PATHS identifica archivos concretos con falsos positivos documentados.
    return any(allowed in path_text for allowed in _ALLOWLIST_PATHS)


def _string_and_comment_lines(source: str) -> set[int]:
    """Retorna líneas que son comentarios o pertenecen a strings multilínea.

    Las líneas que *contienen* un string literal de una sola línea no se
    excluyen: `os.system('ls')` sigue siendo código detectable aunque tenga
    un argumento de tipo string. Solo se excluyen:
    - Líneas de comentario (`# ...`)
    - Líneas interiores a strings multilínea (docstrings / triple-quote)
    """
    ignored: set[int] = set()
    try:
        for token in tokenize.generate_tokens(io.StringIO(source).readline):
            if token.type == tokenize.COMMENT:
                ignored.add(token.start[0])
            elif token.type == tokenize.STRING:
                start_line = token.start[0]
                end_line = token.end[0]
                # Solo strings multilínea (docstrings).
                # Strings de una línea son contexto normal de código.
                if start_line != end_line:
                    ignored.update(range(start_line, end_line + 1))
    except tokenize.TokenError:
        # Si el archivo no tokeniza bien, no bloquear el escaneo.
        return set()
    return ignored


def scan_file(file_path: Path, relative_to: Path | None = None) -> list[Finding]:
    """Escanea un archivo Python individual.

    Args:
        file_path: Ruta al archivo Python.
        relative_to: Directorio base para rutas relativas.

    Returns:
        Lista de findings.
    """
    findings: list[Finding] = []
    display_path = str(file_path.relative_to(relative_to)) if relative_to else str(file_path)

    try:
        source = file_path.read_text(encoding="utf-8")
    except (UnicodeDecodeError, OSError):
        return findings

    lines = source.splitlines()
    ignored_lines = _string_and_comment_lines(source)

    # 1. Line-level rules
    for i, line in enumerate(lines, 1):
        # Omitir comments/docstrings/strings para reducir falsos positivos.
        if i in ignored_lines:
            continue
        stripped = line.strip()

        for rule in LINE_RULES:
            check_line = _mask_inline_strings(line) if rule.code_context_only else line
            if rule.pattern.search(check_line):
                findings.append(
                    Finding(
                        rule_id=rule.id,
                        severity=rule.severity,
                        file=display_path,
                        line=i,
                        category=rule.category,
                        description=rule.description,
                        snippet=stripped[:120],
                    )
                )

    # 2. Source-level rules
    for rule in SOURCE_RULES:
        check_fn = _SOURCE_CHECKS.get(rule.check)
        if check_fn and check_fn(source):
            findings.append(
                Finding(
                    rule_id=rule.id,
                    severity=rule.severity,
                    file=display_path,
                    line=None,
                    category=rule.category,
                    description=rule.description,
                )
            )

    return findings


def scan_directory(
    directory: Path,
    relative_to: Path | None = None,
    min_severity: str = SEVERITY_INFO,
) -> list[Finding]:
    """Escanea todos los archivos Python en un directorio.

    Args:
        directory: Directorio a escanear.
        relative_to: Base para rutas relativas.
        min_severity: Severidad mínima a reportar.

    Returns:
        Lista de findings filtrada por severidad.
    """
    findings: list[Finding] = []
    min_order = SEVERITY_ORDER.get(min_severity, 3)

    if not directory.is_dir():
        return findings

    for py_file in sorted(directory.rglob("*.py")):
        if _should_skip(py_file):
            continue
        file_findings = scan_file(py_file, relative_to)
        findings.extend(f for f in file_findings if SEVERITY_ORDER.get(f.severity, 3) <= min_order)

    return findings


def scan_ecosystem(
    project_root: Path | None = None,
    min_severity: str = SEVERITY_INFO,
) -> ScanReport:
    """Escanea el ecosistema completo: skills, plugins, agents.

    Args:
        project_root: Raíz del proyecto.
        min_severity: Severidad mínima.

    Returns:
        ScanReport con todos los findings.
    """
    root = project_root or PROJECT_ROOT
    agent_dir = root / ".agent"
    report = ScanReport()

    scan_dirs = [
        agent_dir / "skills",
        agent_dir / "plugins",
        agent_dir / "agents",
    ]

    files_scanned = 0
    for scan_dir in scan_dirs:
        if not scan_dir.is_dir():
            continue

        report.directories_scanned.append(str(scan_dir.relative_to(root)))
        py_files = list(scan_dir.rglob("*.py"))
        files_scanned += len(py_files)

        findings = scan_directory(scan_dir, relative_to=root, min_severity=min_severity)
        report.findings.extend(findings)

    report.files_scanned = files_scanned

    # Ordenar por severidad
    report.findings.sort(key=lambda f: SEVERITY_ORDER.get(f.severity, 3))

    return report


# =============================================================================
# CLI
# =============================================================================


def print_report(report: ScanReport) -> None:
    """Imprime reporte legible a stdout."""
    severity_emoji = {
        SEVERITY_CRITICAL: "🔴",
        SEVERITY_HIGH: "🟠",
        SEVERITY_WARN: "🟡",
        SEVERITY_INFO: "🔵",
    }

    print(f"\n{'=' * 70}")
    print(f"Skill & Plugin Security Scanner — {report.files_scanned} files scanned")
    print(f"Directories: {', '.join(report.directories_scanned)}")
    print(f"{'=' * 70}\n")

    if not report.findings:
        print("✅ No security issues found!\n")
        return

    # Agrupar por severidad
    for severity in [SEVERITY_CRITICAL, SEVERITY_HIGH, SEVERITY_WARN, SEVERITY_INFO]:
        findings = [f for f in report.findings if f.severity == severity]
        if not findings:
            continue

        emoji = severity_emoji.get(severity, "⚪")
        print(f"{emoji} {severity} ({len(findings)}):\n")
        for f in findings:
            loc = f"{f.file}:{f.line}" if f.line else f.file
            print(f"  [{f.rule_id}] {loc}")
            print(f"         {f.description}")
            if f.snippet:
                print(f"         → {f.snippet}")
            print()

    print(f"{'=' * 70}")
    print(
        f"Summary: {report.critical_count} critical, {report.high_count} high, "
        f"{len(report.findings) - report.critical_count - report.high_count} other"
    )
    print(f"{'=' * 70}\n")


def main() -> None:
    """Entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="Escanear skills/plugins por código peligroso")
    parser.add_argument("--json", action="store_true", help="Output JSON")
    parser.add_argument(
        "--severity",
        choices=["critical", "high", "warn", "info"],
        default="info",
        help="Severidad mínima a reportar (default: info)",
    )
    parser.add_argument(
        "--fail-on-high",
        action="store_true",
        help="Retornar exit code 1 si hay hallazgos HIGH o CRITICAL",
    )
    parser.add_argument("--dir", type=str, default=None, help="Directorio específico a escanear")
    args = parser.parse_args()

    severity_map = {
        "critical": SEVERITY_CRITICAL,
        "high": SEVERITY_HIGH,
        "warn": SEVERITY_WARN,
        "info": SEVERITY_INFO,
    }
    min_severity = severity_map[args.severity]

    if args.dir:
        scan_dir = Path(args.dir)
        report = ScanReport(directories_scanned=[str(scan_dir)])
        py_files = list(scan_dir.rglob("*.py"))
        report.files_scanned = len(py_files)
        report.findings = scan_directory(scan_dir, min_severity=min_severity)
    else:
        report = scan_ecosystem(min_severity=min_severity)

    if args.json:
        print(json.dumps(report.to_dict(), indent=2))
    else:
        print_report(report)

    # Exit code: 1 si hay CRITICAL, o HIGH si se habilita --fail-on-high
    if report.critical_count > 0:
        sys.exit(1)
    if args.fail_on_high and report.high_count > 0:
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
