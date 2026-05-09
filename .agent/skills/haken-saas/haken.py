#!/usr/bin/env python3
"""
═══════════════════════════════════════════════════════════════════════════════
 HAKEN SaaS - Sistema de Gestión de 人材派遣
═══════════════════════════════════════════════════════════════════════════════
 CLI Unificado para operaciones de agencias de envío de personal en Japón.

 Módulos:
   • core      - Gestión de entidades (workers, clients, placements)
   • payroll   - Cálculo de nóminas
   • billing   - Facturación a clientes
   • documents - Generación de documentos legales
   • zengin    - Transferencias bancarias
   • egov      - Integración con e-Gov
   • attendance- API de asistencia móvil
   • compliance- Auditoría de cumplimiento

 Uso:
   python haken.py <módulo> <comando> [opciones]

 Ejemplos:
   python haken.py init --company "ユニバーサル企画" --permit "派23-303669"
   python haken.py worker add --data worker.json
   python haken.py placement create --worker W0001 --client C0001
   python haken.py compliance audit
   python haken.py zengin demo
═══════════════════════════════════════════════════════════════════════════════
"""

import argparse
import json
import os
import sys
from datetime import datetime, date
from pathlib import Path

# Agregar paths de módulos
BASE_DIR = Path(__file__).parent
sys.path.insert(0, str(BASE_DIR / "core"))
sys.path.insert(0, str(BASE_DIR / "documents"))
sys.path.insert(0, str(BASE_DIR / "integrations"))
sys.path.insert(0, str(BASE_DIR / "mobile"))


def print_banner():
    """Imprime banner del sistema."""
    banner = """
╔═══════════════════════════════════════════════════════════════════════╗
║                                                                       ║
║   ██╗  ██╗ █████╗ ██╗  ██╗███████╗███╗   ██╗                         ║
║   ██║  ██║██╔══██╗██║ ██╔╝██╔════╝████╗  ██║                         ║
║   ███████║███████║█████╔╝ █████╗  ██╔██╗ ██║                         ║
║   ██╔══██║██╔══██║██╔═██╗ ██╔══╝  ██║╚██╗██║                         ║
║   ██║  ██║██║  ██║██║  ██╗███████╗██║ ╚████║                         ║
║   ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝╚═╝  ╚═══╝                         ║
║                                                                       ║
║   人材派遣 SaaS - Sistema de Gestión Integral                         ║
║   Versión 1.0.0                                                       ║
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
    }
    icon = icons.get(level, "•")
    print(f"[{timestamp}] {icon} {message}")


# ═══════════════════════════════════════════════════════════════
# COMANDOS PRINCIPALES
# ═══════════════════════════════════════════════════════════════


def cmd_init(args):
    """Inicializa el sistema."""
    from haken_system import HakenSystem

    system = HakenSystem()
    tenant = system.init_tenant(args.company, args.permit)

    print("\n✅ Sistema inicializado correctamente")
    print(f"   会社名: {tenant.name}")
    print(f"   許可番号: {tenant.permit_number}")
    print(f"   ID: {tenant.id}")


def cmd_worker(args):
    """Gestión de trabajadores."""
    from haken_system import HakenSystem

    system = HakenSystem()

    if args.action == "add":
        with open(args.data, encoding="utf-8") as f:
            data = json.load(f)
        worker = system.add_worker(data)
        print(f"\n✅ Trabajador agregado: {worker.name_kanji} ({worker.id})")

    elif args.action == "list":
        workers = list(system.db.workers.values())
        print(f"\n📋 TRABAJADORES ({len(workers)})")
        print("-" * 60)
        for w in workers:
            print(f"  {w.id} | {w.name_kanji} | ¥{w.hourly_rate}/h | {w.nationality}")

    elif args.action == "search":
        workers = system.search_workers(
            skill=args.skill,
            available=args.available,
        )
        print(f"\n🔍 Resultados: {len(workers)} trabajadores")
        for w in workers:
            print(f"  {w.id} | {w.name_kanji} | Skills: {', '.join(w.skills)}")


def cmd_client(args):
    """Gestión de clientes."""
    from haken_system import HakenSystem

    system = HakenSystem()

    if args.action == "add":
        with open(args.data, encoding="utf-8") as f:
            data = json.load(f)
        client = system.add_client(data)
        print(f"\n✅ Cliente agregado: {client.company_name} ({client.id})")

    elif args.action == "list":
        clients = system.list_clients(active_only=not args.all)
        print(f"\n📋 CLIENTES ({len(clients)})")
        print("-" * 60)
        for c in clients:
            print(f"  {c.id} | {c.company_name} | {c.industry}")


def cmd_placement(args):
    """Gestión de colocaciones."""
    from haken_system import HakenSystem

    system = HakenSystem()

    if args.action == "create":
        start = date.fromisoformat(args.start)
        placement = system.create_placement(
            worker_id=args.worker,
            client_id=args.client,
            start_date=start,
        )
        print(f"\n✅ Colocación creada: {placement.id}")
        print(f"   抵触日: {placement.teishoku_bi} ({placement.days_until_teishoku_bi()} días)")

    elif args.action == "check-teishoku":
        alerts = system.check_teishoku_alerts(args.days)
        print(f"\n📅 ALERTAS DE 抵触日 (próximos {args.days} días)")
        print("-" * 60)

        if not alerts:
            print("  ✅ No hay alertas")
        else:
            for alert in alerts:
                print(f"  {alert['alert_level']} {alert['worker']} @ {alert['client']}")
                print(f"     抵触日: {alert['teishoku_bi']} ({alert['days_remaining']} días)")


def cmd_payroll(args):
    """Cálculo de nóminas."""
    from haken_system import HakenSystem

    system = HakenSystem()

    if args.action == "calculate":
        year, month = map(int, args.month.split("-"))
        records = system.calculate_payroll(year, month)

        print(f"\n💰 NÓMINAS {year}-{month:02d}")
        print("-" * 60)

        total = sum(r.net_salary for r in records)
        for r in records:
            worker = system.db.workers.get(r.worker_id)
            name = worker.name_kanji if worker else r.worker_id
            print(f"  {name}: ¥{r.net_salary:,}")

        print("-" * 60)
        print(f"  TOTAL: ¥{total:,}")


def cmd_billing(args):
    """Facturación."""
    from haken_system import HakenSystem

    system = HakenSystem()

    if args.action == "generate":
        year, month = map(int, args.month.split("-"))
        billing = system.generate_billing(args.client, year, month)

        print("\n📄 FACTURA GENERADA")
        print("-" * 60)
        print(f"  Número: {billing.invoice_number}")
        print(f"  小計: ¥{billing.subtotal:,}")
        print(f"  消費税: ¥{billing.tax_amount:,}")
        print(f"  合計: ¥{billing.total:,}")
        print(f"  粗利: ¥{billing.gross_margin:,}")


def cmd_compliance(args):
    """Auditoría de cumplimiento."""
    from haken_system import HakenSystem

    system = HakenSystem()

    if args.action == "audit":
        result = system.run_compliance_audit()

        print("\n📋 AUDITORÍA DE CUMPLIMIENTO")
        print("=" * 60)
        print(f"Fecha: {result['audit_date']}")
        print(f"Estado: {result['status']}")
        print(f"Issues críticos: {result['total_issues']}")
        print(f"Advertencias: {result['total_warnings']}")

        if result["issues"]:
            print("\n🔴 ISSUES CRÍTICOS:")
            for issue in result["issues"]:
                print(f"   • {issue['message']}")

        if result["warnings"]:
            print("\n🟡 ADVERTENCIAS:")
            for warning in result["warnings"]:
                print(f"   • {warning['message']}")

    elif args.action == "36kyotei":
        year, month = (
            map(int, args.month.split("-"))
            if args.month
            else (date.today().year, date.today().month)
        )
        alerts = system.check_36kyotei(month, year)

        print(f"\n📊 VERIFICACIÓN 36協定 ({year}-{month:02d})")
        print("-" * 60)

        if not alerts:
            print("  ✅ Todos los trabajadores dentro del límite")
        else:
            for alert in alerts:
                print(f"  {alert['level']} {alert['worker_name']}")
                print(f"     Horas extra: {alert['overtime_hours']}h (límite: {alert['limit']}h)")


def cmd_documents(args):
    """Generación de documentos."""
    from document_generator import DocumentGenerator

    DocumentGenerator()

    if args.action == "list":
        print("\n📄 DOCUMENTOS DISPONIBLES")
        print("-" * 60)
        docs = [
            ("派遣元管理台帳", "Registro de gestión de la agencia"),
            ("派遣先管理台帳", "Registro de gestión del cliente"),
            ("労働者派遣契約書", "Contrato de envío de trabajadores"),
            ("労働条件通知書", "Notificación de condiciones de trabajo"),
            ("就業条件明示書", "Documento de condiciones de empleo"),
            ("賃金台帳", "Registro de salarios"),
        ]
        for jp, es in docs:
            print(f"  • {jp}")
            print(f"    {es}")
            print()


def cmd_zengin(args):
    """Formato Zengin para transferencias."""
    from zengin_format import ZenginGenerator, ZenginPayment

    generator = ZenginGenerator()

    if args.action == "demo":
        demo_payments = [
            ZenginPayment(
                bank_code="0001",
                bank_name="ミズホ",
                branch_code="001",
                branch_name="ホンテン",
                account_type="普通",
                account_number="1234567",
                account_holder="グエン バン アイン",
                amount=196614,
                employee_code="EMP001",
            ),
            ZenginPayment(
                bank_code="0005",
                bank_name="ミツビシユーエフジェイ",
                branch_code="100",
                branch_name="シンジュク",
                account_type="普通",
                account_number="7654321",
                account_holder="チャン ティ ビック",
                amount=183560,
                employee_code="EMP002",
            ),
        ]

        filepath = generator.generate_file(
            company_code="1234567890",
            company_name="ユニバーサルキカク",
            bank_code="0150",
            bank_name="アイチ",
            branch_code="123",
            branch_name="トウチ",
            account_type="普通",
            account_number="2075479",
            transfer_date=date.today(),
            payments=demo_payments,
        )

        print(f"\n✅ Archivo Zengin generado: {filepath}")

    elif args.action == "validate":
        result = generator.validate_file(args.file)
        print(f"\n📋 VALIDACIÓN: {'✅ VÁLIDO' if result['valid'] else '❌ INVÁLIDO'}")

        if result["errors"]:
            for err in result["errors"]:
                print(f"  ❌ {err}")


def cmd_egov(args):
    """Integración e-Gov."""
    from egov_api import EGovClient, EGovConfig

    # EGOV_CLIENT_ID y EGOV_CLIENT_SECRET deben estar en variables de entorno
    config = EGovConfig(
        client_id=os.environ.get("EGOV_CLIENT_ID", ""),
        client_secret=os.environ.get("EGOV_CLIENT_SECRET", ""),
        environment="sandbox",
    )
    client = EGovClient(config)

    if args.action == "list":
        print("\n🏛️ TRÁMITES e-Gov DISPONIBLES")
        print("-" * 60)
        procedures = [
            ("派遣事業届出", "Notificación de negocio de派遣"),
            ("雇用保険取得届", "Alta en seguro de empleo"),
            ("雇用保険喪失届", "Baja en seguro de empleo"),
            ("健康保険・厚生年金適用届", "Alta en seguro social"),
            ("算定基礎届", "Base de cálculo anual"),
        ]
        for jp, es in procedures:
            print(f"  • {jp} - {es}")

    elif args.action == "test":
        client.authenticate()
        print("✅ Conexión sandbox exitosa")


def cmd_attendance(args):
    """API de asistencia."""
    if args.action == "serve":
        from attendance_api import run_server

        run_server(args.host, args.port)

    elif args.action == "test":
        from attendance_api import AttendanceService, AttendanceStore, GeofenceLocation

        store = AttendanceStore()
        store.add_geofence(
            GeofenceLocation(
                id="LOC001",
                name="Test Location",
                latitude=35.0853,
                longitude=136.8803,
                radius_meters=100,
            )
        )

        service = AttendanceService(store)
        result = service.clock_in_gps("W0001", "P001", 35.0853, 136.8803)

        print(json.dumps(result, indent=2, ensure_ascii=False))


def cmd_status(args):
    """Muestra estado del sistema."""
    print("\n📊 ESTADO DEL SISTEMA HAKEN SaaS")
    print("=" * 60)

    modules = [
        ("core/haken_system.py", "Sistema principal"),
        ("core/models.py", "Modelos de datos"),
        ("documents/document_generator.py", "Generador de documentos"),
        ("integrations/zengin_format.py", "Formato Zengin"),
        ("integrations/egov_api.py", "API e-Gov"),
        ("mobile/attendance_api.py", "API de asistencia"),
    ]

    for path, desc in modules:
        full_path = BASE_DIR / path
        status = "✅" if full_path.exists() else "❌"
        print(f"  {status} {desc}")
        print(f"     {path}")

    print("\n" + "=" * 60)


# ═══════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="HAKEN SaaS - Sistema de Gestión de 人材派遣",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python haken.py init --company "ユニバーサル企画" --permit "派23-303669"
  python haken.py worker add --data worker.json
  python haken.py compliance audit
  python haken.py zengin demo
  python haken.py attendance serve --port 8081
        """,
    )

    parser.add_argument("--version", action="version", version="HAKEN SaaS 1.0.0")

    subparsers = parser.add_subparsers(dest="command", help="Módulos disponibles")

    # ─── init ───
    init_parser = subparsers.add_parser("init", help="Inicializar sistema")
    init_parser.add_argument("--company", required=True, help="Nombre de la agencia")
    init_parser.add_argument("--permit", required=True, help="Número de permiso")

    # ─── worker ───
    worker_parser = subparsers.add_parser("worker", help="Gestión de trabajadores")
    worker_sub = worker_parser.add_subparsers(dest="action")

    worker_add = worker_sub.add_parser("add", help="Agregar trabajador")
    worker_add.add_argument("--data", required=True, help="Archivo JSON")

    worker_sub.add_parser("list", help="Listar trabajadores")

    worker_search = worker_sub.add_parser("search", help="Buscar trabajadores")
    worker_search.add_argument("--skill", help="Filtrar por habilidad")
    worker_search.add_argument("--available", action="store_true")

    # ─── client ───
    client_parser = subparsers.add_parser("client", help="Gestión de clientes")
    client_sub = client_parser.add_subparsers(dest="action")

    client_add = client_sub.add_parser("add", help="Agregar cliente")
    client_add.add_argument("--data", required=True, help="Archivo JSON")

    client_list = client_sub.add_parser("list", help="Listar clientes")
    client_list.add_argument("--all", action="store_true", help="Incluir inactivos")

    # ─── placement ───
    placement_parser = subparsers.add_parser("placement", help="Gestión de colocaciones")
    placement_sub = placement_parser.add_subparsers(dest="action")

    placement_create = placement_sub.add_parser("create", help="Crear colocación")
    placement_create.add_argument("--worker", required=True, help="ID trabajador")
    placement_create.add_argument("--client", required=True, help="ID cliente")
    placement_create.add_argument("--start", required=True, help="Fecha inicio (YYYY-MM-DD)")

    placement_check = placement_sub.add_parser("check-teishoku", help="Verificar 抵触日")
    placement_check.add_argument("--days", type=int, default=90, help="Días de anticipación")

    # ─── payroll ───
    payroll_parser = subparsers.add_parser("payroll", help="Cálculo de nóminas")
    payroll_sub = payroll_parser.add_subparsers(dest="action")

    payroll_calc = payroll_sub.add_parser("calculate", help="Calcular nómina")
    payroll_calc.add_argument("--month", required=True, help="Período (YYYY-MM)")

    # ─── billing ───
    billing_parser = subparsers.add_parser("billing", help="Facturación")
    billing_sub = billing_parser.add_subparsers(dest="action")

    billing_gen = billing_sub.add_parser("generate", help="Generar factura")
    billing_gen.add_argument("--client", required=True, help="ID cliente")
    billing_gen.add_argument("--month", required=True, help="Período (YYYY-MM)")

    # ─── compliance ───
    compliance_parser = subparsers.add_parser("compliance", help="Cumplimiento legal")
    compliance_sub = compliance_parser.add_subparsers(dest="action")

    compliance_sub.add_parser("audit", help="Auditoría completa")

    compliance_36k = compliance_sub.add_parser("36kyotei", help="Verificar 36協定")
    compliance_36k.add_argument("--month", help="Período (YYYY-MM)")

    # ─── documents ───
    documents_parser = subparsers.add_parser("documents", help="Documentos legales")
    documents_sub = documents_parser.add_subparsers(dest="action")
    documents_sub.add_parser("list", help="Listar documentos disponibles")

    # ─── zengin ───
    zengin_parser = subparsers.add_parser("zengin", help="Formato Zengin")
    zengin_sub = zengin_parser.add_subparsers(dest="action")

    zengin_sub.add_parser("demo", help="Generar archivo de demo")

    zengin_val = zengin_sub.add_parser("validate", help="Validar archivo")
    zengin_val.add_argument("--file", required=True, help="Archivo a validar")

    # ─── egov ───
    egov_parser = subparsers.add_parser("egov", help="Integración e-Gov")
    egov_sub = egov_parser.add_subparsers(dest="action")

    egov_sub.add_parser("list", help="Listar trámites disponibles")
    egov_sub.add_parser("test", help="Probar conexión")

    # ─── attendance ───
    attendance_parser = subparsers.add_parser("attendance", help="API de asistencia")
    attendance_sub = attendance_parser.add_subparsers(dest="action")

    attendance_serve = attendance_sub.add_parser("serve", help="Iniciar servidor")
    attendance_serve.add_argument("--host", default="0.0.0.0")
    attendance_serve.add_argument("--port", type=int, default=8081)

    attendance_sub.add_parser("test", help="Probar fichaje")

    # ─── status ───
    subparsers.add_parser("status", help="Estado del sistema")

    # Parsear y ejecutar
    args = parser.parse_args()

    if not args.command:
        print_banner()
        parser.print_help()
        return

    # Mapeo de comandos
    commands = {
        "init": cmd_init,
        "worker": cmd_worker,
        "client": cmd_client,
        "placement": cmd_placement,
        "payroll": cmd_payroll,
        "billing": cmd_billing,
        "compliance": cmd_compliance,
        "documents": cmd_documents,
        "zengin": cmd_zengin,
        "egov": cmd_egov,
        "attendance": cmd_attendance,
        "status": cmd_status,
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
