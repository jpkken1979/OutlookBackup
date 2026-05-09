#!/usr/bin/env python3
"""
UNS Data Loader - Cargador de Datos Reales
==========================================
Lee archivos Excel y JSON de ユニバーサル企画株式会社.
"""

import json
import logging
from pathlib import Path
from typing import Any

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("uns-data-loader")


# =============================================================================
# CONFIGURACIÓN DE RUTAS
# =============================================================================

# Base path para archivos UNS
UNS_DATA_BASE = Path(
    r"C:\Users\kenji\OneDrive\Desktop\Agentes antigraviti\APP UNS-CLAUDEJP Archivos"
)

# Archivos específicos
UNS_FILES = {
    "shain_daicho": UNS_DATA_BASE / "【新】社員台帳(UNS)T　2022.04.05～.xlsm",
    "shain_sheets": {"haken": "派遣社員", "ukeoi": "請負社員", "staff": "スタッフ"},
    "yukyu_kanri": UNS_DATA_BASE / "有給休暇管理.xlsm",
    "kouza_kanri": UNS_DATA_BASE / "口座管理表.xlsx",
    "yachin_koujyo": UNS_DATA_BASE / "家賃控除(社員№入力）.xlsm",
    "ryo_yachin": UNS_DATA_BASE / "寮家賃(UNS).xlsx",
    "factories_dir": UNS_DATA_BASE / "factories",
    "kintai_dir": UNS_DATA_BASE / "勤怠表ALL2025",
    "kyuryo_dir": UNS_DATA_BASE / "Kyuryo",
}


# =============================================================================
# CARGADOR DE EMPLEADOS (EXCEL)
# =============================================================================


class EmployeeLoader:
    """Carga y procesa datos de empleados desde el 社員台帳 (Excel)."""

    def __init__(self, excel_path: Path = None):
        self.excel_path = excel_path or UNS_FILES["shain_daicho"]
        import pykakasi

        self.kks = pykakasi.kakasi()

    def to_katakana(self, text: Any) -> str:
        """Convierte texto (Kanji/Kana) a Katakana."""
        if not text or not isinstance(text, str):
            return ""
        result = self.kks.convert(text)
        return "".join([item["kana"] for item in result])

    def abbreviate_factory(self, name: Any) -> str:
        """Abrevia nombres de fábricas para que quepan en reportes."""
        if not name or not isinstance(text := str(name), str) or text == "nan":
            return ""

        if "高雄工業" in text:
            # Eliminar redundancias comunes en UNS
            distintivo = (
                text.replace("高雄工業株式会社", "")
                .replace("愛知事業所", "")
                .replace("株式会社", "")
                .strip()
            )
            return f"高雄{distintivo}"

        return text[:20]

    def load_sheet(self, sheet_name: str, header_row: int = 1) -> list[dict[str, Any]]:
        """Lee una hoja específica con la cabecera en la fila indicada (0-indexed)."""
        import pandas as pd

        if not self.excel_path.exists():
            return []

        try:
            df = pd.read_excel(
                self.excel_path, sheet_name=sheet_name, engine="openpyxl", header=header_row
            )
            # Limpiar columnas de nulos o nombres genéricos
            df.columns = [str(c).strip() for c in df.columns]
            # Eliminar filas donde el nombre sea nulo
            if "氏名" in df.columns:
                df = df[df["氏名"].notna()]
            return df.to_dict("records")
        except Exception as e:
            logger.error(f"Error cargando hoja {sheet_name}: {e}")
            return []

    def process_haken(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Procesa datos de 派遣社員 (Haken)."""
        processed = []
        for row in data:
            # En GenzaiX el estado está en '現在'
            status = str(row.get("現在", "在職中")).strip()

            # Priorizar columna 'カナ' del Excel si existe
            kana_excel = str(row.get("カナ", "")).strip()
            name_katakana = (
                kana_excel
                if kana_excel and kana_excel != "nan"
                else self.to_katakana(row.get("氏名", ""))
            )

            emp = {
                "employee_id": str(row.get("社員№", "")),
                "uns_id": str(row.get("社員№", "")),
                "name_kanji": str(row.get("氏名", "")).strip(),
                "name_kana": kana_excel,
                "name_katakana": name_katakana,
                "status": status,
                "is_active": status == "在職中",
                "factory_name_full": row.get("派遣先", ""),
                "factory_name_short": self.abbreviate_factory(row.get("派遣先", "")),
                "factory_id": str(row.get("派遣先ID", "")),
                "visa_type": row.get("ビザ種類", ""),
                "all_fields_json": {k: str(v) for k, v in row.items()},
            }
            processed.append(emp)
        return processed

    def process_ukeoi(self, data: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Procesa datos de 請負社員 (Ukeoi)."""
        processed = []
        for row in data:
            # Priorizar columna 'カナ' (Ukeoi también la tiene en Row 2)
            kana_excel = str(row.get("カナ", "")).strip()
            name_katakana = (
                kana_excel
                if kana_excel and kana_excel != "nan"
                else self.to_katakana(row.get("氏名", ""))
            )

            status = str(row.get("現在", "在職中")).strip()

            emp = {
                "employee_id": str(row.get("社員№", "")),
                "name_kanji": str(row.get("氏名", "")).strip(),
                "name_katakana": name_katakana,
                "status": status,
                "is_active": status == "在職中",
                "factory_name_short": self.abbreviate_factory(row.get("場所", "高雄工業岡山工場")),
                "all_fields_json": {k: str(v) for k, v in row.items()},
            }
            processed.append(emp)
        return processed


# =============================================================================
# CARGADOR DE FÁBRICAS (JSON)
# =============================================================================


class FactoryLoader:
    """Carga datos de fábricas desde archivos JSON."""

    def __init__(self, factories_dir: Path = None):
        self.factories_dir = factories_dir or UNS_FILES["factories_dir"]
        self._cache: dict[str, dict] = {}

    def load_all(self) -> dict[str, dict]:
        """Carga todas las fábricas."""
        if self._cache:
            return self._cache

        if not self.factories_dir.exists():
            logger.warning(f"Directorio de fábricas no existe: {self.factories_dir}")
            return {}

        for json_file in self.factories_dir.glob("*.json"):
            if json_file.name == "factory_id_mapping.json":
                continue  # Skip mapping file

            try:
                with open(json_file, encoding="utf-8") as f:
                    data = json.load(f)
                    factory_id = data.get("factory_id", json_file.stem)
                    self._cache[factory_id] = data
                    logger.debug(f"Cargada fábrica: {factory_id}")
            except Exception as e:
                logger.error(f"Error cargando {json_file}: {e}")

        logger.info(f"Cargadas {len(self._cache)} fábricas")
        return self._cache

    def get_factory(self, factory_id: str) -> dict | None:
        """Obtiene datos de una fábrica específica."""
        if not self._cache:
            self.load_all()
        return self._cache.get(factory_id)

    def get_by_client(self, client_name: str) -> list[dict]:
        """Obtiene fábricas de un cliente específico."""
        if not self._cache:
            self.load_all()

        results = []
        for factory_id, data in self._cache.items():
            client = data.get("client_company", {}).get("name", "")
            if client_name in client or client_name in factory_id:
                results.append(data)
        return results

    def list_clients(self) -> list[str]:
        """Lista todos los clientes únicos."""
        if not self._cache:
            self.load_all()

        clients = set()
        for data in self._cache.values():
            client = data.get("client_company", {}).get("name", "")
            if client:
                clients.add(client)
        return sorted(clients)

    def list_plants(self, client_name: str = None) -> list[dict]:
        """Lista todas las plantas (opcionalmente filtradas por cliente)."""
        if not self._cache:
            self.load_all()

        plants = []
        for factory_id, data in self._cache.items():
            client = data.get("client_company", {}).get("name", "")
            plant = data.get("plant", {}).get("name", "")

            if client_name and client_name not in client:
                continue

            plants.append(
                {
                    "factory_id": factory_id,
                    "client": client,
                    "plant": plant,
                    "address": data.get("plant", {}).get("address", ""),
                }
            )
        return plants

    def get_hourly_rates(self, factory_id: str) -> dict[str, float]:
        """Obtiene tarifas por hora de una fábrica."""
        factory = self.get_factory(factory_id)
        if not factory:
            return {}

        rates = {}
        for line in factory.get("lines", []):
            job = line.get("job", {})
            rate = job.get("hourly_rate", 0)
            description = job.get("description", "")
            line_name = line.get("assignment", {}).get("line", "")
            if rate > 0:
                rates[line_name or description] = rate
        return rates


# =============================================================================
# CARGADOR DE ASISTENCIA
# =============================================================================


class AttendanceLoader:
    """Carga datos de勤怠表 (hojas de asistencia)."""

    def __init__(self, kintai_dir: Path = None):
        self.kintai_dir = kintai_dir or UNS_FILES["kintai_dir"]

    def list_months(self) -> list[str]:
        """Lista meses disponibles."""
        if not self.kintai_dir.exists():
            return []

        months = []
        for folder in self.kintai_dir.iterdir():
            if folder.is_dir() and folder.name.startswith("勤怠表"):
                # Extraer mes: 勤怠表2025.1 -> 2025.1
                month = folder.name.replace("勤怠表", "")
                months.append(month)
        return sorted(months)

    def list_files(self, month: str) -> list[Path]:
        """Lista archivos de asistencia de un mes."""
        month_dir = self.kintai_dir / f"勤怠表{month}"
        if not month_dir.exists():
            return []

        return list(month_dir.glob("*.xlsm")) + list(month_dir.glob("*.xlsx"))

    def get_factory_files(self, month: str, factory_keyword: str) -> list[Path]:
        """Busca archivos de una fábrica específica."""
        files = self.list_files(month)
        return [f for f in files if factory_keyword in f.name]


# =============================================================================
# CARGADOR DE NÓMINA
# =============================================================================


class PayrollLoader:
    """Carga datos de給与明細 (nóminas)."""

    def __init__(self, kyuryo_dir: Path = None):
        self.kyuryo_dir = kyuryo_dir or UNS_FILES["kyuryo_dir"]

    def list_months(self) -> list[str]:
        """Lista meses disponibles de nómina."""
        if not self.kyuryo_dir.exists():
            return []

        months = []
        for file in self.kyuryo_dir.glob("給与明細*.xlsm"):
            # Extraer mes del nombre: 給与明細(派遣社員)2025.1(0217支給).xlsm
            name = file.stem
            # Buscar patrón 2025.X
            import re

            match = re.search(r"(\d{4}\.\d+)", name)
            if match:
                months.append(match.group(1))
        return sorted(set(months))

    def get_file(self, month: str) -> Path | None:
        """Obtiene archivo de nómina de un mes."""
        for file in self.kyuryo_dir.glob(f"給与明細*{month}*.xlsm"):
            return file
        return None


# =============================================================================
# CARGADOR PRINCIPAL
# =============================================================================


class UNSDataLoader:
    """
    Cargador principal de datos UNS.
    Integra todos los sub-cargadores.
    """

    def __init__(self, base_path: Path = None):
        self.base_path = base_path or UNS_DATA_BASE

        # Sub-cargadores
        self.factories = FactoryLoader()
        self.attendance = AttendanceLoader()
        self.payroll = PayrollLoader()

        logger.info(f"UNS Data Loader inicializado: {self.base_path}")

    def check_files(self) -> dict[str, bool]:
        """Verifica qué archivos están disponibles."""
        status = {}
        for name, path in UNS_FILES.items():
            status[name] = path.exists()
        return status

    def summary(self) -> dict[str, Any]:
        """Genera resumen de datos disponibles."""
        return {
            "base_path": str(self.base_path),
            "files_available": self.check_files(),
            "factories_count": len(self.factories.load_all()),
            "clients": self.factories.list_clients(),
            "attendance_months": self.attendance.list_months(),
            "payroll_months": self.payroll.list_months(),
        }

    def load_factories(self) -> dict[str, dict]:
        """Carga todas las fábricas."""
        return self.factories.load_all()

    def get_factory(self, factory_id: str) -> dict | None:
        """Obtiene una fábrica específica."""
        return self.factories.get_factory(factory_id)

    def get_client_factories(self, client_name: str) -> list[dict]:
        """Obtiene fábricas de un cliente."""
        return self.factories.get_by_client(client_name)


# =============================================================================
# CLI
# =============================================================================


def main():
    import argparse

    parser = argparse.ArgumentParser(
        description="UNS Data Loader - Cargador de datos reales",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python data_loader.py status
  python data_loader.py factories
  python data_loader.py factory "高雄工業株式会社_本社工場"
  python data_loader.py clients
  python data_loader.py attendance-months
  python data_loader.py payroll-months
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # Status
    subparsers.add_parser("status", help="Mostrar estado de archivos")

    # Factories
    subparsers.add_parser("factories", help="Listar todas las fábricas")

    # Factory específica
    factory_parser = subparsers.add_parser("factory", help="Mostrar fábrica específica")
    factory_parser.add_argument("factory_id", help="ID de la fábrica")

    # Clients
    subparsers.add_parser("clients", help="Listar clientes派遣先")

    # Attendance months
    subparsers.add_parser("attendance-months", help="Listar meses de asistencia")

    # Payroll months
    subparsers.add_parser("payroll-months", help="Listar meses de nómina")

    # Summary
    subparsers.add_parser("summary", help="Mostrar resumen completo")

    args = parser.parse_args()

    loader = UNSDataLoader()

    if args.command == "status":
        print("=" * 60)
        print("Estado de Archivos UNS")
        print("=" * 60)
        status = loader.check_files()
        for name, exists in status.items():
            icon = "✅" if exists else "❌"
            print(f"{icon} {name}")

    elif args.command == "factories":
        factories = loader.load_factories()
        print(f"\n🏭 Fábricas cargadas: {len(factories)}\n")
        for factory_id in sorted(factories.keys()):
            data = factories[factory_id]
            client = data.get("client_company", {}).get("name", "?")
            plant = data.get("plant", {}).get("name", "?")
            print(f"  - {client} / {plant}")

    elif args.command == "factory":
        factory = loader.get_factory(args.factory_id)
        if factory:
            print(json.dumps(factory, indent=2, ensure_ascii=False))
        else:
            print(f"❌ Fábrica no encontrada: {args.factory_id}")

    elif args.command == "clients":
        clients = loader.factories.list_clients()
        print(f"\n📍 Clientes派遣先: {len(clients)}\n")
        for client in clients:
            print(f"  - {client}")

    elif args.command == "attendance-months":
        months = loader.attendance.list_months()
        print(f"\n📅 Meses de勤怠表: {len(months)}\n")
        for month in months:
            print(f"  - {month}")

    elif args.command == "payroll-months":
        months = loader.payroll.list_months()
        print(f"\n💰 Meses de給与明細: {len(months)}\n")
        for month in months:
            print(f"  - {month}")

    elif args.command == "summary":
        summary = loader.summary()
        print("\n" + "=" * 60)
        print("📊 Resumen de Datos UNS")
        print("=" * 60)
        print(f"\n📁 Base path: {summary['base_path']}")
        print(f"\n🏭 Fábricas: {summary['factories_count']}")
        print(f"📍 Clientes: {len(summary['clients'])}")
        for client in summary["clients"][:5]:
            print(f"   - {client}")
        if len(summary["clients"]) > 5:
            print(f"   ... y {len(summary['clients']) - 5} más")
        print(f"\n📅 Meses de asistencia: {len(summary['attendance_months'])}")
        print(f"💰 Meses de nómina: {len(summary['payroll_months'])}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
