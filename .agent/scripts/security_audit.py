#!/usr/bin/env python3
"""Security Audit Scanner — Auditoría de seguridad para el ecosistema OpenAntigravity.

Inspirado en el concepto AgentShield de ECC, adaptado nativamente para
el ecosistema Antigravity. Escanea CLAUDE.md, .mcp.json, hooks, configs
y archivos de proyecto buscando vulnerabilidades de seguridad.

Categorías de chequeo:
  1. SECRETS   — API keys, tokens, passwords en texto plano
  2. MCP       — Configuración de servidores MCP (auth, paths, flags)
  3. PATHS     — Path traversal, rutas relativas peligrosas
  4. PERMISSIONS — .env files, .gitignore coverage
  5. HOOKS     — Hook scripts con inyección o descargas
  6. CONFIG    — Higiene de configuración, tool budget, deps vulnerables

Severidades:
  HIGH   — Riesgo inmediato de exfiltración o ejecución arbitraria
  MEDIUM — Mala práctica que podría ser explotada
  LOW    — Recomendación de hardening
  INFO   — Observación informativa

Uso:
    python .agent/scripts/security_audit.py
    python .agent/scripts/security_audit.py --target /path/to/project
    python .agent/scripts/security_audit.py --format text
    python .agent/scripts/security_audit.py --severity medium
    python .agent/scripts/security_audit.py --format json --severity high

Exit codes:
  0 = Sin hallazgos HIGH
  1 = Hallazgos HIGH encontrados

v1.0.0 - 2026-03-24 — Inspirado en AgentShield de ECC
"""

from __future__ import annotations

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

logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("antigravity.security_audit")

# =============================================================================
# CONSTANTS
# =============================================================================

SEVERITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}

# Archivos a escanear para secrets (relative to project root)
SCANNABLE_EXTENSIONS = {".md", ".json", ".toml", ".yaml", ".yml", ".cfg", ".ini", ".txt"}

# Archivos/dirs explícitamente seguros (no generar falsos positivos)
SAFE_FILES = {".env.example", ".env.template", ".env.sample"}

# Patrones de secrets conocidos
SECRET_PATTERNS: list[tuple[str, str, str]] = [
    # (nombre, regex, severidad)
    ("API Key de OpenAI", r"sk-[a-zA-Z0-9]{20,}", "HIGH"),
    ("API Key de AWS (AKIA)", r"AKIA[0-9A-Z]{16}", "HIGH"),
    ("Token de GitHub (ghp_)", r"ghp_[a-zA-Z0-9]{36,}", "HIGH"),
    ("Token de GitHub (ghs_)", r"ghs_[a-zA-Z0-9]{36,}", "HIGH"),
    ("Token de GitHub (gho_)", r"gho_[a-zA-Z0-9]{36,}", "HIGH"),
    ("Token de GitHub (github_pat_)", r"github_pat_[a-zA-Z0-9_]{22,}", "HIGH"),
    ("API Key de Anthropic", r"sk-ant-[a-zA-Z0-9\-]{20,}", "HIGH"),
    ("Token Bearer literal", r"Bearer\s+[a-zA-Z0-9\-_.]{20,}", "HIGH"),
    ("API Key de Slack (xoxb)", r"xoxb-[0-9]{10,}-[a-zA-Z0-9]{20,}", "HIGH"),
    ("API Key de Slack (xoxp)", r"xoxp-[0-9]{10,}-[a-zA-Z0-9]{20,}", "HIGH"),
    ("API Key de Stripe (sk_live)", r"sk_live_[a-zA-Z0-9]{20,}", "HIGH"),
    ("API Key de SendGrid (SG.)", r"SG\.[a-zA-Z0-9\-_]{20,}", "HIGH"),
    ("API Key de Telegram Bot", r"\d{8,10}:[a-zA-Z0-9_-]{35}", "MEDIUM"),
    (
        "Contraseña en texto plano",
        r"""(?:password|passwd|pwd)\s*[:=]\s*['"][^'"]{8,}['"]""",
        "HIGH",
    ),
    (
        "Token genérico en config",
        r"""(?:token|secret|api_key)\s*[:=]\s*['"][a-zA-Z0-9\-_.]{16,}['"]""",
        "MEDIUM",
    ),
    ("Clave privada RSA/EC", r"-----BEGIN\s+(?:RSA |EC )?PRIVATE KEY-----", "HIGH"),
    ("URL con credenciales", r"https?://[^:]+:[^@]+@[a-zA-Z0-9]", "HIGH"),
]

# Flags peligrosos en MCP config
DANGEROUS_FLAGS = ["--no-auth", "--no-verify", "--no-ssl", "--insecure", "--allow-all"]

# Paquetes con CVEs conocidos o deprecados
VULNERABLE_PACKAGES = {
    "node-fetch@1": "CVE-2022-0235 — redirect bypass",
    "minimist@<1.2.6": "CVE-2021-44906 — prototype pollution",
    "lodash@<4.17.21": "CVE-2021-23337 — command injection",
    "axios@<0.21.1": "CVE-2020-28168 — SSRF",
}

# Max MCP tools recomendado (context budget)
MAX_MCP_SERVERS_WARN = 10
MAX_TOOL_ESTIMATE_WARN = 80


# =============================================================================
# DATA CLASSES
# =============================================================================


@dataclass
class Finding:
    """Un hallazgo de seguridad."""

    severity: str
    category: str
    file: str
    line: int | None
    message: str
    recommendation: str

    def to_dict(self) -> dict:
        """Convierte a diccionario para serialización JSON."""
        result: dict = {
            "severity": self.severity,
            "category": self.category,
            "file": self.file,
            "message": self.message,
            "recommendation": self.recommendation,
        }
        if self.line is not None:
            result["line"] = self.line
        return result


@dataclass
class AuditResult:
    """Resultado completo de la auditoría."""

    scan_timestamp: str
    project: str
    total_checks: int = 0
    findings: list[Finding] = field(default_factory=list)
    passed_checks: int = 0

    def add_finding(self, finding: Finding) -> None:
        """Agrega un hallazgo al resultado."""
        self.findings.append(finding)

    def pass_check(self) -> None:
        """Registra un chequeo pasado."""
        self.passed_checks += 1
        self.total_checks += 1

    def fail_check(self, finding: Finding) -> None:
        """Registra un chequeo fallido con hallazgo."""
        self.total_checks += 1
        self.add_finding(finding)

    @property
    def summary(self) -> dict[str, int]:
        """Resumen de hallazgos por severidad."""
        counts: dict[str, int] = {"high": 0, "medium": 0, "low": 0, "info": 0}
        for f in self.findings:
            key = f.severity.lower()
            if key in counts:
                counts[key] += 1
        counts["passed"] = self.passed_checks
        return counts

    def to_dict(self) -> dict:
        """Convierte a diccionario para serialización JSON."""
        return {
            "scan_timestamp": self.scan_timestamp,
            "project": self.project,
            "total_checks": self.total_checks,
            "findings": [f.to_dict() for f in self.findings],
            "summary": self.summary,
        }


# =============================================================================
# SCANNER ENGINE
# =============================================================================


class SecurityAuditor:
    """Motor principal de auditoría de seguridad."""

    def __init__(self, target_dir: Path) -> None:
        self.target = target_dir.resolve()
        self.result = AuditResult(
            scan_timestamp=datetime.now(UTC).isoformat(),
            project=self.target.name,
        )

    def run_all_checks(self) -> AuditResult:
        """Ejecuta todos los chequeos de seguridad."""
        logger.info("Iniciando auditoría de seguridad en: %s", self.target)

        self._check_secrets()
        self._check_mcp_security()
        self._check_path_traversal()
        self._check_permissions()
        self._check_hooks()
        self._check_config_hygiene()

        high_count = self.result.summary["high"]
        total_findings = len(self.result.findings)
        logger.info(
            "Auditoría completa: %d chequeos, %d hallazgos (%d HIGH)",
            self.result.total_checks,
            total_findings,
            high_count,
        )
        return self.result

    # -------------------------------------------------------------------------
    # 1. SECRETS DETECTION
    # -------------------------------------------------------------------------

    def _check_secrets(self) -> None:
        """Escanea archivos de configuración y documentación buscando secrets."""
        logger.info("Escaneando secrets en archivos de configuración...")

        files_to_scan = self._collect_scannable_files()

        if not files_to_scan:
            logger.info("No se encontraron archivos escaneables en el proyecto")
            self.result.pass_check()
            return

        found_any = False
        for file_path in files_to_scan:
            # Saltar archivos seguros conocidos
            if file_path.name in SAFE_FILES:
                continue

            findings_in_file = self._scan_file_for_secrets(file_path)
            if findings_in_file:
                found_any = True
                for finding in findings_in_file:
                    self.result.fail_check(finding)

        if not found_any:
            self.result.pass_check()
            logger.info("  OK No se detectaron secrets hardcodeados")

    def _collect_scannable_files(self) -> list[Path]:
        """Recolecta archivos relevantes para escaneo de secrets."""
        files: list[Path] = []

        # Archivos en raíz del proyecto
        for child in self.target.iterdir():
            if child.is_file() and child.suffix in SCANNABLE_EXTENSIONS:
                files.append(child)

        # CLAUDE.md en .claude/ si existe
        claude_dir = self.target / ".claude"
        if claude_dir.is_dir():
            for child in claude_dir.rglob("*"):
                if child.is_file() and child.suffix in SCANNABLE_EXTENSIONS:
                    files.append(child)

        # .mcp.json explícitamente
        mcp_json = self.target / ".mcp.json"
        if mcp_json.is_file() and mcp_json not in files:
            files.append(mcp_json)

        # pyproject.toml, package.json, etc.
        for config_name in ["pyproject.toml", "package.json", "tsconfig.json", "Cargo.toml"]:
            config_path = self.target / config_name
            if config_path.is_file() and config_path not in files:
                files.append(config_path)

        # .env files (que NO deberían existir, pero si existen, escanear)
        for env_file in self.target.glob(".env*"):
            if env_file.is_file() and env_file.name not in SAFE_FILES and env_file not in files:
                files.append(env_file)

        return files

    def _scan_file_for_secrets(self, file_path: Path) -> list[Finding]:
        """Escanea un archivo individual buscando patrones de secrets."""
        findings: list[Finding] = []
        try:
            content = file_path.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError) as e:
            logger.warning("No se pudo leer %s: %s", file_path, e)
            return findings

        relative_path = self._relative_path(file_path)
        lines = content.splitlines()

        for line_num, line in enumerate(lines, 1):
            # Ignorar líneas que son claramente comentarios o documentación
            stripped = line.strip()
            if self._is_documentation_line(stripped, file_path):
                continue

            for pattern_name, pattern, severity in SECRET_PATTERNS:
                matches = re.finditer(pattern, line, re.IGNORECASE)
                for match in matches:
                    matched_text = match.group()

                    # Filtrar falsos positivos conocidos
                    if self._is_false_positive_secret(matched_text, line, file_path):
                        continue

                    findings.append(
                        Finding(
                            severity=severity,
                            category="secrets",
                            file=relative_path,
                            line=line_num,
                            message=f"{pattern_name} detectado en texto plano",
                            recommendation=(
                                "Mover a variable de entorno. "
                                "Nunca hardcodear secrets en archivos trackeados por git."
                            ),
                        )
                    )

        return findings

    def _is_documentation_line(self, stripped: str, file_path: Path) -> bool:
        """Determina si una línea es claramente documentación/ejemplo."""
        # Líneas de ejemplo en markdown con backticks o código
        if file_path.suffix == ".md":
            if stripped.startswith("```") or stripped.startswith("`"):
                return False  # Los bloques de código SÍ pueden tener secrets
            # Líneas que son patrones regex o explicaciones
            if "patrón" in stripped.lower() or "pattern" in stripped.lower():
                return True
            if stripped.startswith("#") and (
                "ejemplo" in stripped.lower() or "example" in stripped.lower()
            ):
                return True
        return False

    def _is_false_positive_secret(self, matched_text: str, line: str, file_path: Path) -> bool:
        """Filtra falsos positivos conocidos de detección de secrets."""
        lower_line = line.lower()

        # Placeholder texts
        placeholders = [
            "your_",
            "xxx",
            "example",
            "placeholder",
            "changeme",
            "todo",
            "fixme",
            "replace_",
            "insert_",
            "sk-xxx",
            "sk-your",
            "sk-test",
            "test_key",
            "dummy",
        ]
        for ph in placeholders:
            if ph in matched_text.lower():
                return True

        # Regex pattern definitions (el scanner definiendo SUS propios patrones)
        if "re.compile" in line or "re.search" in line or "re.match" in line:
            return True
        if 'r"' in line or "r'" in line:
            # Probablemente un raw string regex
            if any(c in line for c in ["\\s", "\\d", "\\w", "(?:", "[a-zA-Z"]):
                return True

        # Líneas que definen patrones de detección (como este mismo archivo)
        if "SECRET_PATTERNS" in line or "pattern" in lower_line and "regex" in lower_line:
            return True

        # Documentación sobre qué tipos de keys buscar
        if file_path.suffix == ".md":
            if any(
                marker in lower_line
                for marker in ["scan", "detect", "buscar", "check", "patrón", "pattern"]
            ):
                return True
            # Líneas que listan patrones: "sk-*, AKIA*, ghp_*"
            if matched_text.endswith("*") or "*" in line[max(0, line.index(matched_text) - 5) :]:
                return True

        # Variable de entorno referencia (no el valor)
        env_ref_patterns = [
            r"os\.environ",
            r"os\.getenv",
            r"env\[",
            r"process\.env",
            r"std::env::var",
            r"\$\{",
            r"%[A-Z_]+%",
        ]
        for erp in env_ref_patterns:
            if re.search(erp, line):
                return True

        # Comentarios explicativos
        comment_markers = ["#", "//", "/*", "<!--"]
        for marker in comment_markers:
            marker_pos = line.find(marker)
            match_pos = line.find(matched_text)
            if 0 <= marker_pos < match_pos:
                return True

        return False

    # -------------------------------------------------------------------------
    # 2. MCP SERVER SECURITY
    # -------------------------------------------------------------------------

    def _check_mcp_security(self) -> None:
        """Analiza la configuración de servidores MCP."""
        logger.info("Verificando seguridad de servidores MCP...")

        mcp_json_path = self.target / ".mcp.json"
        if not mcp_json_path.is_file():
            logger.info("  OK No se encontró .mcp.json (nada que auditar)")
            self.result.pass_check()
            return

        try:
            mcp_data = json.loads(mcp_json_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError) as e:
            self.result.fail_check(
                Finding(
                    severity="MEDIUM",
                    category="mcp",
                    file=self._relative_path(mcp_json_path),
                    line=None,
                    message=f"No se pudo parsear .mcp.json: {e}",
                    recommendation="Verificar que .mcp.json sea JSON válido.",
                )
            )
            return

        servers = mcp_data.get("mcpServers", {})
        if not servers:
            self.result.pass_check()
            return

        # Check: cantidad de servidores
        server_count = len(servers)
        if server_count > MAX_MCP_SERVERS_WARN:
            self.result.fail_check(
                Finding(
                    severity="LOW",
                    category="mcp",
                    file=self._relative_path(mcp_json_path),
                    line=None,
                    message=f"{server_count} servidores MCP activos (umbral: {MAX_MCP_SERVERS_WARN})",
                    recommendation=(
                        "Considerar desactivar servidores no utilizados "
                        "para reducir el presupuesto de contexto."
                    ),
                )
            )
        else:
            self.result.pass_check()

        # Estimar tools totales (~10 tools por servidor como heurística)
        estimated_tools = server_count * 10
        if estimated_tools > MAX_TOOL_ESTIMATE_WARN:
            self.result.fail_check(
                Finding(
                    severity="LOW",
                    category="config",
                    file=self._relative_path(mcp_json_path),
                    line=None,
                    message=(
                        f"Estimación de ~{estimated_tools} tools MCP "
                        f"(umbral recomendado: {MAX_TOOL_ESTIMATE_WARN})"
                    ),
                    recommendation=(
                        "Demasiados tools inflan el contexto y reducen la calidad "
                        "de las respuestas. Considerar consolidar o desactivar servidores."
                    ),
                )
            )
        else:
            self.result.pass_check()

        # Analizar cada servidor
        for name, config in servers.items():
            self._check_single_mcp_server(name, config, mcp_json_path)

    def _check_single_mcp_server(
        self,
        name: str,
        config: dict,
        mcp_json_path: Path,
    ) -> None:
        """Verifica la seguridad de un servidor MCP individual."""
        relative = self._relative_path(mcp_json_path)

        # Tipo HTTP: verificar HTTPS
        if config.get("type") == "http":
            url = config.get("url", "")
            if url.startswith("http://") and "localhost" not in url and "127.0.0.1" not in url:
                self.result.fail_check(
                    Finding(
                        severity="MEDIUM",
                        category="mcp",
                        file=relative,
                        line=None,
                        message=f"Servidor '{name}' usa HTTP sin TLS: {url}",
                        recommendation="Usar HTTPS para servidores MCP remotos.",
                    )
                )
            else:
                self.result.pass_check()
            return

        args = config.get("args", [])
        env_vars = config.get("env", {})

        # Check: flags peligrosos
        for flag in DANGEROUS_FLAGS:
            if flag in args:
                severity = "MEDIUM" if flag == "--no-auth" else "LOW"
                self.result.fail_check(
                    Finding(
                        severity=severity,
                        category="mcp",
                        file=relative,
                        line=None,
                        message=f"Servidor '{name}' usa flag peligroso: {flag}",
                        recommendation=(
                            f"Evitar '{flag}' en producción. Usar autenticación y TLS apropiados."
                        ),
                    )
                )
            else:
                self.result.pass_check()

        # Check: rutas absolutas (requerido)
        command = config.get("command", "")
        # Solo para servidores Python locales (no npx, uvx, etc.)
        if command in ("python", "python3", "py"):
            for arg in args:
                arg_str = str(arg)
                if arg_str.endswith(".py"):
                    # Considerar absolutas tanto rutas Windows (C:\) como Unix (/)
                    is_abs = Path(arg_str).is_absolute() or arg_str.startswith("/")
                    if not is_abs:
                        self.result.fail_check(
                            Finding(
                                severity="MEDIUM",
                                category="mcp",
                                file=relative,
                                line=None,
                                message=(f"Servidor '{name}' usa ruta relativa: {arg_str}"),
                                recommendation=(
                                    "Usar rutas absolutas en .mcp.json para evitar "
                                    "dependencia del CWD."
                                ),
                            )
                        )
                    else:
                        self.result.pass_check()

        # Check: secrets en args (mala práctica)
        for arg in args:
            arg_str = str(arg)
            for _pname, pattern, _sev in SECRET_PATTERNS:
                if re.search(pattern, arg_str):
                    self.result.fail_check(
                        Finding(
                            severity="HIGH",
                            category="mcp",
                            file=relative,
                            line=None,
                            message=f"Servidor '{name}' tiene un secret en args de comando",
                            recommendation=(
                                "Mover secrets a la sección 'env' de la config MCP "
                                "o a variables de entorno del sistema."
                            ),
                        )
                    )
                    break  # Un hallazgo por servidor es suficiente
            else:
                continue
            break

        # Check: secrets en env vars (valores hardcodeados)
        for env_key, env_val in env_vars.items():
            env_val_str = str(env_val)
            for _pname, pattern, _sev in SECRET_PATTERNS:
                if re.search(pattern, env_val_str):
                    self.result.fail_check(
                        Finding(
                            severity="HIGH",
                            category="mcp",
                            file=relative,
                            line=None,
                            message=(
                                f"Servidor '{name}' tiene secret hardcodeado en env.{env_key}"
                            ),
                            recommendation=(
                                "No hardcodear secrets en .mcp.json. "
                                "Usar referencias a variables de entorno del sistema."
                            ),
                        )
                    )
                    break

        # Check: @latest en NPX (supply chain risk)
        if command in ("npx", "npx.cmd"):
            for arg in args:
                if "@latest" in str(arg):
                    self.result.fail_check(
                        Finding(
                            severity="LOW",
                            category="mcp",
                            file=relative,
                            line=None,
                            message=(
                                f"Servidor '{name}' usa @latest ({arg}). "
                                "Riesgo de supply chain si el paquete es comprometido."
                            ),
                            recommendation=(
                                "Considerar fijar versión específica en vez de @latest."
                            ),
                        )
                    )

    # -------------------------------------------------------------------------
    # 3. PATH TRAVERSAL RISKS
    # -------------------------------------------------------------------------

    def _check_path_traversal(self) -> None:
        """Busca riesgos de path traversal en configs."""
        logger.info("Verificando riesgos de path traversal...")
        found_any = False

        config_files = [
            self.target / ".mcp.json",
            self.target / "pyproject.toml",
            self.target / "package.json",
        ]

        for config_path in config_files:
            if not config_path.is_file():
                continue

            try:
                content = config_path.read_text(encoding="utf-8", errors="replace")
            except (OSError, PermissionError):
                continue

            relative = self._relative_path(config_path)
            lines = content.splitlines()

            for line_num, line in enumerate(lines, 1):
                # Detectar ../ en paths
                if "../" in line or "..\\" in line:
                    # Ignorar comentarios y documentación
                    stripped = line.strip()
                    if stripped.startswith("#") or stripped.startswith("//"):
                        continue

                    found_any = True
                    self.result.fail_check(
                        Finding(
                            severity="MEDIUM",
                            category="paths",
                            file=relative,
                            line=line_num,
                            message="Path con '../' detectado — riesgo de directory traversal",
                            recommendation=(
                                "Usar rutas absolutas en configuraciones. "
                                "Los paths relativos con '../' pueden escapar del sandbox."
                            ),
                        )
                    )

        # Check Tauri allowed paths if accessible
        tauri_conf = self.target / "nexus-app" / "src-tauri" / "tauri.conf.json"
        if tauri_conf.is_file():
            try:
                tauri_data = json.loads(tauri_conf.read_text(encoding="utf-8"))
                # Verificar scope de fs si existe
                security = tauri_data.get("app", {}).get("security", {})
                csp = security.get("csp", "")
                if "unsafe-eval" in csp:
                    found_any = True
                    self.result.fail_check(
                        Finding(
                            severity="HIGH",
                            category="paths",
                            file=self._relative_path(tauri_conf),
                            line=None,
                            message="CSP contiene 'unsafe-eval' — riesgo de XSS",
                            recommendation=(
                                "Eliminar 'unsafe-eval' del CSP de Tauri. "
                                "Usar alternativas seguras para eval dinámico."
                            ),
                        )
                    )
                else:
                    self.result.pass_check()

            except (json.JSONDecodeError, OSError):
                pass

        if not found_any:
            self.result.pass_check()
            logger.info("  OK No se detectaron riesgos de path traversal")

    # -------------------------------------------------------------------------
    # 4. PERMISSION ISSUES
    # -------------------------------------------------------------------------

    def _check_permissions(self) -> None:
        """Verifica permisos y presencia de archivos sensibles."""
        logger.info("Verificando permisos y archivos sensibles...")

        # Check: .env file exists (should be gitignored)
        env_files = list(self.target.glob(".env")) + list(self.target.glob(".env.local"))
        env_files += list(self.target.glob(".env.*.local"))

        for env_file in env_files:
            if env_file.name in SAFE_FILES:
                continue
            self.result.fail_check(
                Finding(
                    severity="MEDIUM",
                    category="permissions",
                    file=self._relative_path(env_file),
                    line=None,
                    message=f"Archivo '{env_file.name}' encontrado en el proyecto",
                    recommendation=(
                        "Verificar que esté en .gitignore y no sea trackeado por git. "
                        "Usar .env.example como plantilla sin valores reales."
                    ),
                )
            )

        if not env_files:
            self.result.pass_check()

        # Check: .gitignore cubre patrones sensibles
        gitignore_path = self.target / ".gitignore"
        if gitignore_path.is_file():
            try:
                gitignore_content = gitignore_path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                gitignore_content = ""

            required_patterns = [
                (".env", "Archivos .env con secrets"),
                ("node_modules", "Dependencias de Node.js"),
                ("__pycache__", "Cache de Python"),
            ]

            for pattern, description in required_patterns:
                if pattern in gitignore_content:
                    self.result.pass_check()
                else:
                    self.result.fail_check(
                        Finding(
                            severity="MEDIUM",
                            category="permissions",
                            file=self._relative_path(gitignore_path),
                            line=None,
                            message=f".gitignore no incluye '{pattern}' ({description})",
                            recommendation=f"Agregar '{pattern}' a .gitignore.",
                        )
                    )
        else:
            self.result.fail_check(
                Finding(
                    severity="MEDIUM",
                    category="permissions",
                    file=".gitignore",
                    line=None,
                    message="No existe archivo .gitignore en el proyecto",
                    recommendation="Crear .gitignore con patrones para .env, node_modules, __pycache__, etc.",
                )
            )

        # Check: archivos con permisos de ejecución que no deberían
        # (En Windows esto no aplica igual, pero verificamos scripts)
        hook_dirs = [
            self.target / ".git" / "hooks",
            self.target / ".husky",
        ]
        for hook_dir in hook_dirs:
            if hook_dir.is_dir():
                self.result.pass_check()
                break
        # No es un error si no hay hooks

    # -------------------------------------------------------------------------
    # 5. HOOK SECURITY
    # -------------------------------------------------------------------------

    def _check_hooks(self) -> None:
        """Verifica seguridad de hooks configurados."""
        logger.info("Verificando seguridad de hooks...")

        hooks_json = self.target / "hooks.json"
        hooks_found = False

        if hooks_json.is_file():
            hooks_found = True
            self._check_hooks_json(hooks_json)

        # Check .claude/hooks si existe
        claude_hooks = self.target / ".claude" / "hooks.json"
        if claude_hooks.is_file():
            hooks_found = True
            self._check_hooks_json(claude_hooks)

        # Check git hooks
        git_hooks_dir = self.target / ".git" / "hooks"
        if git_hooks_dir.is_dir():
            hooks_found = True
            self._check_git_hooks(git_hooks_dir)

        # Check husky
        husky_dir = self.target / ".husky"
        if husky_dir.is_dir():
            hooks_found = True
            self._check_husky_hooks(husky_dir)

        if not hooks_found:
            self.result.pass_check()
            logger.info("  OK No se encontraron hooks configurados")

    def _check_hooks_json(self, hooks_path: Path) -> None:
        """Analiza un archivo hooks.json buscando patrones peligrosos."""
        try:
            data = json.loads(hooks_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return

        relative = self._relative_path(hooks_path)

        # Buscar en todos los valores de forma recursiva
        commands = self._extract_commands_from_json(data)

        for cmd in commands:
            self._check_hook_command(cmd, relative)

    def _extract_commands_from_json(self, obj: object) -> list[str]:
        """Extrae todos los strings de un objeto JSON recursivamente."""
        commands: list[str] = []
        if isinstance(obj, str):
            commands.append(obj)
        elif isinstance(obj, list):
            for item in obj:
                commands.extend(self._extract_commands_from_json(item))
        elif isinstance(obj, dict):
            for value in obj.values():
                commands.extend(self._extract_commands_from_json(value))
        return commands

    def _check_hook_command(self, cmd: str, file_path: str) -> None:
        """Verifica un comando de hook individual."""
        # Inyección de shell via interpolación
        shell_injection_patterns = [
            (r"\$\(.*\)", "Command substitution $() en hook"),
            (r"`[^`]+`", "Backtick execution en hook"),
            (r"\$\{.*\}", "Variable expansion ${} en hook"),
        ]
        for pattern, desc in shell_injection_patterns:
            if re.search(pattern, cmd):
                self.result.fail_check(
                    Finding(
                        severity="MEDIUM",
                        category="hooks",
                        file=file_path,
                        line=None,
                        message=f"{desc}: {cmd[:80]}...",
                        recommendation=(
                            "Evitar interpolación de variables en hooks. "
                            "Usar scripts dedicados con validación de inputs."
                        ),
                    )
                )
                return

        # Descargas de internet
        download_patterns = [
            r"\bcurl\b.*\|\s*(?:bash|sh|python)",
            r"\bwget\b.*-O\s*-\s*\|",
            r"\bcurl\b.*-o\s+/",
            r"\bpowershell\b.*(?:Invoke-WebRequest|iwr|wget)",
        ]
        for pattern in download_patterns:
            if re.search(pattern, cmd, re.IGNORECASE):
                self.result.fail_check(
                    Finding(
                        severity="HIGH",
                        category="hooks",
                        file=file_path,
                        line=None,
                        message=f"Hook descarga y ejecuta código de internet: {cmd[:80]}...",
                        recommendation=(
                            "Nunca descargar y ejecutar código en hooks. "
                            "Usar dependencias declaradas y versionadas."
                        ),
                    )
                )
                return

        self.result.pass_check()

    def _check_git_hooks(self, hooks_dir: Path) -> None:
        """Verifica git hooks en .git/hooks/."""
        for hook_file in hooks_dir.iterdir():
            if hook_file.is_file() and not hook_file.name.endswith(".sample"):
                try:
                    content = hook_file.read_text(encoding="utf-8", errors="replace")
                    for line in content.splitlines():
                        if line.strip() and not line.strip().startswith("#"):
                            self._check_hook_command(line, self._relative_path(hook_file))
                except (OSError, PermissionError):
                    pass

    def _check_husky_hooks(self, husky_dir: Path) -> None:
        """Verifica husky hooks."""
        for hook_file in husky_dir.iterdir():
            if hook_file.is_file() and hook_file.name != ".gitignore":
                try:
                    content = hook_file.read_text(encoding="utf-8", errors="replace")
                    for line in content.splitlines():
                        if line.strip() and not line.strip().startswith("#"):
                            self._check_hook_command(line, self._relative_path(hook_file))
                except (OSError, PermissionError):
                    pass

    # -------------------------------------------------------------------------
    # 6. CONFIG HYGIENE
    # -------------------------------------------------------------------------

    def _check_config_hygiene(self) -> None:
        """Verifica higiene general de configuración."""
        logger.info("Verificando higiene de configuración...")

        # Check: CLAUDE.md para patrones peligrosos
        self._check_claude_md_security()

        # Check: shell=True en scripts Python
        self._check_shell_true_usage()

        # Check: paquetes vulnerables conocidos
        self._check_vulnerable_packages()

    def _check_claude_md_security(self) -> None:
        """Verifica que CLAUDE.md no tenga instrucciones peligrosas."""
        claude_md = self.target / "CLAUDE.md"
        if not claude_md.is_file():
            self.result.pass_check()
            return

        try:
            content = claude_md.read_text(encoding="utf-8", errors="replace")
        except (OSError, PermissionError):
            return

        relative = self._relative_path(claude_md)
        lines = content.splitlines()

        dangerous_patterns = [
            (r"\beval\s*\(", "Instrucción de usar eval() detectada en CLAUDE.md"),
            (r"\bexec\s*\(", "Instrucción de usar exec() detectada en CLAUDE.md"),
            (r"shell\s*=\s*True", "Instrucción de shell=True detectada en CLAUDE.md"),
            (r"--no-verify", "Instrucción de --no-verify (skip hooks) en CLAUDE.md"),
            (r"--force\b", "Instrucción de --force en CLAUDE.md"),
            (r"rm\s+-rf\s+/", "Comando destructivo rm -rf / en CLAUDE.md"),
            (r"disable.*security", "Referencia a desactivar seguridad en CLAUDE.md"),
        ]

        found_any = False
        for line_num, line in enumerate(lines, 1):
            stripped = line.strip()
            # Ignorar bloques de código que muestran el patrón INCORRECTO
            # (como la sección "Patrón correcto para subprocess" que muestra el MAL ejemplo)
            if stripped.startswith("# MAL") or stripped.startswith("# BIEN"):
                continue

            for pattern, desc in dangerous_patterns:
                if re.search(pattern, line, re.IGNORECASE):
                    # Verificar si está en un contexto de "no hacer esto"
                    context_lines = lines[max(0, line_num - 4) : line_num]
                    context = " ".join(context_lines).lower()
                    is_negative_instruction = any(
                        neg in context
                        for neg in [
                            "nunca",
                            "never",
                            "no usar",
                            "don't",
                            "do not",
                            "prohibido",
                            "evitar",
                            "avoid",
                            "# mal",
                            "incorrecto",
                            "bad practice",
                            "mala práctica",
                            "no hardcodear",
                            "no `shell",
                        ]
                    )
                    if is_negative_instruction:
                        self.result.pass_check()
                        continue

                    found_any = True
                    self.result.fail_check(
                        Finding(
                            severity="MEDIUM",
                            category="config",
                            file=relative,
                            line=line_num,
                            message=desc,
                            recommendation=(
                                "Revisar si esta instrucción en CLAUDE.md podría "
                                "hacer que un agente IA ejecute código peligroso."
                            ),
                        )
                    )

        if not found_any:
            self.result.pass_check()

    def _check_shell_true_usage(self) -> None:
        """Busca uso de shell=True en scripts Python del proyecto."""
        scripts_dir = self.target / ".agent" / "scripts"
        if not scripts_dir.is_dir():
            self.result.pass_check()
            return

        found_any = False
        for py_file in scripts_dir.glob("*.py"):
            # No escanear el propio scanner (contiene el patrón en strings)
            if py_file.name == "security_audit.py":
                continue

            try:
                content = py_file.read_text(encoding="utf-8", errors="replace")
            except (OSError, PermissionError):
                continue

            relative = self._relative_path(py_file)
            in_docstring = False
            for line_num, line in enumerate(content.splitlines(), 1):
                stripped = line.strip()
                # Track docstring blocks (triple quotes)
                if '"""' in stripped or "'''" in stripped:
                    quote = '"""' if '"""' in stripped else "'''"
                    count = stripped.count(quote)
                    if count == 1:
                        in_docstring = not in_docstring
                    # If count >= 2, opens and closes on same line
                    continue
                if in_docstring:
                    continue
                # Saltar comentarios
                if stripped.startswith("#"):
                    continue
                # Saltar string literals (descriptions, messages, etc.)
                if "description" in stripped.lower() and "shell" in stripped.lower():
                    continue
                # Buscar uso real de shell=True en llamadas subprocess
                if re.search(r"subprocess\.\w+\(.*shell\s*=\s*True", line):
                    found_any = True
                    self.result.fail_check(
                        Finding(
                            severity="HIGH",
                            category="config",
                            file=relative,
                            line=line_num,
                            message="Uso de shell=True en subprocess",
                            recommendation=(
                                "Usar shell=False con shlex.split(). "
                                "shell=True permite inyección de comandos."
                            ),
                        )
                    )
                elif re.search(r"shell\s*=\s*True", line) and "subprocess" in content:
                    # shell=True como kwarg suelto pero en archivo que usa subprocess
                    # Solo si la línea parece una llamada real (tiene paréntesis)
                    if "(" in stripped and not stripped.startswith(("'", '"', "r'", 'r"')):
                        found_any = True
                        self.result.fail_check(
                            Finding(
                                severity="HIGH",
                                category="config",
                                file=relative,
                                line=line_num,
                                message="Uso de shell=True en subprocess",
                                recommendation=(
                                    "Usar shell=False con shlex.split(). "
                                    "shell=True permite inyección de comandos."
                                ),
                            )
                        )

        if not found_any:
            self.result.pass_check()
            logger.info("  OK No se detectó shell=True en scripts")

    def _check_vulnerable_packages(self) -> None:
        """Verifica paquetes vulnerables conocidos en configs."""
        package_json = self.target / "package.json"
        if package_json.is_file():
            try:
                pkg_data = json.loads(package_json.read_text(encoding="utf-8"))
                all_deps: dict[str, str] = {}
                all_deps.update(pkg_data.get("dependencies", {}))
                all_deps.update(pkg_data.get("devDependencies", {}))

                for vuln_pattern, cve_info in VULNERABLE_PACKAGES.items():
                    pkg_name = vuln_pattern.split("@")[0] if "@" in vuln_pattern else vuln_pattern
                    if pkg_name in all_deps:
                        self.result.fail_check(
                            Finding(
                                severity="INFO",
                                category="config",
                                file=self._relative_path(package_json),
                                line=None,
                                message=(
                                    f"Paquete '{pkg_name}' instalado — "
                                    f"verificar versión ({cve_info})"
                                ),
                                recommendation=(
                                    "Ejecutar 'npm audit' para verificar vulnerabilidades "
                                    "conocidas en dependencias."
                                ),
                            )
                        )
                    else:
                        self.result.pass_check()
            except (json.JSONDecodeError, OSError):
                pass

    # -------------------------------------------------------------------------
    # UTILITIES
    # -------------------------------------------------------------------------

    def _relative_path(self, path: Path) -> str:
        """Retorna path relativo al proyecto, con forward slashes."""
        try:
            return str(path.relative_to(self.target)).replace("\\", "/")
        except ValueError:
            return str(path).replace("\\", "/")


# =============================================================================
# OUTPUT FORMATTERS
# =============================================================================


def format_json(result: AuditResult) -> str:
    """Formatea el resultado como JSON."""
    return json.dumps(result.to_dict(), indent=2, ensure_ascii=False)


def format_text(result: AuditResult) -> str:
    """Formatea el resultado como texto legible."""
    lines: list[str] = []

    lines.append("=" * 72)
    lines.append("  ANTIGRAVITY SECURITY AUDIT")
    lines.append("=" * 72)
    lines.append(f"  Proyecto:  {result.project}")
    lines.append(f"  Timestamp: {result.scan_timestamp}")
    lines.append(f"  Chequeos:  {result.total_checks}")
    lines.append("")

    # Agrupar por severidad
    severity_groups: dict[str, list[Finding]] = {
        "HIGH": [],
        "MEDIUM": [],
        "LOW": [],
        "INFO": [],
    }
    for f in result.findings:
        severity_groups.get(f.severity, severity_groups["INFO"]).append(f)

    severity_icons = {
        "HIGH": "!!",
        "MEDIUM": "!",
        "LOW": "~",
        "INFO": "i",
    }

    for severity in ["HIGH", "MEDIUM", "LOW", "INFO"]:
        group = severity_groups[severity]
        if not group:
            continue

        lines.append(f"--- {severity} ({len(group)}) ---")
        lines.append("")
        for finding in group:
            icon = severity_icons[severity]
            location = finding.file
            if finding.line:
                location += f":{finding.line}"
            lines.append(f"  [{icon}] [{finding.category}] {location}")
            lines.append(f"      {finding.message}")
            lines.append(f"      -> {finding.recommendation}")
            lines.append("")

    # Resumen
    summary = result.summary
    lines.append("-" * 72)
    lines.append("  RESUMEN")
    lines.append(f"    HIGH:   {summary['high']}")
    lines.append(f"    MEDIUM: {summary['medium']}")
    lines.append(f"    LOW:    {summary['low']}")
    lines.append(f"    INFO:   {summary['info']}")
    lines.append(f"    PASSED: {summary['passed']}")
    lines.append("")

    if summary["high"] > 0:
        lines.append(
            "  ** ATENCION: Se encontraron hallazgos HIGH que requieren accion inmediata **"
        )
    elif summary["medium"] > 0:
        lines.append("  Hallazgos MEDIUM encontrados — revisar cuando sea posible.")
    else:
        lines.append("  Sin hallazgos criticos. Buen estado de seguridad.")

    lines.append("=" * 72)
    return "\n".join(lines)


# =============================================================================
# MAIN
# =============================================================================


def filter_by_severity(result: AuditResult, min_severity: str) -> AuditResult:
    """Filtra hallazgos por severidad mínima."""
    min_order = SEVERITY_ORDER.get(min_severity.upper(), 3)
    result.findings = [f for f in result.findings if SEVERITY_ORDER.get(f.severity, 3) <= min_order]
    return result


def main() -> int:
    """Entry point principal."""
    parser = argparse.ArgumentParser(
        description="Security Audit Scanner para OpenAntigravity",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=(
            "Ejemplos:\n"
            "  python security_audit.py --target /path/to/project\n"
            "  python security_audit.py --format text\n"
            "  python security_audit.py --severity high --format json\n"
        ),
    )
    parser.add_argument(
        "--target",
        type=str,
        default=".",
        help="Directorio del proyecto a auditar (default: directorio actual)",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "text"],
        default="json",
        help="Formato de salida (default: json)",
    )
    parser.add_argument(
        "--severity",
        type=str,
        choices=["high", "medium", "low", "info", "all"],
        default="all",
        help="Severidad mínima a mostrar (default: all)",
    )

    args = parser.parse_args()

    target_dir = Path(args.target).resolve()
    if not target_dir.is_dir():
        logger.error("El directorio objetivo no existe: %s", target_dir)
        return 1

    # Ejecutar auditoría
    auditor = SecurityAuditor(target_dir)
    result = auditor.run_all_checks()

    # Filtrar por severidad
    if args.severity != "all":
        result = filter_by_severity(result, args.severity)

    # Formatear salida
    if args.format == "json":
        output = format_json(result)
    else:
        output = format_text(result)

    print(output)

    # Exit code: 1 si hay hallazgos HIGH
    return 1 if result.summary["high"] > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
