#!/usr/bin/env python3
"""
UNS Adapter para Haken Documents
================================
Adapta el generador de documentos para usar datos reales de
ユニバーサル企画株式会社.

Este archivo conecta el sistema de documentos con la configuración
central de UNS.
"""

import sys
from pathlib import Path
from typing import Any

# Agregar path para importar configuración
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent))

try:
    from config.UNS_CONFIG import (
        UNS_COMPANY,
        UNS_CLIENTS,
        UNS_PAYROLL,
        UNS_LEGAL,
        UNS_PATHS,
        get_all_factories,
        calculate_teishokubi,
    )

    HAS_UNS_CONFIG = True
except ImportError:
    HAS_UNS_CONFIG = False
    print("⚠️ UNS_CONFIG no disponible, usando datos de ejemplo")


# =============================================================================
# DATOS DE EMPRESA PARA DOCUMENTOS
# =============================================================================


def get_company_data() -> dict[str, Any]:
    """
    Obtiene datos de ユニバーサル企画株式会社 para documentos oficiales.
    """
    if HAS_UNS_CONFIG:
        return {
            "name": UNS_COMPANY.name_kanji,
            "name_short": UNS_COMPANY.name_short,
            "postal_code": UNS_COMPANY.postal_code,
            "address": UNS_COMPANY.full_address,
            "phone": UNS_COMPANY.phone,
            "fax": UNS_COMPANY.fax,
            "representative": UNS_COMPANY.representative.replace("代表取締役 ", ""),
            "permit_number": UNS_COMPANY.dispatch_license,
            "bank": {
                "name": UNS_COMPANY.bank_name,
                "branch": UNS_COMPANY.bank_branch,
                "account_type": UNS_COMPANY.bank_account_type,
                "account_number": UNS_COMPANY.bank_account_number,
                "holder": UNS_COMPANY.bank_account_holder,
            },
            "complaint_handler": UNS_COMPANY.complaint_handler,
            "complaint_department": UNS_COMPANY.complaint_handler_dept,
        }
    else:
        # Datos de fallback
        return {
            "name": "ユニバーサル企画株式会社",
            "name_short": "UNS",
            "postal_code": "455-0884",
            "address": "愛知県名古屋市港区七反野1-2201",
            "phone": "052-938-8840",
            "fax": "052-938-8841",
            "representative": "ブウ ティ サウ",
            "permit_number": "派23-301XXX",
            "bank": {
                "name": "愛知銀行",
                "branch": "当知支店",
                "account_type": "普通",
                "account_number": "2075479",
                "holder": "ユニバーサル企画（株）",
            },
            "complaint_handler": "中山 欣英",
            "complaint_department": "営業部",
        }


def get_client_data(client_name: str) -> dict[str, Any] | None:
    """
    Obtiene datos de un cliente派遣先.

    Args:
        client_name: Nombre del cliente (ej: "高雄工業株式会社")

    Returns:
        Dict con datos del cliente o None si no existe
    """
    if HAS_UNS_CONFIG and client_name in UNS_CLIENTS:
        client = UNS_CLIENTS[client_name]
        return {
            "name": client_name,
            "code": client.get("code"),
            "address": client.get("address", ""),
            "phone": client.get("phone", ""),
            "responsible_person": client.get("responsible_person", ""),
            "complaint_handler": client.get("complaint_handler", ""),
            "plants": client.get("plants", []),
            "hourly_rates": client.get("hourly_rates", {}),
        }
    return None


def get_all_clients() -> dict[str, dict]:
    """Obtiene todos los clientes派遣先."""
    if HAS_UNS_CONFIG:
        return UNS_CLIENTS
    return {}


def list_all_factories() -> list:
    """Lista todas las fábricas disponibles."""
    if HAS_UNS_CONFIG:
        return get_all_factories()
    return []


# =============================================================================
# GENERADOR DE DOCUMENTOS CON DATOS UNS
# =============================================================================


class UNSDocumentHelper:
    """
    Helper para generar documentos con datos reales de UNS.
    """

    def __init__(self):
        self.company = get_company_data()

    def prepare_zaishoku_data(
        self,
        employee_name: str,
        employee_kana: str,
        birth_date: str,
        address: str,
        start_date: str,
        position: str,
        workplace: str,
        monthly_salary: int,
    ) -> dict[str, Any]:
        """
        Prepara datos para 在職証明書.
        """
        return {
            "employee": {
                "name_kanji": employee_name,
                "name_kana": employee_kana,
                "birth_date": birth_date,
                "address": address,
            },
            "employment": {
                "start_date": start_date,
                "position": position,
                "workplace": workplace,
                "monthly_salary": f"{monthly_salary:,}",
            },
            "company": self.company,
        }

    def prepare_taishoku_data(
        self,
        employee_name: str,
        employee_kana: str,
        birth_date: str,
        address: str,
        start_date: str,
        end_date: str,
        position: str,
        workplace: str,
        reason: str = "自己都合",
    ) -> dict[str, Any]:
        """
        Prepara datos para 退職証明書.
        """
        return {
            "employee": {
                "name_kanji": employee_name,
                "name_kana": employee_kana,
                "birth_date": birth_date,
                "address": address,
            },
            "employment": {
                "start_date": start_date,
                "end_date": end_date,
                "position": position,
                "workplace": workplace,
                "reason": reason,
            },
            "company": self.company,
        }

    def prepare_kobetsu_keiyaku_data(
        self,
        employee_name: str,
        client_name: str,
        plant_name: str,
        job_description: str,
        hourly_rate: int,
        start_date: str,
        end_date: str,
        work_hours: str = "8:00～17:00",
        break_time: str = "12:00～13:00（60分）",
    ) -> dict[str, Any]:
        """
        Prepara datos para 個別契約書.
        """
        # Obtener datos del cliente
        client_data = get_client_data(client_name)
        if not client_data:
            client_data = {"name": client_name, "address": "", "phone": ""}

        # Calcular抵触日 (3 años después del inicio)
        from datetime import datetime

        try:
            start = datetime.strptime(start_date, "%Y-%m-%d").date()
            teishokubi = calculate_teishokubi(start) if HAS_UNS_CONFIG else None
        except Exception:
            teishokubi = None

        return {
            "worker": {
                "name": employee_name,
            },
            "client": {
                "name": client_name,
                "address": client_data.get("address", ""),
                "phone": client_data.get("phone", ""),
                "plant": plant_name,
                "responsible_person": client_data.get("responsible_person", ""),
            },
            "dispatch_company": self.company,
            "contract": {
                "start_date": start_date,
                "end_date": end_date,
                "teishokubi": teishokubi.strftime("%Y-%m-%d") if teishokubi else "",
                "hourly_rate": f"{hourly_rate:,}",
                "job_description": job_description,
                "work_hours": work_hours,
                "break_time": break_time,
            },
            "schedule": {
                "overtime_limit": f"{UNS_LEGAL.daily_overtime_limit}時間/日、{UNS_LEGAL.monthly_overtime_limit}時間/月"
                if HAS_UNS_CONFIG
                else "3時間/日、45時間/月",
            },
        }

    def prepare_kyuuyo_meisai_data(
        self,
        employee_name: str,
        employee_number: str,
        period: str,
        regular_hours: float,
        overtime_hours: float,
        night_hours: float,
        holiday_hours: float,
        hourly_rate: int,
        deductions: dict[str, int] = None,
    ) -> dict[str, Any]:
        """
        Prepara datos para 給与明細書.
        """
        # Calcular montos
        overtime_rate = UNS_PAYROLL.overtime_multiplier if HAS_UNS_CONFIG else 1.25
        night_rate = UNS_PAYROLL.night_shift_multiplier if HAS_UNS_CONFIG else 1.25
        holiday_rate = UNS_PAYROLL.holiday_multiplier if HAS_UNS_CONFIG else 1.35

        regular_pay = int(regular_hours * hourly_rate)
        overtime_pay = int(overtime_hours * hourly_rate * overtime_rate)
        night_pay = int(night_hours * hourly_rate * night_rate)
        holiday_pay = int(holiday_hours * hourly_rate * holiday_rate)

        gross_pay = regular_pay + overtime_pay + night_pay + holiday_pay

        # Deducciones por defecto
        if deductions is None:
            deductions = {}

        # Calcular deducciones estándar si no se proporcionan
        health_ins = deductions.get("health_insurance", int(gross_pay * 0.05))
        pension = deductions.get("pension", int(gross_pay * 0.0915))
        employment_ins = deductions.get("employment_insurance", int(gross_pay * 0.006))
        income_tax = deductions.get("income_tax", 0)
        residence_tax = deductions.get("residence_tax", 0)
        housing = deductions.get("housing", 0)
        other = deductions.get("other", 0)

        total_deductions = (
            health_ins + pension + employment_ins + income_tax + residence_tax + housing + other
        )
        net_pay = gross_pay - total_deductions

        return {
            "employee": {
                "name": employee_name,
                "number": employee_number,
            },
            "period": period,
            "earnings": {
                "regular": {"hours": regular_hours, "rate": hourly_rate, "amount": regular_pay},
                "overtime": {
                    "hours": overtime_hours,
                    "rate": int(hourly_rate * overtime_rate),
                    "amount": overtime_pay,
                },
                "night": {
                    "hours": night_hours,
                    "rate": int(hourly_rate * night_rate),
                    "amount": night_pay,
                },
                "holiday": {
                    "hours": holiday_hours,
                    "rate": int(hourly_rate * holiday_rate),
                    "amount": holiday_pay,
                },
                "gross": gross_pay,
            },
            "deductions": {
                "health_insurance": health_ins,
                "pension": pension,
                "employment_insurance": employment_ins,
                "income_tax": income_tax,
                "residence_tax": residence_tax,
                "housing": housing,
                "other": other,
                "total": total_deductions,
            },
            "net_pay": net_pay,
            "company": self.company,
            "payment_date": "",  # Se llena al generar
        }


# =============================================================================
# FUNCIONES DE CONVENIENCIA
# =============================================================================


def quick_zaishoku(
    name: str,
    kana: str,
    birth: str,
    address: str,
    start: str,
    position: str,
    workplace: str,
    salary: int,
) -> dict:
    """Genera datos rápidos para 在職証明書."""
    helper = UNSDocumentHelper()
    return helper.prepare_zaishoku_data(
        name, kana, birth, address, start, position, workplace, salary
    )


def quick_kobetsu(
    worker: str, client: str, plant: str, job: str, rate: int, start: str, end: str
) -> dict:
    """Genera datos rápidos para 個別契約書."""
    helper = UNSDocumentHelper()
    return helper.prepare_kobetsu_keiyaku_data(worker, client, plant, job, rate, start, end)


# =============================================================================
# CLI
# =============================================================================

if __name__ == "__main__":
    import json

    print("=" * 60)
    print("UNS Document Adapter")
    print("=" * 60)

    # Mostrar datos de empresa
    company = get_company_data()
    print("\n🏢 Empresa派遣元:")
    print(f"   {company['name']}")
    print(f"   {company['address']}")
    print(f"   TEL: {company['phone']}")

    # Mostrar clientes
    clients = get_all_clients()
    print(f"\n📍 Clientes派遣先: {len(clients)}")
    for name in list(clients.keys())[:5]:
        print(f"   - {name}")
    if len(clients) > 5:
        print(f"   ... y {len(clients) - 5} más")

    # Mostrar fábricas
    factories = list_all_factories()
    print(f"\n🏭 Fábricas totales: {len(factories)}")

    # Ejemplo de documento
    print("\n📄 Ejemplo de datos para 在職証明書:")
    example = quick_zaishoku(
        name="グエン バン アイン",
        kana="ぐえん ばん あいん",
        birth="1990-05-15",
        address="愛知県豊田市土橋町7-7-7",
        start="2023-04-01",
        position="製造作業",
        workplace="高雄工業株式会社 本社工場",
        salary=250000,
    )
    print(json.dumps(example, indent=2, ensure_ascii=False)[:500] + "...")
