#!/usr/bin/env python3
"""
UNS Quick Start - Generador Rápido de Reportes
==============================================
Script de demostración que genera todos los tipos de reportes.
"""

import json
import sys
from datetime import datetime
from pathlib import Path

# Agregar path del toolkit
SCRIPT_DIR = Path(__file__).parent
TOOLKIT_DIR = SCRIPT_DIR.parent
TEMPLATES_DIR = TOOLKIT_DIR / "templates"

sys.path.insert(0, str(SCRIPT_DIR))


def print_header(title: str):
    """Imprime encabezado decorativo."""
    print("\n" + "=" * 60)
    print(f"  {title}")
    print("=" * 60)


def print_step(step: int, message: str):
    """Imprime paso con formato."""
    print(f"\n  [{step}] {message}")


def main():
    print_header("UNS QUICK START - Demostración")
    print(f"\n  📅 Fecha: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print(f"  📁 Directorio: {Path.cwd()}")

    # Crear directorio de salida
    output_dir = Path("artifacts/uns-demo")
    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"  💾 Salida: {output_dir}")

    # Cargar datos de ejemplo
    sample_file = TEMPLATES_DIR / "sample_data.json"
    if not sample_file.exists():
        print(f"\n  ❌ Error: No se encontró {sample_file}")
        return

    with open(sample_file, encoding="utf-8") as f:
        data = json.load(f)

    # ─── Demo 1: Validaciones ───
    print_header("Demo 1: Validaciones de Datos Japoneses")

    from uns import JapaneseValidators

    validations = [
        ("マイナンバー", "123456789018", JapaneseValidators.validate_my_number),
        ("在留カード", "AB12345678CD", JapaneseValidators.validate_zairyu_card),
        ("電話番号", "052-938-8840", JapaneseValidators.validate_phone),
        ("郵便番号", "455-0000", JapaneseValidators.validate_postal_code),
    ]

    for name, value, validator in validations:
        valid, msg = validator(value)
        status = "✅" if valid else "❌"
        print(f"  {status} {name}: {value} → {msg}")

    # ─── Demo 2: Cálculos Fiscales ───
    print_header("Demo 2: Cálculos Fiscales 2026")

    from uns import TaxCalculator

    # Calcular impuestos para un salario típico
    monthly_salary = 250000  # ¥250,000/mes
    annual_salary = monthly_salary * 12

    print(f"\n  📊 Salario mensual: ¥{monthly_salary:,}")
    print(f"  📊 Salario anual:   ¥{annual_salary:,}")

    # Social insurance
    social = TaxCalculator.calculate_social_insurance(monthly_salary)
    print("\n  社会保険料:")
    print(f"    健康保険:   ¥{social['health_insurance']:,}")
    print(f"    厚生年金:   ¥{social['pension']:,}")
    print(f"    雇用保険:   ¥{social['employment_insurance']:,}")
    print(f"    合計:       ¥{social['total']:,}")

    # Income tax
    income_tax = TaxCalculator.calculate_income_tax(annual_salary)
    print("\n  所得税:")
    print(f"    年間:   ¥{income_tax['total_annual_tax']:,}")
    print(f"    月額:   ¥{income_tax['monthly_tax']:,}")

    # ─── Demo 3: Generación de Reportes Excel ───
    print_header("Demo 3: Generación de Reportes Excel")

    try:
        from excel_generator import ChinginReportGenerator, InvoiceGenerator

        # Generar 賃金台帳
        print_step(1, "Generando 賃金台帳...")
        chingin_gen = ChinginReportGenerator()
        chingin_path = output_dir / "賃金台帳_2026年01月.xlsx"
        result = chingin_gen.generate(data["employees"], "2026年01月", str(chingin_path))
        print(f"      ✅ {chingin_path}")

        # Generar 請求書
        print_step(2, "Generando 請求書...")
        invoice_gen = InvoiceGenerator()
        invoice_path = output_dir / "請求書_加藤木材_2026年01月.xlsx"
        result = invoice_gen.generate(
            data["invoice_sample"]["client"],
            data["invoice_sample"]["items"],
            "2026年01月",
            str(invoice_path),
        )
        print(f"      ✅ {invoice_path}")

    except ImportError as e:
        print("\n  ⚠️  openpyxl no instalado. Ejecuta: pip install openpyxl")
        print(f"      Error: {e}")

    # ─── Demo 4: Sistema de Backup ───
    print_header("Demo 4: Sistema de Backup")

    from uns import BackupSystem

    backup_sys = BackupSystem(output_dir / "backups")

    # Crear archivo de prueba
    test_file = output_dir / "test_data.json"
    with open(test_file, "w", encoding="utf-8") as f:
        json.dump({"test": "data", "timestamp": datetime.now().isoformat()}, f)

    print_step(1, f"Creando backup de {test_file.name}...")
    result = backup_sys.create_backup(str(test_file), "Demo backup")
    if "error" not in result:
        print(f"      ✅ Backup creado: {Path(result['backup']).name}")

    print_step(2, "Listando backups...")
    backups = backup_sys.list_backups()
    for b in backups:
        print(f"      📦 {b['timestamp']} - {Path(b['backup']).name}")

    # ─── Resumen ───
    print_header("Resumen")

    print(f"""
  ✅ Validaciones: 4 tipos de datos japoneses
  ✅ Cálculos: Impuestos y seguro social 2026
  ✅ Reportes: 賃金台帳, 請求書
  ✅ Backup: Sistema con versionado

  📁 Archivos generados en: {output_dir}

  Para usar el CLI completo:
    python uns.py --help
    python uns.py validate my-number 123456789018
    python uns.py tax income --annual 3000000
    python uns.py backup list
    """)


if __name__ == "__main__":
    main()
