#!/usr/bin/env python3
"""
Haken SaaS - Core Data Models
=============================
Modelos de datos para el sistema de gestión de 人材派遣.
Implementa la relación tripartita: 派遣元 ↔ 派遣先 ↔ 派遣社員
"""

from dataclasses import dataclass, field
from datetime import datetime, date, timedelta
from decimal import Decimal, ROUND_HALF_UP
from enum import Enum
import hashlib


# ═══════════════════════════════════════════════════════════════
# ENUMERACIONES
# ═══════════════════════════════════════════════════════════════


class VisaType(Enum):
    """Tipos de visa para trabajadores extranjeros."""

    GINOU_JISSHU_1 = "技能実習1号"  # Trainee Level 1 (1 año)
    GINOU_JISSHU_2 = "技能実習2号"  # Trainee Level 2 (2 años)
    GINOU_JISSHU_3 = "技能実習3号"  # Trainee Level 3 (2 años)
    TOKUTEI_GINOU_1 = "特定技能1号"  # SSW Type 1 (5 años)
    TOKUTEI_GINOU_2 = "特定技能2号"  # SSW Type 2 (indefinido)
    EIJUUSHA = "永住者"  # Permanent Resident
    TEIJUUSHA = "定住者"  # Long-term Resident
    NIHONJIN_HAIGUUSHA = "日本人の配偶者等"  # Spouse of Japanese


class PlacementStatus(Enum):
    """Estados de una colocación."""

    PENDING = "pending"  # Pendiente de inicio
    ACTIVE = "active"  # En curso
    ENDING_SOON = "ending_soon"  # Próximo a terminar (30 días)
    COMPLETED = "completed"  # Finalizado
    TERMINATED = "terminated"  # Terminado anticipadamente


class AttendanceStatus(Enum):
    """Estados de registro de asistencia."""

    PRESENT = "present"  # Presente
    ABSENT = "absent"  # Ausente
    LATE = "late"  # Tardanza
    EARLY_LEAVE = "early_leave"  # Salida temprana
    HOLIDAY = "holiday"  # Festivo trabajado
    PAID_LEAVE = "paid_leave"  # 有給休暇
    SICK_LEAVE = "sick_leave"  # Enfermedad


class ClockMethod(Enum):
    """Métodos de fichaje."""

    GPS_MOBILE = "gps_mobile"
    IC_CARD = "ic_card"
    BIOMETRIC = "biometric"
    FACIAL = "facial"
    SLACK = "slack"
    LINE = "line"
    MANUAL = "manual"


# ═══════════════════════════════════════════════════════════════
# ENTIDAD: TENANT (Agencia 派遣元)
# ═══════════════════════════════════════════════════════════════


@dataclass
class Tenant:
    """
    Agencia de envío de personal (派遣元).
    Entidad raíz para multi-tenancy.
    """

    id: str
    name: str  # 会社名
    name_kana: str  # 会社名カナ
    permit_number: str  # 派遣許可番号 (ej: 派23-303669)
    representative: str  # 代表者名
    address: str  # 本社住所
    phone: str  # 電話番号
    email: str  # メールアドレス
    bank_name: str  # 銀行名
    bank_branch: str  # 支店名
    bank_account_type: str  # 口座種別 (普通/当座)
    bank_account_number: str  # 口座番号
    plan_type: str = "standard"  # Plan de suscripción
    status: str = "active"  # Estado del tenant
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "permit_number": self.permit_number,
            "status": self.status,
        }


# ═══════════════════════════════════════════════════════════════
# ENTIDAD: CLIENT (Empresa Cliente 派遣先)
# ═══════════════════════════════════════════════════════════════


@dataclass
class Client:
    """
    Empresa cliente que recibe trabajadores (派遣先).
    """

    id: str
    tenant_id: str  # FK a Tenant
    company_name: str  # 会社名
    company_name_kana: str  # 会社名カナ
    industry: str  # 業種
    postal_code: str  # 郵便番号
    address: str  # 住所
    contact_name: str  # 担当者名
    contact_phone: str  # 担当者電話
    contact_email: str  # 担当者メール
    billing_address: str  # 請求先住所
    payment_terms: int = 30  # 支払いサイト (日数)
    default_billing_rate: Decimal = Decimal("1500")  # デフォルト請求単価
    notes: str = ""
    status: str = "active"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "company_name": self.company_name,
            "industry": self.industry,
            "status": self.status,
        }


@dataclass
class ClientDepartment:
    """
    Departamento dentro de una empresa cliente.
    Importante para el límite organizacional de 抵触日.
    """

    id: str
    client_id: str  # FK a Client
    name: str  # 部署名
    location: str  # 勤務地
    supervisor_name: str  # 指揮命令者
    supervisor_phone: str  # 指揮命令者電話
    organization_teishoku_bi: date | None = None  # 組織単位の抵触日
    max_workers: int = 0  # 受入可能人数
    current_workers: int = 0  # 現在の派遣人数


# ═══════════════════════════════════════════════════════════════
# ENTIDAD: WORKER (Trabajador 派遣社員)
# ═══════════════════════════════════════════════════════════════


@dataclass
class Worker:
    """
    Trabajador enviado (派遣社員).
    Contiene datos personales, bancarios y de visa.
    """

    id: str
    tenant_id: str  # FK a Tenant

    # 基本情報 (Información básica)
    name_kanji: str  # 氏名
    name_kana: str  # 氏名カナ
    name_romaji: str  # ローマ字
    birth_date: date  # 生年月日
    gender: str  # 性別
    nationality: str  # 国籍
    postal_code: str  # 郵便番号
    address: str  # 住所
    phone: str  # 電話番号
    email: str  # メールアドレス
    emergency_contact: str  # 緊急連絡先
    emergency_phone: str  # 緊急連絡先電話

    # 銀行情報 (Información bancaria) - CIFRADO
    bank_code: str  # 銀行コード
    bank_name: str  # 銀行名
    branch_code: str  # 支店コード
    branch_name: str  # 支店名
    account_type: str  # 口座種別
    account_number: str  # 口座番号 (cifrado)
    account_holder: str  # 口座名義

    # マイナンバー - CIFRADO Y HASH
    my_number_hash: str = ""  # Hash para verificación
    my_number_encrypted: str = ""  # Cifrado para uso

    # 在留資格情報 (Para extranjeros)
    visa_type: VisaType | None = None  # 在留資格
    zairyu_card_number: str = ""  # 在留カード番号
    visa_expiry: date | None = None  # 在留期限

    # スキル情報
    skills: list[str] = field(default_factory=list)
    certifications: list[str] = field(default_factory=list)
    japanese_level: str = ""  # N1-N5 o nativo

    # 雇用情報
    hire_date: date | None = None  # 入社日
    hourly_rate: Decimal = Decimal("1000")  # 時給
    employment_type: str = "派遣"  # 雇用形態

    # 社会保険
    health_insurance_number: str = ""  # 健康保険番号
    pension_number: str = ""  # 年金番号
    employment_insurance_number: str = ""  # 雇用保険番号
    standard_remuneration: Decimal = Decimal("0")  # 標準報酬月額

    status: str = "active"
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def set_my_number(self, my_number: str, encryption_key: str) -> None:
        """Establece My Number con hash y cifrado."""
        # Hash para verificación rápida
        self.my_number_hash = hashlib.sha256(my_number.encode()).hexdigest()
        # En producción, usar cifrado real (AES-256)
        # Aquí simulamos con base64 + key
        import base64

        combined = f"{my_number}:{encryption_key}"
        self.my_number_encrypted = base64.b64encode(combined.encode()).decode()

    def get_age(self) -> int:
        """Calcula la edad actual."""
        today = date.today()
        return (
            today.year
            - self.birth_date.year
            - ((today.month, today.day) < (self.birth_date.month, self.birth_date.day))
        )

    def get_visa_days_remaining(self) -> int | None:
        """Días restantes de visa."""
        if self.visa_expiry:
            return (self.visa_expiry - date.today()).days
        return None

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "name": self.name_kanji,
            "nationality": self.nationality,
            "hourly_rate": str(self.hourly_rate),
            "status": self.status,
            "visa_days_remaining": self.get_visa_days_remaining(),
        }


# ═══════════════════════════════════════════════════════════════
# ENTIDAD: JOB ORDER (Orden de Trabajo)
# ═══════════════════════════════════════════════════════════════


@dataclass
class JobOrder:
    """
    Solicitud de personal de un cliente.
    """

    id: str
    tenant_id: str
    client_id: str  # FK a Client
    department_id: str  # FK a ClientDepartment

    title: str  # 求人タイトル
    description: str  # 業務内容
    required_skills: list[str] = field(default_factory=list)
    required_certifications: list[str] = field(default_factory=list)

    positions_needed: int = 1  # 必要人数
    positions_filled: int = 0  # 配置済人数

    work_location: str = ""  # 就業場所
    work_hours_start: str = "09:00"  # 始業時間
    work_hours_end: str = "18:00"  # 終業時間
    break_time_minutes: int = 60  # 休憩時間

    billing_rate_base: Decimal = Decimal("1500")  # 基本請求単価
    billing_rate_overtime: Decimal = Decimal("1875")  # 残業請求単価 (1.25x)
    billing_rate_night: Decimal = Decimal("1875")  # 深夜請求単価 (1.25x)
    billing_rate_holiday: Decimal = Decimal("2025")  # 休日請求単価 (1.35x)

    start_date: date | None = None  # 派遣開始希望日
    end_date: date | None = None  # 派遣終了予定日

    status: str = "open"  # open, filled, closed, cancelled
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())


# ═══════════════════════════════════════════════════════════════
# ENTIDAD: PLACEMENT (Colocación/Contrato)
# ═══════════════════════════════════════════════════════════════


@dataclass
class Placement:
    """
    Colocación de un trabajador en un cliente.
    Esta es la entidad central que vincula la relación tripartita.
    """

    id: str
    tenant_id: str
    worker_id: str  # FK a Worker
    client_id: str  # FK a Client
    department_id: str  # FK a ClientDepartment
    job_order_id: str  # FK a JobOrder

    # Fechas del contrato
    start_date: date  # 派遣開始日
    end_date: date  # 派遣終了予定日
    teishoku_bi: date  # 抵触日 (fecha límite legal)

    # Tarifas específicas de esta colocación
    worker_hourly_rate: Decimal  # 時給 (trabajador)
    billing_rate_base: Decimal  # 請求単価 (cliente)
    billing_rate_overtime: Decimal
    billing_rate_night: Decimal
    billing_rate_holiday: Decimal

    # Horario
    scheduled_hours_per_day: Decimal = Decimal("8")
    scheduled_days_per_week: int = 5

    # 指揮命令者情報
    supervisor_name: str = ""  # 指揮命令者
    supervisor_position: str = ""  # 役職
    workplace_manager: str = ""  # 派遣先責任者

    # Estado
    status: PlacementStatus = PlacementStatus.PENDING
    termination_reason: str = ""  # Razón de terminación (si aplica)

    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    updated_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def days_until_teishoku_bi(self) -> int:
        """Días restantes hasta 抵触日."""
        return (self.teishoku_bi - date.today()).days

    def get_alert_level(self) -> str:
        """Nivel de alerta basado en proximidad a 抵触日."""
        days = self.days_until_teishoku_bi()
        if days <= 30:
            return "🔴 URGENTE"
        elif days <= 60:
            return "🟠 ADVERTENCIA"
        elif days <= 90:
            return "🟡 ATENCIÓN"
        return "🟢 OK"

    def calculate_margin(self, hours: Decimal, hour_type: str = "base") -> Decimal:
        """Calcula el margen (粗利) para un tipo de hora."""
        rate_map = {
            "base": self.billing_rate_base,
            "overtime": self.billing_rate_overtime,
            "night": self.billing_rate_night,
            "holiday": self.billing_rate_holiday,
        }
        billing = hours * rate_map.get(hour_type, self.billing_rate_base)

        # Factor de multiplicador para el trabajador
        multiplier = {
            "base": Decimal("1.00"),
            "overtime": Decimal("1.25"),
            "night": Decimal("1.25"),
            "holiday": Decimal("1.35"),
        }
        wage = hours * self.worker_hourly_rate * multiplier.get(hour_type, Decimal("1.00"))

        return billing - wage

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "worker_id": self.worker_id,
            "client_id": self.client_id,
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "teishoku_bi": self.teishoku_bi.isoformat(),
            "days_until_teishoku_bi": self.days_until_teishoku_bi(),
            "alert_level": self.get_alert_level(),
            "status": self.status.value,
        }


# ═══════════════════════════════════════════════════════════════
# ENTIDAD: ATTENDANCE (Asistencia)
# ═══════════════════════════════════════════════════════════════


@dataclass
class AttendanceRecord:
    """
    Registro diario de asistencia.
    """

    id: str
    tenant_id: str
    worker_id: str  # FK a Worker
    placement_id: str  # FK a Placement
    work_date: date  # 勤務日

    # Fichaje
    clock_in: datetime | None = None  # 出勤時刻
    clock_out: datetime | None = None  # 退勤時刻
    clock_method: ClockMethod = ClockMethod.MANUAL

    # Ubicación (para GPS)
    clock_in_lat: float | None = None
    clock_in_lng: float | None = None
    clock_out_lat: float | None = None
    clock_out_lng: float | None = None

    # Horas calculadas
    break_minutes: int = 60  # 休憩時間
    regular_hours: Decimal = Decimal("0")  # 通常時間
    overtime_hours: Decimal = Decimal("0")  # 残業時間
    night_hours: Decimal = Decimal("0")  # 深夜時間
    holiday_hours: Decimal = Decimal("0")  # 休日時間

    # Estado
    status: AttendanceStatus = AttendanceStatus.PRESENT
    approved: bool = False  # 承認済み
    approved_by: str = ""  # 承認者
    approved_at: datetime | None = None

    notes: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())

    def calculate_hours(self, is_holiday: bool = False) -> None:
        """
        Calcula las horas trabajadas según reglas japonesas.
        """
        if not self.clock_in or not self.clock_out:
            return

        # Tiempo total trabajado
        total_minutes = (self.clock_out - self.clock_in).seconds // 60
        total_minutes -= self.break_minutes
        total_hours = Decimal(str(total_minutes / 60))

        if is_holiday:
            # Todo el tiempo es 休日
            self.holiday_hours = total_hours
            return

        # Horas regulares (hasta 8h)
        self.regular_hours = min(total_hours, Decimal("8"))
        remaining = total_hours - self.regular_hours

        # Horas extra (más de 8h)
        if remaining > 0:
            self.overtime_hours = remaining

        # Horas nocturnas (22:00 - 05:00)
        night_start = self.clock_in.replace(hour=22, minute=0, second=0)
        night_end = self.clock_in.replace(hour=5, minute=0, second=0) + timedelta(days=1)

        if self.clock_out > night_start:
            night_minutes = min(
                (self.clock_out - night_start).seconds // 60,
                (night_end - night_start).seconds // 60,
            )
            self.night_hours = Decimal(str(night_minutes / 60))

    def total_hours(self) -> Decimal:
        """Total de horas trabajadas."""
        return self.regular_hours + self.overtime_hours + self.night_hours + self.holiday_hours


# ═══════════════════════════════════════════════════════════════
# ENTIDAD: PAYROLL (Nómina)
# ═══════════════════════════════════════════════════════════════


@dataclass
class PayrollRecord:
    """
    Registro de nómina mensual.
    """

    id: str
    tenant_id: str
    worker_id: str  # FK a Worker
    period_year: int  # 年
    period_month: int  # 月

    # Horas trabajadas
    regular_hours: Decimal = Decimal("0")
    overtime_hours: Decimal = Decimal("0")
    night_hours: Decimal = Decimal("0")
    holiday_hours: Decimal = Decimal("0")

    # Salario bruto
    base_salary: Decimal = Decimal("0")  # 基本給
    overtime_pay: Decimal = Decimal("0")  # 残業手当
    night_pay: Decimal = Decimal("0")  # 深夜手当
    holiday_pay: Decimal = Decimal("0")  # 休日手当
    transport_allowance: Decimal = Decimal("0")  # 通勤手当
    other_allowances: Decimal = Decimal("0")  # その他手当
    gross_salary: Decimal = Decimal("0")  # 総支給額

    # Deducciones
    health_insurance: Decimal = Decimal("0")  # 健康保険
    pension: Decimal = Decimal("0")  # 厚生年金
    employment_insurance: Decimal = Decimal("0")  # 雇用保険
    income_tax: Decimal = Decimal("0")  # 所得税
    resident_tax: Decimal = Decimal("0")  # 住民税
    other_deductions: Decimal = Decimal("0")  # その他控除
    total_deductions: Decimal = Decimal("0")  # 控除合計

    # Neto
    net_salary: Decimal = Decimal("0")  # 差引支給額

    # Estado
    calculated_at: str = ""
    approved: bool = False
    paid: bool = False
    paid_at: datetime | None = None

    def calculate(self, worker: Worker, attendance_records: list[AttendanceRecord]) -> None:
        """
        Calcula la nómina basada en los registros de asistencia.
        """
        # Agregar horas
        for record in attendance_records:
            self.regular_hours += record.regular_hours
            self.overtime_hours += record.overtime_hours
            self.night_hours += record.night_hours
            self.holiday_hours += record.holiday_hours

        rate = worker.hourly_rate

        # Calcular salarios
        self.base_salary = (self.regular_hours * rate).quantize(Decimal("1"), ROUND_HALF_UP)
        self.overtime_pay = (self.overtime_hours * rate * Decimal("1.25")).quantize(
            Decimal("1"), ROUND_HALF_UP
        )
        self.night_pay = (self.night_hours * rate * Decimal("1.25")).quantize(
            Decimal("1"), ROUND_HALF_UP
        )
        self.holiday_pay = (self.holiday_hours * rate * Decimal("1.35")).quantize(
            Decimal("1"), ROUND_HALF_UP
        )

        self.gross_salary = (
            self.base_salary
            + self.overtime_pay
            + self.night_pay
            + self.holiday_pay
            + self.transport_allowance
            + self.other_allowances
        )

        # Calcular deducciones (tasas 2026)
        self.health_insurance = (self.gross_salary * Decimal("0.05")).quantize(
            Decimal("1"), ROUND_HALF_UP
        )
        self.pension = (self.gross_salary * Decimal("0.0915")).quantize(Decimal("1"), ROUND_HALF_UP)
        self.employment_insurance = (self.gross_salary * Decimal("0.006")).quantize(
            Decimal("1"), ROUND_HALF_UP
        )

        # Impuesto sobre la renta (simplificado)
        taxable = (
            self.gross_salary - self.health_insurance - self.pension - self.employment_insurance
        )
        self.income_tax = (taxable * Decimal("0.05")).quantize(Decimal("1"), ROUND_HALF_UP)

        self.total_deductions = (
            self.health_insurance
            + self.pension
            + self.employment_insurance
            + self.income_tax
            + self.resident_tax
            + self.other_deductions
        )

        self.net_salary = self.gross_salary - self.total_deductions
        self.calculated_at = datetime.now().isoformat()


# ═══════════════════════════════════════════════════════════════
# ENTIDAD: BILLING (Facturación)
# ═══════════════════════════════════════════════════════════════


@dataclass
class BillingRecord:
    """
    Registro de facturación al cliente.
    """

    id: str
    tenant_id: str
    client_id: str  # FK a Client
    period_year: int
    period_month: int
    invoice_number: str  # 請求書番号

    # Desglose por trabajador
    line_items: list[dict] = field(default_factory=list)

    # Totales
    subtotal: Decimal = Decimal("0")  # 小計
    tax_rate: Decimal = Decimal("0.10")  # 消費税率
    tax_amount: Decimal = Decimal("0")  # 消費税額
    total: Decimal = Decimal("0")  # 合計

    # Margen
    total_wages: Decimal = Decimal("0")  # 給与総額
    gross_margin: Decimal = Decimal("0")  # 粗利

    # Estado
    issued_at: datetime | None = None
    due_date: date | None = None
    paid: bool = False
    paid_at: datetime | None = None

    def add_worker_billing(
        self, worker: Worker, placement: Placement, attendance: list[AttendanceRecord]
    ) -> None:
        """Agrega la facturación de un trabajador."""
        hours = {
            "regular": Decimal("0"),
            "overtime": Decimal("0"),
            "night": Decimal("0"),
            "holiday": Decimal("0"),
        }

        for record in attendance:
            hours["regular"] += record.regular_hours
            hours["overtime"] += record.overtime_hours
            hours["night"] += record.night_hours
            hours["holiday"] += record.holiday_hours

        # Calcular facturación
        billing = {
            "regular": hours["regular"] * placement.billing_rate_base,
            "overtime": hours["overtime"] * placement.billing_rate_overtime,
            "night": hours["night"] * placement.billing_rate_night,
            "holiday": hours["holiday"] * placement.billing_rate_holiday,
        }

        worker_subtotal = sum(billing.values())

        # Calcular salario del trabajador (para margen)
        wage = (
            hours["regular"] * placement.worker_hourly_rate
            + hours["overtime"] * placement.worker_hourly_rate * Decimal("1.25")
            + hours["night"] * placement.worker_hourly_rate * Decimal("1.25")
            + hours["holiday"] * placement.worker_hourly_rate * Decimal("1.35")
        )

        line_item = {
            "worker_id": worker.id,
            "worker_name": worker.name_kanji,
            "hours": {k: str(v) for k, v in hours.items()},
            "billing": {k: str(v) for k, v in billing.items()},
            "subtotal": str(worker_subtotal),
            "wage": str(wage),
            "margin": str(worker_subtotal - wage),
        }

        self.line_items.append(line_item)
        self.subtotal += worker_subtotal
        self.total_wages += wage

    def finalize(self) -> None:
        """Finaliza el cálculo de la factura."""
        self.tax_amount = (self.subtotal * self.tax_rate).quantize(Decimal("1"), ROUND_HALF_UP)
        self.total = self.subtotal + self.tax_amount
        self.gross_margin = self.subtotal - self.total_wages
        self.issued_at = datetime.now()


# ═══════════════════════════════════════════════════════════════
# FUNCIONES DE UTILIDAD
# ═══════════════════════════════════════════════════════════════


def calculate_teishoku_bi(start_date: date, limit_years: int = 3) -> date:
    """
    Calcula la fecha de 抵触日 (límite de 3 años).
    """
    return start_date + timedelta(days=limit_years * 365)


def generate_invoice_number(tenant_id: str, year: int, month: int, sequence: int) -> str:
    """
    Genera número de factura único.
    Formato: INV-YYYYMM-XXXX
    """
    return f"INV-{year}{month:02d}-{sequence:04d}"


def _get_nth_monday(year: int, month: int, n: int) -> date:
    """
    Obtiene el n-ésimo lunes de un mes dado.
    Usado para los festivos del Happy Monday System.
    """
    first_day = date(year, month, 1)
    # Encontrar el primer lunes (weekday 0 = Monday)
    days_until_monday = (7 - first_day.weekday()) % 7
    first_monday = first_day + timedelta(days=days_until_monday)
    return first_monday + timedelta(weeks=n - 1)


def _calculate_vernal_equinox(year: int) -> int:
    """
    Calcula el día de 春分の日 (Equinoccio de Primavera).
    Basado en la fórmula oficial de Japón.
    """
    if year >= 1980 and year <= 2099:
        return int(20.8431 + 0.242194 * (year - 1980) - int((year - 1980) / 4))
    elif year >= 2100 and year <= 2150:
        return int(21.8510 + 0.242194 * (year - 1980) - int((year - 1980) / 4))
    return 21  # Default


def _calculate_autumnal_equinox(year: int) -> int:
    """
    Calcula el día de 秋分の日 (Equinoccio de Otoño).
    Basado en la fórmula oficial de Japón.
    """
    if year >= 1980 and year <= 2099:
        return int(23.2488 + 0.242194 * (year - 1980) - int((year - 1980) / 4))
    elif year >= 2100 and year <= 2150:
        return int(24.2488 + 0.242194 * (year - 1980) - int((year - 1980) / 4))
    return 23  # Default


def get_japanese_holidays(year: int) -> dict[date, str]:
    """
    Genera todos los festivos japoneses para un año dado.
    Retorna un diccionario con fecha -> nombre del festivo.

    Incluye:
    - Festivos fijos (固定祝日)
    - Happy Monday System (ハッピーマンデー)
    - Equinoccios (春分の日、秋分の日)
    - Festivos sustitutos (振替休日)
    - Días del ciudadano (国民の休日)
    """
    holidays: dict[date, str] = {}

    # ═══════════════════════════════════════════════════════════════
    # FESTIVOS FIJOS (固定祝日)
    # ═══════════════════════════════════════════════════════════════

    # 元日 (Año Nuevo) - January 1
    holidays[date(year, 1, 1)] = "元日"

    # 建国記念の日 (Día de la Fundación Nacional) - February 11
    holidays[date(year, 2, 11)] = "建国記念の日"

    # 天皇誕生日 (Cumpleaños del Emperador) - February 23 (desde 2020)
    if year >= 2020:
        holidays[date(year, 2, 23)] = "天皇誕生日"

    # 昭和の日 (Día de Showa) - April 29
    holidays[date(year, 4, 29)] = "昭和の日"

    # 憲法記念日 (Día de la Constitución) - May 3
    holidays[date(year, 5, 3)] = "憲法記念日"

    # みどりの日 (Día del Verdor) - May 4
    holidays[date(year, 5, 4)] = "みどりの日"

    # こどもの日 (Día del Niño) - May 5
    holidays[date(year, 5, 5)] = "こどもの日"

    # 山の日 (Día de la Montaña) - August 11 (desde 2016)
    if year >= 2016:
        holidays[date(year, 8, 11)] = "山の日"

    # 文化の日 (Día de la Cultura) - November 3
    holidays[date(year, 11, 3)] = "文化の日"

    # 勤労感謝の日 (Día de Acción de Gracias al Trabajo) - November 23
    holidays[date(year, 11, 23)] = "勤労感謝の日"

    # ═══════════════════════════════════════════════════════════════
    # HAPPY MONDAY SYSTEM (ハッピーマンデー)
    # ═══════════════════════════════════════════════════════════════

    # 成人の日 (Día de la Mayoría de Edad) - 2do lunes de enero
    holidays[_get_nth_monday(year, 1, 2)] = "成人の日"

    # 海の日 (Día del Mar) - 3er lunes de julio
    holidays[_get_nth_monday(year, 7, 3)] = "海の日"

    # 敬老の日 (Día del Respeto a los Mayores) - 3er lunes de septiembre
    holidays[_get_nth_monday(year, 9, 3)] = "敬老の日"

    # スポーツの日 (Día del Deporte) - 2do lunes de octubre
    holidays[_get_nth_monday(year, 10, 2)] = "スポーツの日"

    # ═══════════════════════════════════════════════════════════════
    # EQUINOCCIOS (計算による祝日)
    # ═══════════════════════════════════════════════════════════════

    # 春分の日 (Equinoccio de Primavera) - Alrededor del 20-21 de marzo
    vernal_day = _calculate_vernal_equinox(year)
    holidays[date(year, 3, vernal_day)] = "春分の日"

    # 秋分の日 (Equinoccio de Otoño) - Alrededor del 22-23 de septiembre
    autumnal_day = _calculate_autumnal_equinox(year)
    holidays[date(year, 9, autumnal_day)] = "秋分の日"

    # ═══════════════════════════════════════════════════════════════
    # FESTIVOS SUSTITUTOS (振替休日)
    # Si un festivo cae en domingo, el siguiente día hábil es festivo
    # ═══════════════════════════════════════════════════════════════

    substitute_holidays: dict[date, str] = {}
    for holiday_date, holiday_name in holidays.items():
        if holiday_date.weekday() == 6:  # Sunday
            # Buscar el siguiente día que no sea festivo
            substitute = holiday_date + timedelta(days=1)
            while substitute in holidays or substitute in substitute_holidays:
                substitute += timedelta(days=1)
            substitute_holidays[substitute] = f"振替休日 ({holiday_name})"

    holidays.update(substitute_holidays)

    # ═══════════════════════════════════════════════════════════════
    # DÍA DEL CIUDADANO (国民の休日)
    # Si un día hábil queda entre dos festivos, es festivo
    # ═══════════════════════════════════════════════════════════════

    # Verificar específicamente septiembre (敬老の日 y 秋分の日 pueden crear esto)
    keiro_no_hi = _get_nth_monday(year, 9, 3)  # 敬老の日
    shubun_no_hi = date(year, 9, autumnal_day)  # 秋分の日

    # Si hay exactamente un día entre ellos
    if (shubun_no_hi - keiro_no_hi).days == 2:
        between_date = keiro_no_hi + timedelta(days=1)
        if between_date not in holidays:
            holidays[between_date] = "国民の休日"

    return holidays


def is_japanese_holiday(check_date: date) -> bool:
    """
    Verifica si es un día festivo japonés (国民の祝日).

    Implementación completa que incluye:
    - 16 festivos nacionales fijos y móviles
    - Happy Monday System (ハッピーマンデー)
    - Equinoccios calculados (春分の日、秋分の日)
    - Festivos sustitutos (振替休日)
    - Días del ciudadano (国民の休日)

    Args:
        check_date: Fecha a verificar

    Returns:
        True si es festivo japonés, False en caso contrario
    """
    holidays = get_japanese_holidays(check_date.year)
    return check_date in holidays


def get_japanese_holiday_name(check_date: date) -> str | None:
    """
    Obtiene el nombre del festivo japonés para una fecha dada.

    Args:
        check_date: Fecha a verificar

    Returns:
        Nombre del festivo en japonés, o None si no es festivo
    """
    holidays = get_japanese_holidays(check_date.year)
    return holidays.get(check_date)
