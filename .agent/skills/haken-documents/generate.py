#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
 HAKEN DOCUMENTS - Generador de Documentos Oficiales para 人材派遣
═══════════════════════════════════════════════════════════════════════════════
 CLI principal para generación de todos los documentos en formato A4.

 Documentos disponibles:
   • 個別契約書      (kobetsu)      - Contrato Individual
   • 在職証明書      (zaishoku)     - Certificado de Empleo
   • 退職証明書      (taishoku)     - Certificado de Retiro
   • 労働条件通知書  (roudou)       - Notificación de Condiciones
   • 就業条件明示書  (shuugyou)     - Condiciones de Empleo
   • 給与明細書      (kyuuyo)       - Recibo de Nómina
   • 源泉徴収票      (gensen)       - Retención Fiscal
   • 就労証明書      (shuuro)       - Historial Laboral (Visa)

 Uso:
   python generate.py list
   python generate.py demo
   python generate.py create --type zaishoku --data employee.json
   python generate.py batch --employee W0001
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

# Agregar paths
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / "core"))
sys.path.insert(0, str(BASE_DIR / "templates"))


def print_banner():
    """Imprime banner del sistema."""
    banner = """
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║   📄 HAKEN DOCUMENTS - 派遣書類ジェネレーター                          ║
║                                                                       ║
║   Generador de Documentos Oficiales para 人材派遣                      ║
║   Formato A4 Vertical (210mm × 297mm)                                 ║
║                                                                       ║
╚═══════════════════════════════════════════════════════════════════════╝
    """
    print(banner)


def log(message: str, level: str = "INFO") -> None:
    """Log con timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    icons = {
        "INFO": "ℹ️",
        "SUCCESS": "✅",
        "WARNING": "⚠️",
        "ERROR": "❌",
        "DOC": "📄",
    }
    icon = icons.get(level, "•")
    print(f"[{timestamp}] {icon} {message}")


# ═══════════════════════════════════════════════════════════════
# DATOS DE DEMOSTRACIÓN
# ═══════════════════════════════════════════════════════════════

DEMO_DATA = {
    "employee": {
        "id": "W0001",
        "name_kanji": "グエン バン アイン",
        "name_kana": "グエン バン アイン",
        "name_romaji": "NGUYEN VAN ANH",
        "birth_date": "1990年5月15日",
        "nationality": "ベトナム",
        "address": "愛知県豊田市若林町1-2-3 コーポ若林201",
        "postal_code": "471-0000",
        "phone": "090-1234-5678",
        "email": "nguyen@example.com",
        "zairyu_card": "AB12345678CD",
        "visa_type": "技能実習2号ロ",
        "visa_expiry": "2027年3月31日",
        "bank_name": "愛知銀行",
        "branch_name": "豊田支店",
        "account_type": "普通",
        "account_number": "1234567",
        "category": "甲欄",
    },
    "company": {
        "name": "ユニバーサル企画株式会社",
        "name_kana": "ユニバーサルキカク",
        "permit_number": "派23-303669",
        "corporate_number": "1234567890123",
        "postal_code": "471-0834",
        "address": "愛知県豊田市土橋町7-7-7",
        "phone": "0565-XX-XXXX",
        "fax": "0565-XX-XXXX",
        "email": "info@universal-kikaku.co.jp",
        "representative": "浅田 健二",
        "manager": "山田 太郎",
        "complaint_handler": "鈴木 花子",
        "complaint_phone": "0565-XX-XXXX",
    },
    "client": {
        "name": "株式会社トヨタ自動車",
        "address": "愛知県豊田市トヨタ町1",
        "postal_code": "471-8571",
        "phone": "0565-XX-XXXX",
        "industry": "自動車製造業",
        "department": "製造部",
        "manager": "加藤 一郎",
        "supervisor": "佐藤 次郎",
        "complaint_handler": "高橋 三郎",
        "complaint_phone": "0565-XX-XXXX",
        "workplace": "豊田本社工場 第3製造ライン",
    },
    "employment": {
        "start_date": "2024年4月1日",
        "end_date": "2027年3月31日",
        "teishoku_bi": "2027年4月1日",
        "position": "製造作業員",
        "title": "派遣社員",
        "job_description": "自動車部品の組立・検査作業",
        "workplace": "豊田本社工場",
        "hourly_rate": "1,200",
        "monthly_salary": "240,000",
        "monthly_estimate": "240,000",
        "start_time": "8:00",
        "end_time": "17:00",
        "break_time": "12:00～13:00",
        "break_minutes": 60,
        "work_days": "月曜日～金曜日",
        "days_per_week": 5,
        "payment_day": "15",
        "bonus": "無",
    },
    "retirement": {
        "date": "2027年3月31日",
        "reason": "契約満了",
        "detail": "派遣契約期間満了のため",
    },
    "contract": {
        "start_date": "2024年4月1日",
        "end_date": "2027年3月31日",
        "teishoku_bi": "2027年4月1日",
        "job_description": "自動車部品の組立・検査作業",
        "work_hours": "8:00～17:00",
        "break_time": "60",
        "overtime": "有（36協定の範囲内）",
        "billing_rate": "1,800",
        "overtime_rate": "2,250",
        "night_rate": "2,250",
        "holiday_rate": "2,430",
        "payment_day": "末日",
    },
    "payroll": {
        "period": {"year": 2026, "month": 1},
        "payment_date": "2026年2月15日",
        "work_days": 20,
        "absent_days": 0,
        "paid_leave": 0,
        "regular_hours": 160,
        "overtime_hours": 20,
        "night_hours": 0,
        "holiday_hours": 0,
        "late_hours": 0,
        "base_salary": 192000,
        "overtime_pay": 30000,
        "night_pay": 0,
        "holiday_pay": 0,
        "transport": 10000,
        "other_allowance": 0,
        "gross_salary": 232000,
        "health_insurance": 11600,
        "pension": 21236,
        "employment_insurance": 1392,
        "income_tax": 5120,
        "resident_tax": 8000,
        "other_deduction": 0,
        "total_deductions": 47348,
        "net_salary": 184652,
    },
    "tax_data": {
        "year": 2025,
        "gross_payment": 2880000,
        "income_after_deduction": 1920000,
        "total_deductions": 860000,
        "withheld_tax": 52800,
        "social_insurance": 380000,
        "basic_deduction": 480000,
        "spouse": "無",
        "spouse_deduction": 0,
        "dependents": 0,
        "life_insurance_deduction": 0,
        "earthquake_insurance": 0,
        "housing_loan_deduction": 0,
        "notes": "年末調整済み",
    },
}


# ═══════════════════════════════════════════════════════════════
# COMANDOS
# ═══════════════════════════════════════════════════════════════


def cmd_list(args):
    """Lista todos los documentos disponibles."""
    print("\n📋 DOCUMENTOS DISPONIBLES")
    print("=" * 70)

    documents = [
        ("kobetsu", "個別契約書", "Contrato Individual de派遣", "✓ 必須"),
        ("zaishoku", "在職証明書", "Certificado de Empleo Actual", ""),
        ("taishoku", "退職証明書", "Certificado de Retiro", "✓ 必須"),
        ("roudou", "労働条件通知書", "Notificación de Condiciones Laborales", "✓ 必須"),
        ("shuugyou", "就業条件明示書", "Condiciones de Empleo派遣", "✓ 必須"),
        ("kyuuyo", "給与明細書", "Recibo de Nómina Mensual", "✓ 必須"),
        ("gensen", "源泉徴収票", "Certificado de Retención Fiscal", "✓ 必須"),
        ("shuuro", "就労証明書", "Historial Laboral (para Visa)", ""),
    ]

    print(f"{'Código':<12} {'日本語名':<20} {'Descripción':<35} {'Obligatorio'}")
    print("-" * 70)

    for code, jp_name, desc, required in documents:
        print(f"{code:<12} {jp_name:<20} {desc:<35} {required}")

    print("\n📁 Formatos de salida: HTML (imprimible A4), JSON")
    print("📐 Tamaño: A4 Vertical (210mm × 297mm)")


def cmd_demo(args):
    """Genera todos los documentos con datos de demostración."""
    from pdf_generator import DocumentGenerator

    print("\n🎯 GENERANDO DOCUMENTOS DE DEMOSTRACIÓN")
    print("=" * 60)

    output_dir = args.output if hasattr(args, "output") and args.output else "output/demo"
    generator = DocumentGenerator(output_dir)

    # Lista de documentos a generar
    docs_to_generate = [
        ("zaishoku", generator.generate_zaishoku_shoumeisho, "在職証明書"),
        ("taishoku", generator.generate_taishoku_shoumeisho, "退職証明書"),
        ("kobetsu", generator.generate_kobetsu_keiyakusho, "個別契約書"),
        ("roudou", generator.generate_roudou_jouken_tsuuchisho, "労働条件通知書"),
        ("kyuuyo", generator.generate_kyuuyo_meisai, "給与明細書"),
        ("shuugyou", generator.generate_shuugyou_jouken_meijisho, "就業条件明示書"),
    ]

    # Generar documentos del generador principal
    for _code, func, name in docs_to_generate:
        try:
            filepath = func(DEMO_DATA)
            log(f"{name} → {filepath}", "DOC")
        except Exception as e:
            log(f"{name} → Error: {e}", "ERROR")

    # Generar 源泉徴収票
    try:
        from gensen_choushuuhyou import generate_gensen_pdf

        filepath = generate_gensen_pdf(DEMO_DATA, output_dir)
        log(f"源泉徴収票 → {filepath}", "DOC")
    except Exception as e:
        log(f"源泉徴収票 → Error: {e}", "ERROR")

    # Generar 就労証明書
    try:
        from shuuro_shoumeisho import generate_shuuro_pdf

        filepath = generate_shuuro_pdf(DEMO_DATA, output_dir)
        log(f"就労証明書 → {filepath}", "DOC")
    except Exception as e:
        log(f"就労証明書 → Error: {e}", "ERROR")

    print("\n" + "=" * 60)
    log(f"Documentos generados en: {output_dir}/", "SUCCESS")
    print("\n💡 Para ver los documentos:")
    print("   1. Abrir archivos HTML en navegador web")
    print("   2. Imprimir con 'Ctrl+P' en formato A4")
    print("   3. O guardar como PDF desde el navegador")


def cmd_create(args):
    """Crea un documento específico."""
    from pdf_generator import DocumentGenerator

    # Cargar datos
    try:
        with open(args.data, encoding="utf-8") as f:
            data = json.load(f)
    except FileNotFoundError:
        log(f"Archivo no encontrado: {args.data}", "ERROR")
        return
    except json.JSONDecodeError as e:
        log(f"Error en JSON: {e}", "ERROR")
        return

    output_dir = args.output if args.output else "output"
    generator = DocumentGenerator(output_dir)

    # Mapeo de tipos a funciones
    generators = {
        "zaishoku": generator.generate_zaishoku_shoumeisho,
        "taishoku": generator.generate_taishoku_shoumeisho,
        "kobetsu": generator.generate_kobetsu_keiyakusho,
        "roudou": generator.generate_roudou_jouken_tsuuchisho,
        "kyuuyo": generator.generate_kyuuyo_meisai,
        "shuugyou": generator.generate_shuugyou_jouken_meijisho,
    }

    # Para gensen y shuuro, importar de templates
    if args.type == "gensen":
        from gensen_choushuuhyou import generate_gensen_pdf

        filepath = generate_gensen_pdf(data, output_dir)
    elif args.type == "shuuro":
        from shuuro_shoumeisho import generate_shuuro_pdf

        filepath = generate_shuuro_pdf(data, output_dir)
    elif args.type in generators:
        filepath = generators[args.type](data)
    else:
        log(f"Tipo de documento no reconocido: {args.type}", "ERROR")
        return

    log(f"Documento generado: {filepath}", "SUCCESS")


def cmd_batch(args):
    """Genera todos los documentos para un empleado."""
    from pdf_generator import DocumentGenerator

    print(f"\n📦 GENERACIÓN BATCH para empleado: {args.employee}")
    print("=" * 60)

    # Si se proporciona archivo de datos, usarlo; sino usar demo
    if args.data:
        try:
            with open(args.data, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            log(f"Error cargando datos: {e}", "ERROR")
            return
    else:
        data = DEMO_DATA.copy()
        data["employee"]["id"] = args.employee

    output_dir = args.output if args.output else f"output/{args.employee}"
    generator = DocumentGenerator(output_dir)

    # Generar todos los documentos
    documents = [
        ("zaishoku", generator.generate_zaishoku_shoumeisho, "在職証明書"),
        ("taishoku", generator.generate_taishoku_shoumeisho, "退職証明書"),
        ("kobetsu", generator.generate_kobetsu_keiyakusho, "個別契約書"),
        ("roudou", generator.generate_roudou_jouken_tsuuchisho, "労働条件通知書"),
        ("kyuuyo", generator.generate_kyuuyo_meisai, "給与明細書"),
        ("shuugyou", generator.generate_shuugyou_jouken_meijisho, "就業条件明示書"),
    ]

    generated = 0
    for _code, func, name in documents:
        try:
            func(data)
            log(f"{name} → OK", "DOC")
            generated += 1
        except Exception as e:
            log(f"{name} → Error: {e}", "ERROR")

    # Templates adicionales
    try:
        from gensen_choushuuhyou import generate_gensen_pdf

        generate_gensen_pdf(data, output_dir)
        log("源泉徴収票 → OK", "DOC")
        generated += 1
    except Exception as e:
        log(f"源泉徴収票 → Error: {e}", "ERROR")

    try:
        from shuuro_shoumeisho import generate_shuuro_pdf

        generate_shuuro_pdf(data, output_dir)
        log("就労証明書 → OK", "DOC")
        generated += 1
    except Exception as e:
        log(f"就労証明書 → Error: {e}", "ERROR")

    print("\n" + "=" * 60)
    log(f"Total: {generated} documentos generados en {output_dir}/", "SUCCESS")


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="HAKEN DOCUMENTS - Generador de Documentos para 人材派遣",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python generate.py list
  python generate.py demo
  python generate.py create --type zaishoku --data employee.json
  python generate.py batch --employee W0001
        """,
    )

    parser.add_argument("--version", action="version", version="Haken Documents v1.0.0")

    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # list
    subparsers.add_parser("list", help="Listar documentos disponibles")

    # demo
    demo_parser = subparsers.add_parser("demo", help="Generar documentos de demostración")
    demo_parser.add_argument("--output", default="output/demo", help="Directorio de salida")

    # create
    create_parser = subparsers.add_parser("create", help="Crear documento específico")
    create_parser.add_argument(
        "--type",
        required=True,
        choices=[
            "kobetsu",
            "zaishoku",
            "taishoku",
            "roudou",
            "kyuuyo",
            "shuugyou",
            "gensen",
            "shuuro",
        ],
        help="Tipo de documento",
    )
    create_parser.add_argument("--data", required=True, help="Archivo JSON con datos")
    create_parser.add_argument("--output", default="output", help="Directorio de salida")

    # batch
    batch_parser = subparsers.add_parser(
        "batch", help="Generar todos los documentos para un empleado"
    )
    batch_parser.add_argument("--employee", required=True, help="ID del empleado")
    batch_parser.add_argument("--data", help="Archivo JSON con datos (opcional)")
    batch_parser.add_argument("--output", help="Directorio de salida")

    args = parser.parse_args()

    if not args.command:
        print_banner()
        parser.print_help()
        return

    commands = {
        "list": cmd_list,
        "demo": cmd_demo,
        "create": cmd_create,
        "batch": cmd_batch,
    }

    cmd_func = commands.get(args.command)
    if cmd_func:
        try:
            cmd_func(args)
        except Exception as e:
            log(f"Error: {e}", "ERROR")
            sys.exit(1)


if __name__ == "__main__":
    main()
