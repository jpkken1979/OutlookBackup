"""
Project Memory - Memoria persistente REAL del proyecto entre sesiones.

A diferencia de SharedMemory (generico), ProjectMemory captura datos
CONCRETOS y UTILES del proyecto:

- Archivos mas modificados (hotspots)
- Decisiones arquitectonicas con razon y resultado
- Errores recurrentes y como se resolvieron
- Resultados de tests por sesion (tendencias)
- Patrones de codigo descubiertos en este proyecto
- Feedback de CI/CD (que pasa, que falla)

Almacenamiento DUAL:
- Primario: ~/.antigravity/projects/<hash>/ (privado, siempre funciona)
- Secundario: <proyecto>/.antigravity/memory/ (visible para TODAS las IAs)

El almacenamiento en el proyecto permite que cualquier IA (Cursor, Windsurf,
Copilot, Gemini, etc.) pueda leer la memoria sin necesidad de MCP.
Al cargar, se fusionan datos de ambas ubicaciones.

Formato: JSON estructurado, consultable, con TTL y relevancia temporal.

v1.2.0 - 2026-02-14
"""
# mypy: ignore-errors

from __future__ import annotations

import hashlib
import json
import logging
import time
import uuid
from dataclasses import asdict, dataclass, field
from datetime import datetime
from pathlib import Path

logger = logging.getLogger(__name__)

# Debounce: no regenerar CONTEXT_SUMMARY.md mas de 1 vez cada N segundos
SUMMARY_DEBOUNCE_SECONDS = 5


def _project_id(project_root: Path) -> str:
    """Genera un ID estable para un proyecto basado en su path absoluto.

    Usa hash del path resuelto para que:
    - Cada proyecto tiene su propio espacio de memoria
    - Funciona via MCP desde cualquier proyecto externo
    - No crea archivos dentro del repo del usuario
    """
    resolved = str(project_root.resolve())
    return hashlib.sha256(resolved.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Data Models
# ---------------------------------------------------------------------------


@dataclass
class FileHotspot:
    """Archivo frecuentemente modificado."""

    path: str
    modifications: int = 0
    last_modified: str = ""
    related_tests: list[str] = field(default_factory=list)
    common_changes: list[str] = field(default_factory=list)


@dataclass
class Decision:
    """Decision arquitectonica o tecnica."""

    id: str
    date: str
    description: str
    options_considered: list[str] = field(default_factory=list)
    chosen: str = ""
    reasoning: str = ""
    outcome: str = ""  # "success", "partial", "reverted"
    impact_files: list[str] = field(default_factory=list)
    tags: list[str] = field(default_factory=list)


@dataclass
class RecurringError:
    """Error que se repite y su resolucion."""

    pattern: str
    occurrences: int = 0
    first_seen: str = ""
    last_seen: str = ""
    resolution: str = ""
    prevention: str = ""
    files_affected: list[str] = field(default_factory=list)


@dataclass
class RunTrend:
    """Resultado de tests en una sesion."""

    date: str
    total: int = 0
    passed: int = 0
    failed: int = 0
    skipped: int = 0
    duration_seconds: float = 0.0
    failures: list[str] = field(default_factory=list)


@dataclass
class CIResult:
    """Resultado de una ejecucion CI/CD."""

    date: str
    workflow: str
    branch: str = ""
    commit: str = ""
    status: str = ""  # "success", "failure"
    duration_seconds: float = 0.0
    failed_jobs: list[str] = field(default_factory=list)
    agent_findings: list[dict] = field(default_factory=list)


@dataclass
class SessionSummary:
    """Resumen de una sesion de trabajo."""

    session_id: str
    date: str
    task_description: str = ""
    files_created: list[str] = field(default_factory=list)
    files_modified: list[str] = field(default_factory=list)
    decisions_made: list[str] = field(default_factory=list)
    tests_added: int = 0
    tests_result: str = ""  # "all_pass", "some_fail"
    commits: list[str] = field(default_factory=list)
    duration_minutes: float = 0.0


# ---------------------------------------------------------------------------
# Project Memory
# ---------------------------------------------------------------------------


class ProjectMemory:
    """Memoria persistente del proyecto con datos concretos y consultables.

    Almacena:
    - hotspots: archivos mas modificados
    - decisions: decisiones arquitectonicas
    - errors: errores recurrentes y resoluciones
    - test_trends: tendencias de tests
    - ci_results: resultados de CI/CD
    - sessions: resumenes de sesiones de trabajo
    """

    def __init__(self, project_root: str | None = None):
        self._root = Path(project_root) if project_root else Path(".")
        pid = _project_id(self._root)
        self._project_id = pid

        # PRIMARIO: ~/.antigravity/projects/<hash>/ (privado, siempre funciona)
        self._data_dir = Path.home() / ".antigravity" / "projects" / pid
        self._data_dir.mkdir(parents=True, exist_ok=True)

        # SECUNDARIO: <proyecto>/.antigravity/memory/ (visible para TODAS las IAs)
        self._project_data_dir = self._root.resolve() / ".antigravity" / "memory"
        self._project_data_dir.mkdir(parents=True, exist_ok=True)

        # Guardar metadata del proyecto para saber a que path pertenece este hash
        meta_file = self._data_dir / "_project_meta.json"
        if not meta_file.exists():
            meta_file.write_text(
                json.dumps(
                    {
                        "project_path": str(self._root.resolve()),
                        "project_name": self._root.resolve().name,
                        "created": datetime.now().isoformat(),
                    },
                    indent=2,
                ),
                encoding="utf-8",
            )

        self._hotspots: dict[str, FileHotspot] = {}
        self._decisions: dict[str, Decision] = {}
        self._errors: dict[str, RecurringError] = {}
        self._test_trends: list[RunTrend] = []
        self._ci_results: list[CIResult] = []
        self._sessions: list[SessionSummary] = []
        self._last_summary_time: float = 0.0

        self._load()

    # -----------------------------------------------------------------------
    # Persistence (Dual Storage: home + proyecto)
    # -----------------------------------------------------------------------

    def _load(self) -> None:
        """Carga datos desde disco, fusionando home y proyecto."""
        self._hotspots = self._load_collection_merged("hotspots.json", FileHotspot)
        self._decisions = self._load_collection_merged("decisions.json", Decision)
        self._errors = self._load_collection_merged("errors.json", RecurringError)
        self._test_trends = self._load_list_merged("test_trends.json", RunTrend)
        self._ci_results = self._load_list_merged("ci_results.json", CIResult)
        self._sessions = self._load_list_merged("sessions.json", SessionSummary)

    def _save(self) -> None:
        """Persiste todos los datos a AMBAS ubicaciones."""
        self._save_collection("hotspots.json", self._hotspots)
        self._save_collection("decisions.json", self._decisions)
        self._save_collection("errors.json", self._errors)
        self._save_list("test_trends.json", self._test_trends)
        self._save_list("ci_results.json", self._ci_results)
        self._save_list("sessions.json", self._sessions)
        self._export_context_summary()

    def _load_collection_from(self, directory: Path, filename: str, cls: type) -> dict:
        """Carga una coleccion (dict) desde un directorio especifico."""
        filepath = directory / filename
        if not filepath.exists():
            return {}
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return {k: cls(**v) for k, v in data.items()}
        except Exception as e:
            logger.warning("Error cargando %s de %s: %s", filename, directory, e)
            return {}

    def _load_list_from(self, directory: Path, filename: str, cls: type) -> list:
        """Carga una lista desde un directorio especifico."""
        filepath = directory / filename
        if not filepath.exists():
            return []
        try:
            data = json.loads(filepath.read_text(encoding="utf-8"))
            return [cls(**item) for item in data]
        except Exception as e:
            logger.warning("Error cargando %s de %s: %s", filename, directory, e)
            return []

    def _load_collection_merged(self, filename: str, cls: type) -> dict:
        """Carga y fusiona una coleccion desde home y proyecto.

        Home es primario; datos del proyecto que no existen en home se agregan.
        """
        home_data = self._load_collection_from(self._data_dir, filename, cls)
        project_data = self._load_collection_from(self._project_data_dir, filename, cls)
        # Fusionar: home gana en conflictos, proyecto agrega lo que falta
        for key, value in project_data.items():
            if key not in home_data:
                home_data[key] = value
        return home_data

    def _load_list_merged(self, filename: str, cls: type) -> list:
        """Carga y fusiona una lista desde home y proyecto.

        Deduplicacion por campo 'date' para evitar entradas repetidas.
        """
        home_data = self._load_list_from(self._data_dir, filename, cls)
        project_data = self._load_list_from(self._project_data_dir, filename, cls)
        if not project_data:
            return home_data
        if not home_data:
            return project_data
        # Deduplicar por date (o session_id para sessions)
        seen = set()
        for item in home_data:
            key = getattr(item, "session_id", None) or getattr(item, "date", id(item))
            seen.add(key)
        for item in project_data:
            key = getattr(item, "session_id", None) or getattr(item, "date", id(item))
            if key not in seen:
                home_data.append(item)
                seen.add(key)
        return home_data

    def _save_collection(self, filename: str, data: dict) -> None:
        """Guarda coleccion en AMBAS ubicaciones (home + proyecto)."""
        serialized = {k: asdict(v) for k, v in data.items()}
        content = json.dumps(serialized, indent=2, default=str, ensure_ascii=False)
        # Guardar en home (primario)
        (self._data_dir / filename).write_text(content, encoding="utf-8")
        # Guardar en proyecto (secundario, para otras IAs)
        try:
            (self._project_data_dir / filename).write_text(content, encoding="utf-8")
        except OSError as e:
            logger.debug("No se pudo guardar en proyecto: %s", e)
        # Regenerar resumen con debounce
        self._maybe_export_summary()

    def _save_list(self, filename: str, data: list) -> None:
        """Guarda lista en AMBAS ubicaciones (home + proyecto)."""
        serialized = [asdict(item) for item in data]
        content = json.dumps(serialized, indent=2, default=str, ensure_ascii=False)
        # Guardar en home (primario)
        (self._data_dir / filename).write_text(content, encoding="utf-8")
        # Guardar en proyecto (secundario, para otras IAs)
        try:
            (self._project_data_dir / filename).write_text(content, encoding="utf-8")
        except OSError as e:
            logger.debug("No se pudo guardar en proyecto: %s", e)
        # Regenerar resumen con debounce
        self._maybe_export_summary()

    def _maybe_export_summary(self) -> None:
        """Exporta el resumen solo si paso suficiente tiempo (debounce)."""
        now = time.monotonic()
        if now - self._last_summary_time >= SUMMARY_DEBOUNCE_SECONDS:
            self._export_context_summary()
            self._last_summary_time = now

    def flush(self) -> None:
        """Fuerza la exportacion del resumen de contexto (ignora debounce)."""
        self._export_context_summary()
        self._last_summary_time = time.monotonic()

    def _build_decisions_section(self, lines: list[str]) -> None:
        """Agrega la sección de decisiones arquitectónicas al resumen."""
        if not self._decisions:
            return
        lines.append("## Decisiones Arquitectonicas")
        lines.append("")
        for dec in sorted(self._decisions.values(), key=lambda d: d.date, reverse=True)[:10]:
            outcome_label = f" [{dec.outcome}]" if dec.outcome else ""
            lines.append(f"- **{dec.description}**: Elegido `{dec.chosen}`{outcome_label}")
            lines.append(f"  - Razon: {dec.reasoning}")
            if dec.options_considered:
                lines.append(f"  - Opciones: {', '.join(dec.options_considered)}")
            if dec.tags:
                lines.append(f"  - Tags: {', '.join(dec.tags)}")
            lines.append("")

    def _build_errors_section(self, lines: list[str]) -> None:
        """Agrega la sección de errores conocidos al resumen."""
        if not self._errors:
            return
        lines.append("## Errores Conocidos y Resoluciones")
        lines.append("")
        for err in sorted(self._errors.values(), key=lambda e: e.occurrences, reverse=True)[:10]:
            lines.append(f"- **{err.pattern}** ({err.occurrences}x)")
            if err.resolution:
                lines.append(f"  - Resolucion: {err.resolution}")
            if err.prevention:
                lines.append(f"  - Prevencion: {err.prevention}")
            lines.append("")

    def _build_hotspots_section(self, lines: list[str]) -> None:
        """Agrega la sección de hotspots al resumen."""
        if not self._hotspots:
            return
        lines.append("## Archivos Mas Modificados (Hotspots)")
        lines.append("")
        sorted_hs = sorted(self._hotspots.values(), key=lambda h: h.modifications, reverse=True)[
            :10
        ]
        for hs in sorted_hs:
            tests_str = f" (tests: {', '.join(hs.related_tests)})" if hs.related_tests else ""
            lines.append(f"- `{hs.path}`: {hs.modifications} modificaciones{tests_str}")
        lines.append("")

    def _build_ci_section(self, lines: list[str]) -> None:
        """Agrega la sección de CI/CD al resumen."""
        ci_health = self.get_ci_health()
        if ci_health["status"] == "no_data":
            return
        lines.append("## Estado CI/CD")
        lines.append("")
        lines.append(f"- Estado: **{ci_health['status']}**")
        lines.append(f"- Tasa de exito: {ci_health['success_rate']:.0%}")
        if ci_health.get("common_failures"):
            lines.append("- Fallos comunes:")
            for f in ci_health["common_failures"][:3]:
                lines.append(f"  - `{f['job']}` ({f['count']}x)")
        lines.append("")

    def _build_sessions_section(self, lines: list[str]) -> None:
        """Agrega la sección de sesiones recientes al resumen."""
        if not self._sessions:
            return
        lines.append("## Sesiones Recientes")
        lines.append("")
        for session in self._sessions[-5:]:
            lines.append(f"- **{session.task_description}** ({session.date[:10]})")
            if session.files_modified:
                lines.append(f"  - Archivos: {', '.join(session.files_modified[:5])}")
            if session.tests_result:
                lines.append(f"  - Tests: {session.tests_result}")
        lines.append("")

    def _build_flaky_section(self, lines: list[str]) -> None:
        """Agrega la sección de tests flaky al resumen."""
        flaky = self.get_flaky_tests()
        if not flaky:
            return
        lines.append("## Tests Flaky (Inestables)")
        lines.append("")
        for f in flaky[:5]:
            lines.append(f"- `{f['test']}`: falla {f['failure_rate']:.0%} de las veces")
        lines.append("")

    def _export_context_summary(self) -> None:
        """Exporta un resumen legible en Markdown para que CUALQUIER IA lo lea.

        Este archivo permite que IAs sin MCP (Cursor, Windsurf, Copilot, etc.)
        obtengan contexto del proyecto con solo leer un archivo.
        """
        try:
            lines = [
                "# Project Memory - Contexto para IAs",
                "",
                "> Archivo auto-generado por Antigravity Agents.",
                "> Cualquier IA puede leer este archivo para obtener contexto del proyecto.",
                f"> Ultima actualizacion: {datetime.now().isoformat()}",
                "",
            ]

            self._build_decisions_section(lines)
            self._build_errors_section(lines)
            self._build_hotspots_section(lines)
            self._build_ci_section(lines)
            self._build_sessions_section(lines)
            self._build_flaky_section(lines)

            summary_path = self._project_data_dir / "CONTEXT_SUMMARY.md"
            summary_path.write_text("\n".join(lines), encoding="utf-8")
        except OSError as e:
            logger.debug("No se pudo exportar resumen de contexto: %s", e)

    # -----------------------------------------------------------------------
    # Hotspots: Archivos mas modificados
    # -----------------------------------------------------------------------

    def record_file_change(
        self, filepath: str, change_description: str = "", related_test: str | None = None
    ) -> None:
        """Registra una modificacion a un archivo."""
        hs = self._hotspots.get(filepath)
        if hs is None:
            hs = FileHotspot(path=filepath)
            self._hotspots[filepath] = hs

        hs.modifications += 1
        hs.last_modified = datetime.now().isoformat()
        if change_description and change_description not in hs.common_changes:
            hs.common_changes.append(change_description)
            # Mantener solo ultimos 10
            if len(hs.common_changes) > 10:
                hs.common_changes = hs.common_changes[-10:]
        if related_test and related_test not in hs.related_tests:
            hs.related_tests.append(related_test)

        self._save_collection("hotspots.json", self._hotspots)

    def get_hotspots(self, top_k: int = 10) -> list[dict]:
        """Top archivos mas modificados."""
        sorted_hs = sorted(
            self._hotspots.values(),
            key=lambda h: h.modifications,
            reverse=True,
        )
        return [asdict(h) for h in sorted_hs[:top_k]]

    # -----------------------------------------------------------------------
    # Decisions: Decisiones arquitectonicas
    # -----------------------------------------------------------------------

    def record_decision(
        self,
        description: str,
        chosen: str,
        reasoning: str,
        options: list[str] | None = None,
        impact_files: list[str] | None = None,
        tags: list[str] | None = None,
    ) -> str:
        """Registra una decision arquitectonica o tecnica."""
        decision_id = f"dec-{uuid.uuid4().hex[:12]}"
        decision = Decision(
            id=decision_id,
            date=datetime.now().isoformat(),
            description=description,
            options_considered=options or [],
            chosen=chosen,
            reasoning=reasoning,
            impact_files=impact_files or [],
            tags=tags or [],
        )
        self._decisions[decision_id] = decision
        self._save_collection("decisions.json", self._decisions)
        logger.info("Decision registrada: %s -> %s", description[:50], chosen)
        return decision_id

    def update_decision_outcome(self, decision_id: str, outcome: str) -> None:
        """Actualiza el resultado de una decision (success/partial/reverted)."""
        if decision_id in self._decisions:
            self._decisions[decision_id].outcome = outcome
            self._save_collection("decisions.json", self._decisions)

    def get_decisions(self, tags: list[str] | None = None, limit: int = 20) -> list[dict]:
        """Consulta decisiones, opcionalmente filtradas por tags."""
        decisions = list(self._decisions.values())
        if tags:
            decisions = [d for d in decisions if any(t in d.tags for t in tags)]
        decisions.sort(key=lambda d: d.date, reverse=True)
        return [asdict(d) for d in decisions[:limit]]

    def search_decisions(self, query: str) -> list[dict]:
        """Busca decisiones por texto en descripcion, chosen o reasoning."""
        query_lower = query.lower()
        results = []
        for d in self._decisions.values():
            text = f"{d.description} {d.chosen} {d.reasoning}".lower()
            if query_lower in text:
                results.append(asdict(d))
        results.sort(key=lambda d: d.get("date", ""), reverse=True)
        return results[:10]

    # -----------------------------------------------------------------------
    # Errors: Errores recurrentes
    # -----------------------------------------------------------------------

    def record_error(
        self,
        pattern: str,
        resolution: str = "",
        prevention: str = "",
        files_affected: list[str] | None = None,
    ) -> None:
        """Registra un error. Si ya existe el patron, incrementa contador."""
        existing = self._errors.get(pattern)
        now = datetime.now().isoformat()

        if existing:
            existing.occurrences += 1
            existing.last_seen = now
            if resolution:
                existing.resolution = resolution
            if prevention:
                existing.prevention = prevention
            if files_affected:
                for f in files_affected:
                    if f not in existing.files_affected:
                        existing.files_affected.append(f)
        else:
            self._errors[pattern] = RecurringError(
                pattern=pattern,
                occurrences=1,
                first_seen=now,
                last_seen=now,
                resolution=resolution,
                prevention=prevention,
                files_affected=files_affected or [],
            )

        self._save_collection("errors.json", self._errors)

    def get_known_errors(self, query: str | None = None) -> list[dict]:
        """Consulta errores conocidos, opcionalmente filtrados por texto."""
        errors = list(self._errors.values())
        if query:
            query_lower = query.lower()
            errors = [
                e
                for e in errors
                if query_lower in e.pattern.lower() or query_lower in e.resolution.lower()
            ]
        errors.sort(key=lambda e: e.occurrences, reverse=True)
        return [asdict(e) for e in errors]

    def check_known_error(self, error_text: str) -> dict | None:
        """Verifica si un error ya fue visto antes. Retorna resolucion si existe."""
        error_lower = error_text.lower()
        for err in self._errors.values():
            if err.pattern.lower() in error_lower or error_lower in err.pattern.lower():
                return {
                    "pattern": err.pattern,
                    "occurrences": err.occurrences,
                    "resolution": err.resolution,
                    "prevention": err.prevention,
                }
        return None

    # -----------------------------------------------------------------------
    # Test Trends: Tendencias de tests
    # -----------------------------------------------------------------------

    def record_test_run(
        self,
        total: int,
        passed: int,
        failed: int,
        skipped: int = 0,
        duration_seconds: float = 0.0,
        failures: list[str] | None = None,
    ) -> None:
        """Registra resultado de una corrida de tests."""
        trend = RunTrend(
            date=datetime.now().isoformat(),
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            duration_seconds=duration_seconds,
            failures=failures or [],
        )
        self._test_trends.append(trend)
        # Mantener ultimos 100 runs
        if len(self._test_trends) > 100:
            self._test_trends = self._test_trends[-100:]
        self._save_list("test_trends.json", self._test_trends)

    def get_test_trends(self, last_n: int = 10) -> list[dict]:
        """Ultimas N corridas de tests."""
        return [asdict(t) for t in self._test_trends[-last_n:]]

    def get_flaky_tests(self) -> list[dict]:
        """Tests que a veces pasan y a veces fallan (flaky)."""
        failure_counts: dict[str, int] = {}
        total_runs = len(self._test_trends)

        for trend in self._test_trends:
            for failure in trend.failures:
                failure_counts[failure] = failure_counts.get(failure, 0) + 1

        flaky = []
        for test, count in failure_counts.items():
            failure_rate = count / max(total_runs, 1)
            if 0.1 < failure_rate < 0.9:  # Falla entre 10% y 90% = flaky
                flaky.append(
                    {
                        "test": test,
                        "failure_count": count,
                        "total_runs": total_runs,
                        "failure_rate": round(failure_rate, 2),
                    }
                )
        flaky.sort(key=lambda f: f["failure_rate"], reverse=True)
        return flaky

    # -----------------------------------------------------------------------
    # CI/CD Results
    # -----------------------------------------------------------------------

    def record_ci_result(
        self,
        workflow: str,
        status: str,
        branch: str = "",
        commit: str = "",
        duration_seconds: float = 0.0,
        failed_jobs: list[str] | None = None,
        agent_findings: list[dict] | None = None,
    ) -> None:
        """Registra resultado de una ejecucion CI/CD."""
        result = CIResult(
            date=datetime.now().isoformat(),
            workflow=workflow,
            branch=branch,
            commit=commit,
            status=status,
            duration_seconds=duration_seconds,
            failed_jobs=failed_jobs or [],
            agent_findings=agent_findings or [],
        )
        self._ci_results.append(result)
        if len(self._ci_results) > 200:
            self._ci_results = self._ci_results[-200:]
        self._save_list("ci_results.json", self._ci_results)

    def get_ci_results(self, workflow: str | None = None, last_n: int = 10) -> list[dict]:
        """Ultimos N resultados CI/CD, opcionalmente filtrados por workflow."""
        results = self._ci_results
        if workflow:
            results = [r for r in results if r.workflow == workflow]
        return [asdict(r) for r in results[-last_n:]]

    def get_ci_health(self) -> dict:
        """Salud general del CI/CD basada en ultimos resultados."""
        if not self._ci_results:
            return {"status": "no_data", "success_rate": 0.0, "total_runs": 0}

        recent = self._ci_results[-20:]
        successes = sum(1 for r in recent if r.status == "success")
        total = len(recent)
        rate = successes / total

        # Errores mas comunes
        all_failures: dict[str, int] = {}
        for r in recent:
            for job in r.failed_jobs:
                all_failures[job] = all_failures.get(job, 0) + 1

        return {
            "status": "healthy" if rate > 0.8 else "degraded" if rate > 0.5 else "unhealthy",
            "success_rate": round(rate, 2),
            "total_runs": total,
            "common_failures": sorted(
                [{"job": k, "count": v} for k, v in all_failures.items()],
                key=lambda x: x["count"],
                reverse=True,
            )[:5],
        }

    # -----------------------------------------------------------------------
    # Sessions
    # -----------------------------------------------------------------------

    def start_session(self, task_description: str) -> str:
        """Inicia una nueva sesion de trabajo."""
        session_id = f"session-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
        session = SessionSummary(
            session_id=session_id,
            date=datetime.now().isoformat(),
            task_description=task_description,
        )
        self._sessions.append(session)
        self._save_list("sessions.json", self._sessions)
        return session_id

    def end_session(
        self,
        session_id: str,
        files_created: list[str] | None = None,
        files_modified: list[str] | None = None,
        decisions_made: list[str] | None = None,
        tests_added: int = 0,
        tests_result: str = "",
        commits: list[str] | None = None,
        duration_minutes: float = 0.0,
    ) -> None:
        """Cierra una sesion con su resumen."""
        for session in self._sessions:
            if session.session_id == session_id:
                session.files_created = files_created or []
                session.files_modified = files_modified or []
                session.decisions_made = decisions_made or []
                session.tests_added = tests_added
                session.tests_result = tests_result
                session.commits = commits or []
                session.duration_minutes = duration_minutes
                break
        self._save_list("sessions.json", self._sessions)

    def get_recent_sessions(self, last_n: int = 5) -> list[dict]:
        """Ultimas N sesiones."""
        return [asdict(s) for s in self._sessions[-last_n:]]

    # -----------------------------------------------------------------------
    # Consulta Inteligente
    # -----------------------------------------------------------------------

    def get_context_for_task(self, task: str) -> dict:
        """Obtiene todo el contexto relevante para una tarea.

        Busca en decisiones, errores, hotspots y CI/CD para dar
        contexto completo antes de empezar a trabajar.
        """
        task_lower = task.lower()

        # Decisiones relevantes
        relevant_decisions = self.search_decisions(task)

        # Errores conocidos relacionados
        relevant_errors = []
        for err in self._errors.values():
            if any(word in err.pattern.lower() for word in task_lower.split() if len(word) > 3):
                relevant_errors.append(asdict(err))

        # Archivos que probablemente se tocaran
        likely_files = []
        for hs in self._hotspots.values():
            path_lower = hs.path.lower()
            if any(word in path_lower for word in task_lower.split() if len(word) > 3):
                likely_files.append(asdict(hs))

        # Estado del CI/CD
        ci_health = self.get_ci_health()

        # Tests flaky
        flaky = self.get_flaky_tests()

        return {
            "relevant_decisions": relevant_decisions[:5],
            "known_errors": relevant_errors[:5],
            "likely_files": likely_files[:10],
            "ci_health": ci_health,
            "flaky_tests": flaky[:5],
            "recent_sessions": self.get_recent_sessions(3),
            "test_trend": self.get_test_trends(5),
        }

    def get_project_health(self) -> dict:
        """Reporte de salud general del proyecto."""
        # Test trends
        test_health = "no_data"
        if self._test_trends:
            recent_tests = self._test_trends[-5:]
            avg_pass_rate = sum(t.passed / max(t.total, 1) for t in recent_tests) / len(
                recent_tests
            )
            test_health = (
                "healthy"
                if avg_pass_rate > 0.95
                else "degraded"
                if avg_pass_rate > 0.80
                else "unhealthy"
            )

        return {
            "timestamp": datetime.now().isoformat(),
            "hotspots_count": len(self._hotspots),
            "decisions_count": len(self._decisions),
            "known_errors": len(self._errors),
            "test_runs_tracked": len(self._test_trends),
            "ci_runs_tracked": len(self._ci_results),
            "sessions_tracked": len(self._sessions),
            "test_health": test_health,
            "ci_health": self.get_ci_health().get("status", "no_data"),
            "top_hotspots": self.get_hotspots(5),
            "flaky_tests": self.get_flaky_tests()[:3],
        }


# ---------------------------------------------------------------------------
# Singleton por proyecto (soporta multiples proyectos simultaneos via MCP)
# ---------------------------------------------------------------------------

_memory_instances: dict[str, ProjectMemory] = {}


def get_project_memory(project_root: str | None = None) -> ProjectMemory:
    """Obtiene la instancia de ProjectMemory para un proyecto especifico.

    Cada proyecto tiene su propia instancia, identificada por su path.
    Esto permite que el MCP server atienda multiples proyectos sin mezclar datos.
    """
    root = Path(project_root) if project_root else Path(".")
    key = _project_id(root)
    if key not in _memory_instances:
        _memory_instances[key] = ProjectMemory(project_root)
    return _memory_instances[key]
