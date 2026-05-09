"""Backend Protocol — interfaz común para openpyxl, xlwings, super-agent."""

from __future__ import annotations

from typing import Any, Literal, Protocol, runtime_checkable

from excel_engine.types import CellFormat


@runtime_checkable
class Backend(Protocol):
    """Interfaz común que todo backend debe implementar.

    Cada método recibe un handle opaco específico del backend retornado por open().
    Los métodos lanzan FileNotFoundError, PermissionError, ValueError, RuntimeError
    según corresponda; el engine los envuelve en ErrorInfo.
    """

    def open(self, path: str, mode: Literal["read", "write", "live"]) -> Any:
        """Abre un workbook y retorna un handle específico del backend.

        Args:
            path: Ruta al archivo .xlsx.
            mode: Modo de apertura — 'read', 'write' o 'live'.

        Returns:
            Handle opaco del backend.

        Raises:
            FileNotFoundError: Si el archivo no existe.
            ValueError: Si el modo no es soportado por el backend.
        """
        ...

    def close(self, handle: Any, save: bool = True) -> None:
        """Cierra el workbook. Si save=True, persiste los cambios.

        Args:
            handle: Handle retornado por open().
            save: Si es True y hay cambios pendientes, guarda antes de cerrar.
        """
        ...

    def read_range(
        self,
        handle: Any,
        sheet: str,
        range_addr: str,
    ) -> list[list[Any]]:
        """Retorna los valores de celdas como lista 2D.

        Args:
            handle: Handle retornado por open().
            sheet: Nombre de la hoja.
            range_addr: Dirección del rango, ej. 'A1:C10' o 'A1'.

        Returns:
            Lista de listas con los valores de las celdas.
        """
        ...

    def write_range(
        self,
        handle: Any,
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
        ...

    def apply_formula(
        self,
        handle: Any,
        sheet: str,
        range_addr: str,
        formula: str,
    ) -> None:
        """Escribe una expresión de fórmula en la(s) celda(s).

        Args:
            handle: Handle retornado por open().
            sheet: Nombre de la hoja.
            range_addr: Dirección de la celda o rango destino.
            formula: Fórmula a escribir, con o sin '=' inicial.

        Raises:
            PermissionError: Si el handle fue abierto en modo 'read'.
        """
        ...

    def set_format(
        self,
        handle: Any,
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
            PermissionError: Si el handle fue abierto en modo 'read'.
        """
        ...

    def create_table(
        self,
        handle: Any,
        sheet: str,
        range_addr: str,
        name: str,
        style: str | None = None,
    ) -> None:
        """Convierte un rango en una Tabla Excel.

        Args:
            handle: Handle retornado por open().
            sheet: Nombre de la hoja.
            range_addr: Rango de la tabla, ej. 'A1:D10'.
            name: Nombre único de la tabla dentro del workbook.
            style: Nombre del estilo de tabla (ej. 'TableStyleMedium9').

        Raises:
            PermissionError: Si el handle fue abierto en modo 'read'.
            ValueError: Si ya existe una tabla con ese nombre en la hoja.
        """
        ...

    def save_as(
        self,
        handle: Any,
        path: str,
        format: Literal["xlsx", "pdf", "csv", "xlsm"],
    ) -> None:
        """Exporta el workbook a una nueva ruta/formato.

        Args:
            handle: Handle retornado por open().
            path: Ruta de destino del archivo exportado.
            format: Formato de exportación — 'xlsx', 'pdf', 'csv' o 'xlsm'.

        Raises:
            NotImplementedError: Si el formato requiere backend externo (ej. pdf con openpyxl).
            ValueError: Si el formato no es soportado.
        """
        ...
