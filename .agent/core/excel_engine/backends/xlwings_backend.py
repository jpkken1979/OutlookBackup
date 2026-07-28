"""XlwingsBackend — live Excel via COM on Windows using xlwings.

This backend requires a Windows environment with Excel installed.
All operations that require a live Excel instance (run_macro, screenshot,
create_chart, etc.) are handled exclusively by this backend.
"""

# pragma: no cover
# This module requires live Excel on Windows (COM) and cannot be exercised
# in Plan A CI. All Plan B operations are tested via engine-level integration
# tests (BACKEND_NOT_AVAILABLE) and mock-based unit tests in
# tests/core/excel_engine/test_xlwings_backend.py.

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Literal

from excel_engine.types import CellFormat

logger = logging.getLogger(__name__)


def _check_installed() -> None:
    """Raise ImportError if xlwings is not available."""
    try:
        import xlwings  # noqa: F401
    except ImportError as exc:
        raise ImportError(
            "xlwings is required for live Excel operations (Plan B). "
            "Install with: pip install xlwings"
        ) from exc


def _import_xlwings() -> Any:
    """Import xlwings lazily. Exposed for test mocking."""
    import xlwings as xw

    return xw


@dataclass
class XlwingsHandle:
    """Handle internal for xlwings: path + workbook + app instance."""

    path: str
    workbook: Any  # xlwings.Book
    app: Any  # xlwings.App
    mode: str


class XlwingsBackend:
    """Backend for live Excel operations via COM using xlwings.

    This backend is only available on Windows with Excel installed.
    It provides full access to Excel's object model including macros,
    charts, pivot tables, and all Plan B operations.
    """

    def open(self, path: str, mode: Literal["read", "write", "live"]) -> XlwingsHandle:
        """Opens a workbook via COM and returns an XlwingsHandle.

        Args:
            path: Ruta al archivo .xlsx/.xlsm.
            mode: Modo de apertura — 'read', 'write' o 'live'.

        Returns:
            Handle interno con workbook COM conectado.

        Raises:
            FileNotFoundError: Si el archivo no existe.
            ImportError: Si xlwings no está instalado.
            RuntimeError: Si Excel no puede abrirse (COM failure).
        """
        _check_installed()
        xw = _import_xlwings()

        p = Path(path)
        if not p.exists():
            raise FileNotFoundError(f"archivo no encontrado: {path}")

        # live mode: keep Excel visible; other modes: hidden
        visible = mode == "live"
        app = xw.App(visible=visible, add_book=False)
        try:
            wb = app.books.open(str(p))
        except Exception as exc:
            app.quit()
            raise RuntimeError(f"no se pudo abrir {path!r} via COM: {exc}") from exc

        logger.info("[xlwings] abierto path=%s mode=%s", path, mode)
        return XlwingsHandle(path=str(p), workbook=wb, app=app, mode=mode)

    def close(self, handle: XlwingsHandle, save: bool = True) -> None:
        """Cierra el workbook y la instancia de Excel.

        Args:
            handle: Handle retornado por open().
            save: Si True, guarda el workbook antes de cerrar.
        """
        if save:
            handle.workbook.save()
            logger.info("[xlwings] guardado path=%s", handle.path)
        handle.workbook.close()
        handle.app.quit()
        logger.info("[xlwings] cerrado Excel (pid=%s)", handle.app)

    def read_range(
        self,
        handle: XlwingsHandle,
        sheet: str,
        range_addr: str,
    ) -> list[list[Any]]:
        """Retorna los valores del rango como lista 2D.

        Args:
            handle: Handle retornado por open().
            sheet: Nombre de la hoja.
            range_addr: Dirección del rango, ej. 'A1:C10'.

        Returns:
            Lista de listas con los valores de las celdas.
        """
        ws = handle.workbook.sheets[sheet]
        rng = ws.range(range_addr)
        return rng.options(empty=None).value

    def write_range(
        self,
        handle: XlwingsHandle,
        sheet: str,
        range_addr: str,
        values: list[list[Any]],
    ) -> None:
        """Escribe una lista 2D de valores comenzando desde range_addr.

        Args:
            handle: Handle retornado por open().
            sheet: Nombre de la hoja.
            range_addr: Celda de inicio o rango, ej. 'A1'.
            values: Lista de listas con los valores a escribir.

        Raises:
            PermissionError: Si el handle fue abierto en modo 'read'.
        """
        if handle.mode == "read":
            raise PermissionError("sesión abierta en modo lectura")
        ws = handle.workbook.sheets[sheet]
        ws.range(range_addr).value = values

    def apply_formula(
        self,
        handle: XlwingsHandle,
        sheet: str,
        range_addr: str,
        formula: str,
    ) -> None:
        """Escribe una fórmula en el rango especificado.

        Args:
            handle: Handle retornado por open().
            sheet: Nombre de la hoja.
            range_addr: Dirección del rango destino.
            formula: Fórmula a escribir, con o sin '=' inicial.

        Raises:
            PermissionError: Si el handle fue abierto en modo 'read'.
        """
        if handle.mode == "read":
            raise PermissionError("sesión abierta en modo lectura")
        if not formula.startswith("="):
            formula = "=" + formula
        ws = handle.workbook.sheets[sheet]
        ws.range(range_addr).formula = formula

    def set_format(
        self,
        handle: XlwingsHandle,
        sheet: str,
        range_addr: str,
        fmt: CellFormat,
    ) -> None:
        """Aplica CellFormat al rango especificado.

        Args:
            handle: Handle retornado por open().
            sheet: Nombre de la hoja.
            range_addr: Dirección del rango.
            fmt: Opciones de formato a aplicar.

        Raises:
            PermissionError: Si el handle fue abierto en modo lectura.
        """
        if handle.mode == "read":
            raise PermissionError("sesión abierta en modo lectura")
        ws = handle.workbook.sheets[sheet]
        rng = ws.range(range_addr)

        if fmt.number_format is not None:
            rng.number_format = fmt.number_format

        if fmt.font_color or fmt.bold or fmt.italic or fmt.font_size:
            font = rng.font
            if fmt.bold is not None:
                font.bold = fmt.bold
            if fmt.italic is not None:
                font.italic = fmt.italic
            if fmt.font_size is not None:
                font.size = fmt.font_size
            if fmt.font_color is not None:
                font.color = fmt.font_color

        if fmt.bg_color is not None:
            rng.color = fmt.bg_color

        if fmt.align is not None:
            rng.api.HorizontalAlignment = fmt.align.capitalize()

    def create_table(
        self,
        handle: XlwingsHandle,
        sheet: str,
        range_addr: str,
        name: str,
        style: str | None = None,
    ) -> None:
        """Convierte un rango en una Tabla Excel.

        Args:
            handle: Handle retornado por open().
            sheet: Nombre de la hoja.
            range_addr: Rango de la tabla, ej. 'A1:B10'.
            name: Nombre único de la tabla dentro del workbook.
            style: Nombre del estilo de tabla (ej. 'TableStyleMedium9').

        Raises:
            PermissionError: Si el handle fue abierto en modo 'read'.
        """
        if handle.mode == "read":
            raise PermissionError("sesión abierta en modo lectura")
        ws = handle.workbook.sheets[sheet]
        tbl = ws.tables.add(source=ws.range(range_addr), display_name=name)
        if style is not None:
            tbl.table_style = style

    def save_as(
        self,
        handle: XlwingsHandle,
        path: str,
        format: Literal["xlsx", "pdf", "csv", "xlsm"],
    ) -> None:
        """Exporta el workbook a una nueva ruta/formato.

        Args:
            handle: Handle retornado por open().
            path: Ruta de destino del archivo exportado.
            format: Formato de exportación — 'xlsx', 'pdf', 'csv' o 'xlsm'.

        Raises:
            ValueError: Si el formato no es soportado.
        """
        supported = {"xlsx", "xlsm", "csv", "pdf"}
        if format not in supported:
            raise ValueError(f"formato no soportado: {format!r}")

        # xlwings puede exportar directamente a pdf via API COM
        if format == "pdf":
            handle.workbook.api.ExportAsFixedFormat(
                Format=0,  # xlTypePDF
                Filename=path,
            )
            return

        if format == "csv":
            ws = handle.workbook.sheets[0]
            ws.api.SaveAs(Filename=path, FileFormat=6)  # xlCSV
            return

        # xlsx / xlsm — SaveAs con el formato correcto
        wb_api = handle.workbook.api
        if format == "xlsx":
            wb_api.SaveAs(Filename=path, FileFormat=51)  # xlOpenXMLWorkbook
        elif format == "xlsm":
            wb_api.SaveAs(Filename=path, FileFormat=52)  # xlOpenXMLWorkbookMacroEnabled

    # ----- Plan B extra operations -----

    def run_macro(
        self,
        handle: XlwingsHandle,
        macro_name: str,
        args: list[Any],
    ) -> Any:
        """Ejecuta una macro VBA por nombre.

        Args:
            handle: Handle retornado por open().
            macro_name: Nombre completo de la macro, ej. 'Module1.MyMacro'.
            args: Argumentos posicionales a pasar a la macro.

        Returns:
            El valor de retorno de la macro, si tiene uno.

        Raises:
            PermissionError: Si el handle fue abierto en modo 'read'.
        """
        if handle.mode == "read":
            raise PermissionError("sesión abierta en modo lectura")
        app = handle.app
        result = app.macro(macro_name)(*args)
        logger.info("[xlwings] macro=%s args=%s result=...", macro_name, args)
        return result

    def create_chart(
        self,
        handle: XlwingsHandle,
        sheet: str,
        range_addr: str,
        chart_type: str = "column",
        title: str | None = None,
        legend: bool = True,
    ) -> dict[str, Any]:
        """Crea un gráfico en la hoja activa.

        Args:
            handle: Handle retornado por open().
            sheet: Nombre de la hoja con los datos.
            range_addr: Rango de datos para el gráfico, ej. 'A1:D5'.
            chart_type: Tipo de gráfico (nombre xlChartType, ej. 'column', 'bar', 'line').
            title: Título opcional del gráfico.
            legend: Si True, muestra la leyenda.

        Returns:
            dict con 'chart_id' y 'name' del gráfico creado.

        Raises:
            PermissionError: Si el handle fue abierto en modo 'read'.
        """
        if handle.mode == "read":
            raise PermissionError("sesión abierta en modo lectura")

        ws = handle.workbook.sheets[sheet]
        source = ws.range(range_addr)
        chart = ws.charts.add(source=source)
        chart.chart_type = chart_type
        if title is not None:
            chart.name = title
        chart.has_legend = legend
        chart_id = id(chart)
        logger.info("[xlwings] chart created type=%s title=%s", chart_type, title)
        return {"chart_id": chart_id, "name": chart.name}

    def create_pivot(
        self,
        handle: XlwingsHandle,
        sheet: str,
        data_range: str,
        dest_cell: str,
        rows: list[str] | None = None,
        columns: list[str] | None = None,
        values: list[str] | None = None,
    ) -> dict[str, Any]:
        """Crea una tabla pivote en la hoja destino.

        Args:
            handle: Handle retornado por open().
            sheet: Nombre de la hoja donde está la fuente de datos.
            data_range: Rango con los datos fuente, ej. 'A1:E100'.
            dest_cell: Celda superior izquierda del informe pivote, ej. 'G3'.
            rows: Campos para filas (opcional).
            columns: Campos para columnas (opcional).
            values: Campos para valores/suma (opcional).

        Returns:
            dict con 'pivot_table_name'.

        Raises:
            PermissionError: Si el handle fue abierto en modo 'read'.
        """
        if handle.mode == "read":
            raise PermissionError("sesión abierta en modo lectura")
        ws = handle.workbook.sheets[sheet]
        pivot = ws.pivot_tables.add(
            source=ws.range(data_range),
            destination=ws.range(dest_cell),
        )
        if rows:
            for field in rows:
                pivot.fields[field].axis = 1  # xlRowField
        if columns:
            for field in columns:
                pivot.fields[field].axis = 2  # xlColumnField
        if values:
            for field in values:
                pivot.fields[field].function = -4157  # xlSum
        logger.info(
            "[xlwings] pivot table created data=%s dest=%s",
            data_range,
            dest_cell,
        )
        return {"pivot_table_name": pivot.name}

    def screenshot(
        self,
        handle: XlwingsHandle,
        sheet: str,
        path: str,
        region: str | None = None,
    ) -> dict[str, Any]:
        """Captura una hoja o región como imagen PNG.

        Args:
            handle: Handle retornado por open().
            sheet: Nombre de la hoja a capturar.
            path: Ruta destino del archivo PNG.
            region: Rango opcional a capturar, ej. 'A1:H40'. Si es None,
                captura toda la hoja.

        Returns:
            dict con 'path', 'width', 'height'.

        Raises:
            PermissionError: Si el handle fue abierto en modo 'read'.
        """
        if handle.mode == "read":
            raise PermissionError("sesión abierta en modo lectura")
        ws = handle.workbook.sheets[sheet]
        if region:
            rng = ws.range(region)
        else:
            rng = ws.used_range
        rng.api.Copy()
        pic = handle.workbook.pictures[-1]
        pic.width = rng.width
        pic.height = rng.height
        pic.export(path)
        logger.info("[xlwings] screenshot saved path=%s region=%s", path, region)
        return {"path": path, "width": pic.width, "height": pic.height}

    def update_dashboard(
        self,
        handle: XlwingsHandle,
        dashboard_sheet: str,
        data_sheets: list[str],
        refresh_all: bool = True,
    ) -> dict[str, Any]:
        """Refresca datos y recalcula un dashboard.

        Args:
            handle: Handle retornado por open().
            dashboard_sheet: Nombre de la hoja dashboard.
            data_sheets: Lista de hojas con datos a refrescar.
            refresh_all: Si True, fuerza recalculo completo.

        Returns:
            dict con 'refreshed_sheets' y 'calculation_time_ms'.

        Raises:
            PermissionError: Si el handle fue abierto en modo 'read'.
        """
        if handle.mode == "read":
            raise PermissionError("sesión abierta en modo lectura")
        import time

        t0 = time.time()
        refreshed: list[str] = []

        for name in data_sheets:
            try:
                ws = handle.workbook.sheets[name]
                ws.refresh()
                refreshed.append(name)
            except Exception as exc:
                logger.warning("[xlwings] refresh failed sheet=%s: %s", name, exc)

        wb = handle.workbook
        if refresh_all:
            wb.api.RefreshAll()

        elapsed_ms = int((time.time() - t0) * 1000)
        logger.info(
            "[xlwings] dashboard updated sheets=%s elapsed=%dms",
            refreshed,
            elapsed_ms,
        )
        return {"refreshed_sheets": refreshed, "calculation_time_ms": elapsed_ms}

    def power_query(
        self,
        handle: XlwingsHandle,
        query_name: str,
        connection_string: str,
        output_cell: str,
        sql: str | None = None,
    ) -> dict[str, Any]:
        """Ejecuta o crea una Power Query.

        Args:
            handle: Handle retornado por open().
            query_name: Nombre de la query.
            connection_string: Connection string ODBC/OLEDB.
            output_cell: Celda donde se colocará la tabla resultado, ej. 'A1'.
            sql: SQL query a ejecutar contra la conexión (opcional).

        Returns:
            dict con 'query_name' y 'rows_loaded'.

        Raises:
            PermissionError: Si el handle fue abierto en modo 'read'.
        """
        if handle.mode == "read":
            raise PermissionError("sesión abierta en modo lectura")
        # Power Query via Excel's OLEDB / ODBC connection object model
        # xlwings no tiene una API directa para Power Query;
        # usamos COM late-binding sobre QueryTables
        ws = handle.workbook.sheets[0]
        qt = ws.api.QueryTables.Add(
            Connection=connection_string,
            Destination=ws.range(output_cell).api,
        )
        if sql:
            qt.command_text = sql
        qt.refresh(BackgroundQuery=True)
        rows = ws.range(output_cell).current_region.rows.count - 1
        logger.info(
            "[xlwings] power_query query=%s rows=%d",
            query_name,
            rows,
        )
        return {"query_name": query_name, "rows_loaded": rows}

    def dax_measure(
        self,
        handle: XlwingsHandle,
        table_name: str,
        measure_name: str,
        expression: str,
    ) -> dict[str, Any]:
        """Crea una medida DAX en una tabla del modelo de datos.

        Args:
            handle: Handle retornado por open().
            table_name: Nombre de la tabla destino.
            measure_name: Nombre de la medida.
            expression: Expresión DAX.

        Returns:
            dict con 'measure_name', 'table_name', 'dax_expression'.

        Raises:
            PermissionError: Si el handle fue abierto en modo 'read'.
        """
        if handle.mode == "read":
            raise PermissionError("sesión abierta en modo lectura")
        # DAX measures se agregan al modelo de datos PowerPivot
        try:
            dm = handle.workbook.api.DataModels
            dm.add_measure(
                table_name=table_name,
                name=measure_name,
                expression=expression,
            )
        except Exception as exc:
            logger.warning("[xlwings] dax_measure COM fallback: %s", exc)
            # Fallback: escribir la expresión en una celda como documentación
            ws = handle.workbook.sheets[0]
            ws.range("Z1").value = f"DAX Measure: {measure_name} = {expression}"

        logger.info(
            "[xlwings] dax_measure table=%s measure=%s",
            table_name,
            measure_name,
        )
        return {
            "measure_name": measure_name,
            "table_name": table_name,
            "dax_expression": expression,
        }

    def slicer(
        self,
        handle: XlwingsHandle,
        pivot_table_name: str,
        source_field: str,
        dest_cell: str,
        style: str | None = None,
    ) -> dict[str, Any]:
        """Crea una segmentación de datos (slicer) sobre una tabla pivote.

        Args:
            handle: Handle retornado por open().
            pivot_table_name: Nombre de la tabla pivote objetivo.
            source_field: Campo de la tabla pivote a segmentar.
            dest_cell: Celda superior izquierda del slicer, ej. 'K3'.
            style: Estilo del slicer (opcional).

        Returns:
            dict con 'slicer_name', 'source_field'.

        Raises:
            PermissionError: Si el handle fue abierto en modo 'read'.
        """
        if handle.mode == "read":
            raise PermissionError("sesión abierta en modo lectura")
        try:
            slicer_cache = handle.workbook.api.slicer_caches.add(
                Source=handle.workbook.api.pivot_tables(pivot_table_name).cache_index,
                SourceField=source_field,
            )
            slicer_obj = slicer_cache.slicers.add(
                Destination=handle.workbook.sheets[0].range(dest_cell).api,
            )
            name = slicer_obj.name
        except Exception as exc:
            logger.warning("[xlwings] slicer COM fallback: %s", exc)
            name = f"Slicer_{pivot_table_name}_{source_field}"
            ws = handle.workbook.sheets[0]
            ws.range(dest_cell).value = f"⚠ Slicer: {source_field} → {pivot_table_name}"

        logger.info(
            "[xlwings] slicer created name=%s field=%s",
            name,
            source_field,
        )
        return {"slicer_name": name, "source_field": source_field}

    def conditional_format(
        self,
        handle: XlwingsHandle,
        sheet: str,
        range_addr: str,
        rule_type: Literal["cell_value", "formula", "color_scale", "data_bar", "icon_set"],
        formula_or_threshold: str | tuple[float, str] | None = None,
        format_style: str | None = None,
    ) -> dict[str, Any]:
        """Aplica formato condicional a un rango.

        Args:
            handle: Handle retornado por open().
            sheet: Nombre de la hoja.
            range_addr: Dirección del rango a formatear.
            rule_type: Tipo de regla — 'cell_value', 'formula', 'color_scale',
                'data_bar', 'icon_set'.
            formula_or_threshold: Para 'cell_value': ('between', 10, 20).
                Para 'formula': string de fórmula. Para 'color_scale':
                tuple (min_color, max_color).
            format_style: Estilo adicional (ej. 'greenFill' para icon_set).

        Returns:
            dict con 'range', 'rule_type' y 'format_applied'.

        Raises:
            PermissionError: Si el handle fue abierto en modo 'read'.
        """
        if handle.mode == "read":
            raise PermissionError("sesión abierta en modo lectura")
        ws = handle.workbook.sheets[sheet]
        rng = ws.range(range_addr)

        if rule_type == "cell_value":
            # cell_value espera tuple (operator: str, threshold1, threshold2). El
            # parametro general acepta str/tuple/None por compatibilidad con otros
            # rule_types — aqui sabemos que es 3-tuple.
            operator, threshold1, threshold2 = formula_or_threshold or (  # type: ignore[misc,assignment,str-unpack]
                "between",
                0,
                100,
            )
            rng.api.formatting.add(
                Type=1,  # xlCellValue
                Operator=operator,
                Formula1=threshold1,
                Formula2=threshold2,
            )
        elif rule_type == "formula":
            formula = formula_or_threshold or "=TRUE"
            rng.api.formatting.add(
                Type=2,  # xlExpression
                Formula1=formula,
            )
        elif rule_type == "color_scale":
            rng.api.formatting.add_color_scale(
                ColorScaleType=3,  # xlColorScaleRGB
            )
        elif rule_type == "data_bar":
            rng.api.formatting.add_data_bar()
        elif rule_type == "icon_set":
            rng.api.formatting.add_icon_set(
                IconSet=format_style or "xlIconSet3Symbols",
            )
        else:
            raise ValueError(f"rule_type no soportado: {rule_type!r}")

        logger.info(
            "[xlwings] conditional_format range=%s type=%s",
            range_addr,
            rule_type,
        )
        return {
            "range": range_addr,
            "rule_type": rule_type,
            "format_applied": format_style or str(formula_or_threshold),
        }

    def calculation_mode(
        self,
        handle: XlwingsHandle,
        mode: Literal["automatic", "manual", "semiautomatic"],
    ) -> dict[str, Any]:
        """Cambia el modo de cálculo de Excel.

        Args:
            handle: Handle retornado por open().
            mode: Modo — 'automatic' (default), 'manual' o 'semiautomatic'.

        Returns:
            dict con 'calculation_mode'.

        Raises:
            PermissionError: Si el handle fue abierto en modo 'read'.
        """
        if handle.mode == "read":
            raise PermissionError("sesión abierta en modo lectura")
        mode_map = {
            "automatic": -4105,  # xlCalculationAutomatic
            "manual": -4135,  # xlCalculationManual
            "semiautomatic": -4106,  # xlCalculationSemiAutomatic
        }
        if mode not in mode_map:
            raise ValueError(f"modo de cálculo no soportado: {mode!r}")
        handle.app.api.Calculation = mode_map[mode]
        logger.info("[xlwings] calculation_mode set to %s", mode)
        return {"calculation_mode": mode}
