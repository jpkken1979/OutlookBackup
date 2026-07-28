"""ExcelEngine — orchestrator that wires sessions, router, backends, brain."""

from __future__ import annotations

import logging
import secrets
import time
from collections import Counter
from pathlib import Path
from typing import Any, Literal

from excel_engine.backends.openpyxl_backend import OpenpyxlBackend
from excel_engine.backends.super_agent_backend import (
    SuperAgentBackend,
    SuperAgentInvocationError,
)
from excel_engine.backends.xlwings_backend import XlwingsBackend
from excel_engine.brain_tracker import BrainTracker
from excel_engine.router import (
    BackendRouter,
    BackendUnavailable,
    RouterEnv,
)
from excel_engine.sessions import SessionManager
from excel_engine.types import (
    Backend,
    CellFormat,
    ErrorInfo,
    OpResult,
    SessionId,
)

logger = logging.getLogger(__name__)


class ExcelEngine:
    """High-level Excel orchestrator.

    Public API mirrors the spec's section 5.1. Each method returns OpResult.

    Args:
        brain: Brain instance (Brain Network) for recall + ingest. Required.
        max_sessions: passed through to SessionManager.
        ttl_seconds: passed through to SessionManager.
    """

    def __init__(
        self,
        brain: Any,
        max_sessions: int = 5,
        ttl_seconds: int = 1800,
    ) -> None:
        self._brain = brain
        self._sessions = SessionManager(
            max_sessions=max_sessions,
            ttl_seconds=ttl_seconds,
        )
        self._router = BackendRouter()
        self._tracker = BrainTracker(brain)
        self._openpyxl = OpenpyxlBackend()
        self._xlwings = XlwingsBackend()
        self._super_agent = SuperAgentBackend()
        # Per-session backend handles
        self._handles: dict[SessionId, Any] = {}
        # Per-session op breakdown for the closing summary
        self._op_history: dict[SessionId, Counter[str]] = {}

    # ----- Session lifecycle -----

    def open(
        self,
        path: str,
        mode: Literal["read", "write", "live"] = "read",
    ) -> OpResult:
        """Abre un archivo Excel y crea una sesión.

        Args:
            path: Ruta al archivo .xlsx.
            mode: Modo de apertura — read, write o live.

        Returns:
            OpResult con session_id en data si status='ok'.
        """
        rid = self._rid()
        t0 = time.time()
        if mode == "live":
            try:
                handle = self._xlwings.open(path, mode=mode)
            except ImportError as exc:
                return self._error(
                    rid,
                    t0,
                    None,
                    category="fatal",
                    code="BACKEND_NOT_AVAILABLE",
                    message=str(exc),
                )
            except (FileNotFoundError, RuntimeError) as exc:
                return self._error(
                    rid,
                    t0,
                    None,
                    category="user",
                    code="OPEN_FAILED",
                    message=str(exc),
                )
            sid = self._sessions.create(path, mode, Backend.XLWINGS)
            self._handles[sid] = handle
            self._op_history[sid] = Counter()
            return OpResult(
                status="ok",
                request_id=rid,
                duration_ms=self._ms(t0),
                backend_used=Backend.XLWINGS,
                data={
                    "session_id": sid,
                    "path": path,
                    "mode": mode,
                    "backend": Backend.XLWINGS.value,
                },
            )
        if not Path(path).exists():
            return self._error(
                rid,
                t0,
                None,
                category="user",
                code="PATH_NOT_FOUND",
                message=f"file not found: {path}",
                suggested=["verificar el path"],
            )
        try:
            handle = self._openpyxl.open(path, mode=mode)
        except (FileNotFoundError, PermissionError, ValueError) as exc:
            return self._error(
                rid,
                t0,
                None,
                category="user",
                code="OPEN_FAILED",
                message=str(exc),
            )
        sid = self._sessions.create(path, mode, Backend.OPENPYXL)
        self._handles[sid] = handle
        self._op_history[sid] = Counter()
        return OpResult(
            status="ok",
            request_id=rid,
            duration_ms=self._ms(t0),
            backend_used=Backend.OPENPYXL,
            data={
                "session_id": sid,
                "path": path,
                "mode": mode,
                "backend": Backend.OPENPYXL.value,
            },
        )

    def close(self, session_id: SessionId, save: bool = True) -> OpResult:
        """Cierra una sesión y opcionalmente guarda los cambios.

        Args:
            session_id: ID de la sesión a cerrar.
            save: Si True, persiste cambios antes de cerrar.

        Returns:
            OpResult con status='ok' si la sesión fue cerrada correctamente.
        """
        rid = self._rid()
        t0 = time.time()
        try:
            st = self._sessions.get(session_id)
        except KeyError:
            return self._error(
                rid,
                t0,
                None,
                category="user",
                code="SESSION_UNKNOWN",
                message=f"unknown session: {session_id}",
            )
        opened_at = st.opened_at
        path = st.path
        backends = [st.opened_with.value]
        breakdown = dict(self._op_history.get(session_id, Counter()))
        n_ops = st.n_ops
        n_errors = st.error_count

        handle = self._handles.pop(session_id, None)
        if handle is not None:
            try:
                if st.opened_with == Backend.XLWINGS:
                    self._xlwings.close(handle, save=save)
                else:
                    self._openpyxl.close(handle, save=save)
            except Exception as exc:
                logger.warning("[engine] error closing handle: %s", exc)
        self._op_history.pop(session_id, None)
        self._sessions.close(session_id)

        # Brain ingest summary
        try:
            self._tracker.ingest_session(
                path=path,
                opened_at=opened_at,
                closed_at=time.time(),
                n_ops=n_ops,
                op_breakdown=breakdown,
                backends_used=backends,
                n_errors=n_errors,
                request_id=rid,
            )
        except Exception as exc:
            logger.warning("[engine] brain ingest_session failed: %s", exc)

        return OpResult(
            status="ok",
            request_id=rid,
            duration_ms=self._ms(t0),
            backend_used=None,
            data={"session_id": session_id, "saved": save},
        )

    def list_sessions(self) -> OpResult:
        """Lista todas las sesiones activas.

        Returns:
            OpResult con lista de sesiones en data['sessions'].
        """
        rid = self._rid()
        t0 = time.time()
        return OpResult(
            status="ok",
            request_id=rid,
            duration_ms=self._ms(t0),
            backend_used=None,
            data={"sessions": [s.to_dict() for s in self._sessions.list()]},
        )

    # ----- Read/parse -----

    def parse_smart(
        self,
        path: str,
        hints: dict[str, Any] | None = None,
    ) -> OpResult:
        """Parseo inteligente de un archivo Excel via SuperAgentBackend.

        Args:
            path: Ruta al archivo Excel.
            hints: Pistas opcionales para el super-agente.

        Returns:
            OpResult con los datos parseados en data si status='ok'.
        """
        rid = self._rid()
        t0 = time.time()
        if not Path(path).exists():
            return self._error(
                rid,
                t0,
                None,
                category="user",
                code="PATH_NOT_FOUND",
                message=f"file not found: {path}",
            )
        try:
            data = self._super_agent.parse_smart(path, hints=hints)
        except FileNotFoundError as exc:
            return self._error(
                rid,
                t0,
                Backend.SUPER_AGENT,
                category="user",
                code="PATH_NOT_FOUND",
                message=str(exc),
            )
        except SuperAgentInvocationError as exc:
            return self._error(
                rid,
                t0,
                Backend.SUPER_AGENT,
                category="fatal",
                code="SUPER_AGENT_FAILURE",
                message=str(exc),
            )
        return OpResult(
            status="ok",
            request_id=rid,
            duration_ms=self._ms(t0),
            backend_used=Backend.SUPER_AGENT,
            data=data,
        )

    def read_range(
        self,
        session_id: SessionId,
        sheet: str,
        range_addr: str,
    ) -> OpResult:
        """Lee un rango de celdas de la sesión activa.

        Args:
            session_id: ID de la sesión.
            sheet: Nombre de la hoja.
            range_addr: Dirección del rango, ej. 'A1:C10'.

        Returns:
            OpResult con los valores leídos en data['values'].
        """
        return self._with_session(
            session_id,
            "read_range",
            lambda h: self._openpyxl.read_range(h, sheet=sheet, range_addr=range_addr),
            data_key="values",
        )

    # ----- Write ops -----

    def write_range(
        self,
        session_id: SessionId,
        sheet: str,
        range_addr: str,
        values: list[list[Any]],
        fmt: CellFormat | None = None,
    ) -> OpResult:
        """Escribe valores en un rango de celdas.

        Args:
            session_id: ID de la sesión.
            sheet: Nombre de la hoja.
            range_addr: Celda de inicio o rango, ej. 'A1'.
            values: Lista 2D de valores a escribir.
            fmt: Formato opcional a aplicar al rango.

        Returns:
            OpResult con metadata de la operación si status='ok'.
        """

        def _do(h: Any) -> dict[str, Any]:
            self._openpyxl.write_range(h, sheet=sheet, range_addr=range_addr, values=values)
            if fmt is not None:
                self._openpyxl.set_format(h, sheet=sheet, range_addr=range_addr, fmt=fmt)
            return {"sheet": sheet, "range": range_addr, "rows_written": len(values)}

        return self._with_session(session_id, "write_range", _do)

    def apply_formula(
        self,
        session_id: SessionId,
        sheet: str,
        range_addr: str,
        formula: str,
    ) -> OpResult:
        """Escribe una fórmula en una celda.

        Args:
            session_id: ID de la sesión.
            sheet: Nombre de la hoja.
            range_addr: Dirección de la celda destino.
            formula: Fórmula a escribir, con o sin '=' inicial.

        Returns:
            OpResult con metadata de la operación si status='ok'.
        """
        return self._with_session(
            session_id,
            "apply_formula",
            lambda h: (
                self._openpyxl.apply_formula(h, sheet=sheet, range_addr=range_addr, formula=formula)
                or {"sheet": sheet, "range": range_addr}
            ),
        )

    def set_format(
        self,
        session_id: SessionId,
        sheet: str,
        range_addr: str,
        fmt: CellFormat,
    ) -> OpResult:
        """Aplica formato a un rango de celdas.

        Args:
            session_id: ID de la sesión.
            sheet: Nombre de la hoja.
            range_addr: Dirección del rango.
            fmt: Opciones de formato a aplicar.

        Returns:
            OpResult con metadata de la operación si status='ok'.
        """
        return self._with_session(
            session_id,
            "set_format",
            lambda h: (
                self._openpyxl.set_format(h, sheet=sheet, range_addr=range_addr, fmt=fmt)
                or {"sheet": sheet, "range": range_addr}
            ),
        )

    def create_table(
        self,
        session_id: SessionId,
        sheet: str,
        range_addr: str,
        name: str,
        style: str | None = None,
    ) -> OpResult:
        """Convierte un rango en una Tabla Excel.

        Args:
            session_id: ID de la sesión.
            sheet: Nombre de la hoja.
            range_addr: Rango de la tabla, ej. 'A1:B10'.
            name: Nombre único de la tabla.
            style: Nombre del estilo de tabla (opcional).

        Returns:
            OpResult con metadata de la tabla si status='ok'.
        """
        return self._with_session(
            session_id,
            "create_table",
            lambda h: (
                self._openpyxl.create_table(
                    h, sheet=sheet, range_addr=range_addr, name=name, style=style
                )
                or {"name": name, "sheet": sheet, "range": range_addr}
            ),
        )

    def save_as(
        self,
        session_id: SessionId,
        path: str,
        format: Literal["xlsx", "pdf", "csv", "xlsm"],
    ) -> OpResult:
        """Exporta el workbook a una nueva ruta/formato.

        Args:
            session_id: ID de la sesión.
            path: Ruta de destino del archivo exportado.
            format: Formato de exportación — 'xlsx', 'pdf', 'csv' o 'xlsm'.

        Returns:
            OpResult con path y formato si status='ok'.
        """
        return self._with_session(
            session_id,
            "save_as",
            lambda h: (
                self._openpyxl.save_as(h, path=path, format=format)
                or {"path": path, "format": format}
            ),
        )

    # ----- Plan B placeholders -----

    def run_macro(
        self,
        session_id: SessionId,
        macro_name: str,
        args: list[Any],
    ) -> OpResult:
        """Ejecuta una macro VBA via xlwings.

        Args:
            session_id: ID de la sesión.
            macro_name: Nombre de la macro a ejecutar.
            args: Argumentos a pasar a la macro.

        Returns:
            OpResult con el resultado de la macro.
        """

        def _do(h: Any) -> dict[str, Any]:
            result = self._xlwings.run_macro(h, macro_name=macro_name, args=args)
            return {"macro": macro_name, "result": str(result) if result is not None else None}

        return self._with_session(session_id, "run_macro", _do)

    def create_chart(
        self,
        session_id: SessionId,
        sheet: str,
        range_addr: str,
        chart_type: str = "column",
        title: str | None = None,
        legend: bool = True,
    ) -> OpResult:
        """Crea un gráfico en la hoja.

        Args:
            session_id: ID de la sesión.
            sheet: Nombre de la hoja con los datos.
            range_addr: Rango de datos, ej. 'A1:D5'.
            chart_type: Tipo de gráfico (xlChartType).
            title: Título opcional del gráfico.
            legend: Si True, muestra la leyenda.

        Returns:
            OpResult con chart_id y name del gráfico.
        """

        def _do(h: Any) -> dict[str, Any]:
            return self._xlwings.create_chart(
                h,
                sheet=sheet,
                range_addr=range_addr,
                chart_type=chart_type,
                title=title,
                legend=legend,
            )

        return self._with_session(session_id, "create_chart", _do)

    def create_pivot(
        self,
        session_id: SessionId,
        sheet: str,
        data_range: str,
        dest_cell: str,
        rows: list[str] | None = None,
        columns: list[str] | None = None,
        values: list[str] | None = None,
    ) -> OpResult:
        """Crea una tabla pivote.

        Args:
            session_id: ID de la sesión.
            sheet: Nombre de la hoja con los datos.
            data_range: Rango de datos fuente, ej. 'A1:E100'.
            dest_cell: Celda destino del informe pivote, ej. 'G3'.
            rows: Campos para filas (opcional).
            columns: Campos para columnas (opcional).
            values: Campos para valores (opcional).

        Returns:
            OpResult con pivot_table_name.
        """

        def _do(h: Any) -> dict[str, Any]:
            return self._xlwings.create_pivot(
                h,
                sheet=sheet,
                data_range=data_range,
                dest_cell=dest_cell,
                rows=rows,
                columns=columns,
                values=values,
            )

        return self._with_session(session_id, "create_pivot", _do)

    def update_dashboard(
        self,
        session_id: SessionId,
        dashboard_sheet: str,
        data_sheets: list[str],
        refresh_all: bool = True,
    ) -> OpResult:
        """Refresca y recalcula un dashboard.

        Args:
            session_id: ID de la sesión.
            dashboard_sheet: Nombre de la hoja dashboard.
            data_sheets: Hojas con datos a refrescar.
            refresh_all: Si True, fuerza recalculo completo.

        Returns:
            OpResult con refreshed_sheets y calculation_time_ms.
        """

        def _do(h: Any) -> dict[str, Any]:
            return self._xlwings.update_dashboard(
                h,
                dashboard_sheet=dashboard_sheet,
                data_sheets=data_sheets,
                refresh_all=refresh_all,
            )

        return self._with_session(session_id, "update_dashboard", _do)

    def screenshot(
        self,
        session_id: SessionId,
        sheet: str,
        path: str,
        region: str | None = None,
    ) -> OpResult:
        """Captura una hoja o región como imagen PNG.

        Args:
            session_id: ID de la sesión.
            sheet: Nombre de la hoja a capturar.
            path: Ruta destino del PNG.
            region: Rango opcional a capturar.

        Returns:
            OpResult con path, width y height.
        """

        def _do(h: Any) -> dict[str, Any]:
            return self._xlwings.screenshot(h, sheet=sheet, path=path, region=region)

        return self._with_session(session_id, "screenshot", _do)

    def power_query(
        self,
        session_id: SessionId,
        query_name: str,
        connection_string: str,
        output_cell: str,
        sql: str | None = None,
    ) -> OpResult:
        """Ejecuta una Power Query.

        Args:
            session_id: ID de la sesión.
            query_name: Nombre de la query.
            connection_string: Connection string ODBC/OLEDB.
            output_cell: Celda destino del resultado.
            sql: SQL query a ejecutar (opcional).

        Returns:
            OpResult con query_name y rows_loaded.
        """

        def _do(h: Any) -> dict[str, Any]:
            return self._xlwings.power_query(
                h,
                query_name=query_name,
                connection_string=connection_string,
                output_cell=output_cell,
                sql=sql,
            )

        return self._with_session(session_id, "power_query", _do)

    def dax_measure(
        self,
        session_id: SessionId,
        table_name: str,
        measure_name: str,
        expression: str,
    ) -> OpResult:
        """Crea una medida DAX en una tabla del modelo de datos.

        Args:
            session_id: ID de la sesión.
            table_name: Nombre de la tabla destino.
            measure_name: Nombre de la medida.
            expression: Expresión DAX.

        Returns:
            OpResult con measure_name, table_name y dax_expression.
        """

        def _do(h: Any) -> dict[str, Any]:
            return self._xlwings.dax_measure(
                h,
                table_name=table_name,
                measure_name=measure_name,
                expression=expression,
            )

        return self._with_session(session_id, "dax_measure", _do)

    def slicer(
        self,
        session_id: SessionId,
        pivot_table_name: str,
        source_field: str,
        dest_cell: str,
        style: str | None = None,
    ) -> OpResult:
        """Crea una segmentación de datos (slicer).

        Args:
            session_id: ID de la sesión.
            pivot_table_name: Nombre de la tabla pivote objetivo.
            source_field: Campo de la tabla pivote a segmentar.
            dest_cell: Celda superior izquierda del slicer.
            style: Estilo del slicer (opcional).

        Returns:
            OpResult con slicer_name y source_field.
        """

        def _do(h: Any) -> dict[str, Any]:
            return self._xlwings.slicer(
                h,
                pivot_table_name=pivot_table_name,
                source_field=source_field,
                dest_cell=dest_cell,
                style=style,
            )

        return self._with_session(session_id, "slicer", _do)

    def conditional_format(
        self,
        session_id: SessionId,
        sheet: str,
        range_addr: str,
        rule_type: Literal["cell_value", "formula", "color_scale", "data_bar", "icon_set"],
        formula_or_threshold: str | tuple[float, str] | None = None,
        format_style: str | None = None,
    ) -> OpResult:
        """Aplica formato condicional a un rango.

        Args:
            session_id: ID de la sesión.
            sheet: Nombre de la hoja.
            range_addr: Rango a formatear.
            rule_type: Tipo de regla.
            formula_or_threshold: Parámetros según rule_type.
            format_style: Estilo adicional.

        Returns:
            OpResult con range, rule_type y format_applied.
        """

        def _do(h: Any) -> dict[str, Any]:
            return self._xlwings.conditional_format(
                h,
                sheet=sheet,
                range_addr=range_addr,
                rule_type=rule_type,
                formula_or_threshold=formula_or_threshold,
                format_style=format_style,
            )

        return self._with_session(session_id, "conditional_format", _do)

    def calculation_mode(
        self,
        session_id: SessionId,
        mode: Literal["automatic", "manual", "semiautomatic"],
    ) -> OpResult:
        """Cambia el modo de cálculo de Excel.

        Args:
            session_id: ID de la sesión.
            mode: Modo — 'automatic', 'manual' o 'semiautomatic'.

        Returns:
            OpResult con calculation_mode.
        """

        def _do(h: Any) -> dict[str, Any]:
            return self._xlwings.calculation_mode(h, mode=mode)

        return self._with_session(session_id, "calculation_mode", _do)

    # ----- Helpers -----

    @staticmethod
    def _normalize_op_data(value: Any, data_key: str | None) -> dict[str, Any]:
        """Normaliza el valor devuelto por fn a un dict de datos.

        Args:
            value: Valor retornado por la operación.
            data_key: Clave para envolver valores no-dict (o None).

        Returns:
            El propio dict si value es dict; {data_key: value} si hay key; si no, {}.
        """
        if isinstance(value, dict):
            return value
        if data_key is not None:
            return {data_key: value}
        return {}

    def _with_session(
        self,
        session_id: SessionId,
        op: str,
        fn: Any,
        data_key: str | None = None,
    ) -> OpResult:
        """Ejecuta fn dentro del contexto de una sesión adquirida.

        Args:
            session_id: ID de la sesión.
            op: Nombre de la operación (usado para routing y historial).
            fn: Callable que recibe el handle y retorna dict o valor.
            data_key: Si fn retorna un valor no-dict, lo envuelve en {data_key: valor}.

        Returns:
            OpResult con el resultado de fn si status='ok', o error estructurado.
        """
        rid = self._rid()
        t0 = time.time()
        try:
            st = self._sessions.get(session_id)
        except KeyError:
            return self._error(
                rid,
                t0,
                None,
                category="user",
                code="SESSION_UNKNOWN",
                message=f"unknown session: {session_id}",
            )

        # Routing
        env = RouterEnv(excel_running=False, can_launch_excel=False)
        try:
            backend = self._router.choose(op, st, env)
        except BackendUnavailable as exc:
            return self._error(
                rid,
                t0,
                None,
                category="fatal",
                code="BACKEND_NOT_AVAILABLE",
                message=str(exc),
            )

        handle = self._handles.get(session_id)
        if handle is None:
            return self._error(
                rid,
                t0,
                None,
                category="fatal",
                code="HANDLE_MISSING",
                message="session handle not found",
            )

        # For XLWINGS sessions, ensure the handle is from _xlwings
        if st.opened_with == Backend.XLWINGS:
            xlwings_handle = handle
        else:
            xlwings_handle = None

        # Acquire and execute
        try:
            with self._sessions.acquire(session_id):
                self._op_history.setdefault(session_id, Counter())[op] += 1
                if xlwings_handle is not None:
                    value = fn(xlwings_handle)
                else:
                    value = fn(handle)
        except PermissionError as exc:
            return self._error(
                rid,
                t0,
                backend,
                category="user",
                code="READ_ONLY_SESSION",
                message=str(exc),
            )
        except (ValueError, KeyError) as exc:
            return self._error(
                rid,
                t0,
                backend,
                category="user",
                code="INVALID_ARGS",
                message=str(exc),
            )
        except Exception as exc:  # noqa: BLE001
            st.error_count += 1
            return self._error(
                rid,
                t0,
                backend,
                category="fatal",
                code="BACKEND_ERROR",
                message=str(exc),
            )

        data = self._normalize_op_data(value, data_key)

        return OpResult(
            status="ok",
            request_id=rid,
            duration_ms=self._ms(t0),
            backend_used=backend,
            data=data,
        )

    def _error(
        self,
        rid: str,
        t0: float,
        backend: Backend | None,
        *,
        category: str,
        code: str,
        message: str,
        suggested: list[str] | None = None,
        retryable: bool = False,
    ) -> OpResult:
        """Construye un OpResult de error y lo ingesta en Brain de forma no bloqueante.

        Args:
            rid: Request ID para correlación.
            t0: Timestamp de inicio para calcular duration_ms.
            backend: Backend que generó el error, si aplica.
            category: Categoría del error (user, fatal, transient, recoverable).
            code: Código canónico del error.
            message: Mensaje legible del error.
            suggested: Acciones sugeridas para el usuario.
            retryable: Si True, el cliente puede reintentar.

        Returns:
            OpResult con status='error' y ErrorInfo poblado.
        """
        err = ErrorInfo(
            category=category,  # type: ignore[arg-type]
            code=code,
            message=message,
            backend_message=None,
            suggested_next_actions=suggested or [],
            retryable=retryable,
            retry_after_ms=None,
            brain_hint_used=None,
        )
        # Best-effort error ingest (non-fatal si Brain no está disponible)
        try:
            self._tracker.ingest_error(
                op="engine",
                path="",
                backend_used=backend.value if backend else "engine",
                error_code=code,
                error_message=message,
                next_action=(suggested[0] if suggested else None),
                request_id=rid,
            )
        except Exception:
            pass
        return OpResult(
            status="error",
            request_id=rid,
            duration_ms=self._ms(t0),
            backend_used=backend,
            error=err,
        )

    @staticmethod
    def _rid() -> str:
        """Genera un request ID único con prefijo req_.

        Returns:
            String de la forma 'req_<12 hex chars>'.
        """
        return f"req_{secrets.token_hex(6)}"

    @staticmethod
    def _ms(t0: float) -> int:
        """Calcula la duración en milisegundos desde t0.

        Args:
            t0: Timestamp de inicio (time.time()).

        Returns:
            Duración en milisegundos como entero.
        """
        return int((time.time() - t0) * 1000)
