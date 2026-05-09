#!/usr/bin/env python3
"""
Haken Documents - Generador PDF A4
===================================
Genera documentos PDF en formato A4 vertical (210mm × 297mm).
Diseñado para documentos oficiales japoneses de 人材派遣.
"""

from dataclasses import dataclass
from datetime import datetime, date
from pathlib import Path
import json


# ═══════════════════════════════════════════════════════════════
# CONFIGURACIÓN A4
# ═══════════════════════════════════════════════════════════════


@dataclass
class A4Config:
    """Configuración de página A4."""

    # Dimensiones en mm
    width_mm: float = 210.0
    height_mm: float = 297.0

    # Márgenes en mm
    margin_top: float = 20.0
    margin_bottom: float = 20.0
    margin_left: float = 25.0
    margin_right: float = 25.0

    # Fuentes
    font_family: str = "Yu Gothic, MS Gothic, sans-serif"
    font_size_body: int = 11
    font_size_title: int = 16
    font_size_subtitle: int = 14
    font_size_small: int = 9

    # Colores
    color_text: str = "#000000"
    color_border: str = "#333333"
    color_header_bg: str = "#f5f5f5"

    @property
    def content_width(self) -> float:
        return self.width_mm - self.margin_left - self.margin_right

    @property
    def content_height(self) -> float:
        return self.height_mm - self.margin_top - self.margin_bottom


# ═══════════════════════════════════════════════════════════════
# ESTILOS CSS BASE
# ═══════════════════════════════════════════════════════════════

A4_CSS = """
@page {
    size: A4;
    margin: 20mm 25mm;
}

* {
    margin: 0;
    padding: 0;
    box-sizing: border-box;
}

body {
    font-family: "Yu Gothic", "MS Gothic", "Hiragino Kaku Gothic Pro", sans-serif;
    font-size: 11pt;
    line-height: 1.6;
    color: #000;
    background: #fff;
}

.document {
    width: 210mm;
    min-height: 297mm;
    padding: 20mm 25mm;
    margin: 0 auto;
    background: #fff;
}

.document-number {
    text-align: right;
    font-size: 9pt;
    color: #666;
    margin-bottom: 10mm;
}

.document-date {
    text-align: right;
    font-size: 10pt;
    margin-bottom: 15mm;
}

.document-title {
    text-align: center;
    font-size: 18pt;
    font-weight: bold;
    margin-bottom: 15mm;
    letter-spacing: 3pt;
}

.document-subtitle {
    text-align: center;
    font-size: 12pt;
    margin-bottom: 10mm;
}

.recipient {
    margin-bottom: 10mm;
}

.recipient-name {
    font-size: 14pt;
    border-bottom: 1px solid #000;
    display: inline-block;
    min-width: 50%;
    padding-bottom: 2mm;
}

.recipient-suffix {
    font-size: 12pt;
    margin-left: 5mm;
}

.issuer {
    text-align: right;
    margin-top: 15mm;
    margin-bottom: 15mm;
}

.issuer-line {
    margin-bottom: 3mm;
}

.seal-placeholder {
    display: inline-block;
    width: 20mm;
    height: 20mm;
    border: 1px dashed #999;
    border-radius: 50%;
    text-align: center;
    line-height: 20mm;
    font-size: 8pt;
    color: #999;
    margin-left: 5mm;
    vertical-align: middle;
}

.content-section {
    margin-bottom: 10mm;
}

.section-title {
    font-size: 12pt;
    font-weight: bold;
    margin-bottom: 5mm;
    padding-bottom: 2mm;
    border-bottom: 1px solid #333;
}

.info-table {
    width: 100%;
    border-collapse: collapse;
    margin-bottom: 10mm;
}

.info-table th,
.info-table td {
    border: 1px solid #333;
    padding: 3mm 4mm;
    text-align: left;
    vertical-align: top;
}

.info-table th {
    background-color: #f5f5f5;
    font-weight: normal;
    width: 30%;
}

.info-table td {
    width: 70%;
}

.certification-text {
    margin: 10mm 0;
    text-indent: 1em;
    line-height: 2;
}

.signature-area {
    margin-top: 20mm;
    text-align: right;
}

.signature-line {
    display: inline-block;
    min-width: 60mm;
    border-bottom: 1px solid #000;
    margin-left: 10mm;
}

.footer {
    position: absolute;
    bottom: 15mm;
    left: 25mm;
    right: 25mm;
    font-size: 8pt;
    color: #666;
    text-align: center;
    border-top: 1px solid #ddd;
    padding-top: 3mm;
}

.hanko-red {
    color: #cc0000;
    border-color: #cc0000;
}

.note {
    font-size: 9pt;
    color: #666;
    margin-top: 5mm;
}

.checkbox {
    display: inline-block;
    width: 4mm;
    height: 4mm;
    border: 1px solid #000;
    margin-right: 2mm;
    vertical-align: middle;
}

.checkbox.checked::after {
    content: "✓";
    font-size: 10pt;
}

/* Tablas específicas */
.payroll-table {
    width: 100%;
    border-collapse: collapse;
    font-size: 9pt;
}

.payroll-table th,
.payroll-table td {
    border: 1px solid #333;
    padding: 2mm;
    text-align: center;
}

.payroll-table .amount {
    text-align: right;
    font-family: monospace;
}

.payroll-table .category-header {
    background-color: #e0e0e0;
    font-weight: bold;
}

.payroll-table .subtotal {
    background-color: #f0f0f0;
}

.payroll-table .total {
    background-color: #d0d0d0;
    font-weight: bold;
}

/* Formato vertical (縦書き) para documentos formales */
.vertical-text {
    writing-mode: vertical-rl;
    text-orientation: upright;
}

@media print {
    .document {
        page-break-after: always;
    }
}
"""


# ═══════════════════════════════════════════════════════════════
# GENERADOR HTML/PDF
# ═══════════════════════════════════════════════════════════════


class DocumentGenerator:
    """
    Generador de documentos oficiales en formato A4.
    """

    def __init__(self, output_dir: str = "output"):
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.config = A4Config()

    def log(self, message: str) -> None:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        print(f"[{timestamp}] 📄 {message}")

    def _generate_document_number(self, prefix: str = "DOC") -> str:
        """Genera número de documento único."""
        return f"{prefix}-{datetime.now().strftime('%Y%m%d')}-{datetime.now().strftime('%H%M%S')}"

    def _format_date_japanese(self, d: date) -> str:
        """Formatea fecha en estilo japonés (令和X年Y月Z日)."""
        # Calcular año Reiwa (令和 comenzó en 2019)
        reiwa_year = d.year - 2018
        return f"令和{reiwa_year}年{d.month}月{d.day}日"

    def _format_date_western(self, d: date) -> str:
        """Formatea fecha en estilo occidental."""
        return f"{d.year}年{d.month}月{d.day}日"

    def _wrap_html(self, content: str, title: str = "Document") -> str:
        """Envuelve contenido en estructura HTML completa."""
        return f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
{A4_CSS}
    </style>
</head>
<body>
{content}
</body>
</html>"""

    def _save_html(self, html: str, filename: str) -> str:
        """Guarda documento HTML."""
        filepath = self.output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(html)
        self.log(f"HTML guardado: {filepath}")
        return str(filepath)

    def _save_json(self, data: dict, filename: str) -> str:
        """Guarda datos en JSON."""
        filepath = self.output_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False, default=str)
        return str(filepath)

    # ═══════════════════════════════════════════════════════════════
    # GENERADORES DE DOCUMENTOS ESPECÍFICOS
    # ═══════════════════════════════════════════════════════════════

    def generate_zaishoku_shoumeisho(self, data: dict) -> str:
        """
        Genera 在職証明書 (Certificado de Empleo Actual).
        """
        doc_number = self._generate_document_number("ZS")
        today = self._format_date_japanese(date.today())

        employee = data.get("employee", {})
        company = data.get("company", {})
        employment = data.get("employment", {})

        content = f"""
<div class="document">
    <div class="document-number">文書番号: {doc_number}</div>
    <div class="document-date">{today}</div>

    <h1 class="document-title">在 職 証 明 書</h1>

    <div class="recipient">
        <span class="recipient-name">{employee.get("name_kanji", "")}</span>
        <span class="recipient-suffix">殿</span>
    </div>

    <div class="certification-text">
        下記の者は、当社に在職していることを証明いたします。
    </div>

    <table class="info-table">
        <tr>
            <th>氏名</th>
            <td>{employee.get("name_kanji", "")}</td>
        </tr>
        <tr>
            <th>フリガナ</th>
            <td>{employee.get("name_kana", "")}</td>
        </tr>
        <tr>
            <th>生年月日</th>
            <td>{employee.get("birth_date", "")}</td>
        </tr>
        <tr>
            <th>住所</th>
            <td>{employee.get("address", "")}</td>
        </tr>
        <tr>
            <th>雇用形態</th>
            <td>派遣社員</td>
        </tr>
        <tr>
            <th>入社年月日</th>
            <td>{employment.get("start_date", "")}</td>
        </tr>
        <tr>
            <th>職種</th>
            <td>{employment.get("position", "")}</td>
        </tr>
        <tr>
            <th>就業場所</th>
            <td>{employment.get("workplace", data.get("client", {}).get("name", ""))}</td>
        </tr>
        <tr>
            <th>月額給与</th>
            <td>約 {employment.get("monthly_salary", "")} 円</td>
        </tr>
    </table>

    <div class="content-section">
        <p>上記の内容に相違ないことを証明します。</p>
    </div>

    <div class="issuer">
        <div class="issuer-line">〒{company.get("postal_code", "")}</div>
        <div class="issuer-line">{company.get("address", "")}</div>
        <div class="issuer-line">{company.get("name", "")}</div>
        <div class="issuer-line">代表取締役 {company.get("representative", "")}</div>
        <div class="issuer-line">
            TEL: {company.get("phone", "")}
            <span class="seal-placeholder hanko-red">社印</span>
        </div>
    </div>

    <div class="note">
        ※本証明書の有効期限は発行日より3ヶ月間です。<br>
        ※許可番号: {company.get("permit_number", "")}
    </div>

    <div class="footer">
        {company.get("name", "")} | 派遣事業許可番号: {company.get("permit_number", "")}
    </div>
</div>
"""

        html = self._wrap_html(content, "在職証明書")
        filename = f"zaishoku_shoumeisho_{employee.get('id', 'unknown')}_{date.today().strftime('%Y%m%d')}.html"
        return self._save_html(html, filename)

    def generate_taishoku_shoumeisho(self, data: dict) -> str:
        """
        Genera 退職証明書 (Certificado de Retiro).
        Según 労働基準法第22条.
        """
        doc_number = self._generate_document_number("TS")
        today = self._format_date_japanese(date.today())

        employee = data.get("employee", {})
        company = data.get("company", {})
        employment = data.get("employment", {})
        retirement = data.get("retirement", {})

        # Razón de retiro con checkboxes
        reason = retirement.get("reason", "自己都合")
        reasons_list = [
            ("自己都合による退職", reason == "自己都合"),
            ("契約期間満了", reason == "契約満了"),
            ("会社都合による退職", reason == "会社都合"),
            ("定年退職", reason == "定年"),
            ("その他", reason not in ["自己都合", "契約満了", "会社都合", "定年"]),
        ]

        reasons_html = ""
        for text, checked in reasons_list:
            checkbox = "checked" if checked else ""
            reasons_html += f'<div><span class="checkbox {checkbox}"></span> {text}</div>'

        content = f"""
<div class="document">
    <div class="document-number">文書番号: {doc_number}</div>
    <div class="document-date">{today}</div>

    <h1 class="document-title">退 職 証 明 書</h1>

    <div class="recipient">
        <span class="recipient-name">{employee.get("name_kanji", "")}</span>
        <span class="recipient-suffix">殿</span>
    </div>

    <div class="certification-text">
        下記の者は、以下の事由により、当社を{retirement.get("date", "")}に退職したことを証明します。
    </div>

    <table class="info-table">
        <tr>
            <th>氏名</th>
            <td>{employee.get("name_kanji", "")}</td>
        </tr>
        <tr>
            <th>生年月日</th>
            <td>{employee.get("birth_date", "")}</td>
        </tr>
        <tr>
            <th>住所</th>
            <td>{employee.get("address", "")}</td>
        </tr>
        <tr>
            <th>使用期間</th>
            <td>{employment.get("start_date", "")} ～ {retirement.get("date", "")}</td>
        </tr>
        <tr>
            <th>業務の種類</th>
            <td>{employment.get("position", "")}</td>
        </tr>
        <tr>
            <th>地位</th>
            <td>{employment.get("title", "派遣社員")}</td>
        </tr>
        <tr>
            <th>最終給与</th>
            <td>時給 {employment.get("hourly_rate", "")} 円</td>
        </tr>
    </table>

    <div class="content-section">
        <div class="section-title">退職事由</div>
        {reasons_html}
        <div style="margin-top: 5mm;">
            具体的理由: {retirement.get("detail", "")}
        </div>
    </div>

    <div class="content-section">
        <p>上記の内容に相違ないことを証明します。</p>
    </div>

    <div class="issuer">
        <div class="issuer-line">〒{company.get("postal_code", "")}</div>
        <div class="issuer-line">{company.get("address", "")}</div>
        <div class="issuer-line">{company.get("name", "")}</div>
        <div class="issuer-line">代表取締役 {company.get("representative", "")}</div>
        <div class="issuer-line">
            TEL: {company.get("phone", "")}
            <span class="seal-placeholder hanko-red">社印</span>
        </div>
    </div>

    <div class="note">
        ※本証明書は労働基準法第22条に基づき発行されたものです。<br>
        ※記載事項は本人の請求に基づく項目のみを記載しています。<br>
        ※許可番号: {company.get("permit_number", "")}
    </div>

    <div class="footer">
        {company.get("name", "")} | 派遣事業許可番号: {company.get("permit_number", "")}
    </div>
</div>
"""

        html = self._wrap_html(content, "退職証明書")
        filename = f"taishoku_shoumeisho_{employee.get('id', 'unknown')}_{date.today().strftime('%Y%m%d')}.html"
        return self._save_html(html, filename)

    def generate_kobetsu_keiyakusho(self, data: dict) -> str:
        """
        Genera 個別契約書 (Contrato Individual de派遣).
        """
        doc_number = self._generate_document_number("KK")
        today = self._format_date_japanese(date.today())

        data.get("employee", {})
        company = data.get("company", {})  # 派遣元
        client = data.get("client", {})  # 派遣先
        contract = data.get("contract", {})

        content = f"""
<div class="document">
    <div class="document-number">契約番号: {doc_number}</div>
    <div class="document-date">{today}</div>

    <h1 class="document-title">労働者派遣個別契約書</h1>

    <div class="certification-text">
        {company.get("name", "")}（以下「甲」という）と{client.get("name", "")}（以下「乙」という）は、
        労働者派遣法に基づき、以下の条件にて労働者派遣契約を締結する。
    </div>

    <table class="info-table">
        <tr>
            <th colspan="2" style="background-color: #d0d0d0; text-align: center;">派遣元事業主（甲）</th>
        </tr>
        <tr>
            <th>事業所名称</th>
            <td>{company.get("name", "")}</td>
        </tr>
        <tr>
            <th>許可番号</th>
            <td>{company.get("permit_number", "")}</td>
        </tr>
        <tr>
            <th>所在地</th>
            <td>{company.get("address", "")}</td>
        </tr>
        <tr>
            <th>派遣元責任者</th>
            <td>{company.get("manager", company.get("representative", ""))}</td>
        </tr>
    </table>

    <table class="info-table">
        <tr>
            <th colspan="2" style="background-color: #d0d0d0; text-align: center;">派遣先事業主（乙）</th>
        </tr>
        <tr>
            <th>事業所名称</th>
            <td>{client.get("name", "")}</td>
        </tr>
        <tr>
            <th>所在地</th>
            <td>{client.get("address", "")}</td>
        </tr>
        <tr>
            <th>派遣先責任者</th>
            <td>{client.get("manager", "")}</td>
        </tr>
        <tr>
            <th>指揮命令者</th>
            <td>{client.get("supervisor", "")}</td>
        </tr>
    </table>

    <table class="info-table">
        <tr>
            <th colspan="2" style="background-color: #d0d0d0; text-align: center;">派遣条件</th>
        </tr>
        <tr>
            <th>派遣期間</th>
            <td>{contract.get("start_date", "")} ～ {contract.get("end_date", "")}</td>
        </tr>
        <tr>
            <th>抵触日</th>
            <td>{contract.get("teishoku_bi", "")}</td>
        </tr>
        <tr>
            <th>業務内容</th>
            <td>{contract.get("job_description", "")}</td>
        </tr>
        <tr>
            <th>就業場所</th>
            <td>{contract.get("workplace", client.get("address", ""))}</td>
        </tr>
        <tr>
            <th>就業日</th>
            <td>{contract.get("work_days", "月曜日～金曜日")}</td>
        </tr>
        <tr>
            <th>就業時間</th>
            <td>{contract.get("work_hours", "9:00～18:00")}（休憩{contract.get("break_time", "60")}分）</td>
        </tr>
        <tr>
            <th>時間外労働</th>
            <td>{contract.get("overtime", "有（36協定の範囲内）")}</td>
        </tr>
    </table>

    <table class="info-table">
        <tr>
            <th colspan="2" style="background-color: #d0d0d0; text-align: center;">派遣料金</th>
        </tr>
        <tr>
            <th>基本単価</th>
            <td>{contract.get("billing_rate", "")} 円/時間</td>
        </tr>
        <tr>
            <th>時間外単価</th>
            <td>{contract.get("overtime_rate", "")} 円/時間（125%）</td>
        </tr>
        <tr>
            <th>深夜単価</th>
            <td>{contract.get("night_rate", "")} 円/時間（125%）</td>
        </tr>
        <tr>
            <th>休日単価</th>
            <td>{contract.get("holiday_rate", "")} 円/時間（135%）</td>
        </tr>
        <tr>
            <th>支払条件</th>
            <td>月末締め、翌月{contract.get("payment_day", "末日")}払い</td>
        </tr>
    </table>

    <div class="content-section">
        <div class="section-title">苦情処理</div>
        <table class="info-table">
            <tr>
                <th>派遣元苦情処理担当</th>
                <td>{company.get("complaint_handler", "")} TEL: {company.get("phone", "")}</td>
            </tr>
            <tr>
                <th>派遣先苦情処理担当</th>
                <td>{client.get("complaint_handler", "")} TEL: {client.get("phone", "")}</td>
            </tr>
        </table>
    </div>

    <div class="content-section" style="margin-top: 15mm;">
        <p>上記の条件にて労働者派遣契約を締結することに合意します。</p>
    </div>

    <div style="display: flex; justify-content: space-between; margin-top: 15mm;">
        <div style="width: 45%;">
            <div>甲（派遣元）</div>
            <div class="issuer-line">{company.get("name", "")}</div>
            <div class="issuer-line">代表取締役 {company.get("representative", "")}</div>
            <div class="signature-line"></div>
            <span class="seal-placeholder hanko-red">印</span>
        </div>
        <div style="width: 45%;">
            <div>乙（派遣先）</div>
            <div class="issuer-line">{client.get("name", "")}</div>
            <div class="issuer-line">代表取締役 {client.get("representative", "")}</div>
            <div class="signature-line"></div>
            <span class="seal-placeholder hanko-red">印</span>
        </div>
    </div>

    <div class="footer">
        本契約書は2通作成し、甲乙各1通を保管する
    </div>
</div>
"""

        html = self._wrap_html(content, "労働者派遣個別契約書")
        filename = f"kobetsu_keiyakusho_{doc_number}.html"
        return self._save_html(html, filename)

    def generate_roudou_jouken_tsuuchisho(self, data: dict) -> str:
        """
        Genera 労働条件通知書 (Notificación de Condiciones Laborales).
        Documento obligatorio según 労働基準法第15条.
        """
        doc_number = self._generate_document_number("RJ")
        today = self._format_date_japanese(date.today())

        employee = data.get("employee", {})
        company = data.get("company", {})
        employment = data.get("employment", {})
        client = data.get("client", {})

        content = f"""
<div class="document">
    <div class="document-number">通知番号: {doc_number}</div>
    <div class="document-date">{today}</div>

    <h1 class="document-title">労働条件通知書</h1>
    <div class="document-subtitle">（派遣労働者用）</div>

    <div class="recipient">
        <span class="recipient-name">{employee.get("name_kanji", "")}</span>
        <span class="recipient-suffix">殿</span>
    </div>

    <table class="info-table">
        <tr>
            <th>契約期間</th>
            <td>
                期間の定めあり（{employment.get("start_date", "")} ～ {employment.get("end_date", "")}）<br>
                <span class="note">※更新の有無：業務量・能力等により判断</span>
            </td>
        </tr>
        <tr>
            <th>就業の場所</th>
            <td>
                {client.get("name", "")}<br>
                {client.get("address", "")}<br>
                <span class="note">※変更の範囲：会社の定める事業所</span>
            </td>
        </tr>
        <tr>
            <th>従事すべき業務</th>
            <td>
                {employment.get("job_description", "")}<br>
                <span class="note">※変更の範囲：会社の定める業務</span>
            </td>
        </tr>
        <tr>
            <th>始業・終業時刻</th>
            <td>
                始業: {employment.get("start_time", "9:00")}<br>
                終業: {employment.get("end_time", "18:00")}
            </td>
        </tr>
        <tr>
            <th>休憩時間</th>
            <td>{employment.get("break_time", "60")}分</td>
        </tr>
        <tr>
            <th>所定時間外労働</th>
            <td>有（36協定の範囲内：月45時間、年360時間を限度）</td>
        </tr>
        <tr>
            <th>休日</th>
            <td>土曜日、日曜日、国民の祝日、年末年始、夏季休暇</td>
        </tr>
        <tr>
            <th>休暇</th>
            <td>
                年次有給休暇：6ヶ月継続勤務後10日付与<br>
                その他：慶弔休暇等、就業規則に定める
            </td>
        </tr>
    </table>

    <table class="info-table">
        <tr>
            <th colspan="2" style="background-color: #d0d0d0; text-align: center;">賃金</th>
        </tr>
        <tr>
            <th>基本賃金</th>
            <td>時給 {employment.get("hourly_rate", "")} 円</td>
        </tr>
        <tr>
            <th>時間外割増</th>
            <td>25%増（時給 × 1.25）</td>
        </tr>
        <tr>
            <th>深夜割増</th>
            <td>25%増（22:00～5:00）</td>
        </tr>
        <tr>
            <th>休日割増</th>
            <td>35%増（法定休日）</td>
        </tr>
        <tr>
            <th>賃金締切日</th>
            <td>毎月末日</td>
        </tr>
        <tr>
            <th>賃金支払日</th>
            <td>翌月{employment.get("payment_day", "15")}日</td>
        </tr>
        <tr>
            <th>支払方法</th>
            <td>銀行振込</td>
        </tr>
        <tr>
            <th>昇給</th>
            <td>有（年1回、能力・業績による）</td>
        </tr>
        <tr>
            <th>賞与</th>
            <td>{employment.get("bonus", "無")}</td>
        </tr>
    </table>

    <table class="info-table">
        <tr>
            <th colspan="2" style="background-color: #d0d0d0; text-align: center;">社会保険等</th>
        </tr>
        <tr>
            <th>健康保険</th>
            <td>加入（協会けんぽ）</td>
        </tr>
        <tr>
            <th>厚生年金</th>
            <td>加入</td>
        </tr>
        <tr>
            <th>雇用保険</th>
            <td>加入</td>
        </tr>
        <tr>
            <th>労災保険</th>
            <td>適用</td>
        </tr>
    </table>

    <table class="info-table">
        <tr>
            <th colspan="2" style="background-color: #d0d0d0; text-align: center;">退職に関する事項</th>
        </tr>
        <tr>
            <th>自己都合退職</th>
            <td>退職予定日の30日前までに届け出ること</td>
        </tr>
        <tr>
            <th>解雇事由</th>
            <td>就業規則に定める</td>
        </tr>
    </table>

    <div class="content-section">
        <div class="section-title">派遣元事業主</div>
        <div class="issuer-line">{company.get("name", "")}</div>
        <div class="issuer-line">〒{company.get("postal_code", "")} {company.get("address", "")}</div>
        <div class="issuer-line">許可番号: {company.get("permit_number", "")}</div>
        <div class="issuer-line">代表取締役 {company.get("representative", "")}
            <span class="seal-placeholder hanko-red">社印</span>
        </div>
    </div>

    <div class="note" style="margin-top: 10mm;">
        ※本通知書は労働基準法第15条に基づき交付するものです。<br>
        ※2024年4月改正対応：就業場所・業務の変更の範囲を明示しています。
    </div>

    <div class="footer">
        {company.get("name", "")} | 派遣事業許可番号: {company.get("permit_number", "")}
    </div>
</div>
"""

        html = self._wrap_html(content, "労働条件通知書")
        filename = (
            f"roudou_jouken_{employee.get('id', 'unknown')}_{date.today().strftime('%Y%m%d')}.html"
        )
        return self._save_html(html, filename)

    def generate_kyuuyo_meisai(self, data: dict) -> str:
        """
        Genera 給与明細書 (Recibo de Nómina).
        """
        doc_number = self._generate_document_number("KM")

        employee = data.get("employee", {})
        company = data.get("company", {})
        payroll = data.get("payroll", {})
        period = payroll.get("period", {})

        content = f"""
<div class="document">
    <div class="document-number">明細番号: {doc_number}</div>

    <h1 class="document-title">給 与 明 細 書</h1>

    <div style="display: flex; justify-content: space-between; margin-bottom: 10mm;">
        <div>
            <strong>{employee.get("name_kanji", "")}</strong> 様
        </div>
        <div>
            {period.get("year", "")}年{period.get("month", "")}月分<br>
            支給日: {payroll.get("payment_date", "")}
        </div>
    </div>

    <table class="payroll-table">
        <tr>
            <th colspan="4" class="category-header">勤怠</th>
        </tr>
        <tr>
            <th>出勤日数</th>
            <td class="amount">{payroll.get("work_days", "")} 日</td>
            <th>欠勤日数</th>
            <td class="amount">{payroll.get("absent_days", "0")} 日</td>
        </tr>
        <tr>
            <th>所定労働時間</th>
            <td class="amount">{payroll.get("regular_hours", "")} h</td>
            <th>有給取得</th>
            <td class="amount">{payroll.get("paid_leave", "0")} 日</td>
        </tr>
        <tr>
            <th>残業時間</th>
            <td class="amount">{payroll.get("overtime_hours", "0")} h</td>
            <th>深夜時間</th>
            <td class="amount">{payroll.get("night_hours", "0")} h</td>
        </tr>
        <tr>
            <th>休日出勤</th>
            <td class="amount">{payroll.get("holiday_hours", "0")} h</td>
            <th>遅刻・早退</th>
            <td class="amount">{payroll.get("late_hours", "0")} h</td>
        </tr>
    </table>

    <div style="display: flex; gap: 5mm; margin-top: 5mm;">
        <table class="payroll-table" style="flex: 1;">
            <tr>
                <th colspan="2" class="category-header">支給</th>
            </tr>
            <tr>
                <th>基本給</th>
                <td class="amount">¥{payroll.get("base_salary", 0):,}</td>
            </tr>
            <tr>
                <th>残業手当</th>
                <td class="amount">¥{payroll.get("overtime_pay", 0):,}</td>
            </tr>
            <tr>
                <th>深夜手当</th>
                <td class="amount">¥{payroll.get("night_pay", 0):,}</td>
            </tr>
            <tr>
                <th>休日手当</th>
                <td class="amount">¥{payroll.get("holiday_pay", 0):,}</td>
            </tr>
            <tr>
                <th>通勤手当</th>
                <td class="amount">¥{payroll.get("transport", 0):,}</td>
            </tr>
            <tr>
                <th>その他手当</th>
                <td class="amount">¥{payroll.get("other_allowance", 0):,}</td>
            </tr>
            <tr class="subtotal">
                <th>支給合計</th>
                <td class="amount">¥{payroll.get("gross_salary", 0):,}</td>
            </tr>
        </table>

        <table class="payroll-table" style="flex: 1;">
            <tr>
                <th colspan="2" class="category-header">控除</th>
            </tr>
            <tr>
                <th>健康保険</th>
                <td class="amount">¥{payroll.get("health_insurance", 0):,}</td>
            </tr>
            <tr>
                <th>厚生年金</th>
                <td class="amount">¥{payroll.get("pension", 0):,}</td>
            </tr>
            <tr>
                <th>雇用保険</th>
                <td class="amount">¥{payroll.get("employment_insurance", 0):,}</td>
            </tr>
            <tr>
                <th>所得税</th>
                <td class="amount">¥{payroll.get("income_tax", 0):,}</td>
            </tr>
            <tr>
                <th>住民税</th>
                <td class="amount">¥{payroll.get("resident_tax", 0):,}</td>
            </tr>
            <tr>
                <th>その他控除</th>
                <td class="amount">¥{payroll.get("other_deduction", 0):,}</td>
            </tr>
            <tr class="subtotal">
                <th>控除合計</th>
                <td class="amount">¥{payroll.get("total_deductions", 0):,}</td>
            </tr>
        </table>
    </div>

    <table class="payroll-table" style="margin-top: 5mm;">
        <tr class="total">
            <th style="width: 70%;">差引支給額</th>
            <td class="amount" style="font-size: 14pt;">¥{payroll.get("net_salary", 0):,}</td>
        </tr>
    </table>

    <div style="margin-top: 10mm; font-size: 9pt;">
        <div><strong>振込先:</strong> {employee.get("bank_name", "")} {employee.get("branch_name", "")} {employee.get("account_type", "普通")} {employee.get("account_number", "")}</div>
    </div>

    <div class="issuer" style="margin-top: 15mm;">
        <div class="issuer-line">{company.get("name", "")}</div>
        <div class="issuer-line">〒{company.get("postal_code", "")} {company.get("address", "")}</div>
        <div class="issuer-line">TEL: {company.get("phone", "")}</div>
    </div>

    <div class="note">
        ※本明細書は再発行いたしませんので大切に保管してください。<br>
        ※内容に相違がある場合は、支給日から7日以内にご連絡ください。
    </div>

    <div class="footer">
        {company.get("name", "")} | 派遣事業許可番号: {company.get("permit_number", "")}
    </div>
</div>
"""

        html = self._wrap_html(content, "給与明細書")
        filename = f"kyuuyo_meisai_{employee.get('id', 'unknown')}_{period.get('year', '')}{period.get('month', ''):02d}.html"
        return self._save_html(html, filename)

    def generate_shuugyou_jouken_meijisho(self, data: dict) -> str:
        """
        Genera 就業条件明示書 (Documento de Condiciones de Empleo).
        Documento específico para派遣社員.
        """
        doc_number = self._generate_document_number("SJ")
        today = self._format_date_japanese(date.today())

        employee = data.get("employee", {})
        company = data.get("company", {})
        client = data.get("client", {})
        employment = data.get("employment", {})

        content = f"""
<div class="document">
    <div class="document-number">通知番号: {doc_number}</div>
    <div class="document-date">{today}</div>

    <h1 class="document-title">就業条件明示書</h1>

    <div class="recipient">
        <span class="recipient-name">{employee.get("name_kanji", "")}</span>
        <span class="recipient-suffix">殿</span>
    </div>

    <div class="certification-text">
        労働者派遣法第34条の規定に基づき、下記のとおり就業条件を明示します。
    </div>

    <table class="info-table">
        <tr>
            <th colspan="2" style="background-color: #d0d0d0; text-align: center;">派遣元事業主</th>
        </tr>
        <tr>
            <th>事業所名</th>
            <td>{company.get("name", "")}</td>
        </tr>
        <tr>
            <th>許可番号</th>
            <td>{company.get("permit_number", "")}</td>
        </tr>
        <tr>
            <th>派遣元責任者</th>
            <td>{company.get("manager", "")} TEL: {company.get("phone", "")}</td>
        </tr>
    </table>

    <table class="info-table">
        <tr>
            <th colspan="2" style="background-color: #d0d0d0; text-align: center;">派遣先</th>
        </tr>
        <tr>
            <th>事業所名</th>
            <td>{client.get("name", "")}</td>
        </tr>
        <tr>
            <th>所在地</th>
            <td>{client.get("address", "")}</td>
        </tr>
        <tr>
            <th>派遣先責任者</th>
            <td>{client.get("manager", "")} TEL: {client.get("phone", "")}</td>
        </tr>
        <tr>
            <th>指揮命令者</th>
            <td>{client.get("supervisor", "")}</td>
        </tr>
    </table>

    <table class="info-table">
        <tr>
            <th colspan="2" style="background-color: #d0d0d0; text-align: center;">派遣期間・業務内容</th>
        </tr>
        <tr>
            <th>派遣期間</th>
            <td>{employment.get("start_date", "")} ～ {employment.get("end_date", "")}</td>
        </tr>
        <tr>
            <th>抵触日</th>
            <td style="color: #cc0000; font-weight: bold;">{employment.get("teishoku_bi", "")}</td>
        </tr>
        <tr>
            <th>業務内容</th>
            <td>{employment.get("job_description", "")}</td>
        </tr>
        <tr>
            <th>就業場所</th>
            <td>{client.get("workplace", client.get("address", ""))}</td>
        </tr>
    </table>

    <table class="info-table">
        <tr>
            <th colspan="2" style="background-color: #d0d0d0; text-align: center;">就業時間</th>
        </tr>
        <tr>
            <th>始業・終業</th>
            <td>{employment.get("start_time", "9:00")} ～ {employment.get("end_time", "18:00")}</td>
        </tr>
        <tr>
            <th>休憩時間</th>
            <td>{employment.get("break_time", "12:00～13:00")}（{employment.get("break_minutes", "60")}分）</td>
        </tr>
        <tr>
            <th>就業日</th>
            <td>{employment.get("work_days", "月曜日～金曜日")}</td>
        </tr>
        <tr>
            <th>時間外労働</th>
            <td>有（36協定の範囲内）</td>
        </tr>
    </table>

    <table class="info-table">
        <tr>
            <th colspan="2" style="background-color: #d0d0d0; text-align: center;">苦情処理</th>
        </tr>
        <tr>
            <th>派遣元苦情申出先</th>
            <td>{company.get("complaint_handler", "")} TEL: {company.get("complaint_phone", company.get("phone", ""))}</td>
        </tr>
        <tr>
            <th>派遣先苦情申出先</th>
            <td>{client.get("complaint_handler", "")} TEL: {client.get("complaint_phone", client.get("phone", ""))}</td>
        </tr>
    </table>

    <div class="issuer" style="margin-top: 15mm;">
        <div class="issuer-line">{company.get("name", "")}</div>
        <div class="issuer-line">代表取締役 {company.get("representative", "")}</div>
        <span class="seal-placeholder hanko-red">社印</span>
    </div>

    <div class="note" style="margin-top: 10mm;">
        ※本書面は労働者派遣法第34条に基づき交付するものです。<br>
        ※抵触日とは、派遣期間の上限日（3年）の翌日を指します。<br>
        ※本書面は5年間保管してください。
    </div>

    <div class="footer">
        {company.get("name", "")} | 派遣事業許可番号: {company.get("permit_number", "")}
    </div>
</div>
"""

        html = self._wrap_html(content, "就業条件明示書")
        filename = f"shuugyou_jouken_{employee.get('id', 'unknown')}_{date.today().strftime('%Y%m%d')}.html"
        return self._save_html(html, filename)


# ═══════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Haken Documents - Generador de Documentos A4")

    subparsers = parser.add_subparsers(dest="command")

    # List
    subparsers.add_parser("list", help="Listar documentos disponibles")

    # Create
    create_parser = subparsers.add_parser("create", help="Crear documento")
    create_parser.add_argument(
        "--type",
        required=True,
        choices=["zaishoku", "taishoku", "kobetsu", "roudou", "kyuuyo", "shuugyou"],
        help="Tipo de documento",
    )
    create_parser.add_argument("--data", required=True, help="Archivo JSON con datos")
    create_parser.add_argument("--output", default="output", help="Directorio de salida")

    # Demo
    subparsers.add_parser("demo", help="Generar documentos de demostración")

    args = parser.parse_args()

    generator = DocumentGenerator(args.output if hasattr(args, "output") else "output")

    if args.command == "list":
        print("\n📄 DOCUMENTOS DISPONIBLES")
        print("=" * 60)
        docs = [
            ("zaishoku", "在職証明書", "Certificado de Empleo Actual"),
            ("taishoku", "退職証明書", "Certificado de Retiro"),
            ("kobetsu", "個別契約書", "Contrato Individual"),
            ("roudou", "労働条件通知書", "Notificación de Condiciones"),
            ("kyuuyo", "給与明細書", "Recibo de Nómina"),
            ("shuugyou", "就業条件明示書", "Condiciones de Empleo"),
        ]
        for code, jp, es in docs:
            print(f"  {code:12} | {jp} | {es}")

    elif args.command == "demo":
        print("\n🎯 GENERANDO DOCUMENTOS DE DEMOSTRACIÓN")
        print("=" * 60)

        # Datos de demostración
        demo_data = {
            "employee": {
                "id": "W0001",
                "name_kanji": "グエン バン アイン",
                "name_kana": "グエン バン アイン",
                "name_romaji": "NGUYEN VAN ANH",
                "birth_date": "1990-05-15",
                "nationality": "ベトナム",
                "address": "愛知県豊田市若林町1-2-3",
                "phone": "090-1234-5678",
                "bank_name": "愛知銀行",
                "branch_name": "豊田支店",
                "account_type": "普通",
                "account_number": "1234567",
            },
            "company": {
                "name": "ユニバーサル企画株式会社",
                "permit_number": "派23-303669",
                "postal_code": "471-0834",
                "address": "愛知県豊田市土橋町7-7-7",
                "phone": "0565-XX-XXXX",
                "representative": "浅田 健二",
                "manager": "山田 太郎",
                "complaint_handler": "鈴木 花子",
            },
            "client": {
                "name": "株式会社トヨタ",
                "address": "愛知県豊田市トヨタ町1",
                "phone": "0565-XX-XXXX",
                "manager": "加藤 一郎",
                "supervisor": "佐藤 次郎",
                "complaint_handler": "高橋 三郎",
            },
            "employment": {
                "start_date": "2024-04-01",
                "end_date": "2027-03-31",
                "teishoku_bi": "2027-04-01",
                "hourly_rate": 1200,
                "position": "製造作業員",
                "job_description": "自動車部品の組立作業",
                "workplace": "豊田本社工場",
                "start_time": "8:00",
                "end_time": "17:00",
                "break_time": "12:00～13:00",
                "break_minutes": 60,
                "work_days": "月曜日～金曜日",
                "monthly_salary": "250,000",
            },
            "retirement": {
                "date": "2027-03-31",
                "reason": "契約満了",
                "detail": "派遣契約期間満了による退職",
            },
            "contract": {
                "start_date": "2024-04-01",
                "end_date": "2027-03-31",
                "teishoku_bi": "2027-04-01",
                "job_description": "自動車部品の組立作業",
                "work_hours": "8:00～17:00",
                "break_time": "60",
                "billing_rate": "1,800",
                "overtime_rate": "2,250",
                "night_rate": "2,250",
                "holiday_rate": "2,430",
            },
            "payroll": {
                "period": {"year": 2026, "month": 1},
                "payment_date": "2026-02-15",
                "work_days": 20,
                "regular_hours": 160,
                "overtime_hours": 20,
                "base_salary": 192000,
                "overtime_pay": 30000,
                "transport": 10000,
                "gross_salary": 232000,
                "health_insurance": 11600,
                "pension": 21236,
                "employment_insurance": 1392,
                "income_tax": 5120,
                "resident_tax": 8000,
                "total_deductions": 47348,
                "net_salary": 184652,
            },
        }

        # Generar todos los documentos de demo
        docs = [
            ("zaishoku", generator.generate_zaishoku_shoumeisho),
            ("taishoku", generator.generate_taishoku_shoumeisho),
            ("kobetsu", generator.generate_kobetsu_keiyakusho),
            ("roudou", generator.generate_roudou_jouken_tsuuchisho),
            ("kyuuyo", generator.generate_kyuuyo_meisai),
            ("shuugyou", generator.generate_shuugyou_jouken_meijisho),
        ]

        for name, func in docs:
            try:
                filepath = func(demo_data)
                print(f"  ✅ {name}: {filepath}")
            except Exception as e:
                print(f"  ❌ {name}: {e}")

        print("\n✅ Documentos generados en ./output/")
        print("   Abrir con navegador web para ver formato A4")

    elif args.command == "create":
        with open(args.data, encoding="utf-8") as f:
            data = json.load(f)

        generators = {
            "zaishoku": generator.generate_zaishoku_shoumeisho,
            "taishoku": generator.generate_taishoku_shoumeisho,
            "kobetsu": generator.generate_kobetsu_keiyakusho,
            "roudou": generator.generate_roudou_jouken_tsuuchisho,
            "kyuuyo": generator.generate_kyuuyo_meisai,
            "shuugyou": generator.generate_shuugyou_jouken_meijisho,
        }

        func = generators.get(args.type)
        if func:
            filepath = func(data)
            print(f"\n✅ Documento generado: {filepath}")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
