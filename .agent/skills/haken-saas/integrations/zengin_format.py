#!/usr/bin/env python3
"""
Haken SaaS - Formato Zengin (全銀フォーマット)
=============================================
Generador de archivos de transferencia bancaria en formato Zengin.
Utilizado para pago masivo de nóminas via振込.

Especificación: JBA (Japanese Bankers Association) File Format
- Encoding: Shift-JIS
- Fixed-width records
- Record length: 120 bytes
"""

from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path

# Mapeo Zengin de caracteres
ZENGIN_KANA_MAP = {
    "ア": "ｱ",
    "イ": "ｲ",
    "ウ": "ｳ",
    "エ": "ｴ",
    "オ": "ｵ",
    "カ": "ｶ",
    "キ": "ｷ",
    "ク": "ｸ",
    "ケ": "ｹ",
    "コ": "ｺ",
    "サ": "ｻ",
    "シ": "ｼ",
    "ス": "ｽ",
    "セ": "ｾ",
    "ソ": "ｿ",
    "タ": "ﾀ",
    "チ": "ﾁ",
    "ツ": "ﾂ",
    "テ": "ﾃ",
    "ト": "ﾄ",
    "ナ": "ﾅ",
    "ニ": "ﾆ",
    "ヌ": "ﾇ",
    "ネ": "ﾈ",
    "ノ": "ﾉ",
    "ハ": "ﾊ",
    "ヒ": "ﾋ",
    "フ": "ﾌ",
    "ヘ": "ﾍ",
    "ホ": "ﾎ",
    "マ": "ﾏ",
    "ミ": "ﾐ",
    "ム": "ﾑ",
    "メ": "ﾒ",
    "モ": "ﾓ",
    "ヤ": "ﾔ",
    "ユ": "ﾕ",
    "ヨ": "ﾖ",
    "ラ": "ﾗ",
    "リ": "ﾘ",
    "ル": "ﾙ",
    "レ": "ﾚ",
    "ロ": "ﾛ",
    "ワ": "ﾜ",
    "ヲ": "ｦ",
    "ン": "ﾝ",
    "ガ": "ｶﾞ",
    "ギ": "ｷﾞ",
    "グ": "ｸﾞ",
    "ゲ": "ｹﾞ",
    "ゴ": "ｺﾞ",
    "ザ": "ｻﾞ",
    "ジ": "ｼﾞ",
    "ズ": "ｽﾞ",
    "ゼ": "ｾﾞ",
    "ゾ": "ｿﾞ",
    "ダ": "ﾀﾞ",
    "ヂ": "ﾁﾞ",
    "ヅ": "ﾂﾞ",
    "デ": "ﾃﾞ",
    "ド": "ﾄﾞ",
    "バ": "ﾊﾞ",
    "ビ": "ﾋﾞ",
    "ブ": "ﾌﾞ",
    "ベ": "ﾍﾞ",
    "ボ": "ﾎﾞ",
    "パ": "ﾊﾟ",
    "ピ": "ﾋﾟ",
    "プ": "ﾌﾟ",
    "ペ": "ﾍﾟ",
    "ポ": "ﾎﾟ",
    "ァ": "ｧ",
    "ィ": "ｨ",
    "ゥ": "ｩ",
    "ェ": "ｪ",
    "ォ": "ｫ",
    "ャ": "ｬ",
    "ュ": "ｭ",
    "ョ": "ｮ",
    "ッ": "ｯ",
    "ー": "ｰ",
    "　": " ",
    " ": " ",
    "ヴ": "ｳﾞ",
}


def to_half_width_kana(text: str) -> str:
    """Convierte katakana full-width a half-width."""
    result = ""
    for char in text:
        result += ZENGIN_KANA_MAP.get(char, char)
    return result


def pad_right(text: str, length: int) -> str:
    """Rellena con espacios a la derecha."""
    text = text[:length]  # Truncar si es más largo
    return text.ljust(length)


def pad_left_zero(number: int, length: int) -> str:
    """Rellena con ceros a la izquierda."""
    return str(number).zfill(length)[:length]


@dataclass
class ZenginPayment:
    """Registro de pago individual."""

    bank_code: str  # 銀行コード (4 dígitos)
    bank_name: str  # 銀行名
    branch_code: str  # 支店コード (3 dígitos)
    branch_name: str  # 支店名
    account_type: str  # 口座種別 (1=普通, 2=当座, 4=貯蓄)
    account_number: str  # 口座番号 (7 dígitos)
    account_holder: str  # 口座名義 (カタカナ)
    amount: int  # 金額
    employee_code: str = ""  # 従業員番号 (opcional)


@dataclass
class ZenginHeader:
    """Registro de cabecera (Header Record)."""

    record_type: str = "1"  # Data区分: 1=Header
    transfer_type: str = "21"  # 振込種別: 21=総合振込
    classification: str = "0"  # 依頼人区分: 0=その他
    company_code: str = ""  # 会社コード (10桁)
    company_name: str = ""  # 会社名 (40桁, カタカナ)
    transfer_date: str = ""  # 振込日 (MMDD)
    bank_code: str = ""  # 仕向銀行コード (4桁)
    bank_name: str = ""  # 仕向銀行名 (15桁)
    branch_code: str = ""  # 仕向支店コード (3桁)
    branch_name: str = ""  # 仕向支店名 (15桁)
    account_type: str = "1"  # 口座種別
    account_number: str = ""  # 口座番号 (7桁)


@dataclass
class ZenginTrailer:
    """Registro de trailer (Trailer Record)."""

    record_type: str = "8"
    total_count: int = 0
    total_amount: int = 0


class ZenginGenerator:
    """
    Generador de archivos Zengin para transferencias bancarias.
    """

    RECORD_LENGTH = 120
    ENCODING = "shift_jis"

    def __init__(self, output_dir: str = "artifacts/zengin"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] 💴 {message}")

    # ═══════════════════════════════════════════════════════════════
    # GENERACIÓN DE REGISTROS
    # ═══════════════════════════════════════════════════════════════

    def generate_header_record(self, header: ZenginHeader) -> str:
        """
        Genera el registro de cabecera (120 bytes).

        Formato:
        Pos.  1     : Data区分 (1)
        Pos.  2-3   : 振込種別コード (21)
        Pos.  4     : 依頼人区分 (0)
        Pos.  5-14  : 会社コード
        Pos. 15-54  : 会社名
        Pos. 55-58  : 振込日 (MMDD)
        Pos. 59-62  : 仕向銀行コード
        Pos. 63-77  : 仕向銀行名
        Pos. 78-80  : 仕向支店コード
        Pos. 81-95  : 仕向支店名
        Pos. 96     : 口座種別
        Pos. 97-103 : 口座番号
        Pos. 104-120: ダミー
        """
        record = (
            header.record_type  # 1: Data区分
            + header.transfer_type  # 2-3: 振込種別
            + header.classification  # 4: 依頼人区分
            + pad_right(header.company_code, 10)  # 5-14: 会社コード
            + pad_right(to_half_width_kana(header.company_name), 40)  # 15-54: 会社名
            + header.transfer_date  # 55-58: 振込日
            + pad_left_zero(int(header.bank_code), 4)  # 59-62: 銀行コード
            + pad_right(to_half_width_kana(header.bank_name), 15)  # 63-77: 銀行名
            + pad_left_zero(int(header.branch_code), 3)  # 78-80: 支店コード
            + pad_right(to_half_width_kana(header.branch_name), 15)  # 81-95: 支店名
            + header.account_type  # 96: 口座種別
            + pad_left_zero(int(header.account_number), 7)  # 97-103: 口座番号
            + " " * 17  # 104-120: ダミー
        )
        return record

    def generate_data_record(self, payment: ZenginPayment, seq: int) -> str:
        """
        Genera un registro de datos (120 bytes).

        Formato:
        Pos.  1     : Data区分 (2)
        Pos.  2-5   : 被仕向銀行コード
        Pos.  6-20  : 被仕向銀行名
        Pos. 21-23  : 被仕向支店コード
        Pos. 24-38  : 被仕向支店名
        Pos. 39-42  : ダミー
        Pos. 43     : 口座種別
        Pos. 44-50  : 口座番号
        Pos. 51-80  : 口座名義
        Pos. 81-90  : 金額
        Pos. 91     : 新規コード (0=新規以外)
        Pos. 92-111 : 従業員コード/EDI情報
        Pos. 112-120: ダミー
        """
        # Mapeo de tipo de cuenta
        account_type_map = {"普通": "1", "当座": "2", "貯蓄": "4"}
        account_type = account_type_map.get(payment.account_type, "1")

        record = (
            "2"  # 1: Data区分
            + pad_left_zero(int(payment.bank_code), 4)  # 2-5: 銀行コード
            + pad_right(to_half_width_kana(payment.bank_name), 15)  # 6-20: 銀行名
            + pad_left_zero(int(payment.branch_code), 3)  # 21-23: 支店コード
            + pad_right(to_half_width_kana(payment.branch_name), 15)  # 24-38: 支店名
            + " " * 4  # 39-42: ダミー
            + account_type  # 43: 口座種別
            + pad_left_zero(int(payment.account_number), 7)  # 44-50: 口座番号
            + pad_right(to_half_width_kana(payment.account_holder), 30)  # 51-80: 口座名義
            + pad_left_zero(payment.amount, 10)  # 81-90: 金額
            + "0"  # 91: 新規コード
            + pad_right(payment.employee_code, 20)  # 92-111: 従業員コード
            + " " * 9  # 112-120: ダミー
        )
        return record

    def generate_trailer_record(self, trailer: ZenginTrailer) -> str:
        """
        Genera el registro de trailer (120 bytes).

        Formato:
        Pos.  1     : Data区分 (8)
        Pos.  2-7   : 合計件数
        Pos.  8-19  : 合計金額
        Pos. 20-120 : ダミー
        """
        record = (
            trailer.record_type  # 1: Data区分
            + pad_left_zero(trailer.total_count, 6)  # 2-7: 合計件数
            + pad_left_zero(trailer.total_amount, 12)  # 8-19: 合計金額
            + " " * 101  # 20-120: ダミー
        )
        return record

    def generate_end_record(self) -> str:
        """Genera el registro de fin (End Record)."""
        return "9" + " " * 119

    # ═══════════════════════════════════════════════════════════════
    # GENERACIÓN DE ARCHIVO COMPLETO
    # ═══════════════════════════════════════════════════════════════

    def generate_file(
        self,
        company_code: str,
        company_name: str,
        bank_code: str,
        bank_name: str,
        branch_code: str,
        branch_name: str,
        account_type: str,
        account_number: str,
        transfer_date: date,
        payments: list[ZenginPayment],
    ) -> str:
        """
        Genera un archivo Zengin completo.

        Returns:
            Ruta del archivo generado
        """

        # Header
        header = ZenginHeader(
            company_code=company_code,
            company_name=company_name,
            transfer_date=transfer_date.strftime("%m%d"),
            bank_code=bank_code,
            bank_name=bank_name,
            branch_code=branch_code,
            branch_name=branch_name,
            account_type="1" if account_type == "普通" else "2",
            account_number=account_number,
        )

        # Trailer
        trailer = ZenginTrailer(
            total_count=len(payments),
            total_amount=sum(p.amount for p in payments),
        )

        # Generar registros
        records = []
        records.append(self.generate_header_record(header))

        for i, payment in enumerate(payments, 1):
            records.append(self.generate_data_record(payment, i))

        records.append(self.generate_trailer_record(trailer))
        records.append(self.generate_end_record())

        # Escribir archivo
        filename = (
            f"zengin_{transfer_date.strftime('%Y%m%d')}_{datetime.now().strftime('%H%M%S')}.txt"
        )
        filepath = self.output_dir / filename

        # Usar CRLF como terminador de línea (requerido por Zengin)
        content = "\r\n".join(records) + "\r\n"

        with open(filepath, "w", encoding=self.ENCODING, newline="") as f:
            f.write(content)

        self.log(f"Archivo Zengin generado: {filepath}")
        self.log(f"  件数: {trailer.total_count}件")
        self.log(f"  合計: ¥{trailer.total_amount:,}")

        return str(filepath)

    # ═══════════════════════════════════════════════════════════════
    # INTEGRACIÓN CON PAYROLL
    # ═══════════════════════════════════════════════════════════════

    def generate_from_payroll(
        self,
        tenant_info: dict,
        workers: list[dict],
        payroll_records: list[dict],
        transfer_date: date,
    ) -> str:
        """
        Genera archivo Zengin desde registros de nómina.

        Args:
            tenant_info: Información del tenant (banco, cuenta, etc.)
            workers: Lista de trabajadores con datos bancarios
            payroll_records: Registros de nómina con net_salary
            transfer_date: Fecha de transferencia

        Returns:
            Ruta del archivo generado
        """
        # Crear mapeo de workers por ID
        worker_map = {w["id"]: w for w in workers}

        # Crear pagos
        payments = []
        for record in payroll_records:
            worker = worker_map.get(record["worker_id"])
            if not worker:
                continue

            if int(record.get("net_salary", 0)) <= 0:
                continue

            payment = ZenginPayment(
                bank_code=worker.get("bank_code", ""),
                bank_name=worker.get("bank_name", ""),
                branch_code=worker.get("branch_code", ""),
                branch_name=worker.get("branch_name", ""),
                account_type=worker.get("account_type", "普通"),
                account_number=worker.get("account_number", ""),
                account_holder=worker.get("account_holder", worker.get("name_kana", "")),
                amount=int(record["net_salary"]),
                employee_code=record["worker_id"],
            )
            payments.append(payment)

        if not payments:
            raise ValueError("No hay pagos válidos para generar")

        return self.generate_file(
            company_code=tenant_info.get("company_code", ""),
            company_name=tenant_info.get("name", ""),
            bank_code=tenant_info.get("bank_code", ""),
            bank_name=tenant_info.get("bank_name", ""),
            branch_code=tenant_info.get("branch_code", ""),
            branch_name=tenant_info.get("branch_name", ""),
            account_type=tenant_info.get("account_type", "普通"),
            account_number=tenant_info.get("account_number", ""),
            transfer_date=transfer_date,
            payments=payments,
        )

    # ═══════════════════════════════════════════════════════════════
    # VALIDACIÓN
    # ═══════════════════════════════════════════════════════════════

    def validate_file(self, filepath: str) -> dict:
        """
        Valida un archivo Zengin existente.

        Returns:
            Diccionario con resultado de validación
        """
        errors = []
        warnings = []

        try:
            with open(filepath, encoding=self.ENCODING) as f:
                lines = f.readlines()
        except Exception as e:
            return {"valid": False, "errors": [f"No se pudo leer archivo: {e}"]}

        if len(lines) < 3:
            errors.append("Archivo muy corto (mínimo 3 registros: header, data, trailer)")
            return {"valid": False, "errors": errors}

        # Validar header
        header = lines[0].rstrip("\r\n")
        if len(header) != self.RECORD_LENGTH:
            errors.append(
                f"Header incorrecto: {len(header)} bytes (esperado: {self.RECORD_LENGTH})"
            )
        if not header.startswith("1"):
            errors.append("Header debe comenzar con '1'")

        # Validar registros de datos
        data_count = 0
        total_amount = 0

        for i, line in enumerate(lines[1:-2], 2):
            record = line.rstrip("\r\n")
            if len(record) != self.RECORD_LENGTH:
                errors.append(f"Registro {i}: longitud incorrecta ({len(record)} bytes)")

            if record.startswith("2"):
                data_count += 1
                try:
                    amount = int(record[80:90])
                    total_amount += amount
                except ValueError:
                    errors.append(f"Registro {i}: monto inválido")

        # Validar trailer
        trailer = lines[-2].rstrip("\r\n")
        if not trailer.startswith("8"):
            errors.append("Trailer debe comenzar con '8'")
        else:
            try:
                trailer_count = int(trailer[1:7])
                trailer_amount = int(trailer[7:19])

                if trailer_count != data_count:
                    errors.append(
                        f"Conteo inconsistente: header={trailer_count}, real={data_count}"
                    )
                if trailer_amount != total_amount:
                    errors.append(
                        f"Monto inconsistente: header={trailer_amount}, real={total_amount}"
                    )
            except ValueError:
                errors.append("Trailer: valores numéricos inválidos")

        # Validar end record
        end = lines[-1].rstrip("\r\n")
        if not end.startswith("9"):
            errors.append("End record debe comenzar con '9'")

        return {
            "valid": len(errors) == 0,
            "errors": errors,
            "warnings": warnings,
            "statistics": {
                "total_records": data_count,
                "total_amount": total_amount,
            },
        }


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Generador de Archivos Zengin (全銀フォーマット)")

    subparsers = parser.add_subparsers(dest="command")

    # Generate command
    gen_parser = subparsers.add_parser("generate", help="Generar archivo Zengin")
    gen_parser.add_argument("--data", required=True, help="Archivo JSON con datos")
    gen_parser.add_argument("--date", help="Fecha de transferencia (YYYY-MM-DD)")

    # Validate command
    val_parser = subparsers.add_parser("validate", help="Validar archivo Zengin")
    val_parser.add_argument("--file", required=True, help="Archivo a validar")

    # Demo command
    subparsers.add_parser("demo", help="Generar archivo de demostración")

    args = parser.parse_args()

    generator = ZenginGenerator()

    if args.command == "demo":
        # Datos de demostración
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

        print(f"\n✅ Archivo de demostración generado: {filepath}")

        # Validar
        result = generator.validate_file(filepath)
        print(f"\n📋 Validación: {'✅ VÁLIDO' if result['valid'] else '❌ INVÁLIDO'}")
        if result["errors"]:
            for err in result["errors"]:
                print(f"   ❌ {err}")

    elif args.command == "validate" and args.file:
        result = generator.validate_file(args.file)
        print("\n📋 VALIDACIÓN DE ARCHIVO ZENGIN")
        print("=" * 50)
        print(f"Archivo: {args.file}")
        print(f"Estado: {'✅ VÁLIDO' if result['valid'] else '❌ INVÁLIDO'}")

        if result["errors"]:
            print("\n❌ Errores:")
            for err in result["errors"]:
                print(f"   • {err}")

        print("\n📊 Estadísticas:")
        print(f"   件数: {result['statistics']['total_records']}件")
        print(f"   合計: ¥{result['statistics']['total_amount']:,}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
