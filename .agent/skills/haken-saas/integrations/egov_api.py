#!/usr/bin/env python3
"""
Haken SaaS - Integración e-Gov API
===================================
Cliente para la API de e-Gov (電子政府) de Japón.
Permite envío electrónico de:
- 届出 (Notificaciones)
- 申請 (Solicitudes)
- 報告 (Reportes)

Documentación oficial: https://www.e-gov.go.jp/shinsei/api/api_doc.html
"""

import json
import hashlib
import os
from dataclasses import dataclass, field
from datetime import datetime, date
import urllib.request
import urllib.parse
import ssl


# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN
# ═══════════════════════════════════════════════════════════════


@dataclass
class EGovConfig:
    """Configuración para e-Gov API."""

    api_key: str = ""
    api_secret: str = ""
    client_id: str = ""
    client_secret: str = ""
    certificate_path: str = ""  # Certificado digital (電子証明書)
    private_key_path: str = ""  # Clave privada
    environment: str = "sandbox"  # sandbox | production

    @property
    def base_url(self) -> str:
        if self.environment == "production":
            return "https://api.e-gov.go.jp/v1"
        return "https://api-sandbox.e-gov.go.jp/v1"


# ═══════════════════════════════════════════════════════════════
# TIPOS DE PROCEDIMIENTOS
# ═══════════════════════════════════════════════════════════════


class EGovProcedureType:
    """Tipos de procedimientos para 人材派遣."""

    # ─── 労働者派遣法関連 (Ley de Trabajadores Temporales) ───
    HAKEN_JIGYO_TODOKE = "派遣事業届出"  # Notificación de negocio de派遣
    HAKEN_JIGYO_HENKO = "派遣事業変更届"  # Notificación de cambio
    HAKEN_KEIYAKU_HOUKOKU = "派遣契約報告"  # Reporte de contratos

    # ─── 労働保険関連 (Seguro laboral) ───
    ROUDOU_HOKEN_TEKIYO = "労働保険適用届"  # Alta en seguro laboral
    ROUDOU_HOKEN_SANTEIKISO = "労働保険算定基礎届"  # Base de cálculo anual
    KOYOU_HOKEN_SHUTOKU = "雇用保険取得届"  # Alta en seguro de empleo
    KOYOU_HOKEN_SOUSHITSU = "雇用保険喪失届"  # Baja en seguro de empleo

    # ─── 社会保険関連 (Seguro social) ───
    KENKOU_NENKIN_TEKIYO = "健康保険・厚生年金適用届"  # Alta SS
    KENKOU_NENKIN_SANTEIKISO = "健康保険・厚生年金算定基礎届"  # Base cálculo
    KENKOU_NENKIN_HENKO = "健康保険・厚生年金変更届"  # Cambios
    KENKOU_NENKIN_SOUSHITSU = "健康保険・厚生年金喪失届"  # Baja

    # ─── 税務関連 (Impuestos) ───
    GENSEN_CHOUSHUUHYOU = "源泉徴収票"  # Certificado retención
    HOUKOKUSHO_GENSEN = "給与所得の源泉徴収票等の法定調書"  # Informe legal


# ═══════════════════════════════════════════════════════════════
# MODELOS DE DATOS
# ═══════════════════════════════════════════════════════════════


@dataclass
class EGovSubmission:
    """Representación de un envío a e-Gov."""

    id: str
    procedure_type: str
    status: str = "draft"  # draft, submitted, processing, completed, rejected
    submitted_at: datetime | None = None
    receipt_number: str = ""  # 受付番号
    response_data: dict = field(default_factory=dict)
    error_message: str = ""


@dataclass
class EmployeeInsuranceData:
    """Datos para trámites de seguro de empleados."""

    # 被保険者情報
    employee_number: str  # 被保険者番号
    name_kanji: str  # 氏名
    name_kana: str  # 氏名カナ
    birth_date: date  # 生年月日
    gender: str  # 性別 (1=男, 2=女)
    my_number: str  # マイナンバー
    postal_code: str  # 郵便番号
    address: str  # 住所

    # 資格情報
    acquisition_date: date | None = None  # 取得日
    loss_date: date | None = None  # 喪失日
    loss_reason: str = ""  # 喪失理由

    # 報酬情報
    monthly_remuneration: int = 0  # 報酬月額
    standard_remuneration: int = 0  # 標準報酬月額


# ═══════════════════════════════════════════════════════════════
# CLIENTE API
# ═══════════════════════════════════════════════════════════════


class EGovClient:
    """
    Cliente para e-Gov API.

    Nota: Esta es una implementación de referencia.
    En producción, se requiere:
    1. Certificado digital válido (電子証明書)
    2. Registro en e-Gov
    3. Aprobación de API key
    """

    def __init__(self, config: EGovConfig):
        self.config = config
        self.submissions: dict[str, EGovSubmission] = {}
        self._access_token: str | None = None
        self._token_expires: datetime | None = None

    def log(self, message: str, level: str = "INFO") -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] [{level}] 🏛️ e-Gov: {message}")

    # ═══════════════════════════════════════════════════════════════
    # AUTENTICACIÓN
    # ═══════════════════════════════════════════════════════════════

    def authenticate(self) -> bool:
        """
        Autentica con e-Gov API usando OAuth2.
        """
        if not self.config.client_id or not self.config.client_secret:
            self.log("Credenciales no configuradas", "ERROR")
            return False

        # En modo sandbox, simular autenticación
        if self.config.environment == "sandbox":
            self._access_token = (
                "sandbox_token_" + hashlib.md5(self.config.client_id.encode()).hexdigest()[:16]
            )
            self._token_expires = datetime.now()
            self.log("Autenticación sandbox exitosa")
            return True

        # Producción: OAuth2 flow
        try:
            url = f"{self.config.base_url}/oauth/token"
            data = urllib.parse.urlencode(
                {
                    "grant_type": "client_credentials",
                    "client_id": self.config.client_id,
                    "client_secret": self.config.client_secret,
                }
            ).encode()

            req = urllib.request.Request(url, data=data, method="POST")
            req.add_header("Content-Type", "application/x-www-form-urlencoded")

            # Deshabilitar verificación SSL solo para sandbox
            context = ssl.create_default_context()
            if self.config.environment == "sandbox":
                context.check_hostname = False
                context.verify_mode = ssl.CERT_NONE

            with urllib.request.urlopen(req, context=context) as response:
                result = json.loads(response.read().decode())
                self._access_token = result.get("access_token")
                self.log("Autenticación exitosa")
                return True

        except Exception as e:
            self.log(f"Error de autenticación: {e}", "ERROR")
            return False

    def _get_headers(self) -> dict:
        """Obtiene headers para requests autenticados."""
        return {
            "Authorization": f"Bearer {self._access_token}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

    # ═══════════════════════════════════════════════════════════════
    # ENVÍO DE TRÁMITES
    # ═══════════════════════════════════════════════════════════════

    def submit_procedure(
        self,
        procedure_type: str,
        data: dict,
        attachments: list[str] = None,
    ) -> EGovSubmission:
        """
        Envía un trámite a e-Gov.

        Args:
            procedure_type: Tipo de procedimiento
            data: Datos del formulario
            attachments: Lista de rutas a archivos adjuntos

        Returns:
            EGovSubmission con el resultado
        """
        submission_id = f"SUB-{datetime.now().strftime('%Y%m%d%H%M%S')}"

        submission = EGovSubmission(
            id=submission_id,
            procedure_type=procedure_type,
        )

        # Validar datos antes de enviar
        validation = self._validate_data(procedure_type, data)
        if not validation["valid"]:
            submission.status = "rejected"
            submission.error_message = "; ".join(validation["errors"])
            self.submissions[submission_id] = submission
            self.log(f"Validación fallida: {submission.error_message}", "ERROR")
            return submission

        # Modo sandbox: simular envío
        if self.config.environment == "sandbox":
            submission.status = "submitted"
            submission.submitted_at = datetime.now()
            submission.receipt_number = f"R{datetime.now().strftime('%Y%m%d')}-{submission_id[-6:]}"
            submission.response_data = {
                "mode": "sandbox",
                "message": "Envío simulado exitoso",
                "estimated_processing_days": 3,
            }
            self.submissions[submission_id] = submission
            self.log(f"Envío sandbox completado: {submission.receipt_number}")
            return submission

        # Producción: envío real
        try:
            url = f"{self.config.base_url}/procedures/submit"

            payload = {
                "procedure_type": procedure_type,
                "data": data,
                "has_attachments": bool(attachments),
            }

            req = urllib.request.Request(
                url, data=json.dumps(payload).encode(), headers=self._get_headers(), method="POST"
            )

            context = ssl.create_default_context()
            with urllib.request.urlopen(req, context=context) as response:
                result = json.loads(response.read().decode())

                submission.status = "submitted"
                submission.submitted_at = datetime.now()
                submission.receipt_number = result.get("receipt_number", "")
                submission.response_data = result

        except Exception as e:
            submission.status = "error"
            submission.error_message = str(e)
            self.log(f"Error de envío: {e}", "ERROR")

        self.submissions[submission_id] = submission
        return submission

    def check_status(self, receipt_number: str) -> dict:
        """
        Consulta el estado de un trámite.
        """
        if self.config.environment == "sandbox":
            return {
                "receipt_number": receipt_number,
                "status": "processing",
                "message": "Trámite en proceso de revisión",
                "estimated_completion": "3-5 días hábiles",
            }

        # Producción: consulta real
        try:
            url = f"{self.config.base_url}/procedures/status/{receipt_number}"
            req = urllib.request.Request(url, headers=self._get_headers())

            context = ssl.create_default_context()
            with urllib.request.urlopen(req, context=context) as response:
                return json.loads(response.read().decode())

        except Exception as e:
            return {"error": str(e)}

    # ═══════════════════════════════════════════════════════════════
    # VALIDACIÓN DE DATOS
    # ═══════════════════════════════════════════════════════════════

    def _validate_data(self, procedure_type: str, data: dict) -> dict:
        """Valida los datos antes de enviar."""
        errors = []
        warnings = []

        # Validaciones comunes
        if not data.get("company_name"):
            errors.append("会社名 es requerido")

        if not data.get("company_number"):
            warnings.append("法人番号 no proporcionado")

        # Validaciones específicas por tipo
        if "保険" in procedure_type:
            if not data.get("insurance_number"):
                errors.append("保険番号 es requerido")

        if "マイナンバー" in str(data.values()):
            # Validar formato de My Number
            my_number = data.get("my_number", "")
            if my_number and not self._validate_my_number(my_number):
                errors.append("マイナンバー inválido")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
        }

    def _validate_my_number(self, my_number: str) -> bool:
        """Valida formato de マイナンバー (12 dígitos con checksum)."""
        if not my_number.isdigit() or len(my_number) != 12:
            return False

        # Algoritmo de checksum
        digits = [int(d) for d in my_number]
        weights = [6, 5, 4, 3, 2, 7, 6, 5, 4, 3, 2]

        total = sum(d * w for d, w in zip(digits[:11], weights, strict=False))
        remainder = total % 11
        check_digit = 0 if remainder <= 1 else 11 - remainder

        return digits[11] == check_digit

    # ═══════════════════════════════════════════════════════════════
    # TRÁMITES ESPECÍFICOS
    # ═══════════════════════════════════════════════════════════════

    def submit_koyou_hoken_shutoku(
        self,
        company_info: dict,
        employee: EmployeeInsuranceData,
    ) -> EGovSubmission:
        """
        Envía 雇用保険被保険者資格取得届.
        Alta de empleado en seguro de empleo.
        """
        data = {
            "form_type": "雇用保険被保険者資格取得届",
            "company": {
                "name": company_info.get("name"),
                "number": company_info.get("hoken_number"),
                "address": company_info.get("address"),
            },
            "employee": {
                "number": employee.employee_number,
                "name_kanji": employee.name_kanji,
                "name_kana": employee.name_kana,
                "birth_date": employee.birth_date.isoformat(),
                "gender": employee.gender,
                "postal_code": employee.postal_code,
                "address": employee.address,
                "acquisition_date": employee.acquisition_date.isoformat()
                if employee.acquisition_date
                else None,
                "monthly_remuneration": employee.monthly_remuneration,
            },
        }

        return self.submit_procedure(EGovProcedureType.KOYOU_HOKEN_SHUTOKU, data)

    def submit_koyou_hoken_soushitsu(
        self,
        company_info: dict,
        employee: EmployeeInsuranceData,
    ) -> EGovSubmission:
        """
        Envía 雇用保険被保険者資格喪失届.
        Baja de empleado en seguro de empleo.
        """
        data = {
            "form_type": "雇用保険被保険者資格喪失届",
            "company": {
                "name": company_info.get("name"),
                "number": company_info.get("hoken_number"),
            },
            "employee": {
                "number": employee.employee_number,
                "name_kanji": employee.name_kanji,
                "loss_date": employee.loss_date.isoformat() if employee.loss_date else None,
                "loss_reason": employee.loss_reason,
            },
        }

        return self.submit_procedure(EGovProcedureType.KOYOU_HOKEN_SOUSHITSU, data)

    def submit_kenkou_nenkin_santeikiso(
        self,
        company_info: dict,
        employees: list[EmployeeInsuranceData],
        period_year: int,
    ) -> EGovSubmission:
        """
        Envía 健康保険・厚生年金保険被保険者報酬月額算定基礎届.
        Base de cálculo de remuneración mensual (anual, julio).
        """
        employee_records = []
        for emp in employees:
            employee_records.append(
                {
                    "number": emp.employee_number,
                    "name": emp.name_kanji,
                    "birth_date": emp.birth_date.isoformat(),
                    "standard_remuneration": emp.standard_remuneration,
                    "monthly_remuneration": emp.monthly_remuneration,
                }
            )

        data = {
            "form_type": "算定基礎届",
            "period_year": period_year,
            "company": {
                "name": company_info.get("name"),
                "jigyousho_number": company_info.get("jigyousho_number"),
            },
            "employees": employee_records,
            "total_count": len(employee_records),
        }

        return self.submit_procedure(EGovProcedureType.KENKOU_NENKIN_SANTEIKISO, data)


# ═══════════════════════════════════════════════════════════════
# GENERADOR DE XML PARA e-Gov
# ═══════════════════════════════════════════════════════════════


class EGovXMLGenerator:
    """
    Genera XML en formato requerido por e-Gov.
    Muchos trámites requieren formato XML específico.
    """

    def generate_koyou_hoken_xml(self, data: dict) -> str:
        """Genera XML para trámites de 雇用保険."""
        xml_template = """<?xml version="1.0" encoding="UTF-8"?>
<雇用保険被保険者資格取得届 xmlns="urn:egov:koyou-hoken">
  <届出事業所>
    <事業所番号>{company_number}</事業所番号>
    <事業所名称>{company_name}</事業所名称>
  </届出事業所>
  <被保険者>
    <被保険者番号>{employee_number}</被保険者番号>
    <氏名>
      <漢字>{name_kanji}</漢字>
      <カナ>{name_kana}</カナ>
    </氏名>
    <生年月日>{birth_date}</生年月日>
    <性別>{gender}</性別>
    <資格取得年月日>{acquisition_date}</資格取得年月日>
    <賃金月額>{monthly_remuneration}</賃金月額>
  </被保険者>
</雇用保険被保険者資格取得届>"""

        return xml_template.format(**data)


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Cliente e-Gov API para 人材派遣")

    subparsers = parser.add_subparsers(dest="command")

    # Test connection
    subparsers.add_parser("test", help="Probar conexión")

    # Submit
    submit_parser = subparsers.add_parser("submit", help="Enviar trámite")
    submit_parser.add_argument("--type", required=True, help="Tipo de trámite")
    submit_parser.add_argument("--data", required=True, help="Archivo JSON con datos")

    # Status
    status_parser = subparsers.add_parser("status", help="Consultar estado")
    status_parser.add_argument("--receipt", required=True, help="Número de recibo")

    # List procedures
    subparsers.add_parser("list", help="Listar tipos de trámites")

    args = parser.parse_args()

    # Configuración sandbox por defecto
    # EGOV_CLIENT_ID y EGOV_CLIENT_SECRET deben estar en variables de entorno
    config = EGovConfig(
        client_id=os.environ.get("EGOV_CLIENT_ID", ""),
        client_secret=os.environ.get("EGOV_CLIENT_SECRET", ""),
        environment="sandbox",
    )

    client = EGovClient(config)

    if args.command == "test":
        print("\n🏛️ TEST DE CONEXIÓN e-Gov API")
        print("=" * 50)
        print(f"Entorno: {config.environment}")
        print(f"URL Base: {config.base_url}")

        if client.authenticate():
            print("✅ Autenticación exitosa")
        else:
            print("❌ Error de autenticación")

    elif args.command == "list":
        print("\n📋 TIPOS DE TRÁMITES DISPONIBLES")
        print("=" * 50)
        procedures = [
            ("派遣事業届出", "Notificación de negocio de派遣"),
            ("雇用保険取得届", "Alta en seguro de empleo"),
            ("雇用保険喪失届", "Baja en seguro de empleo"),
            ("健康保険・厚生年金適用届", "Alta en seguro social"),
            ("算定基礎届", "Base de cálculo anual"),
            ("源泉徴収票", "Certificado de retención"),
        ]

        for jp, es in procedures:
            print(f"  • {jp}")
            print(f"    {es}")
            print()

    elif args.command == "submit":
        print(f"\n📤 ENVÍO DE TRÁMITE: {args.type}")
        print("=" * 50)

        # Cargar datos
        try:
            with open(args.data, encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            print(f"❌ Error cargando datos: {e}")
            return

        client.authenticate()
        submission = client.submit_procedure(args.type, data)

        print(f"\n状態: {submission.status}")
        print(f"受付番号: {submission.receipt_number}")

        if submission.error_message:
            print(f"❌ Error: {submission.error_message}")

    elif args.command == "status":
        print(f"\n📊 ESTADO DE TRÁMITE: {args.receipt}")
        print("=" * 50)

        client.authenticate()
        status = client.check_status(args.receipt)

        for key, value in status.items():
            print(f"  {key}: {value}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
