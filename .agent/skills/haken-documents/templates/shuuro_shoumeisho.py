#!/usr/bin/env python3
"""
就労証明書 (Shuuro Shoumeisho) Template
=========================================
Certificado de Historial Laboral - Para renovación de visa y otros trámites.
"""

from datetime import date


def generate_shuuro_shoumeisho(data: dict) -> str:
    """
    Genera 就労証明書 (Certificado de Historial Laboral).
    Documento frecuentemente requerido para renovación de visa de trabajo.
    """

    employee = data.get("employee", {})
    company = data.get("company", {})
    employment = data.get("employment", {})
    client = data.get("client", {})

    # Calcular año Reiwa
    today = date.today()
    reiwa_year = today.year - 2018

    content = f"""
<div class="document">
    <div class="document-date" style="text-align: right;">
        令和{reiwa_year}年{today.month}月{today.day}日
    </div>

    <h1 class="document-title" style="text-align: center; font-size: 18pt; margin: 15mm 0;">
        就 労 証 明 書
    </h1>

    <div style="text-align: center; margin-bottom: 10mm;">
        <span style="font-size: 12pt;">(Employment Certificate / Giấy Chứng Nhận Làm Việc)</span>
    </div>

    <div style="margin-bottom: 15mm;">
        <p style="text-indent: 1em; line-height: 2;">
            下記の者は、当社において就労していることを証明いたします。<br>
            <span style="font-size: 10pt; color: #666;">
            (This is to certify that the person named below is employed by our company.)
            </span>
        </p>
    </div>

    <div style="text-align: center; margin-bottom: 10mm;">
        <span style="font-size: 12pt; font-weight: bold;">記</span>
    </div>

    <table class="info-table" style="width: 100%; border-collapse: collapse;">
        <tr>
            <th style="width: 30%; background-color: #f5f5f5; border: 1px solid #333; padding: 3mm;">
                氏名<br><small>(Name)</small>
            </th>
            <td style="border: 1px solid #333; padding: 3mm; font-size: 12pt;">
                <strong>{employee.get("name_kanji", "")}</strong><br>
                {employee.get("name_romaji", "")}
            </td>
        </tr>
        <tr>
            <th style="background-color: #f5f5f5; border: 1px solid #333; padding: 3mm;">
                国籍<br><small>(Nationality)</small>
            </th>
            <td style="border: 1px solid #333; padding: 3mm;">
                {employee.get("nationality", "")}
            </td>
        </tr>
        <tr>
            <th style="background-color: #f5f5f5; border: 1px solid #333; padding: 3mm;">
                生年月日<br><small>(Date of Birth)</small>
            </th>
            <td style="border: 1px solid #333; padding: 3mm;">
                {employee.get("birth_date", "")}
            </td>
        </tr>
        <tr>
            <th style="background-color: #f5f5f5; border: 1px solid #333; padding: 3mm;">
                在留カード番号<br><small>(Residence Card No.)</small>
            </th>
            <td style="border: 1px solid #333; padding: 3mm;">
                {employee.get("zairyu_card", "")}
            </td>
        </tr>
        <tr>
            <th style="background-color: #f5f5f5; border: 1px solid #333; padding: 3mm;">
                在留資格<br><small>(Status of Residence)</small>
            </th>
            <td style="border: 1px solid #333; padding: 3mm;">
                {employee.get("visa_type", "")}
            </td>
        </tr>
        <tr>
            <th style="background-color: #f5f5f5; border: 1px solid #333; padding: 3mm;">
                雇用形態<br><small>(Employment Type)</small>
            </th>
            <td style="border: 1px solid #333; padding: 3mm;">
                派遣社員 (Dispatched Worker)
            </td>
        </tr>
        <tr>
            <th style="background-color: #f5f5f5; border: 1px solid #333; padding: 3mm;">
                雇用期間<br><small>(Employment Period)</small>
            </th>
            <td style="border: 1px solid #333; padding: 3mm;">
                {employment.get("start_date", "")} ～ {employment.get("end_date", "")}<br>
                <small>（契約更新の可能性あり / Subject to renewal）</small>
            </td>
        </tr>
        <tr>
            <th style="background-color: #f5f5f5; border: 1px solid #333; padding: 3mm;">
                就業場所<br><small>(Work Location)</small>
            </th>
            <td style="border: 1px solid #333; padding: 3mm;">
                {client.get("name", "")}<br>
                {client.get("address", "")}
            </td>
        </tr>
        <tr>
            <th style="background-color: #f5f5f5; border: 1px solid #333; padding: 3mm;">
                職種・業務内容<br><small>(Job Description)</small>
            </th>
            <td style="border: 1px solid #333; padding: 3mm;">
                {employment.get("position", "")}<br>
                {employment.get("job_description", "")}
            </td>
        </tr>
        <tr>
            <th style="background-color: #f5f5f5; border: 1px solid #333; padding: 3mm;">
                就業時間<br><small>(Working Hours)</small>
            </th>
            <td style="border: 1px solid #333; padding: 3mm;">
                {employment.get("start_time", "8:00")} ～ {employment.get("end_time", "17:00")}<br>
                週{employment.get("days_per_week", "5")}日勤務
            </td>
        </tr>
        <tr>
            <th style="background-color: #f5f5f5; border: 1px solid #333; padding: 3mm;">
                給与<br><small>(Salary)</small>
            </th>
            <td style="border: 1px solid #333; padding: 3mm;">
                時給 {employment.get("hourly_rate", "")} 円<br>
                月額約 {employment.get("monthly_estimate", "")} 円（見込み）
            </td>
        </tr>
        <tr>
            <th style="background-color: #f5f5f5; border: 1px solid #333; padding: 3mm;">
                社会保険<br><small>(Social Insurance)</small>
            </th>
            <td style="border: 1px solid #333; padding: 3mm;">
                ☑ 健康保険 ☑ 厚生年金 ☑ 雇用保険 ☑ 労災保険
            </td>
        </tr>
    </table>

    <div style="margin-top: 10mm;">
        <p style="line-height: 2;">
            上記の内容に相違ないことを証明します。<br>
            <small style="color: #666;">
            (We hereby certify that the above information is true and correct.)
            </small>
        </p>
    </div>

    <div style="text-align: right; margin-top: 15mm;">
        <div style="text-align: left; display: inline-block;">
            <div style="margin-bottom: 3mm;">
                〒{company.get("postal_code", "")}
            </div>
            <div style="margin-bottom: 3mm;">
                {company.get("address", "")}
            </div>
            <div style="margin-bottom: 3mm; font-size: 12pt;">
                <strong>{company.get("name", "")}</strong>
            </div>
            <div style="margin-bottom: 3mm;">
                代表取締役 {company.get("representative", "")}
                <span style="display: inline-block; width: 18mm; height: 18mm; border: 1px dashed #999; border-radius: 50%; text-align: center; line-height: 18mm; font-size: 8pt; color: #cc0000; margin-left: 5mm;">社印</span>
            </div>
            <div style="margin-bottom: 3mm;">
                TEL: {company.get("phone", "")}
            </div>
            <div>
                派遣事業許可番号: {company.get("permit_number", "")}
            </div>
        </div>
    </div>

    <div style="margin-top: 15mm; font-size: 9pt; color: #666; border-top: 1px solid #ddd; padding-top: 5mm;">
        <p>【注意事項 / Notes】</p>
        <ul style="margin-left: 5mm;">
            <li>本証明書の有効期限は発行日から3ヶ月間です。</li>
            <li>This certificate is valid for 3 months from the date of issue.</li>
            <li>在留資格の変更・更新については、出入国在留管理局にお問い合わせください。</li>
            <li>For changes or renewals of residence status, please contact the Immigration Bureau.</li>
        </ul>
    </div>
</div>
"""

    return content


def generate_shuuro_pdf(data: dict, output_dir: str = "output") -> str:
    """Genera el archivo HTML/PDF de就労証明書."""
    from pathlib import Path

    content = generate_shuuro_shoumeisho(data)

    css = """
@page { size: A4; margin: 20mm 25mm; }
body { font-family: "Yu Gothic", "MS Gothic", sans-serif; font-size: 11pt; line-height: 1.6; }
.document { }
"""

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>就労証明書</title>
    <style>{css}</style>
</head>
<body>{content}</body>
</html>"""

    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    employee = data.get("employee", {})
    filename = (
        f"shuuro_shoumeisho_{employee.get('id', 'unknown')}_{date.today().strftime('%Y%m%d')}.html"
    )
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
            "name_romaji": "NGUYEN VAN ANH",
            "nationality": "ベトナム",
            "birth_date": "1990年5月15日",
            "zairyu_card": "AB12345678CD",
            "visa_type": "技能実習2号",
        },
        "company": {
            "name": "ユニバーサル企画株式会社",
            "postal_code": "471-0834",
            "address": "愛知県豊田市土橋町7-7-7",
            "phone": "0565-XX-XXXX",
            "representative": "浅田 健二",
            "permit_number": "派23-303669",
        },
        "client": {
            "name": "株式会社トヨタ",
            "address": "愛知県豊田市トヨタ町1",
        },
        "employment": {
            "start_date": "2024年4月1日",
            "end_date": "2027年3月31日",
            "position": "製造作業員",
            "job_description": "自動車部品の組立作業",
            "start_time": "8:00",
            "end_time": "17:00",
            "days_per_week": 5,
            "hourly_rate": "1,200",
            "monthly_estimate": "200,000",
        },
    }

    filepath = generate_shuuro_pdf(demo_data)
    print(f"✅ 就労証明書 generado: {filepath}")
