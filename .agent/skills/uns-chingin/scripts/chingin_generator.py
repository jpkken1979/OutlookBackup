#!/usr/bin/env python3
"""
UNS 賃金台帳 Generator - Chingin Skill
Sistema de generación de nóminas con cálculos fiscales japoneses.
Basado en: Chingin-v8.0-PRO1.28v, UNS-KintaiPRO
"""

import json
import argparse
from dataclasses import dataclass, field, asdict
from datetime import datetime
from decimal import Decimal, ROUND_HALF_UP
from pathlib import Path


# ===============================================
# CONFIGURACIÓN UNS
# ===============================================

UNS_CONFIG = {
    "company_name": "ユニバーサル企画株式会社",
    "permit_number": "派23-303669",
    "address": "愛知県名古屋市港区名港二丁目6-30",
    "phone": "052-938-8840",
    "bank_account": "愛知銀行 当知支店 普通2075479",
}

# 控除率 (Deduction rates) 2026
DEDUCTION_RATES = {
    "health_insurance": Decimal("0.05"),  # 健康保険 5%
    "pension": Decimal("0.0915"),  # 厚生年金 9.15%
    "employment_insurance": Decimal("0.006"),  # 雇用保険 0.6%
    "income_tax_base": Decimal("0.05"),  # 所得税基本 5%
}

# 割増率 (Premium rates)
PREMIUM_RATES = {
    "overtime": Decimal("1.25"),  # 時間外 25%増
    "late_night": Decimal("1.25"),  # 深夜 25%増
    "holiday": Decimal("1.35"),  # 休日 35%増
    "overtime_60h": Decimal("1.50"),  # 60h超過 50%増
    "late_overtime": Decimal("1.50"),  # 深夜残業 50%増
    "holiday_late": Decimal("1.60"),  # 休日深夜 60%増
}

# 所得税ブラケット (Income tax brackets)
INCOME_TAX_BRACKETS = [
    (Decimal("1950000"), Decimal("0.05")),
    (Decimal("3300000"), Decimal("0.10")),
    (Decimal("6950000"), Decimal("0.20")),
    (Decimal("9000000"), Decimal("0.23")),
    (Decimal("18000000"), Decimal("0.33")),
    (Decimal("40000000"), Decimal("0.40")),
    (Decimal("999999999"), Decimal("0.45")),
]


@dataclass
class Employee:
    """Empleado派遣社員."""

    id: str
    name: str
    name_kana: str
    hourly_rate: Decimal
    visa_type: str = "技能実習"
    bank_account: str = ""
    zairyu_card: str = ""
    my_number: str = ""


@dataclass
class WorkHours:
    """Registro de horas trabajadas."""

    regular: Decimal = Decimal("0")  # 通常時間
    overtime: Decimal = Decimal("0")  # 残業
    late_night: Decimal = Decimal("0")  # 深夜
    holiday: Decimal = Decimal("0")  # 休日
    holiday_late: Decimal = Decimal("0")  # 休日深夜
    late_overtime: Decimal = Decimal("0")  # 深夜残業

    def total(self) -> Decimal:
        return (
            self.regular
            + self.overtime
            + self.late_night
            + self.holiday
            + self.holiday_late
            + self.late_overtime
        )


@dataclass
class Deductions:
    """Deducciones del salario."""

    health_insurance: Decimal = Decimal("0")  # 健康保険
    pension: Decimal = Decimal("0")  # 厚生年金
    employment_insurance: Decimal = Decimal("0")  # 雇用保険
    income_tax: Decimal = Decimal("0")  # 所得税
    resident_tax: Decimal = Decimal("0")  # 住民税
    housing: Decimal = Decimal("0")  # 社宅控除
    other: Decimal = Decimal("0")  # その他

    def total(self) -> Decimal:
        return (
            self.health_insurance
            + self.pension
            + self.employment_insurance
            + self.income_tax
            + self.resident_tax
            + self.housing
            + self.other
        )


@dataclass
class PaySlip:
    """Recibo de nómina 給与明細."""

    employee: Employee
    period: str
    work_hours: WorkHours
    gross_pay: Decimal
    deductions: Deductions
    net_pay: Decimal
    breakdown: dict = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


class ChinginGenerator:
    """Generador de 賃金台帳."""

    def __init__(self, config: dict = None):
        self.config = config or UNS_CONFIG
        self.artifacts_dir = Path("artifacts/chingin")
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def log(self, message: str, level: str = "INFO") -> None:
        """Log con timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    def calculate_gross_pay(self, employee: Employee, hours: WorkHours) -> tuple[Decimal, dict]:
        """Calcula el salario bruto con desglose."""
        rate = employee.hourly_rate
        breakdown = {}

        # Salario regular
        breakdown["regular"] = (hours.regular * rate).quantize(Decimal("1"), ROUND_HALF_UP)

        # Horas extra (1.25x)
        breakdown["overtime"] = (hours.overtime * rate * PREMIUM_RATES["overtime"]).quantize(
            Decimal("1"), ROUND_HALF_UP
        )

        # Horas nocturnas (1.25x)
        breakdown["late_night"] = (hours.late_night * rate * PREMIUM_RATES["late_night"]).quantize(
            Decimal("1"), ROUND_HALF_UP
        )

        # Días festivos (1.35x)
        breakdown["holiday"] = (hours.holiday * rate * PREMIUM_RATES["holiday"]).quantize(
            Decimal("1"), ROUND_HALF_UP
        )

        # Festivo nocturno (1.60x)
        breakdown["holiday_late"] = (
            hours.holiday_late * rate * PREMIUM_RATES["holiday_late"]
        ).quantize(Decimal("1"), ROUND_HALF_UP)

        # Horas extra nocturnas (1.50x)
        breakdown["late_overtime"] = (
            hours.late_overtime * rate * PREMIUM_RATES["late_overtime"]
        ).quantize(Decimal("1"), ROUND_HALF_UP)

        gross = sum(breakdown.values())
        return gross, breakdown

    def calculate_deductions(
        self, gross_pay: Decimal, housing: Decimal = Decimal("0")
    ) -> Deductions:
        """Calcula las deducciones."""
        # Seguro de salud
        health = (gross_pay * DEDUCTION_RATES["health_insurance"]).quantize(
            Decimal("1"), ROUND_HALF_UP
        )

        # Pensión
        pension = (gross_pay * DEDUCTION_RATES["pension"]).quantize(Decimal("1"), ROUND_HALF_UP)

        # Seguro de empleo
        employment = (gross_pay * DEDUCTION_RATES["employment_insurance"]).quantize(
            Decimal("1"), ROUND_HALF_UP
        )

        # Base imponible (bruto - seguros sociales)
        taxable = gross_pay - health - pension - employment

        # Impuesto sobre la renta (simplificado)
        income_tax = self._calculate_income_tax(taxable)

        return Deductions(
            health_insurance=health,
            pension=pension,
            employment_insurance=employment,
            income_tax=income_tax,
            housing=housing,
        )

    def _calculate_income_tax(self, taxable_income: Decimal) -> Decimal:
        """Calcula el impuesto sobre la renta mensual."""
        # Proyección anual
        annual = taxable_income * 12

        # Encontrar bracket
        for limit, rate in INCOME_TAX_BRACKETS:
            if annual <= limit:
                annual_tax = annual * rate
                break
        else:
            annual_tax = annual * Decimal("0.45")

        # Retorno mensual
        monthly_tax = (annual_tax / 12).quantize(Decimal("1"), ROUND_HALF_UP)
        return monthly_tax

    def generate_payslip(
        self,
        employee: Employee,
        hours: WorkHours,
        period: str,
        housing_deduction: Decimal = Decimal("0"),
    ) -> PaySlip:
        """Genera un recibo de nómina completo."""
        self.log(f"Generando nómina para {employee.name} - {period}")

        # Calcular bruto
        gross, breakdown = self.calculate_gross_pay(employee, hours)

        # Calcular deducciones
        deductions = self.calculate_deductions(gross, housing_deduction)

        # Calcular neto
        net = gross - deductions.total()

        payslip = PaySlip(
            employee=employee,
            period=period,
            work_hours=hours,
            gross_pay=gross,
            deductions=deductions,
            net_pay=net,
            breakdown=breakdown,
        )

        self._save_payslip(payslip)
        return payslip

    def _save_payslip(self, payslip: PaySlip) -> None:
        """Guarda el recibo como JSON."""
        filename = f"payslip_{payslip.employee.id}_{payslip.period.replace('-', '')}.json"
        filepath = self.artifacts_dir / filename

        # Convertir a dict serializable
        data = {
            "employee": asdict(payslip.employee),
            "period": payslip.period,
            "work_hours": asdict(payslip.work_hours),
            "gross_pay": str(payslip.gross_pay),
            "deductions": asdict(payslip.deductions),
            "net_pay": str(payslip.net_pay),
            "breakdown": {k: str(v) for k, v in payslip.breakdown.items()},
            "created_at": payslip.created_at,
        }

        # Convertir Decimals a strings
        def convert_decimals(obj):
            if isinstance(obj, dict):
                return {k: convert_decimals(v) for k, v in obj.items()}
            elif isinstance(obj, Decimal):
                return str(obj)
            return obj

        data = convert_decimals(data)

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

        self.log(f"Guardado: {filepath}")

    def print_payslip(self, payslip: PaySlip) -> None:
        """Imprime el recibo en consola."""
        print("\n" + "=" * 60)
        print(f"  給与明細書 - {self.config['company_name']}")
        print(f"  派遣許可番号: {self.config['permit_number']}")
        print("=" * 60)
        print(f"\n  期間: {payslip.period}")
        print(f"  氏名: {payslip.employee.name} ({payslip.employee.name_kana})")
        print(f"  時給: ¥{payslip.employee.hourly_rate:,}")

        print("\n  【勤務時間】")
        print(f"    通常時間:   {payslip.work_hours.regular}h")
        print(f"    残業:       {payslip.work_hours.overtime}h")
        print(f"    深夜:       {payslip.work_hours.late_night}h")
        print(f"    休日:       {payslip.work_hours.holiday}h")
        print(f"    合計:       {payslip.work_hours.total()}h")

        print("\n  【支給額】")
        for key, value in payslip.breakdown.items():
            label = {
                "regular": "基本給",
                "overtime": "残業手当",
                "late_night": "深夜手当",
                "holiday": "休日手当",
                "holiday_late": "休日深夜",
                "late_overtime": "深夜残業",
            }.get(key, key)
            print(f"    {label}:     ¥{value:,}")
        print("    ────────────────")
        print(f"    総支給額:   ¥{payslip.gross_pay:,}")

        print("\n  【控除額】")
        print(f"    健康保険:   ¥{payslip.deductions.health_insurance:,}")
        print(f"    厚生年金:   ¥{payslip.deductions.pension:,}")
        print(f"    雇用保険:   ¥{payslip.deductions.employment_insurance:,}")
        print(f"    所得税:     ¥{payslip.deductions.income_tax:,}")
        if payslip.deductions.housing > 0:
            print(f"    社宅控除:   ¥{payslip.deductions.housing:,}")
        print("    ────────────────")
        print(f"    控除合計:   ¥{payslip.deductions.total():,}")

        print("\n  " + "=" * 40)
        print(f"    差引支給額: ¥{payslip.net_pay:,}")
        print("  " + "=" * 40)
        print()


def main():
    parser = argparse.ArgumentParser(description="UNS 賃金台帳 Generator")
    parser.add_argument(
        "command", choices=["calculate", "filter", "batch"], help="Comando a ejecutar"
    )
    parser.add_argument("--employee", "-e", help="Nombre del empleado")
    parser.add_argument(
        "--rate", "-r", type=int, default=1200, help="Tarifa por hora (default: 1200)"
    )
    parser.add_argument("--regular", type=float, default=160, help="Horas regulares")
    parser.add_argument("--overtime", type=float, default=0, help="Horas extra")
    parser.add_argument("--late-night", type=float, default=0, help="Horas nocturnas")
    parser.add_argument("--holiday", type=float, default=0, help="Horas festivas")
    parser.add_argument("--month", "-m", default=None, help="Período (YYYY-MM)")
    parser.add_argument("--housing", type=int, default=0, help="Deducción de vivienda")
    parser.add_argument("--folder", "-f", help="Carpeta para filtrar archivos")

    args = parser.parse_args()
    generator = ChinginGenerator()

    if args.command == "calculate":
        if not args.employee:
            print("❌ Error: Especifica --employee")
            return

        period = args.month or datetime.now().strftime("%Y-%m")

        employee = Employee(
            id="EMP001", name=args.employee, name_kana="テスト", hourly_rate=Decimal(str(args.rate))
        )

        hours = WorkHours(
            regular=Decimal(str(args.regular)),
            overtime=Decimal(str(args.overtime)),
            late_night=Decimal(str(args.late_night)),
            holiday=Decimal(str(args.holiday)),
        )

        payslip = generator.generate_payslip(
            employee=employee,
            hours=hours,
            period=period,
            housing_deduction=Decimal(str(args.housing)),
        )

        generator.print_payslip(payslip)

    elif args.command == "filter":
        if not args.folder:
            print("❌ Error: Especifica --folder")
            return

        # Filtrar archivos Excel
        patterns = ["従業員賃金計", "請負"]
        folder = Path(args.folder)

        if not folder.exists():
            print(f"❌ Error: Carpeta no existe: {folder}")
            return

        excel_files = list(folder.glob("*.xls")) + list(folder.glob("*.xlsx"))
        matched = []

        for f in excel_files:
            for pattern in patterns:
                if pattern in f.name:
                    matched.append(f)
                    break

        print(f"\n📂 Archivos filtrados en: {folder}")
        print(f"   Patrones: {', '.join(patterns)}")
        print(f"   Encontrados: {len(matched)}/{len(excel_files)}\n")

        for f in matched:
            print(f"   ✅ {f.name}")

    elif args.command == "batch":
        print("📦 Procesamiento batch - Por implementar")
        print("   Uso: python chingin_generator.py batch --folder data/ --month 2026-01")


if __name__ == "__main__":
    main()
