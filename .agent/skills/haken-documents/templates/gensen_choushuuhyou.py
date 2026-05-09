#!/usr/bin/env python3
"""
源泉徴収票 (Gensen Choushuuhyou) Template
==========================================
Certificado de Retención Fiscal - Formato oficial japonés.
"""

from datetime import date


def generate_gensen_choushuuhyou(data: dict) -> str:
    """
    Genera 源泉徴収票 (Certificado de Retención Fiscal).
    Documento anual obligatorio para declaración de impuestos.
    """

    employee = data.get("employee", {})
    company = data.get("company", {})
    tax_data = data.get("tax_data", {})
    year = tax_data.get("year", date.today().year)

    # Calcular año Reiwa
    reiwa_year = year - 2018

    content = f"""
<div class="document" style="font-size: 9pt;">
    <div style="text-align: center; margin-bottom: 5mm;">
        <h1 style="font-size: 14pt; margin: 0;">令和{reiwa_year}年分 給与所得の源泉徴収票</h1>
    </div>

    <table style="width: 100%; border-collapse: collapse; border: 2px solid #000;">
        <!-- Fila 1: Información del empleado -->
        <tr>
            <td style="border: 1px solid #000; padding: 2mm; width: 15%;">
                <small>住所又は居所</small>
            </td>
            <td colspan="5" style="border: 1px solid #000; padding: 2mm;">
                {employee.get("address", "")}
            </td>
        </tr>

        <tr>
            <td style="border: 1px solid #000; padding: 2mm;">
                <small>氏名</small>
            </td>
            <td colspan="3" style="border: 1px solid #000; padding: 2mm; font-size: 11pt;">
                <strong>{employee.get("name_kanji", "")}</strong>
            </td>
            <td style="border: 1px solid #000; padding: 2mm; text-align: center;">
                <small>生年月日</small><br>
                {employee.get("birth_date", "")}
            </td>
            <td style="border: 1px solid #000; padding: 2mm; text-align: center;">
                <small>区分</small><br>
                {employee.get("category", "甲欄")}
            </td>
        </tr>

        <!-- Fila 2: Montos principales -->
        <tr style="background-color: #f5f5f5;">
            <td style="border: 1px solid #000; padding: 2mm; text-align: center;">
                <small>支払金額</small>
            </td>
            <td style="border: 1px solid #000; padding: 2mm; text-align: center;">
                <small>給与所得控除後<br>の金額</small>
            </td>
            <td style="border: 1px solid #000; padding: 2mm; text-align: center;">
                <small>所得控除の額<br>の合計額</small>
            </td>
            <td style="border: 1px solid #000; padding: 2mm; text-align: center;">
                <small>源泉徴収税額</small>
            </td>
            <td colspan="2" style="border: 1px solid #000; padding: 2mm; text-align: center;">
                <small>（摘要）</small>
            </td>
        </tr>
        <tr>
            <td style="border: 1px solid #000; padding: 3mm; text-align: right; font-size: 11pt;">
                <strong>¥{tax_data.get("gross_payment", 0):,}</strong>
            </td>
            <td style="border: 1px solid #000; padding: 3mm; text-align: right; font-size: 11pt;">
                ¥{tax_data.get("income_after_deduction", 0):,}
            </td>
            <td style="border: 1px solid #000; padding: 3mm; text-align: right; font-size: 11pt;">
                ¥{tax_data.get("total_deductions", 0):,}
            </td>
            <td style="border: 1px solid #000; padding: 3mm; text-align: right; font-size: 11pt; color: #cc0000;">
                <strong>¥{tax_data.get("withheld_tax", 0):,}</strong>
            </td>
            <td colspan="2" style="border: 1px solid #000; padding: 2mm; font-size: 8pt;">
                {tax_data.get("notes", "")}
            </td>
        </tr>

        <!-- Fila 3: Control de configuración del pago -->
        <tr>
            <td style="border: 1px solid #000; padding: 2mm;">
                <small>控除対象配偶者<br>の有無等</small>
            </td>
            <td style="border: 1px solid #000; padding: 2mm; text-align: center;">
                {tax_data.get("spouse", "無")}
            </td>
            <td style="border: 1px solid #000; padding: 2mm;">
                <small>配偶者（特別）<br>控除の額</small>
            </td>
            <td style="border: 1px solid #000; padding: 2mm; text-align: right;">
                ¥{tax_data.get("spouse_deduction", 0):,}
            </td>
            <td style="border: 1px solid #000; padding: 2mm;">
                <small>扶養親族の数</small>
            </td>
            <td style="border: 1px solid #000; padding: 2mm; text-align: center;">
                {tax_data.get("dependents", 0)}人
            </td>
        </tr>

        <!-- Fila 4: Seguros sociales -->
        <tr>
            <td colspan="2" style="border: 1px solid #000; padding: 2mm;">
                <small>社会保険料等の金額</small>
            </td>
            <td style="border: 1px solid #000; padding: 2mm; text-align: right;">
                ¥{tax_data.get("social_insurance", 0):,}
            </td>
            <td style="border: 1px solid #000; padding: 2mm;">
                <small>生命保険料の<br>控除額</small>
            </td>
            <td colspan="2" style="border: 1px solid #000; padding: 2mm; text-align: right;">
                ¥{tax_data.get("life_insurance_deduction", 0):,}
            </td>
        </tr>

        <!-- Fila 5: Seguro de terremoto -->
        <tr>
            <td colspan="2" style="border: 1px solid #000; padding: 2mm;">
                <small>地震保険料の控除額</small>
            </td>
            <td style="border: 1px solid #000; padding: 2mm; text-align: right;">
                ¥{tax_data.get("earthquake_insurance", 0):,}
            </td>
            <td style="border: 1px solid #000; padding: 2mm;">
                <small>住宅借入金等<br>特別控除の額</small>
            </td>
            <td colspan="2" style="border: 1px solid #000; padding: 2mm; text-align: right;">
                ¥{tax_data.get("housing_loan_deduction", 0):,}
            </td>
        </tr>

        <!-- Fila 6: Deducción básica -->
        <tr>
            <td colspan="2" style="border: 1px solid #000; padding: 2mm;">
                <small>基礎控除の額</small>
            </td>
            <td style="border: 1px solid #000; padding: 2mm; text-align: right;">
                ¥{tax_data.get("basic_deduction", 480000):,}
            </td>
            <td colspan="3" style="border: 1px solid #000; padding: 2mm;">
                <small>（その他控除）</small>
            </td>
        </tr>
    </table>

    <!-- Información del pagador -->
    <table style="width: 100%; border-collapse: collapse; border: 2px solid #000; margin-top: 3mm;">
        <tr>
            <td style="border: 1px solid #000; padding: 2mm; width: 15%; background-color: #f5f5f5;">
                <small>支払者</small>
            </td>
            <td style="border: 1px solid #000; padding: 3mm;">
                <div>〒{company.get("postal_code", "")}</div>
                <div>{company.get("address", "")}</div>
                <div style="font-size: 11pt; margin-top: 2mm;"><strong>{company.get("name", "")}</strong></div>
                <div>電話: {company.get("phone", "")}</div>
            </td>
            <td style="border: 1px solid #000; padding: 2mm; width: 20%; text-align: center;">
                <small>法人番号</small><br>
                {company.get("corporate_number", "")}
            </td>
        </tr>
        <tr>
            <td style="border: 1px solid #000; padding: 2mm; background-color: #f5f5f5;">
                <small>種別</small>
            </td>
            <td colspan="2" style="border: 1px solid #000; padding: 2mm;">
                給与・賞与
            </td>
        </tr>
    </table>

    <div style="margin-top: 5mm; font-size: 8pt; color: #666;">
        <p>※この源泉徴収票は、確定申告、住宅ローン控除の申請等に使用できます。</p>
        <p>※紛失した場合は再発行いたしますので、お申し出ください。</p>
        <p>※本票は電子的に作成されたものです。</p>
    </div>

    <div style="text-align: right; margin-top: 5mm;">
        <span style="border: 1px dashed #999; border-radius: 50%; width: 15mm; height: 15mm; display: inline-block; text-align: center; line-height: 15mm; font-size: 8pt; color: #999;">社印</span>
    </div>
</div>
"""

    return content


def generate_gensen_pdf(data: dict, output_dir: str = "output") -> str:
    """Genera el PDF de源泉徴収票."""
    from pathlib import Path

    content = generate_gensen_choushuuhyou(data)

    # CSS para A4
    css = """
@page { size: A4; margin: 15mm; }
body { font-family: "Yu Gothic", "MS Gothic", sans-serif; }
.document { padding: 10mm; }
"""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>源泉徴収票</title>
    <style>{css}</style>
</head>
<body>{content}</body>
</html>"""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    employee = data.get("employee", {})
    year = data.get("tax_data", {}).get("year", date.today().year)

    filename = f"gensen_choushuuhyou_{employee.get('id', 'unknown')}_{year}.html"
    filepath = output_path / filename

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)

    return str(filepath)


if __name__ == "__main__":
    # Demo
    demo_data = {
        "employee": {
            "id": "W0001",
            "name_kanji": "グエン バン アイン",
            "address": "愛知県豊田市若林町1-2-3",
            "birth_date": "1990年5月15日",
            "category": "甲欄",
        },
        "company": {
            "name": "ユニバーサル企画株式会社",
            "postal_code": "471-0834",
            "address": "愛知県豊田市土橋町7-7-7",
            "phone": "0565-XX-XXXX",
            "corporate_number": "1234567890123",
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
            "dependents": 0,
        },
    }

    filepath = generate_gensen_pdf(demo_data)
    print(f"✅ 源泉徴収票 generado: {filepath}")
