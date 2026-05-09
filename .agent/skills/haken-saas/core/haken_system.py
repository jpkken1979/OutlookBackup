#!/usr/bin/env python3
"""
Haken SaaS - Sistema Principal
==============================
CLI y núcleo del sistema de gestión de 人材派遣.
"""

import argparse
import json
import sys
from dataclasses import asdict
from datetime import datetime, date, timedelta
from decimal import Decimal
from pathlib import Path

# Importar modelos
sys.path.insert(0, str(Path(__file__).parent))
from models import (
    Tenant,
    Client,
    ClientDepartment,
    Worker,
    JobOrder,
    Placement,
    PlacementStatus,
    AttendanceRecord,
    PayrollRecord,
    BillingRecord,
    VisaType,
    calculate_teishoku_bi,
    generate_invoice_number,
)


class HakenDatabase:
    """
    Base de datos en memoria para demostración.
    En producción: PostgreSQL con multi-tenancy RLS.
    """

    def __init__(self):
        self.tenants: dict[str, Tenant] = {}
        self.clients: dict[str, Client] = {}
        self.departments: dict[str, ClientDepartment] = {}
        self.workers: dict[str, Worker] = {}
        self.job_orders: dict[str, JobOrder] = {}
        self.placements: dict[str, Placement] = {}
        self.attendance: dict[str, AttendanceRecord] = {}
        self.payroll: dict[str, PayrollRecord] = {}
        self.billing: dict[str, BillingRecord] = {}

    def save(self, filepath: str) -> None:
        """Guarda la base de datos a JSON."""
        data = {
            "tenants": {k: asdict(v) for k, v in self.tenants.items()},
            "clients": {k: asdict(v) for k, v in self.clients.items()},
            "workers": {k: asdict(v) for k, v in self.workers.items()},
            "placements": {k: asdict(v) for k, v in self.placements.items()},
        }
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)

    def load(self, filepath: str) -> None:
        """Carga la base de datos desde JSON."""
        if Path(filepath).exists():
            with open(filepath, encoding="utf-8") as f:
                data = json.load(f)
                self._deserialize_data(data)

    def _deserialize_data(self, data: dict) -> None:
        """Deserializa los datos JSON a objetos dataclass."""
        # Deserializar tenants
        for key, tenant_data in data.get("tenants", {}).items():
            self.tenants[key] = Tenant(
                id=tenant_data.get("id", ""),
                name=tenant_data.get("name", ""),
                name_kana=tenant_data.get("name_kana", ""),
                permit_number=tenant_data.get("permit_number", ""),
                representative=tenant_data.get("representative", ""),
                address=tenant_data.get("address", ""),
                phone=tenant_data.get("phone", ""),
                email=tenant_data.get("email", ""),
                bank_name=tenant_data.get("bank_name", ""),
                bank_branch=tenant_data.get("bank_branch", ""),
                bank_account_type=tenant_data.get("bank_account_type", "普通"),
                bank_account_number=tenant_data.get("bank_account_number", ""),
                plan_type=tenant_data.get("plan_type", "standard"),
                status=tenant_data.get("status", "active"),
                created_at=tenant_data.get("created_at", ""),
            )

        # Deserializar clients
        for key, client_data in data.get("clients", {}).items():
            self.clients[key] = Client(
                id=client_data.get("id", ""),
                tenant_id=client_data.get("tenant_id", ""),
                company_name=client_data.get("company_name", ""),
                company_name_kana=client_data.get("company_name_kana", ""),
                industry=client_data.get("industry", ""),
                postal_code=client_data.get("postal_code", ""),
                address=client_data.get("address", ""),
                contact_name=client_data.get("contact_name", ""),
                contact_phone=client_data.get("contact_phone", ""),
                contact_email=client_data.get("contact_email", ""),
                billing_address=client_data.get("billing_address", ""),
                payment_terms=client_data.get("payment_terms", 30),
                default_billing_rate=Decimal(str(client_data.get("default_billing_rate", "1500"))),
                notes=client_data.get("notes", ""),
                status=client_data.get("status", "active"),
                created_at=client_data.get("created_at", ""),
            )

        # Deserializar workers
        for key, worker_data in data.get("workers", {}).items():
            # Parsear fechas
            birth_date = worker_data.get("birth_date")
            if isinstance(birth_date, str):
                birth_date = date.fromisoformat(birth_date)
            elif birth_date is None:
                birth_date = date(1990, 1, 1)

            visa_expiry = worker_data.get("visa_expiry")
            if isinstance(visa_expiry, str):
                visa_expiry = date.fromisoformat(visa_expiry)

            hire_date = worker_data.get("hire_date")
            if isinstance(hire_date, str):
                hire_date = date.fromisoformat(hire_date)

            # Parsear tipo de visa
            visa_type = worker_data.get("visa_type")
            if visa_type and isinstance(visa_type, str):
                visa_type = VisaType(visa_type)

            self.workers[key] = Worker(
                id=worker_data.get("id", ""),
                tenant_id=worker_data.get("tenant_id", ""),
                name_kanji=worker_data.get("name_kanji", ""),
                name_kana=worker_data.get("name_kana", ""),
                name_romaji=worker_data.get("name_romaji", ""),
                birth_date=birth_date,
                gender=worker_data.get("gender", ""),
                nationality=worker_data.get("nationality", "日本"),
                postal_code=worker_data.get("postal_code", ""),
                address=worker_data.get("address", ""),
                phone=worker_data.get("phone", ""),
                email=worker_data.get("email", ""),
                emergency_contact=worker_data.get("emergency_contact", ""),
                emergency_phone=worker_data.get("emergency_phone", ""),
                bank_code=worker_data.get("bank_code", ""),
                bank_name=worker_data.get("bank_name", ""),
                branch_code=worker_data.get("branch_code", ""),
                branch_name=worker_data.get("branch_name", ""),
                account_type=worker_data.get("account_type", "普通"),
                account_number=worker_data.get("account_number", ""),
                account_holder=worker_data.get("account_holder", ""),
                my_number_hash=worker_data.get("my_number_hash", ""),
                my_number_encrypted=worker_data.get("my_number_encrypted", ""),
                visa_type=visa_type,
                zairyu_card_number=worker_data.get("zairyu_card_number", ""),
                visa_expiry=visa_expiry,
                skills=worker_data.get("skills", []),
                certifications=worker_data.get("certifications", []),
                japanese_level=worker_data.get("japanese_level", ""),
                hire_date=hire_date,
                hourly_rate=Decimal(str(worker_data.get("hourly_rate", "1000"))),
                employment_type=worker_data.get("employment_type", "派遣"),
                health_insurance_number=worker_data.get("health_insurance_number", ""),
                pension_number=worker_data.get("pension_number", ""),
                employment_insurance_number=worker_data.get("employment_insurance_number", ""),
                standard_remuneration=Decimal(str(worker_data.get("standard_remuneration", "0"))),
                status=worker_data.get("status", "active"),
                created_at=worker_data.get("created_at", ""),
            )

        # Deserializar placements
        for key, placement_data in data.get("placements", {}).items():
            # Parsear fechas
            start_date = placement_data.get("start_date")
            if isinstance(start_date, str):
                start_date = date.fromisoformat(start_date)

            end_date = placement_data.get("end_date")
            if isinstance(end_date, str):
                end_date = date.fromisoformat(end_date)

            teishoku_bi = placement_data.get("teishoku_bi")
            if isinstance(teishoku_bi, str):
                teishoku_bi = date.fromisoformat(teishoku_bi)

            # Parsear status
            status = placement_data.get("status", "pending")
            if isinstance(status, str):
                status = PlacementStatus(status)

            self.placements[key] = Placement(
                id=placement_data.get("id", ""),
                tenant_id=placement_data.get("tenant_id", ""),
                worker_id=placement_data.get("worker_id", ""),
                client_id=placement_data.get("client_id", ""),
                department_id=placement_data.get("department_id", ""),
                job_order_id=placement_data.get("job_order_id", ""),
                start_date=start_date,
                end_date=end_date,
                teishoku_bi=teishoku_bi,
                worker_hourly_rate=Decimal(str(placement_data.get("worker_hourly_rate", "1000"))),
                billing_rate_base=Decimal(str(placement_data.get("billing_rate_base", "1500"))),
                billing_rate_overtime=Decimal(
                    str(placement_data.get("billing_rate_overtime", "1875"))
                ),
                billing_rate_night=Decimal(str(placement_data.get("billing_rate_night", "1875"))),
                billing_rate_holiday=Decimal(
                    str(placement_data.get("billing_rate_holiday", "2025"))
                ),
                scheduled_hours_per_day=Decimal(
                    str(placement_data.get("scheduled_hours_per_day", "8"))
                ),
                scheduled_days_per_week=placement_data.get("scheduled_days_per_week", 5),
                supervisor_name=placement_data.get("supervisor_name", ""),
                supervisor_position=placement_data.get("supervisor_position", ""),
                workplace_manager=placement_data.get("workplace_manager", ""),
                status=status,
                termination_reason=placement_data.get("termination_reason", ""),
                created_at=placement_data.get("created_at", ""),
                updated_at=placement_data.get("updated_at", ""),
            )


class HakenSystem:
    """
    Sistema principal de gestión de 人材派遣.
    """

    def __init__(self, db_path: str = "haken_db.json"):
        self.db = HakenDatabase()
        self.db_path = db_path
        self.current_tenant: Tenant | None = None
        self.artifacts_dir = Path("artifacts/haken")
        self.artifacts_dir.mkdir(parents=True, exist_ok=True)

    def log(self, message: str, level: str = "INFO") -> None:
        """Log con timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] {message}")

    # ═══════════════════════════════════════════════════════════════
    # GESTIÓN DE TENANT (Agencia)
    # ═══════════════════════════════════════════════════════════════

    def init_tenant(self, name: str, permit_number: str) -> Tenant:
        """Inicializa una nueva agencia (tenant)."""
        tenant_id = f"T{len(self.db.tenants) + 1:04d}"

        tenant = Tenant(
            id=tenant_id,
            name=name,
            name_kana="",
            permit_number=permit_number,
            representative="",
            address="",
            phone="",
            email="",
            bank_name="",
            bank_branch="",
            bank_account_type="普通",
            bank_account_number="",
        )

        self.db.tenants[tenant_id] = tenant
        self.current_tenant = tenant
        self.log(f"Tenant creado: {name} ({permit_number})")
        return tenant

    # ═══════════════════════════════════════════════════════════════
    # GESTIÓN DE CLIENTES
    # ═══════════════════════════════════════════════════════════════

    def add_client(self, data: dict) -> Client:
        """Agrega un nuevo cliente."""
        client_id = f"C{len(self.db.clients) + 1:04d}"

        client = Client(
            id=client_id,
            tenant_id=self.current_tenant.id if self.current_tenant else "",
            company_name=data.get("company_name", ""),
            company_name_kana=data.get("company_name_kana", ""),
            industry=data.get("industry", ""),
            postal_code=data.get("postal_code", ""),
            address=data.get("address", ""),
            contact_name=data.get("contact_name", ""),
            contact_phone=data.get("contact_phone", ""),
            contact_email=data.get("contact_email", ""),
            billing_address=data.get("billing_address", data.get("address", "")),
            payment_terms=data.get("payment_terms", 30),
            default_billing_rate=Decimal(str(data.get("default_billing_rate", 1500))),
        )

        self.db.clients[client_id] = client
        self.log(f"Cliente agregado: {client.company_name}")
        return client

    def list_clients(self, active_only: bool = True) -> list[Client]:
        """Lista clientes."""
        clients = list(self.db.clients.values())
        if active_only:
            clients = [c for c in clients if c.status == "active"]
        return clients

    # ═══════════════════════════════════════════════════════════════
    # GESTIÓN DE TRABAJADORES
    # ═══════════════════════════════════════════════════════════════

    def add_worker(self, data: dict) -> Worker:
        """Agrega un nuevo trabajador."""
        worker_id = f"W{len(self.db.workers) + 1:04d}"

        # Parsear fecha de nacimiento
        birth_date = data.get("birth_date")
        if isinstance(birth_date, str):
            birth_date = date.fromisoformat(birth_date)

        # Parsear visa expiry
        visa_expiry = data.get("visa_expiry")
        if isinstance(visa_expiry, str):
            visa_expiry = date.fromisoformat(visa_expiry)

        # Parsear tipo de visa
        visa_type = data.get("visa_type")
        if visa_type and isinstance(visa_type, str):
            for vt in VisaType:
                if vt.value == visa_type:
                    visa_type = vt
                    break

        worker = Worker(
            id=worker_id,
            tenant_id=self.current_tenant.id if self.current_tenant else "",
            name_kanji=data.get("name_kanji", ""),
            name_kana=data.get("name_kana", ""),
            name_romaji=data.get("name_romaji", ""),
            birth_date=birth_date or date(1990, 1, 1),
            gender=data.get("gender", ""),
            nationality=data.get("nationality", "日本"),
            postal_code=data.get("postal_code", ""),
            address=data.get("address", ""),
            phone=data.get("phone", ""),
            email=data.get("email", ""),
            emergency_contact=data.get("emergency_contact", ""),
            emergency_phone=data.get("emergency_phone", ""),
            bank_code=data.get("bank_code", ""),
            bank_name=data.get("bank_name", ""),
            branch_code=data.get("branch_code", ""),
            branch_name=data.get("branch_name", ""),
            account_type=data.get("account_type", "普通"),
            account_number=data.get("account_number", ""),
            account_holder=data.get("account_holder", ""),
            visa_type=visa_type if isinstance(visa_type, VisaType) else None,
            zairyu_card_number=data.get("zairyu_card_number", ""),
            visa_expiry=visa_expiry,
            skills=data.get("skills", []),
            certifications=data.get("certifications", []),
            japanese_level=data.get("japanese_level", ""),
            hourly_rate=Decimal(str(data.get("hourly_rate", 1000))),
        )

        # Establecer My Number si se proporciona
        if data.get("my_number"):
            worker.set_my_number(data["my_number"], "encryption_key_placeholder")

        self.db.workers[worker_id] = worker
        self.log(f"Trabajador agregado: {worker.name_kanji} ({worker_id})")
        return worker

    def search_workers(
        self, skill: str = None, available: bool = False, nationality: str = None
    ) -> list[Worker]:
        """Busca trabajadores por criterios."""
        workers = list(self.db.workers.values())

        if skill:
            workers = [w for w in workers if skill.lower() in [s.lower() for s in w.skills]]

        if nationality:
            workers = [w for w in workers if w.nationality == nationality]

        if available:
            # Filtrar los que no tienen colocación activa
            active_worker_ids = {
                p.worker_id
                for p in self.db.placements.values()
                if p.status == PlacementStatus.ACTIVE
            }
            workers = [w for w in workers if w.id not in active_worker_ids]

        return workers

    # ═══════════════════════════════════════════════════════════════
    # GESTIÓN DE COLOCACIONES
    # ═══════════════════════════════════════════════════════════════

    def create_placement(
        self,
        worker_id: str,
        client_id: str,
        start_date: date,
        end_date: date = None,
        billing_rate: Decimal = None,
    ) -> Placement:
        """Crea una nueva colocación."""
        placement_id = f"P{len(self.db.placements) + 1:04d}"

        worker = self.db.workers.get(worker_id)
        client = self.db.clients.get(client_id)

        if not worker:
            raise ValueError(f"Trabajador no encontrado: {worker_id}")
        if not client:
            raise ValueError(f"Cliente no encontrado: {client_id}")

        # Calcular fecha de fin por defecto (3 meses)
        if not end_date:
            end_date = start_date + timedelta(days=90)

        # Calcular 抵触日 (3 años desde inicio)
        teishoku_bi = calculate_teishoku_bi(start_date)

        # Tarifas
        base_rate = billing_rate or client.default_billing_rate

        placement = Placement(
            id=placement_id,
            tenant_id=self.current_tenant.id if self.current_tenant else "",
            worker_id=worker_id,
            client_id=client_id,
            department_id="",
            job_order_id="",
            start_date=start_date,
            end_date=end_date,
            teishoku_bi=teishoku_bi,
            worker_hourly_rate=worker.hourly_rate,
            billing_rate_base=base_rate,
            billing_rate_overtime=base_rate * Decimal("1.25"),
            billing_rate_night=base_rate * Decimal("1.25"),
            billing_rate_holiday=base_rate * Decimal("1.35"),
            status=PlacementStatus.PENDING if start_date > date.today() else PlacementStatus.ACTIVE,
        )

        self.db.placements[placement_id] = placement
        self.log(f"Colocación creada: {worker.name_kanji} → {client.company_name}")
        self.log(f"  抵触日: {teishoku_bi.isoformat()} ({placement.days_until_teishoku_bi()} días)")
        return placement

    def check_teishoku_alerts(self, days: int = 90) -> list[dict]:
        """Verifica colocaciones próximas a 抵触日."""
        alerts = []
        date.today()

        for placement in self.db.placements.values():
            if placement.status != PlacementStatus.ACTIVE:
                continue

            days_remaining = placement.days_until_teishoku_bi()

            if days_remaining <= days:
                worker = self.db.workers.get(placement.worker_id)
                client = self.db.clients.get(placement.client_id)

                alerts.append(
                    {
                        "placement_id": placement.id,
                        "worker": worker.name_kanji if worker else "不明",
                        "client": client.company_name if client else "不明",
                        "teishoku_bi": placement.teishoku_bi.isoformat(),
                        "days_remaining": days_remaining,
                        "alert_level": placement.get_alert_level(),
                    }
                )

        return sorted(alerts, key=lambda x: x["days_remaining"])

    # ═══════════════════════════════════════════════════════════════
    # GESTIÓN DE ASISTENCIA
    # ═══════════════════════════════════════════════════════════════

    def record_attendance(
        self,
        worker_id: str,
        work_date: date,
        clock_in: datetime,
        clock_out: datetime,
        is_holiday: bool = False,
    ) -> AttendanceRecord:
        """Registra asistencia de un trabajador."""
        record_id = f"A{len(self.db.attendance) + 1:06d}"

        # Encontrar colocación activa
        placement = None
        for p in self.db.placements.values():
            if p.worker_id == worker_id and p.status == PlacementStatus.ACTIVE:
                placement = p
                break

        if not placement:
            raise ValueError(f"No hay colocación activa para trabajador: {worker_id}")

        record = AttendanceRecord(
            id=record_id,
            tenant_id=self.current_tenant.id if self.current_tenant else "",
            worker_id=worker_id,
            placement_id=placement.id,
            work_date=work_date,
            clock_in=clock_in,
            clock_out=clock_out,
        )

        # Calcular horas
        record.calculate_hours(is_holiday)

        self.db.attendance[record_id] = record
        self.log(f"Asistencia registrada: {worker_id} - {work_date}")
        return record

    def check_36kyotei(self, month: int, year: int = None) -> list[dict]:
        """
        Verifica cumplimiento del 36協定 (límite de horas extra).
        Límites estándar: 45h/mes, 360h/año
        """
        year = year or date.today().year
        alerts = []

        # Agrupar asistencia por trabajador
        worker_hours = {}
        for record in self.db.attendance.values():
            if record.work_date.year == year and record.work_date.month == month:
                if record.worker_id not in worker_hours:
                    worker_hours[record.worker_id] = Decimal("0")
                worker_hours[record.worker_id] += record.overtime_hours

        for worker_id, overtime in worker_hours.items():
            worker = self.db.workers.get(worker_id)

            if overtime > 45:
                level = "🔴 VIOLACIÓN" if overtime > 80 else "🟠 ADVERTENCIA"
                alerts.append(
                    {
                        "worker_id": worker_id,
                        "worker_name": worker.name_kanji if worker else "不明",
                        "overtime_hours": float(overtime),
                        "limit": 45,
                        "level": level,
                        "message": f"{overtime}h de horas extra (límite: 45h)",
                    }
                )
            elif overtime > 35:
                alerts.append(
                    {
                        "worker_id": worker_id,
                        "worker_name": worker.name_kanji if worker else "不明",
                        "overtime_hours": float(overtime),
                        "limit": 45,
                        "level": "🟡 ATENCIÓN",
                        "message": f"{overtime}h de horas extra (se acerca al límite de 45h)",
                    }
                )

        return alerts

    # ═══════════════════════════════════════════════════════════════
    # CÁLCULO DE NÓMINA
    # ═══════════════════════════════════════════════════════════════

    def calculate_payroll(self, year: int, month: int) -> list[PayrollRecord]:
        """Calcula nómina mensual para todos los trabajadores."""
        payroll_records = []

        # Agrupar asistencia por trabajador
        worker_attendance = {}
        for record in self.db.attendance.values():
            if record.work_date.year == year and record.work_date.month == month:
                if record.worker_id not in worker_attendance:
                    worker_attendance[record.worker_id] = []
                worker_attendance[record.worker_id].append(record)

        for worker_id, attendance in worker_attendance.items():
            worker = self.db.workers.get(worker_id)
            if not worker:
                continue

            payroll_id = f"PAY{year}{month:02d}{worker_id}"

            payroll = PayrollRecord(
                id=payroll_id,
                tenant_id=self.current_tenant.id if self.current_tenant else "",
                worker_id=worker_id,
                period_year=year,
                period_month=month,
            )

            payroll.calculate(worker, attendance)
            self.db.payroll[payroll_id] = payroll
            payroll_records.append(payroll)

            self.log(f"Nómina calculada: {worker.name_kanji} - ¥{payroll.net_salary:,}")

        return payroll_records

    # ═══════════════════════════════════════════════════════════════
    # FACTURACIÓN
    # ═══════════════════════════════════════════════════════════════

    def generate_billing(self, client_id: str, year: int, month: int) -> BillingRecord:
        """Genera factura para un cliente."""
        client = self.db.clients.get(client_id)
        if not client:
            raise ValueError(f"Cliente no encontrado: {client_id}")

        billing_id = f"BIL{year}{month:02d}{client_id}"
        invoice_number = generate_invoice_number(
            self.current_tenant.id if self.current_tenant else "",
            year,
            month,
            len([b for b in self.db.billing.values() if b.client_id == client_id]) + 1,
        )

        billing = BillingRecord(
            id=billing_id,
            tenant_id=self.current_tenant.id if self.current_tenant else "",
            client_id=client_id,
            period_year=year,
            period_month=month,
            invoice_number=invoice_number,
        )

        # Encontrar colocaciones activas para este cliente
        for placement in self.db.placements.values():
            if placement.client_id != client_id:
                continue
            if placement.status != PlacementStatus.ACTIVE:
                continue

            worker = self.db.workers.get(placement.worker_id)
            if not worker:
                continue

            # Obtener asistencia del mes
            attendance = [
                r
                for r in self.db.attendance.values()
                if r.placement_id == placement.id
                and r.work_date.year == year
                and r.work_date.month == month
            ]

            if attendance:
                billing.add_worker_billing(worker, placement, attendance)

        billing.finalize()
        billing.due_date = date(year, month, 1) + timedelta(days=client.payment_terms + 30)

        self.db.billing[billing_id] = billing
        self.log(f"Factura generada: {client.company_name} - ¥{billing.total:,}")
        self.log(f"  粗利 (Margen bruto): ¥{billing.gross_margin:,}")

        return billing

    # ═══════════════════════════════════════════════════════════════
    # COMPLIANCE
    # ═══════════════════════════════════════════════════════════════

    def run_compliance_audit(self) -> dict:
        """Ejecuta auditoría de cumplimiento."""
        issues = []
        warnings = []

        # 1. Verificar 抵触日
        teishoku_alerts = self.check_teishoku_alerts(90)
        for alert in teishoku_alerts:
            if alert["days_remaining"] <= 30:
                issues.append(
                    {
                        "type": "teishoku_bi",
                        "severity": "critical",
                        "message": f"抵触日 en {alert['days_remaining']} días: {alert['worker']} @ {alert['client']}",
                    }
                )
            else:
                warnings.append(
                    {
                        "type": "teishoku_bi",
                        "severity": "warning",
                        "message": f"抵触日 en {alert['days_remaining']} días: {alert['worker']} @ {alert['client']}",
                    }
                )

        # 2. Verificar visas vencidas o próximas a vencer
        for worker in self.db.workers.values():
            if worker.visa_expiry:
                days = worker.get_visa_days_remaining()
                if days and days <= 0:
                    issues.append(
                        {
                            "type": "visa_expired",
                            "severity": "critical",
                            "message": f"Visa VENCIDA: {worker.name_kanji}",
                        }
                    )
                elif days and days <= 30:
                    issues.append(
                        {
                            "type": "visa_expiring",
                            "severity": "critical",
                            "message": f"Visa vence en {days} días: {worker.name_kanji}",
                        }
                    )
                elif days and days <= 90:
                    warnings.append(
                        {
                            "type": "visa_expiring",
                            "severity": "warning",
                            "message": f"Visa vence en {days} días: {worker.name_kanji}",
                        }
                    )

        # 3. Verificar 36協定
        today = date.today()
        kyotei_alerts = self.check_36kyotei(today.month, today.year)
        for alert in kyotei_alerts:
            if "VIOLACIÓN" in alert["level"]:
                issues.append(
                    {
                        "type": "36kyotei_violation",
                        "severity": "critical",
                        "message": f"Violación 36協定: {alert['worker_name']} ({alert['overtime_hours']}h)",
                    }
                )
            else:
                warnings.append(
                    {"type": "36kyotei_warning", "severity": "warning", "message": alert["message"]}
                )

        return {
            "audit_date": datetime.now().isoformat(),
            "total_issues": len(issues),
            "total_warnings": len(warnings),
            "issues": issues,
            "warnings": warnings,
            "status": "FAIL" if issues else "PASS" if not warnings else "WARNING",
        }


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════


def main():
    parser = argparse.ArgumentParser(
        description="Haken SaaS - Sistema de Gestión de 人材派遣",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", help="Comandos disponibles")

    # ─── init ───
    init_parser = subparsers.add_parser("init", help="Inicializar sistema")
    init_parser.add_argument("--company", required=True, help="Nombre de la agencia")
    init_parser.add_argument("--permit", required=True, help="Número de permiso")

    # ─── worker ───
    worker_parser = subparsers.add_parser("worker", help="Gestión de trabajadores")
    worker_sub = worker_parser.add_subparsers(dest="worker_action")

    worker_add = worker_sub.add_parser("add", help="Agregar trabajador")
    worker_add.add_argument("--data", required=True, help="Archivo JSON con datos")

    worker_search = worker_sub.add_parser("search", help="Buscar trabajadores")
    worker_search.add_argument("--skill", help="Filtrar por habilidad")
    worker_search.add_argument("--available", action="store_true", help="Solo disponibles")

    # ─── client ───
    client_parser = subparsers.add_parser("client", help="Gestión de clientes")
    client_sub = client_parser.add_subparsers(dest="client_action")

    client_add = client_sub.add_parser("add", help="Agregar cliente")
    client_add.add_argument("--data", required=True, help="Archivo JSON con datos")

    client_list = client_sub.add_parser("list", help="Listar clientes")
    client_list.add_argument("--active", action="store_true", help="Solo activos")

    # ─── placement ───
    placement_parser = subparsers.add_parser("placement", help="Gestión de colocaciones")
    placement_sub = placement_parser.add_subparsers(dest="placement_action")

    placement_create = placement_sub.add_parser("create", help="Crear colocación")
    placement_create.add_argument("--worker", required=True, help="ID del trabajador")
    placement_create.add_argument("--client", required=True, help="ID del cliente")
    placement_create.add_argument("--start", required=True, help="Fecha de inicio (YYYY-MM-DD)")

    placement_check = placement_sub.add_parser("check-teishoku", help="Verificar 抵触日")
    placement_check.add_argument("--days", type=int, default=90, help="Días de anticipación")

    # ─── payroll ───
    payroll_parser = subparsers.add_parser("payroll", help="Cálculo de nómina")
    payroll_sub = payroll_parser.add_subparsers(dest="payroll_action")

    payroll_calc = payroll_sub.add_parser("calculate", help="Calcular nómina")
    payroll_calc.add_argument("--month", required=True, help="Período (YYYY-MM)")

    # ─── billing ───
    billing_parser = subparsers.add_parser("billing", help="Facturación")
    billing_sub = billing_parser.add_subparsers(dest="billing_action")

    billing_gen = billing_sub.add_parser("generate", help="Generar factura")
    billing_gen.add_argument("--client", required=True, help="ID del cliente")
    billing_gen.add_argument("--month", required=True, help="Período (YYYY-MM)")

    # ─── compliance ───
    compliance_parser = subparsers.add_parser("compliance", help="Cumplimiento legal")
    compliance_sub = compliance_parser.add_subparsers(dest="compliance_action")

    compliance_sub.add_parser("audit", help="Auditoría completa")
    compliance_sub.add_parser("alerts", help="Ver alertas activas")

    # Parsear y ejecutar
    args = parser.parse_args()
    system = HakenSystem()

    if args.command == "init":
        tenant = system.init_tenant(args.company, args.permit)
        print("\n✅ Sistema inicializado")
        print(f"   会社名: {tenant.name}")
        print(f"   許可番号: {tenant.permit_number}")

    elif args.command == "compliance" and args.compliance_action == "audit":
        result = system.run_compliance_audit()
        print("\n📋 AUDITORÍA DE CUMPLIMIENTO")
        print("=" * 50)
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

    elif args.command == "placement" and args.placement_action == "check-teishoku":
        alerts = system.check_teishoku_alerts(args.days)
        print(f"\n📅 ALERTAS DE 抵触日 (próximos {args.days} días)")
        print("=" * 50)

        if not alerts:
            print("   ✅ No hay alertas")
        else:
            for alert in alerts:
                print(f"   {alert['alert_level']} {alert['worker']} @ {alert['client']}")
                print(f"      抵触日: {alert['teishoku_bi']} ({alert['days_remaining']} días)")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
