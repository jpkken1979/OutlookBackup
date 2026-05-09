#!/usr/bin/env python3
"""
Haken SaaS - Generador de Documentos Legales
=============================================
Genera todos los documentos obligatorios para 人材派遣:
- 派遣元管理台帳 (Haken Moto Kanri Taicho)
- 派遣先管理台帳 (Haken Saki Kanri Taicho)
- 労働者派遣契約書 (Roudousha Haken Keiyakusho)
- 労働条件通知書 (Roudou Jouken Tsuuchisho)
- 就業条件明示書 (Shuugyou Jouken Meijisho)
"""

import json
from datetime import datetime, date
from decimal import Decimal
from pathlib import Path
import sys

# Importar modelos
sys.path.insert(0, str(Path(__file__).parent.parent / "core"))
from models import (
    Tenant,
    Client,
    Worker,
    Placement,
    AttendanceRecord,
    PayrollRecord,
)


class DocumentGenerator:
    """
    Generador de documentos legales para 人材派遣.
    """

    def __init__(self, output_dir: str = "artifacts/documents"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] 📄 {message}")

    # ═══════════════════════════════════════════════════════════════
    # 派遣元管理台帳 (Registro de Gestión de la Agencia)
    # ═══════════════════════════════════════════════════════════════

    def generate_haken_moto_kanri_taicho(
        self,
        tenant: Tenant,
        worker: Worker,
        placement: Placement,
        client: Client,
        attendance: list[AttendanceRecord],
        payroll: PayrollRecord = None,
    ) -> dict:
        """
        Genera 派遣元管理台帳.
        Documento obligatorio que la agencia debe mantener por cada trabajador.
        Período de retención: 3 años después de finalizar el contrato.

        Contenido obligatorio según la Ley de Trabajadores Temporales:
        1. 派遣労働者の氏名 (Nombre del trabajador)
        2. 派遣先の名称 (Nombre del cliente)
        3. 派遣期間 (Período de envío)
        4. 業務内容 (Descripción del trabajo)
        5. 就業時間 (Horario de trabajo)
        6. 賃金 (Salario)
        """

        # Calcular totales de horas del período
        total_regular = sum(r.regular_hours for r in attendance)
        total_overtime = sum(r.overtime_hours for r in attendance)
        total_night = sum(r.night_hours for r in attendance)
        total_holiday = sum(r.holiday_hours for r in attendance)

        document = {
            "document_type": "派遣元管理台帳",
            "document_number": f"HMKT-{placement.id}-{datetime.now().strftime('%Y%m%d')}",
            "generated_at": datetime.now().isoformat(),
            "retention_until": (date.today().replace(year=date.today().year + 3)).isoformat(),
            # ─── 派遣元事業者情報 (Información de la agencia) ───
            "agency": {
                "name": tenant.name,
                "name_kana": tenant.name_kana,
                "permit_number": tenant.permit_number,
                "representative": tenant.representative,
                "address": tenant.address,
                "phone": tenant.phone,
            },
            # ─── 派遣労働者情報 (Información del trabajador) ───
            "worker": {
                "id": worker.id,
                "name": worker.name_kanji,
                "name_kana": worker.name_kana,
                "name_romaji": worker.name_romaji,
                "birth_date": worker.birth_date.isoformat(),
                "gender": worker.gender,
                "address": worker.address,
                "phone": worker.phone,
                "nationality": worker.nationality,
                "visa_type": worker.visa_type.value if worker.visa_type else "日本国籍",
                "visa_expiry": worker.visa_expiry.isoformat() if worker.visa_expiry else None,
                "zairyu_card": worker.zairyu_card_number,
                "health_insurance_number": worker.health_insurance_number,
                "pension_number": worker.pension_number,
                "employment_insurance_number": worker.employment_insurance_number,
            },
            # ─── 派遣先情報 (Información del cliente) ───
            "client": {
                "company_name": client.company_name,
                "company_name_kana": client.company_name_kana,
                "address": client.address,
                "contact_name": client.contact_name,
                "contact_phone": client.contact_phone,
            },
            # ─── 派遣契約情報 (Información del contrato) ───
            "contract": {
                "placement_id": placement.id,
                "start_date": placement.start_date.isoformat(),
                "end_date": placement.end_date.isoformat(),
                "teishoku_bi": placement.teishoku_bi.isoformat(),
                "status": placement.status.value,
                "supervisor": placement.supervisor_name,
                "workplace_manager": placement.workplace_manager,
            },
            # ─── 就業条件 (Condiciones de trabajo) ───
            "work_conditions": {
                "scheduled_hours_per_day": str(placement.scheduled_hours_per_day),
                "scheduled_days_per_week": placement.scheduled_days_per_week,
                "work_location": client.address,
            },
            # ─── 賃金情報 (Información salarial) ───
            "wages": {
                "hourly_rate": str(worker.hourly_rate),
                "overtime_rate": str(worker.hourly_rate * Decimal("1.25")),
                "night_rate": str(worker.hourly_rate * Decimal("1.25")),
                "holiday_rate": str(worker.hourly_rate * Decimal("1.35")),
            },
            # ─── 勤務実績 (Registro de asistencia del período) ───
            "attendance_summary": {
                "period_start": attendance[0].work_date.isoformat() if attendance else None,
                "period_end": attendance[-1].work_date.isoformat() if attendance else None,
                "total_days": len(attendance),
                "regular_hours": str(total_regular),
                "overtime_hours": str(total_overtime),
                "night_hours": str(total_night),
                "holiday_hours": str(total_holiday),
                "total_hours": str(total_regular + total_overtime + total_night + total_holiday),
            },
            # ─── 給与実績 (Registro de pagos si existe) ───
            "payroll": {
                "gross_salary": str(payroll.gross_salary) if payroll else "0",
                "total_deductions": str(payroll.total_deductions) if payroll else "0",
                "net_salary": str(payroll.net_salary) if payroll else "0",
            }
            if payroll
            else None,
        }

        # Guardar documento
        filename = f"haken_moto_kanri_taicho_{worker.id}_{datetime.now().strftime('%Y%m%d')}.json"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(document, f, indent=2, ensure_ascii=False)

        self.log(f"派遣元管理台帳 generado: {filepath}")
        return document

    # ═══════════════════════════════════════════════════════════════
    # 派遣先管理台帳 (Registro de Gestión del Cliente)
    # ═══════════════════════════════════════════════════════════════

    def generate_haken_saki_kanri_taicho(
        self,
        client: Client,
        placements: list[tuple[Worker, Placement]],
    ) -> dict:
        """
        Genera 派遣先管理台帳.
        Documento que el cliente debe mantener.
        Lista todos los trabajadores enviados activos.
        """

        workers_info = []
        for worker, placement in placements:
            workers_info.append(
                {
                    "worker_id": worker.id,
                    "name": worker.name_kanji,
                    "name_kana": worker.name_kana,
                    "nationality": worker.nationality,
                    "visa_type": worker.visa_type.value if worker.visa_type else "日本国籍",
                    "start_date": placement.start_date.isoformat(),
                    "end_date": placement.end_date.isoformat(),
                    "teishoku_bi": placement.teishoku_bi.isoformat(),
                    "days_until_teishoku_bi": placement.days_until_teishoku_bi(),
                    "alert_level": placement.get_alert_level(),
                    "supervisor": placement.supervisor_name,
                    "status": placement.status.value,
                }
            )

        document = {
            "document_type": "派遣先管理台帳",
            "document_number": f"HSKT-{client.id}-{datetime.now().strftime('%Y%m%d')}",
            "generated_at": datetime.now().isoformat(),
            # ─── 派遣先事業者情報 ───
            "client": {
                "company_name": client.company_name,
                "company_name_kana": client.company_name_kana,
                "industry": client.industry,
                "address": client.address,
                "contact_name": client.contact_name,
                "contact_phone": client.contact_phone,
            },
            # ─── 派遣労働者一覧 ───
            "workers": workers_info,
            # ─── 統計 ───
            "statistics": {
                "total_workers": len(workers_info),
                "active_workers": len([w for w in workers_info if w["status"] == "active"]),
                "alerts_urgent": len([w for w in workers_info if "URGENTE" in w["alert_level"]]),
                "alerts_warning": len(
                    [w for w in workers_info if "ADVERTENCIA" in w["alert_level"]]
                ),
            },
        }

        filename = f"haken_saki_kanri_taicho_{client.id}_{datetime.now().strftime('%Y%m%d')}.json"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(document, f, indent=2, ensure_ascii=False)

        self.log(f"派遣先管理台帳 generado: {filepath}")
        return document

    # ═══════════════════════════════════════════════════════════════
    # 労働者派遣契約書 (Contrato de Envío de Trabajadores)
    # ═══════════════════════════════════════════════════════════════

    def generate_haken_keiyakusho(
        self,
        tenant: Tenant,
        client: Client,
        placement: Placement,
        worker: Worker,
    ) -> dict:
        """
        Genera 労働者派遣契約書.
        Contrato entre la agencia y el cliente.
        """

        document = {
            "document_type": "労働者派遣契約書",
            "document_number": f"HKS-{placement.id}",
            "contract_date": date.today().isoformat(),
            "generated_at": datetime.now().isoformat(),
            # ─── 契約当事者 (Partes del contrato) ───
            "parties": {
                "agency": {
                    "name": tenant.name,
                    "representative": tenant.representative,
                    "address": tenant.address,
                    "permit_number": tenant.permit_number,
                },
                "client": {
                    "name": client.company_name,
                    "address": client.address,
                    "contact": client.contact_name,
                },
            },
            # ─── 派遣労働者 ───
            "worker": {
                "name": worker.name_kanji,
                "specialization": ", ".join(worker.skills) if worker.skills else "一般事務",
            },
            # ─── 契約条件 ───
            "terms": {
                # 第1条: 派遣期間
                "article_1_period": {
                    "title": "派遣期間",
                    "start_date": placement.start_date.isoformat(),
                    "end_date": placement.end_date.isoformat(),
                    "teishoku_bi": placement.teishoku_bi.isoformat(),
                },
                # 第2条: 業務内容
                "article_2_work": {
                    "title": "業務内容",
                    "description": "派遣先の指揮命令に従い、業務を遂行する",
                    "location": client.address,
                },
                # 第3条: 就業時間
                "article_3_hours": {
                    "title": "就業時間",
                    "hours_per_day": str(placement.scheduled_hours_per_day),
                    "days_per_week": placement.scheduled_days_per_week,
                    "break_time": "60分",
                },
                # 第4条: 派遣料金
                "article_4_billing": {
                    "title": "派遣料金",
                    "base_rate": str(placement.billing_rate_base),
                    "overtime_rate": str(placement.billing_rate_overtime),
                    "night_rate": str(placement.billing_rate_night),
                    "holiday_rate": str(placement.billing_rate_holiday),
                    "payment_terms": f"{client.payment_terms}日以内",
                },
                # 第5条: 安全衛生
                "article_5_safety": {
                    "title": "安全衛生",
                    "content": "派遣先は派遣労働者の安全衛生に配慮するものとする",
                },
                # 第6条: 指揮命令者
                "article_6_supervisor": {
                    "title": "指揮命令者",
                    "name": placement.supervisor_name or client.contact_name,
                    "position": placement.supervisor_position,
                },
                # 第7条: 苦情処理
                "article_7_complaints": {
                    "title": "苦情処理",
                    "agency_contact": tenant.phone,
                    "client_contact": client.contact_phone,
                },
            },
            # ─── 署名欄 ───
            "signatures": {
                "agency": {
                    "company": tenant.name,
                    "representative": tenant.representative,
                    "date": "",
                    "seal": "[印]",
                },
                "client": {
                    "company": client.company_name,
                    "representative": client.contact_name,
                    "date": "",
                    "seal": "[印]",
                },
            },
        }

        filename = f"haken_keiyakusho_{placement.id}.json"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(document, f, indent=2, ensure_ascii=False)

        self.log(f"労働者派遣契約書 generado: {filepath}")
        return document

    # ═══════════════════════════════════════════════════════════════
    # 労働条件通知書 (Notificación de Condiciones de Trabajo)
    # ═══════════════════════════════════════════════════════════════

    def generate_roudou_jouken_tsuuchisho(
        self,
        tenant: Tenant,
        worker: Worker,
        placement: Placement,
        client: Client,
    ) -> dict:
        """
        Genera 労働条件通知書.
        Documento obligatorio para notificar condiciones laborales al trabajador.
        """

        document = {
            "document_type": "労働条件通知書",
            "document_number": f"RJT-{worker.id}-{placement.id}",
            "issue_date": date.today().isoformat(),
            "generated_at": datetime.now().isoformat(),
            # ─── 事業者情報 ───
            "employer": {
                "name": tenant.name,
                "address": tenant.address,
                "representative": tenant.representative,
                "phone": tenant.phone,
            },
            # ─── 労働者情報 ───
            "employee": {
                "name": worker.name_kanji,
                "name_kana": worker.name_kana,
                "address": worker.address,
            },
            # ─── 労働条件 ───
            "conditions": {
                # 1. 契約期間
                "contract_period": {
                    "label": "契約期間",
                    "start_date": placement.start_date.isoformat(),
                    "end_date": placement.end_date.isoformat(),
                    "renewal": "更新の可能性あり（業務量・能力等により判断）",
                },
                # 2. 就業場所
                "workplace": {
                    "label": "就業の場所",
                    "name": client.company_name,
                    "address": client.address,
                },
                # 3. 業務内容
                "work_description": {
                    "label": "従事すべき業務の内容",
                    "content": "派遣先の指揮命令に基づく業務全般",
                },
                # 4. 就業時間
                "work_hours": {
                    "label": "就業時間",
                    "hours_per_day": f"{placement.scheduled_hours_per_day}時間",
                    "days_per_week": f"週{placement.scheduled_days_per_week}日",
                    "break_time": "60分",
                    "overtime": "有（36協定の範囲内）",
                },
                # 5. 休日
                "holidays": {
                    "label": "休日",
                    "weekly": "土曜日、日曜日",
                    "national": "国民の祝日",
                    "other": "年末年始、夏季休暇",
                },
                # 6. 賃金
                "wages": {
                    "label": "賃金",
                    "type": "時給制",
                    "base_rate": str(worker.hourly_rate),
                    "overtime_rate": f"{worker.hourly_rate * Decimal('1.25')} (125%)",
                    "night_rate": f"{worker.hourly_rate * Decimal('1.25')} (125%)",
                    "holiday_rate": f"{worker.hourly_rate * Decimal('1.35')} (135%)",
                    "payment_day": "毎月末日締め、翌月15日払い",
                    "payment_method": "銀行振込",
                },
                # 7. 社会保険
                "insurance": {
                    "label": "社会保険の加入状況",
                    "health_insurance": "加入" if worker.health_insurance_number else "未加入",
                    "pension": "加入" if worker.pension_number else "未加入",
                    "employment_insurance": "加入"
                    if worker.employment_insurance_number
                    else "未加入",
                    "workers_comp": "加入",
                },
                # 8. 退職に関する事項
                "termination": {
                    "label": "退職に関する事項",
                    "notice_period": "30日前までに申し出ること",
                    "retirement_age": "なし",
                },
            },
            # ─── 確認欄 ───
            "acknowledgment": {
                "statement": "上記の労働条件に同意します",
                "employee_signature": "",
                "date": "",
            },
        }

        filename = f"roudou_jouken_tsuuchisho_{worker.id}_{placement.id}.json"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(document, f, indent=2, ensure_ascii=False)

        self.log(f"労働条件通知書 generado: {filepath}")
        return document

    # ═══════════════════════════════════════════════════════════════
    # 就業条件明示書 (Documento de Condiciones de Empleo)
    # ═══════════════════════════════════════════════════════════════

    def generate_shuugyou_jouken_meijisho(
        self,
        tenant: Tenant,
        worker: Worker,
        placement: Placement,
        client: Client,
    ) -> dict:
        """
        Genera 就業条件明示書.
        Documento específico para派遣社員 con detalles del envío.
        """

        document = {
            "document_type": "就業条件明示書",
            "document_number": f"SJM-{placement.id}",
            "issue_date": date.today().isoformat(),
            "generated_at": datetime.now().isoformat(),
            # ─── 派遣元情報 ───
            "agency": {
                "name": tenant.name,
                "permit_number": tenant.permit_number,
                "address": tenant.address,
                "phone": tenant.phone,
            },
            # ─── 派遣労働者情報 ───
            "worker": {
                "name": worker.name_kanji,
            },
            # ─── 派遣先情報 ───
            "client": {
                "company_name": client.company_name,
                "address": client.address,
                "department": "",
                "supervisor": placement.supervisor_name,
            },
            # ─── 派遣期間 ───
            "dispatch_period": {
                "start_date": placement.start_date.isoformat(),
                "end_date": placement.end_date.isoformat(),
                "teishoku_bi": placement.teishoku_bi.isoformat(),
                "teishoku_warning": f"抵触日まで残り{placement.days_until_teishoku_bi()}日",
            },
            # ─── 業務内容 ───
            "work_details": {
                "description": "派遣先の指揮命令に基づく業務",
                "skills_required": worker.skills,
            },
            # ─── 就業場所 ───
            "workplace": {
                "address": client.address,
                "nearest_station": "",
            },
            # ─── 就業時間 ───
            "work_hours": {
                "start": "09:00",
                "end": "18:00",
                "break": "12:00-13:00 (60分)",
                "hours_per_day": str(placement.scheduled_hours_per_day),
            },
            # ─── 賃金 ───
            "compensation": {
                "hourly_rate": str(worker.hourly_rate),
                "overtime_multiplier": "1.25",
                "night_multiplier": "1.25",
                "holiday_multiplier": "1.35",
                "payment_date": "翌月15日",
            },
            # ─── 苦情申出先 ───
            "complaint_contacts": {
                "agency": {
                    "department": "派遣事業部",
                    "person": tenant.representative,
                    "phone": tenant.phone,
                },
                "client": {
                    "person": client.contact_name,
                    "phone": client.contact_phone,
                },
            },
            # ─── 派遣元責任者 ───
            "agency_manager": {
                "name": tenant.representative,
                "phone": tenant.phone,
            },
            # ─── 派遣先責任者 ───
            "client_manager": {
                "name": placement.workplace_manager or client.contact_name,
                "phone": client.contact_phone,
            },
        }

        filename = f"shuugyou_jouken_meijisho_{placement.id}.json"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(document, f, indent=2, ensure_ascii=False)

        self.log(f"就業条件明示書 generado: {filepath}")
        return document

    # ═══════════════════════════════════════════════════════════════
    # 賃金台帳 (Registro de Salarios)
    # ═══════════════════════════════════════════════════════════════

    def generate_chingin_daicho(
        self,
        tenant: Tenant,
        worker: Worker,
        payroll_records: list[PayrollRecord],
    ) -> dict:
        """
        Genera 賃金台帳.
        Registro obligatorio de salarios por trabajador.
        """

        records = []
        yearly_totals = {
            "regular_hours": Decimal("0"),
            "overtime_hours": Decimal("0"),
            "gross_salary": Decimal("0"),
            "total_deductions": Decimal("0"),
            "net_salary": Decimal("0"),
        }

        for record in sorted(payroll_records, key=lambda r: (r.period_year, r.period_month)):
            entry = {
                "year": record.period_year,
                "month": record.period_month,
                "regular_hours": str(record.regular_hours),
                "overtime_hours": str(record.overtime_hours),
                "night_hours": str(record.night_hours),
                "holiday_hours": str(record.holiday_hours),
                "base_salary": str(record.base_salary),
                "overtime_pay": str(record.overtime_pay),
                "night_pay": str(record.night_pay),
                "holiday_pay": str(record.holiday_pay),
                "transport_allowance": str(record.transport_allowance),
                "gross_salary": str(record.gross_salary),
                "health_insurance": str(record.health_insurance),
                "pension": str(record.pension),
                "employment_insurance": str(record.employment_insurance),
                "income_tax": str(record.income_tax),
                "resident_tax": str(record.resident_tax),
                "total_deductions": str(record.total_deductions),
                "net_salary": str(record.net_salary),
            }
            records.append(entry)

            yearly_totals["regular_hours"] += record.regular_hours
            yearly_totals["overtime_hours"] += record.overtime_hours
            yearly_totals["gross_salary"] += record.gross_salary
            yearly_totals["total_deductions"] += record.total_deductions
            yearly_totals["net_salary"] += record.net_salary

        document = {
            "document_type": "賃金台帳",
            "document_number": f"CD-{worker.id}-{datetime.now().strftime('%Y')}",
            "generated_at": datetime.now().isoformat(),
            "employer": {
                "name": tenant.name,
                "permit_number": tenant.permit_number,
            },
            "employee": {
                "id": worker.id,
                "name": worker.name_kanji,
                "name_kana": worker.name_kana,
                "hourly_rate": str(worker.hourly_rate),
            },
            "records": records,
            "yearly_totals": {k: str(v) for k, v in yearly_totals.items()},
        }

        filename = f"chingin_daicho_{worker.id}_{datetime.now().strftime('%Y')}.json"
        filepath = self.output_dir / filename

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(document, f, indent=2, ensure_ascii=False)

        self.log(f"賃金台帳 generado: {filepath}")
        return document

    # ═══════════════════════════════════════════════════════════════
    # Generación Batch
    # ═══════════════════════════════════════════════════════════════

    def generate_all_for_placement(
        self,
        tenant: Tenant,
        client: Client,
        worker: Worker,
        placement: Placement,
        attendance: list[AttendanceRecord] = None,
        payroll: PayrollRecord = None,
    ) -> dict:
        """
        Genera todos los documentos relacionados con una colocación.
        """
        attendance = attendance or []

        documents = {
            "haken_keiyakusho": self.generate_haken_keiyakusho(tenant, client, placement, worker),
            "roudou_jouken_tsuuchisho": self.generate_roudou_jouken_tsuuchisho(
                tenant, worker, placement, client
            ),
            "shuugyou_jouken_meijisho": self.generate_shuugyou_jouken_meijisho(
                tenant, worker, placement, client
            ),
        }

        if attendance:
            documents["haken_moto_kanri_taicho"] = self.generate_haken_moto_kanri_taicho(
                tenant, worker, placement, client, attendance, payroll
            )

        self.log(f"Batch completado: {len(documents)} documentos generados")
        return documents


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generador de Documentos Legales para 人材派遣")

    parser.add_argument(
        "--type",
        choices=["kanri-taicho", "keiyakusho", "jouken", "chingin", "all"],
        required=True,
        help="Tipo de documento a generar",
    )

    parser.add_argument("--data", help="Archivo JSON con datos")
    parser.add_argument("--output", default="artifacts/documents", help="Directorio de salida")

    args = parser.parse_args()

    DocumentGenerator(args.output)

    print("\n📄 GENERADOR DE DOCUMENTOS - HAKEN SAAS")
    print("=" * 50)
    print(f"Tipo: {args.type}")
    print(f"Output: {args.output}")

    if args.type == "all":
        print("\n✅ Para generar documentos, proporcione datos con --data")
        print("   Ejemplo: --data placement_data.json")

    print("\nDocumentos disponibles:")
    print("  1. 派遣元管理台帳 (kanri-taicho)")
    print("  2. 労働者派遣契約書 (keiyakusho)")
    print("  3. 労働条件通知書 / 就業条件明示書 (jouken)")
    print("  4. 賃金台帳 (chingin)")


if __name__ == "__main__":
    main()
