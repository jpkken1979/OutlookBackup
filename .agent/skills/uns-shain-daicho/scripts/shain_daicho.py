#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
 UNS 社員台帳 (Shain Daicho) - Registro de Empleados
═══════════════════════════════════════════════════════════════════════════════
 Sistema de gestión de社員台帳 (Registro de Empleados) para empresas japonesas.

 Funcionalidades:
   • CRUD de empleados
   • Validación de datos (My Number, 在留カード, etc.)
   • Exportación a Excel/CSV
   • Tracking de visas y contratos
   • Generación de reportes
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import csv
import json
from dataclasses import dataclass, asdict
from datetime import datetime, date
from pathlib import Path


@dataclass
class Employee:
    """Modelo de empleado para社員台帳."""

    # ID
    id: str
    employee_code: str = ""

    # Datos personales básicos
    name_kanji: str = ""
    name_kana: str = ""
    name_romaji: str = ""
    birth_date: date | None = None
    gender: str = ""  # 男/女

    # Nacionalidad y visa
    nationality: str = "日本"
    visa_type: str = ""
    zairyu_card_number: str = ""
    visa_expiry: date | None = None

    # Contacto
    postal_code: str = ""
    address: str = ""
    phone: str = ""
    email: str = ""
    emergency_contact: str = ""
    emergency_phone: str = ""

    # Empleo
    hire_date: date | None = None
    employment_type: str = "派遣社員"  # 正社員, 派遣社員, パート, etc.
    department: str = ""
    position: str = ""
    hourly_rate: int = 0

    # Datos bancarios
    bank_name: str = ""
    branch_name: str = ""
    account_type: str = "普通"
    account_number: str = ""
    account_holder: str = ""

    # Seguros sociales
    health_insurance_number: str = ""
    pension_number: str = ""
    employment_insurance_number: str = ""

    # My Number (almacenar cifrado en producción)
    my_number: str = ""

    # Estado
    status: str = "active"  # active, inactive, terminated

    # Metadata
    created_at: datetime | None = None
    updated_at: datetime | None = None
    notes: str = ""

    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now()
        if self.updated_at is None:
            self.updated_at = datetime.now()

    def get_age(self) -> int | None:
        """Calcula edad actual."""
        if self.birth_date:
            today = date.today()
            return (
                today.year
                - self.birth_date.year
                - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
            )
        return None

    def get_tenure_days(self) -> int | None:
        """Calcula días de antigüedad."""
        if self.hire_date:
            return (date.today() - self.hire_date).days
        return None

    def is_visa_expiring_soon(self, days: int = 90) -> bool:
        """Verifica si la visa expira pronto."""
        if self.visa_expiry:
            return (self.visa_expiry - date.today()).days <= days
        return False

    def validate_my_number(self) -> bool:
        """Valida formato de My Number (12 dígitos con checksum)."""
        if not self.my_number or len(self.my_number) != 12:
            return False
        if not self.my_number.isdigit():
            return False

        # Checksum
        digits = [int(d) for d in self.my_number]
        weights = [6, 5, 4, 3, 2, 7, 6, 5, 4, 3, 2]
        total = sum(d * w for d, w in zip(digits[:11], weights, strict=False))
        remainder = total % 11
        check = 0 if remainder <= 1 else 11 - remainder
        return digits[11] == check


class ShainDaichoManager:
    """Gestor de社員台帳."""

    def __init__(self, data_file: str = "shain_daicho.json"):
        self.data_file = Path(data_file)
        self.employees: dict[str, Employee] = {}
        self._load()

    def _load(self):
        """Carga datos desde archivo."""
        if self.data_file.exists():
            with open(self.data_file, encoding="utf-8") as f:
                data = json.load(f)
                for emp_data in data.get("employees", []):
                    # Convertir fechas
                    for field in ["birth_date", "visa_expiry", "hire_date"]:
                        if emp_data.get(field):
                            emp_data[field] = date.fromisoformat(emp_data[field])
                    for field in ["created_at", "updated_at"]:
                        if emp_data.get(field):
                            emp_data[field] = datetime.fromisoformat(emp_data[field])

                    emp = Employee(**emp_data)
                    self.employees[emp.id] = emp

    def _save(self):
        """Guarda datos a archivo."""
        data = {"version": "1.0", "updated_at": datetime.now().isoformat(), "employees": []}

        for emp in self.employees.values():
            emp_dict = asdict(emp)
            # Convertir fechas a string
            for field in ["birth_date", "visa_expiry", "hire_date"]:
                if emp_dict.get(field):
                    emp_dict[field] = emp_dict[field].isoformat()
            for field in ["created_at", "updated_at"]:
                if emp_dict.get(field):
                    emp_dict[field] = emp_dict[field].isoformat()
            data["employees"].append(emp_dict)

        with open(self.data_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] 📋 {message}")

    # ═══════════════════════════════════════════════════════════════
    # CRUD
    # ═══════════════════════════════════════════════════════════════

    def add_employee(self, employee: Employee) -> Employee:
        """Agrega un nuevo empleado."""
        if employee.id in self.employees:
            raise ValueError(f"Empleado ya existe: {employee.id}")

        self.employees[employee.id] = employee
        self._save()
        self.log(f"Empleado agregado: {employee.name_kanji} ({employee.id})")
        return employee

    def get_employee(self, employee_id: str) -> Employee | None:
        """Obtiene un empleado por ID."""
        return self.employees.get(employee_id)

    def update_employee(self, employee_id: str, updates: dict) -> Employee | None:
        """Actualiza un empleado."""
        emp = self.employees.get(employee_id)
        if not emp:
            return None

        for key, value in updates.items():
            if hasattr(emp, key):
                setattr(emp, key, value)

        emp.updated_at = datetime.now()
        self._save()
        self.log(f"Empleado actualizado: {emp.name_kanji}")
        return emp

    def delete_employee(self, employee_id: str, soft: bool = True) -> bool:
        """Elimina un empleado."""
        emp = self.employees.get(employee_id)
        if not emp:
            return False

        if soft:
            emp.status = "terminated"
            emp.updated_at = datetime.now()
            self._save()
            self.log(f"Empleado desactivado: {emp.name_kanji}")
        else:
            del self.employees[employee_id]
            self._save()
            self.log(f"Empleado eliminado: {employee_id}")

        return True

    def list_employees(
        self,
        status: str = None,
        nationality: str = None,
        department: str = None,
    ) -> list[Employee]:
        """Lista empleados con filtros."""
        result = list(self.employees.values())

        if status:
            result = [e for e in result if e.status == status]
        if nationality:
            result = [e for e in result if e.nationality == nationality]
        if department:
            result = [e for e in result if e.department == department]

        return result

    def search(self, query: str) -> list[Employee]:
        """Busca empleados por nombre o código."""
        query_lower = query.lower()
        return [
            e
            for e in self.employees.values()
            if query_lower in e.name_kanji.lower()
            or query_lower in e.name_kana.lower()
            or query_lower in e.name_romaji.lower()
            or query_lower in e.employee_code.lower()
        ]

    # ═══════════════════════════════════════════════════════════════
    # ALERTAS
    # ═══════════════════════════════════════════════════════════════

    def get_visa_alerts(self, days: int = 90) -> list[dict]:
        """Obtiene alertas de visas por expirar."""
        alerts = []
        for emp in self.employees.values():
            if emp.status != "active":
                continue
            if emp.is_visa_expiring_soon(days):
                remaining = (emp.visa_expiry - date.today()).days
                alerts.append(
                    {
                        "employee_id": emp.id,
                        "name": emp.name_kanji,
                        "nationality": emp.nationality,
                        "visa_type": emp.visa_type,
                        "expiry": emp.visa_expiry.isoformat(),
                        "days_remaining": remaining,
                        "level": "CRITICAL" if remaining <= 30 else "WARNING",
                    }
                )

        return sorted(alerts, key=lambda x: x["days_remaining"])

    def get_statistics(self) -> dict:
        """Obtiene estadísticas del registro."""
        active = [e for e in self.employees.values() if e.status == "active"]

        by_nationality = {}
        by_employment_type = {}
        by_department = {}

        for emp in active:
            by_nationality[emp.nationality] = by_nationality.get(emp.nationality, 0) + 1
            by_employment_type[emp.employment_type] = (
                by_employment_type.get(emp.employment_type, 0) + 1
            )
            by_department[emp.department] = by_department.get(emp.department, 0) + 1

        return {
            "total": len(self.employees),
            "active": len(active),
            "inactive": len(self.employees) - len(active),
            "by_nationality": by_nationality,
            "by_employment_type": by_employment_type,
            "by_department": by_department,
            "visa_expiring_90d": len(self.get_visa_alerts(90)),
        }

    # ═══════════════════════════════════════════════════════════════
    # EXPORTACIÓN
    # ═══════════════════════════════════════════════════════════════

    def export_csv(self, output_file: str, include_sensitive: bool = False) -> str:
        """Exporta a CSV."""
        fields = [
            "id",
            "employee_code",
            "name_kanji",
            "name_kana",
            "name_romaji",
            "birth_date",
            "gender",
            "nationality",
            "visa_type",
            "visa_expiry",
            "postal_code",
            "address",
            "phone",
            "email",
            "hire_date",
            "employment_type",
            "department",
            "position",
            "hourly_rate",
            "status",
        ]

        if include_sensitive:
            fields.extend(["bank_name", "account_number", "my_number"])

        with open(output_file, "w", encoding="utf-8-sig", newline="") as f:
            writer = csv.DictWriter(f, fieldnames=fields)
            writer.writeheader()

            for emp in self.employees.values():
                row = {k: getattr(emp, k, "") for k in fields}
                # Convertir fechas
                for field in ["birth_date", "visa_expiry", "hire_date"]:
                    if row.get(field):
                        row[field] = row[field].isoformat()
                writer.writerow(row)

        self.log(f"Exportado a CSV: {output_file}")
        return output_file

    def export_json(self, output_file: str) -> str:
        """Exporta a JSON."""
        data = {
            "exported_at": datetime.now().isoformat(),
            "total": len(self.employees),
            "employees": [],
        }

        for emp in self.employees.values():
            emp_dict = asdict(emp)
            # Remover datos sensibles
            emp_dict.pop("my_number", None)
            # Convertir fechas
            for field in ["birth_date", "visa_expiry", "hire_date", "created_at", "updated_at"]:
                if emp_dict.get(field):
                    emp_dict[field] = emp_dict[field].isoformat() if emp_dict[field] else None
            data["employees"].append(emp_dict)

        with open(output_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.log(f"Exportado a JSON: {output_file}")
        return output_file


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(description="UNS 社員台帳 - Registro de Empleados")

    parser.add_argument("--data", default="shain_daicho.json", help="Archivo de datos")

    subparsers = parser.add_subparsers(dest="command")

    # List
    list_parser = subparsers.add_parser("list", help="Listar empleados")
    list_parser.add_argument("--status", help="Filtrar por estado")
    list_parser.add_argument("--nationality", help="Filtrar por nacionalidad")

    # Add
    add_parser = subparsers.add_parser("add", help="Agregar empleado")
    add_parser.add_argument("--json", required=True, help="Datos en JSON")

    # Search
    search_parser = subparsers.add_parser("search", help="Buscar empleado")
    search_parser.add_argument("query", help="Término de búsqueda")

    # Alerts
    alerts_parser = subparsers.add_parser("alerts", help="Ver alertas de visas")
    alerts_parser.add_argument("--days", type=int, default=90)

    # Stats
    subparsers.add_parser("stats", help="Ver estadísticas")

    # Export
    export_parser = subparsers.add_parser("export", help="Exportar datos")
    export_parser.add_argument("--format", choices=["csv", "json"], default="csv")
    export_parser.add_argument("--output", required=True, help="Archivo de salida")

    # Demo
    subparsers.add_parser("demo", help="Crear datos de demostración")

    args = parser.parse_args()

    manager = ShainDaichoManager(args.data)

    if args.command == "list":
        employees = manager.list_employees(
            status=args.status,
            nationality=args.nationality,
        )
        print(f"\n📋 EMPLEADOS ({len(employees)})")
        print("-" * 70)
        for emp in employees:
            visa_alert = "⚠️" if emp.is_visa_expiring_soon() else ""
            print(f"  {emp.id} | {emp.name_kanji} | {emp.nationality} | {emp.status} {visa_alert}")

    elif args.command == "search":
        results = manager.search(args.query)
        print(f"\n🔍 Resultados para '{args.query}': {len(results)}")
        for emp in results:
            print(f"  {emp.id} | {emp.name_kanji} | {emp.department}")

    elif args.command == "alerts":
        alerts = manager.get_visa_alerts(args.days)
        print(f"\n⚠️ ALERTAS DE VISA (próximos {args.days} días)")
        print("-" * 70)
        if not alerts:
            print("  ✅ No hay alertas")
        else:
            for alert in alerts:
                level = "🔴" if alert["level"] == "CRITICAL" else "🟡"
                print(f"  {level} {alert['name']} | {alert['visa_type']}")
                print(f"     Expira: {alert['expiry']} ({alert['days_remaining']} días)")

    elif args.command == "stats":
        stats = manager.get_statistics()
        print("\n📊 ESTADÍSTICAS")
        print("-" * 50)
        print(f"  Total: {stats['total']}")
        print(f"  Activos: {stats['active']}")
        print(f"  Inactivos: {stats['inactive']}")
        print(f"  Visas por expirar (90d): {stats['visa_expiring_90d']}")
        print("\n  Por nacionalidad:")
        for nat, count in stats["by_nationality"].items():
            print(f"    {nat}: {count}")

    elif args.command == "export":
        if args.format == "csv":
            manager.export_csv(args.output)
        else:
            manager.export_json(args.output)
        print(f"\n✅ Exportado a: {args.output}")

    elif args.command == "demo":
        # Crear empleados de demostración
        demo_employees = [
            Employee(
                id="EMP001",
                employee_code="E001",
                name_kanji="グエン バン アイン",
                name_kana="グエン バン アイン",
                name_romaji="NGUYEN VAN ANH",
                birth_date=date(1990, 5, 15),
                gender="男",
                nationality="ベトナム",
                visa_type="技能実習2号",
                visa_expiry=date(2027, 3, 31),
                hire_date=date(2024, 4, 1),
                employment_type="派遣社員",
                department="製造部",
                hourly_rate=1200,
                status="active",
            ),
            Employee(
                id="EMP002",
                employee_code="E002",
                name_kanji="チャン ティ ビック",
                name_kana="チャン ティ ビック",
                name_romaji="TRAN THI BICH",
                birth_date=date(1995, 8, 20),
                gender="女",
                nationality="ベトナム",
                visa_type="特定技能1号",
                visa_expiry=date(2026, 6, 30),
                hire_date=date(2023, 7, 1),
                employment_type="派遣社員",
                department="製造部",
                hourly_rate=1300,
                status="active",
            ),
        ]

        for emp in demo_employees:
            try:
                manager.add_employee(emp)
            except ValueError:
                pass  # Ya existe

        print("\n✅ Datos de demostración creados")
        print(f"   Empleados: {len(manager.employees)}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
