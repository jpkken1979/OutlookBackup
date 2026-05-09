#!/usr/bin/env python3
"""
Compliance Auditor - Auditor de cumplimiento regulatorio.

Escanea codigo y sistemas buscando violaciones de:
- GDPR (Proteccion de datos EU)
- SOC2 (Controles de seguridad)
- HIPAA (Datos de salud)
- PCI-DSS (Datos de pago)

Uso:
    python compliance_auditor.py <path> [--regulation GDPR,SOC2]
    python compliance_auditor.py . --regulation GDPR --json
    python compliance_auditor.py src/ --all
"""

from __future__ import annotations

import argparse
import json
import logging
import re
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path

# Configuracion de logging
logging.basicConfig(
    level=logging.INFO,
    format="[%(asctime)s] [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger("antigravity.agents.compliance-auditor")


class Severity(Enum):
    """Severidad de hallazgos."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    INFO = "info"


class Regulation(Enum):
    """Regulaciones soportadas."""

    GDPR = "GDPR"
    SOC2 = "SOC2"
    HIPAA = "HIPAA"
    PCI_DSS = "PCI-DSS"
    CCPA = "CCPA"


@dataclass
class Finding:
    """Un hallazgo de compliance."""

    id: str
    severity: Severity
    regulation: Regulation
    article: str
    title: str
    description: str
    file_path: str
    line_number: int
    code_snippet: str
    remediation: str
    effort_hours: float

    def to_dict(self) -> dict:
        d = asdict(self)
        d["severity"] = self.severity.value
        d["regulation"] = self.regulation.value
        return d


@dataclass
class ComplianceReport:
    """Reporte de compliance."""

    scan_path: str
    regulations: list[str]
    scan_time: str
    files_scanned: int
    findings: list[Finding]
    score: float
    summary: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return {
            "scan_path": self.scan_path,
            "regulations": self.regulations,
            "scan_time": self.scan_time,
            "files_scanned": self.files_scanned,
            "findings": [f.to_dict() for f in self.findings],
            "score": self.score,
            "summary": self.summary,
        }

    def to_markdown(self) -> str:
        """Generar reporte en markdown."""
        lines = [
            "# Reporte de Cumplimiento Regulatorio",
            "",
            f"**Fecha:** {self.scan_time}",
            f"**Path:** {self.scan_path}",
            f"**Regulaciones:** {', '.join(self.regulations)}",
            f"**Archivos escaneados:** {self.files_scanned}",
            f"**Score de cumplimiento:** {self.score:.0f}/100",
            "",
            "## Resumen de Hallazgos",
            "",
            "| Severidad | Cantidad |",
            "|-----------|----------|",
        ]

        for sev in Severity:
            count = sum(1 for f in self.findings if f.severity == sev)
            if count > 0:
                lines.append(f"| {sev.value.upper()} | {count} |")

        lines.extend(["", "## Hallazgos Detallados", ""])

        for i, finding in enumerate(self.findings, 1):
            icon = {
                Severity.CRITICAL: "🔴",
                Severity.HIGH: "🟠",
                Severity.MEDIUM: "🟡",
                Severity.LOW: "🔵",
                Severity.INFO: "⚪",
            }.get(finding.severity, "⚪")

            lines.extend(
                [
                    f"### {i}. {icon} [{finding.severity.value.upper()}] {finding.title}",
                    "",
                    f"**ID:** {finding.id}",
                    f"**Regulacion:** {finding.regulation.value} - {finding.article}",
                    f"**Ubicacion:** `{finding.file_path}:{finding.line_number}`",
                    "",
                    "**Descripcion:**",
                    finding.description,
                    "",
                    "**Codigo afectado:**",
                    "```",
                    finding.code_snippet,
                    "```",
                    "",
                    "**Remediacion:**",
                    finding.remediation,
                    "",
                    f"**Esfuerzo estimado:** {finding.effort_hours} horas",
                    "",
                    "---",
                    "",
                ]
            )

        return "\n".join(lines)


class ComplianceAuditor:
    """Auditor de cumplimiento regulatorio."""

    # Patrones de PII
    PII_PATTERNS = {
        "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
        "phone": r"\b(\+\d{1,3}[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b",
        "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
        "credit_card": r"\b(?:\d{4}[-\s]?){3}\d{4}\b",
        "ip_address": r"\b(?:\d{1,3}\.){3}\d{1,3}\b",
    }

    # Patrones de logging inseguro
    INSECURE_LOG_PATTERNS = [
        r"log(?:ger)?\.(?:info|debug|warn|error)\s*\([^)]*(?:password|token|secret|api_key|credential)",
        r"print\s*\([^)]*(?:password|token|secret|api_key|credential)",
        r"console\.log\s*\([^)]*(?:password|token|secret|apiKey|credential)",
    ]

    # Patrones de datos sensibles hardcodeados
    HARDCODED_SECRETS = [
        r'(?:password|passwd|pwd)\s*=\s*["\'][^"\']+["\']',
        r'(?:api_key|apikey|api-key)\s*=\s*["\'][^"\']+["\']',
        r'(?:secret|token)\s*=\s*["\'][^"\']+["\']',
        r'(?:auth|bearer)\s*=\s*["\'][^"\']+["\']',
    ]

    def __init__(self, regulations: list[Regulation] = None):
        self.regulations = regulations or list(Regulation)
        self.findings: list[Finding] = []
        self.files_scanned = 0
        self.finding_counter = 0

    def _generate_id(self) -> str:
        """Generar ID unico para hallazgo."""
        self.finding_counter += 1
        return f"COMP-{self.finding_counter:04d}"

    def detect_pii(
        self, content: str, file_path: str, ignore_test_check: bool = False
    ) -> list[Finding]:
        """Detectar PII en contenido."""
        findings = []
        lines = content.split("\n")
        for line_num, line in enumerate(lines, 1):
            for pii_type, pattern in self.PII_PATTERNS.items():
                if re.search(pattern, line, re.IGNORECASE):
                    if not ignore_test_check and self._is_test_or_comment(line, Path(file_path)):
                        continue
                    findings.append(
                        Finding(
                            id=self._generate_id(),
                            severity=Severity.HIGH,
                            regulation=Regulation.GDPR,
                            article="Art. 25 - Privacy by Design",
                            title=f"PII detectada: {pii_type}",
                            description=f"Se detecto informacion personal ({pii_type}) en el codigo.",
                            file_path=file_path,
                            line_number=line_num,
                            code_snippet=line.strip()[:100],
                            remediation=f"Usar variables de entorno para {pii_type}.",
                            effort_hours=1.0,
                        )
                    )
        return findings

    def detect_hardcoded_secrets(
        self, content: str, file_path: str, ignore_test_check: bool = False
    ) -> list[Finding]:
        """Detectar secretos hardcodeados."""
        findings = []
        lines = content.split("\n")
        for line_num, line in enumerate(lines, 1):
            for pattern in self.HARDCODED_SECRETS:
                if re.search(pattern, line, re.IGNORECASE):
                    if not ignore_test_check and self._is_test_or_comment(line, Path(file_path)):
                        continue
                    findings.append(
                        Finding(
                            id=self._generate_id(),
                            severity=Severity.CRITICAL,
                            regulation=Regulation.SOC2,
                            article="Security - Access Control",
                            title="Credencial hardcodeada",
                            description="Se detectaron credenciales hardcodeadas en el codigo.",
                            file_path=file_path,
                            line_number=line_num,
                            code_snippet=line.strip()[:100],
                            remediation="Mover secretos a variables de entorno o vault.",
                            effort_hours=1.5,
                        )
                    )
        return findings

    def scan(self, path: str) -> list[Finding]:
        """Metodo de conveniencia para escanear y obtener hallazgos."""
        report = self.scan_directory(Path(path))
        return report.findings

    def generate_report(self, path: str) -> str:
        """Generar reporte en markdown."""
        report = self.scan_directory(Path(path))
        return report.to_markdown()

    def scan_file(self, file_path: Path) -> list[Finding]:
        """Escanear un archivo buscando violaciones."""
        findings = []

        try:
            content = file_path.read_text(encoding="utf-8", errors="ignore")
            lines = content.split("\n")
        except Exception as e:
            logger.warning(f"No se pudo leer {file_path}: {e}")
            return findings

        # Buscar PII hardcodeada
        findings.extend(self.detect_pii(content, str(file_path)))

        # Buscar secrets hardcodeados
        findings.extend(self.detect_hardcoded_secrets(content, str(file_path)))

        # Buscar logging inseguro
        for line_num, line in enumerate(lines, 1):
            for pattern in self.INSECURE_LOG_PATTERNS:
                if re.search(pattern, line, re.IGNORECASE):
                    findings.append(
                        Finding(
                            id=self._generate_id(),
                            severity=Severity.CRITICAL,
                            regulation=Regulation.GDPR,
                            article="Art. 32 - Seguridad del procesamiento",
                            title="Datos sensibles en logs",
                            description="Se estan registrando datos sensibles (passwords, tokens, etc.) "
                            "en logs. Esto expone credenciales y viola seguridad.",
                            file_path=str(file_path),
                            line_number=line_num,
                            code_snippet=line.strip()[:100],
                            remediation="Eliminar datos sensibles de logs. Usar mascaras: "
                            "password=****. Nunca loggear tokens completos.",
                            effort_hours=0.5,
                        )
                    )

        # Buscar falta de validacion de entrada
        if file_path.suffix in [".py", ".js", ".ts"]:
            for line_num, line in enumerate(lines, 1):
                # SQL injection potencial
                if re.search(
                    r'execute\s*\([^)]*%s|execute\s*\([^)]*\+|f"[^"]*{[^}]+}[^"]*SELECT',
                    line,
                    re.IGNORECASE,
                ):
                    findings.append(
                        Finding(
                            id=self._generate_id(),
                            severity=Severity.CRITICAL,
                            regulation=Regulation.SOC2,
                            article="Processing Integrity",
                            title="Potencial SQL Injection",
                            description="Se detecta concatenacion de strings en queries SQL. "
                            "Esto puede permitir inyeccion SQL.",
                            file_path=str(file_path),
                            line_number=line_num,
                            code_snippet=line.strip()[:100],
                            remediation="Usar queries parametrizadas o un ORM. "
                            "Nunca concatenar input del usuario en queries.",
                            effort_hours=2.0,
                        )
                    )

        return findings

    def _is_test_or_comment(self, line: str, file_path: Path) -> bool:
        """Verificar si la linea es test o comentario."""
        line_stripped = line.strip()

        # Comentarios
        if line_stripped.startswith(("#", "//", "/*", "*", '"""', "'''")):
            return True

        # Ejemplos/docs
        return bool("example" in line_stripped.lower() or "sample" in line_stripped.lower())

    def scan_directory(self, path: Path) -> ComplianceReport:
        """Escanear directorio recursivamente."""
        logger.info(f"Iniciando escaneo de compliance en {path}")

        self.findings = []
        self.files_scanned = 0
        self.finding_counter = 0

        # Extensiones a escanear
        extensions = {".py", ".js", ".ts", ".jsx", ".tsx", ".java", ".go", ".rb", ".php"}

        # Directorios a ignorar
        ignore_dirs = {"node_modules", ".git", "__pycache__", "venv", ".venv", "dist", "build"}

        for file_path in path.rglob("*"):
            if file_path.is_file() and file_path.suffix in extensions:
                # Ignorar directorios especificos
                if any(ignored in file_path.parts for ignored in ignore_dirs):
                    continue

                self.files_scanned += 1
                file_findings = self.scan_file(file_path)
                self.findings.extend(file_findings)

        # Calcular score
        score = self._calculate_score()

        # Generar summary
        summary = {
            "critical": sum(1 for f in self.findings if f.severity == Severity.CRITICAL),
            "high": sum(1 for f in self.findings if f.severity == Severity.HIGH),
            "medium": sum(1 for f in self.findings if f.severity == Severity.MEDIUM),
            "low": sum(1 for f in self.findings if f.severity == Severity.LOW),
            "info": sum(1 for f in self.findings if f.severity == Severity.INFO),
        }

        logger.info(
            f"Escaneo completado: {self.files_scanned} archivos, {len(self.findings)} hallazgos"
        )

        return ComplianceReport(
            scan_path=str(path),
            regulations=[r.value for r in self.regulations],
            scan_time=datetime.now().isoformat(),
            files_scanned=self.files_scanned,
            findings=self.findings,
            score=score,
            summary=summary,
        )

    def _calculate_score(self) -> float:
        """Calcular score de compliance (0-100)."""
        if not self.findings:
            return 100.0

        # Pesos por severidad
        weights = {
            Severity.CRITICAL: 25,
            Severity.HIGH: 15,
            Severity.MEDIUM: 8,
            Severity.LOW: 3,
            Severity.INFO: 1,
        }

        total_penalty = sum(weights[f.severity] for f in self.findings)

        # Score base 100, restando penalidades (minimo 0)
        score = max(0, 100 - total_penalty)

        return score


def main():
    """Entry point principal."""
    parser = argparse.ArgumentParser(
        description="Compliance Auditor - Auditor de cumplimiento regulatorio"
    )
    parser.add_argument("path", help="Path a escanear")
    parser.add_argument(
        "--regulation",
        "-r",
        help="Regulaciones a verificar (comma-separated): GDPR,SOC2,HIPAA,PCI-DSS",
        default="GDPR,SOC2",
    )
    parser.add_argument("--all", action="store_true", help="Verificar todas las regulaciones")
    parser.add_argument("--json", action="store_true", help="Output en JSON")
    parser.add_argument("--output", "-o", help="Archivo de salida")

    args = parser.parse_args()

    # Parsear regulaciones
    if args.all:
        regulations = list(Regulation)
    else:
        regulation_names = [r.strip().upper().replace("-", "_") for r in args.regulation.split(",")]
        regulations = []
        for name in regulation_names:
            try:
                regulations.append(Regulation[name])
            except KeyError:
                logger.warning(f"Regulacion desconocida: {name}")

    # Ejecutar escaneo
    auditor = ComplianceAuditor(regulations)
    report = auditor.scan_directory(Path(args.path))

    # Output
    if args.json:
        output = json.dumps(report.to_dict(), indent=2, ensure_ascii=False)
    else:
        output = report.to_markdown()

    if args.output:
        Path(args.output).write_text(output)
        logger.info(f"Reporte guardado en {args.output}")
    else:
        print(output)

    # Exit code basado en hallazgos criticos
    critical_count = sum(1 for f in report.findings if f.severity == Severity.CRITICAL)
    sys.exit(1 if critical_count > 0 else 0)


if __name__ == "__main__":
    main()
