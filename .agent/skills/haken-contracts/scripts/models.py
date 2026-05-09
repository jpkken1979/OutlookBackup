#!/usr/bin/env python3
"""
Haken Contracts - Data Models
=============================
Modelos de datos para los documentos de 派遣契約.

Usa dataclasses (standard library) para compatibilidad sin dependencias externas.
Si Pydantic está disponible, se usa para validación adicional.
"""

from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

# Try to import pydantic for validation, fallback to dataclasses
try:
    from pydantic import BaseModel, Field

    USE_PYDANTIC = True
except ImportError:
    USE_PYDANTIC = False


class InsuranceStatus(str, Enum):
    """Estado de seguro social."""

    ENROLLED = "加入"
    NOT_ENROLLED = "未加入"
    PENDING = "手続中"


@dataclass
class WorkHours:
    """Horario de trabajo."""

    start: str = "09:00"
    end: str = "18:00"
    break_minutes: int = 60

    @property
    def scheduled_hours(self) -> float:
        """Calcula las horas programadas por día."""
        start_dt = datetime.strptime(self.start, "%H:%M")
        end_dt = datetime.strptime(self.end, "%H:%M")
        total_minutes = (end_dt - start_dt).seconds // 60
        return (total_minutes - self.break_minutes) / 60


@dataclass
class AgencyInfo:
    """
    Información de la 派遣元 (agencia de派遣).
    Ejemplo: ユニバーサル企画株式会社
    """

    name: str
    permit_number: str
    address: str
    phone: str
    representative: str
    name_kana: str = ""
    postal_code: str = ""
    fax: str = ""
    responsible_person: str = ""
    responsible_phone: str = ""
    complaint_handler: str = ""
    complaint_phone: str = ""


@dataclass
class ClientInfo:
    """Información de la 派遣先 (empresa cliente)."""

    name: str
    address: str
    supervisor: str
    name_kana: str = ""
    postal_code: str = ""
    phone: str = ""
    department: str = ""
    supervisor_position: str = ""
    supervisor_phone: str = ""
    responsible_person: str = ""
    complaint_handler: str = ""
    complaint_phone: str = ""


@dataclass
class WorkerInfo:
    """Información del 派遣労働者."""

    name: str
    name_kana: str = ""
    name_romaji: str = ""
    gender: str = ""
    birth_date: date | None = None
    nationality: str = "日本"
    address: str = ""
    phone: str = ""
    health_insurance: InsuranceStatus = InsuranceStatus.ENROLLED
    pension: InsuranceStatus = InsuranceStatus.ENROLLED
    employment_insurance: InsuranceStatus = InsuranceStatus.ENROLLED


@dataclass
class PlacementDetails:
    """Detalles de la colocación/派遣."""

    start_date: date
    end_date: date
    work_location: str
    work_description: str
    billing_rate: Decimal
    worker_wage: Decimal
    work_hours: WorkHours = field(default_factory=WorkHours)
    work_days: str = "月～金"
    billing_rate_overtime: Decimal | None = None
    billing_rate_night: Decimal | None = None
    billing_rate_holiday: Decimal | None = None
    worker_wage_overtime: Decimal | None = None
    transport_allowance: Decimal = Decimal("0")
    other_allowances: str = ""

    def __post_init__(self):
        """Calcular tarifas automáticamente si no se especifican."""
        if self.billing_rate_overtime is None:
            self.billing_rate_overtime = self.billing_rate * Decimal("1.25")
        if self.billing_rate_night is None:
            self.billing_rate_night = self.billing_rate * Decimal("1.25")
        if self.billing_rate_holiday is None:
            self.billing_rate_holiday = self.billing_rate * Decimal("1.35")
        if self.worker_wage_overtime is None:
            self.worker_wage_overtime = self.worker_wage * Decimal("1.25")


@dataclass
class KobetsuKeiyaku:
    """
    個別契約書 - Contrato Individual entre 派遣元 y 派遣先

    Este documento formaliza la relación comercial para un trabajador específico.
    """

    contract_number: str
    contract_date: date
    agency: AgencyInfo
    client: ClientInfo
    worker: WorkerInfo
    placement: PlacementDetails
    safety_health_items: str = "別紙安全衛生事項による"
    welfare_facilities: str = "派遣先の福利厚生施設の利用可"
    special_conditions: str = ""
    teishoku_bi: date | None = None


@dataclass
class RoudoushaKeiyaku:
    """
    労働者派遣契約書 / 雇用契約書 - Contrato de Empleo

    Contrato entre la 派遣元 y el 派遣労働者.
    """

    contract_number: str
    contract_date: date
    agency: AgencyInfo
    worker: WorkerInfo
    client: ClientInfo
    placement: PlacementDetails
    employment_type: str = "派遣社員"
    employment_period_type: str = "有期雇用"
    paid_leave_days: int = 0
    holidays: str = "土日祝日、年末年始"
    social_insurance_note: str = "健康保険、厚生年金、雇用保険に加入"
    resignation_notice_days: int = 14
    special_conditions: str = ""


@dataclass
class ShugyouJokenMeijisho:
    """
    就業条件明示書 - Notificación de Condiciones de Trabajo

    Debe entregarse al trabajador antes de cada派遣.
    """

    document_date: date
    worker: WorkerInfo
    agency: AgencyInfo
    client: ClientInfo
    placement: PlacementDetails
    no_26_business: bool = False
    teishoku_bi: date | None = None
    teishoku_bi_notified: bool = True


@dataclass
class HakensekiTsuuchisho:
    """
    派遣先通知書 - Notificación a la Empresa Cliente

    Información del trabajador que debe enviarse a la 派遣先.
    """

    document_date: date
    agency: AgencyInfo
    client: ClientInfo
    worker: WorkerInfo
    placement: PlacementDetails


# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN POR DEFECTO PARA ユニバーサル企画株式会社
# ═══════════════════════════════════════════════════════════════

DEFAULT_AGENCY = AgencyInfo(
    name="ユニバーサル企画株式会社",
    name_kana="ユニバーサルキカクカブシキガイシャ",
    permit_number="派13-XXXXXX",  # Reemplazar con número real
    address="東京都...",  # Reemplazar con dirección real
    postal_code="100-0001",
    phone="03-XXXX-XXXX",
    fax="03-XXXX-XXXX",
    representative="代表取締役 〇〇〇〇",
    responsible_person="派遣元責任者 〇〇〇〇",
    responsible_phone="03-XXXX-XXXX",
    complaint_handler="〇〇〇〇",
    complaint_phone="03-XXXX-XXXX",
)


def generate_contract_number(prefix: str, year: int, sequence: int) -> str:
    """Genera un número de contrato único."""
    return f"{prefix}-{year}-{sequence:04d}"
