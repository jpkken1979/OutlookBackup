#!/usr/bin/env python3
"""
UNS-RIREKISHO - 履歴書生成システム
===================================
Generador de履歴書 (CV japonés) y職務経歴書 en formato JIS estándar.
"""

import argparse
import json
import logging
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path
from typing import Any

# Configurar logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("uns-rirekisho")


# =============================================================================
# MODELOS DE DATOS
# =============================================================================


@dataclass
class RirekishoEntry:
    """Entrada de historial (educación o trabajo)."""

    date: str  # Formato "YYYY-MM" o "現在"
    event: str  # Descripción del evento


@dataclass
class PersonalInfo:
    """Información personal del candidato."""

    name_kanji: str
    name_furigana: str
    birth_date: str
    address: str
    phone: str
    gender: str = "男"
    nationality: str = "日本"
    name_romaji: str | None = None
    email: str | None = None
    photo_path: str | None = None
    # Para extranjeros
    zairyu_card: str | None = None
    visa_type: str | None = None


@dataclass
class Rirekisho:
    """Modelo completo de履歴書."""

    personal: PersonalInfo
    education: list[RirekishoEntry] = field(default_factory=list)
    work_history: list[RirekishoEntry] = field(default_factory=list)
    licenses: list[str] = field(default_factory=list)
    motivation: str = ""
    preferences: str | None = None


# =============================================================================
# UTILIDADES DE FECHA
# =============================================================================


def gregorian_to_wareki(date_str: str) -> str:
    """
    Convierte fecha gregoriana a 和暦 (calendario japonés).

    Args:
        date_str: Fecha en formato "YYYY-MM-DD" o "YYYY-MM"

    Returns:
        Fecha en formato japonés (ej: "令和6年5月15日")
    """
    if date_str == "現在":
        return "現在"

    try:
        # Parsear fecha
        parts = date_str.split("-")
        year = int(parts[0])
        month = int(parts[1]) if len(parts) > 1 else 1
        day = int(parts[2]) if len(parts) > 2 else None

        # Determinar era
        if year >= 2019:
            era = "令和"
            era_year = year - 2018
        elif year >= 1989:
            era = "平成"
            era_year = year - 1988
        elif year >= 1926:
            era = "昭和"
            era_year = year - 1925
        elif year >= 1912:
            era = "大正"
            era_year = year - 1911
        else:
            era = "明治"
            era_year = year - 1867

        # Formatear
        if day:
            return f"{era}{era_year}年{month}月{day}日"
        else:
            return f"{era}{era_year}年{month}月"

    except (ValueError, IndexError):
        logger.warning(f"No se pudo convertir fecha: {date_str}")
        return date_str


def calculate_age(birth_date_str: str) -> int:
    """Calcula edad a partir de fecha de nacimiento."""
    try:
        parts = birth_date_str.split("-")
        birth = date(int(parts[0]), int(parts[1]), int(parts[2]))
        today = date.today()
        age = today.year - birth.year
        if (today.month, today.day) < (birth.month, birth.day):
            age -= 1
        return age
    except (ValueError, IndexError):
        return 0


# =============================================================================
# VALIDACIÓN
# =============================================================================


def validate_phone(phone: str) -> bool:
    """Valida formato de teléfono japonés."""
    import re

    # Patrones válidos: 090-XXXX-XXXX, 03-XXXX-XXXX, etc.
    patterns = [r"^0\d{1,4}-\d{1,4}-\d{4}$", r"^0\d{9,10}$"]
    return any(re.match(p, phone.replace(" ", "")) for p in patterns)


def validate_postal_code(postal: str) -> bool:
    """Valida código postal japonés (〒XXX-XXXX)."""
    import re

    return bool(re.match(r"^\d{3}-?\d{4}$", postal.replace("〒", "").strip()))


def validate_rirekisho(data: dict[str, Any]) -> list[str]:
    """
    Valida datos de履歴書.

    Returns:
        Lista de errores encontrados (vacía si todo OK)
    """
    errors = []

    personal = data.get("personal", {})

    # Campos requeridos
    required = ["name_kanji", "name_furigana", "birth_date", "address", "phone"]
    for field in required:
        if not personal.get(field):
            errors.append(f"Campo requerido faltante: {field}")

    # Validar teléfono
    if personal.get("phone") and not validate_phone(personal["phone"]):
        errors.append(f"Formato de teléfono inválido: {personal['phone']}")

    # Validar fechas cronológicas
    education = data.get("education", [])
    data.get("work_history", [])

    # Verificar que educación tenga al menos una entrada
    if not education:
        errors.append("Se requiere al menos una entrada de educación")

    # Para extranjeros, verificar campos adicionales
    if personal.get("nationality") and personal["nationality"] != "日本":
        if not personal.get("visa_type"):
            errors.append("Para extranjeros se requiere visa_type (在留資格)")

    return errors


# =============================================================================
# GENERADOR DE HTML
# =============================================================================


def generate_rirekisho_html(rirekisho: Rirekisho) -> str:
    """
    Genera履歴書 en formato HTML A4.

    Args:
        rirekisho: Objeto Rirekisho con todos los datos

    Returns:
        String HTML completo
    """
    today = date.today()
    reiwa_year = today.year - 2018

    # Calcular edad
    age = calculate_age(rirekisho.personal.birth_date)
    birth_wareki = gregorian_to_wareki(rirekisho.personal.birth_date)

    # Generar filas de educación
    education_rows = ""
    for entry in rirekisho.education:
        wareki = gregorian_to_wareki(entry.date)
        education_rows += f"""
        <tr>
            <td class="date-cell">{wareki}</td>
            <td class="event-cell">{entry.event}</td>
        </tr>
        """

    # Separador
    education_rows += """
        <tr>
            <td colspan="2" style="text-align: center; padding: 2mm 0;">職 歴</td>
        </tr>
    """

    # Generar filas de trabajo
    for entry in rirekisho.work_history:
        wareki = gregorian_to_wareki(entry.date)
        education_rows += f"""
        <tr>
            <td class="date-cell">{wareki}</td>
            <td class="event-cell">{entry.event}</td>
        </tr>
        """

    # Fila final
    education_rows += """
        <tr>
            <td colspan="2" style="text-align: right; padding: 2mm;">以上</td>
        </tr>
    """

    # Generar licencias
    license_rows = ""
    for lic in rirekisho.licenses:
        license_rows += f"<tr><td>{lic}</td></tr>"

    # Sección para extranjeros
    foreign_section = ""
    if rirekisho.personal.nationality != "日本":
        foreign_section = f"""
        <tr>
            <th>国籍</th>
            <td>{rirekisho.personal.nationality}</td>
        </tr>
        <tr>
            <th>在留資格</th>
            <td>{rirekisho.personal.visa_type or ""}</td>
        </tr>
        <tr>
            <th>在留カード番号</th>
            <td>{rirekisho.personal.zairyu_card or ""}</td>
        </tr>
        """

    # Foto placeholder
    photo_section = ""
    if rirekisho.personal.photo_path:
        photo_section = f'<img src="{rirekisho.personal.photo_path}" alt="写真" />'
    else:
        photo_section = """
        <div class="photo-placeholder">
            写真貼付欄<br>
            <small>(3cm × 4cm)</small>
        </div>
        """

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>履歴書 - {rirekisho.personal.name_kanji}</title>
    <style>
        @page {{
            size: A4 portrait;
            margin: 15mm 20mm;
        }}

        * {{
            box-sizing: border-box;
            margin: 0;
            padding: 0;
        }}

        body {{
            font-family: "Yu Gothic", "YuGothic", "Hiragino Sans", "MS Gothic", sans-serif;
            font-size: 10.5pt;
            line-height: 1.5;
            color: #000;
        }}

        .document {{
            width: 100%;
            max-width: 210mm;
            margin: 0 auto;
        }}

        .header {{
            display: flex;
            justify-content: space-between;
            align-items: flex-start;
            margin-bottom: 5mm;
        }}

        .title {{
            font-size: 18pt;
            font-weight: bold;
            text-align: center;
            letter-spacing: 1em;
            margin-bottom: 5mm;
        }}

        .date-section {{
            text-align: right;
            font-size: 10pt;
        }}

        .personal-section {{
            display: flex;
            gap: 5mm;
            margin-bottom: 5mm;
        }}

        .personal-info {{
            flex: 1;
        }}

        .photo-area {{
            width: 30mm;
            height: 40mm;
            border: 1px solid #333;
            display: flex;
            align-items: center;
            justify-content: center;
            text-align: center;
            font-size: 8pt;
            color: #666;
        }}

        .photo-area img {{
            width: 100%;
            height: 100%;
            object-fit: cover;
        }}

        .photo-placeholder {{
            padding: 5mm;
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
            margin-bottom: 5mm;
        }}

        th, td {{
            border: 1px solid #333;
            padding: 2mm 3mm;
            text-align: left;
            vertical-align: top;
        }}

        th {{
            background-color: #f5f5f5;
            width: 25%;
            font-weight: normal;
        }}

        .name-cell {{
            font-size: 14pt;
            font-weight: bold;
        }}

        .furigana {{
            font-size: 8pt;
            color: #666;
        }}

        .history-table th {{
            width: 25%;
            text-align: center;
        }}

        .date-cell {{
            width: 25%;
            text-align: center;
            white-space: nowrap;
        }}

        .event-cell {{
            width: 75%;
        }}

        .section-title {{
            background-color: #e8e8e8;
            text-align: center;
            font-weight: bold;
            padding: 2mm;
        }}

        .motivation-box {{
            min-height: 30mm;
            padding: 3mm;
        }}

        .preferences-box {{
            min-height: 20mm;
            padding: 3mm;
        }}

        @media print {{
            body {{
                -webkit-print-color-adjust: exact;
                print-color-adjust: exact;
            }}
        }}
    </style>
</head>
<body>
    <div class="document">
        <!-- 日付 -->
        <div class="date-section">
            令和{reiwa_year}年{today.month}月{today.day}日現在
        </div>

        <!-- タイトル -->
        <h1 class="title">履 歴 書</h1>

        <!-- 基本情報 -->
        <div class="personal-section">
            <div class="personal-info">
                <table>
                    <tr>
                        <th>ふりがな</th>
                        <td colspan="3" class="furigana">{rirekisho.personal.name_furigana}</td>
                    </tr>
                    <tr>
                        <th>氏名</th>
                        <td colspan="3" class="name-cell">
                            {rirekisho.personal.name_kanji}
                            {f"<br><small>({rirekisho.personal.name_romaji})</small>" if rirekisho.personal.name_romaji else ""}
                        </td>
                    </tr>
                    <tr>
                        <th>生年月日</th>
                        <td colspan="2">{birth_wareki}</td>
                        <td>満{age}歳</td>
                    </tr>
                    <tr>
                        <th>性別</th>
                        <td colspan="3">{rirekisho.personal.gender}</td>
                    </tr>
                    {foreign_section}
                    <tr>
                        <th>現住所</th>
                        <td colspan="3">{rirekisho.personal.address}</td>
                    </tr>
                    <tr>
                        <th>電話番号</th>
                        <td colspan="3">{rirekisho.personal.phone}</td>
                    </tr>
                    <tr>
                        <th>メール</th>
                        <td colspan="3">{rirekisho.personal.email or ""}</td>
                    </tr>
                </table>
            </div>
            <div class="photo-area">
                {photo_section}
            </div>
        </div>

        <!-- 学歴・職歴 -->
        <table class="history-table">
            <tr class="section-title">
                <td colspan="2">学歴・職歴</td>
            </tr>
            <tr>
                <th>年月</th>
                <th>学歴・職歴</th>
            </tr>
            {education_rows}
        </table>

        <!-- 免許・資格 -->
        <table>
            <tr class="section-title">
                <td>免許・資格</td>
            </tr>
            {license_rows if license_rows else "<tr><td>なし</td></tr>"}
        </table>

        <!-- 志望動機 -->
        <table>
            <tr class="section-title">
                <td>志望の動機、特技、好きな学科、アピールポイントなど</td>
            </tr>
            <tr>
                <td class="motivation-box">{rirekisho.motivation}</td>
            </tr>
        </table>

        <!-- 本人希望欄 -->
        <table>
            <tr class="section-title">
                <td>本人希望記入欄（特に給料・職種・勤務時間・勤務地・その他についての希望などがあれば記入）</td>
            </tr>
            <tr>
                <td class="preferences-box">{rirekisho.preferences or "貴社規定に従います。"}</td>
            </tr>
        </table>
    </div>
</body>
</html>"""

    return html


def generate_shokumu_keirekisho_html(rirekisho: Rirekisho) -> str:
    """
    Genera職務経歴書 (historial profesional detallado) en formato HTML.
    """
    today = date.today()
    reiwa_year = today.year - 2018

    # Agrupar trabajo por empresas (simplificado)
    work_entries = ""

    for entry in rirekisho.work_history:
        if "入社" in entry.event:
            company_name = entry.event.replace(" 入社", "").replace("入社", "")
            work_entries += f"""
            <div class="company-section">
                <h3>{gregorian_to_wareki(entry.date)} - {company_name}</h3>
                <p>【業務内容】</p>
                <ul>
                    <li>業務詳細をここに記載</li>
                </ul>
            </div>
            """

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <title>職務経歴書 - {rirekisho.personal.name_kanji}</title>
    <style>
        @page {{
            size: A4 portrait;
            margin: 20mm 25mm;
        }}

        body {{
            font-family: "Yu Gothic", "YuGothic", "MS Gothic", sans-serif;
            font-size: 10.5pt;
            line-height: 1.8;
        }}

        .title {{
            font-size: 16pt;
            text-align: center;
            font-weight: bold;
            margin-bottom: 10mm;
            letter-spacing: 0.5em;
        }}

        .date-section {{
            text-align: right;
            margin-bottom: 5mm;
        }}

        .name-section {{
            text-align: right;
            margin-bottom: 10mm;
            font-size: 12pt;
        }}

        h2 {{
            font-size: 12pt;
            border-bottom: 2px solid #333;
            padding-bottom: 2mm;
            margin: 8mm 0 5mm 0;
        }}

        .company-section {{
            margin-bottom: 8mm;
            padding-left: 5mm;
        }}

        .company-section h3 {{
            font-size: 11pt;
            margin-bottom: 3mm;
        }}

        ul {{
            margin-left: 10mm;
        }}

        li {{
            margin-bottom: 2mm;
        }}

        .skills-section {{
            margin-top: 10mm;
        }}

        .skill-list {{
            display: flex;
            flex-wrap: wrap;
            gap: 3mm;
        }}

        .skill-item {{
            background: #f0f0f0;
            padding: 1mm 3mm;
            border-radius: 2mm;
            font-size: 9pt;
        }}
    </style>
</head>
<body>
    <div class="document">
        <div class="date-section">
            令和{reiwa_year}年{today.month}月{today.day}日現在
        </div>

        <h1 class="title">職 務 経 歴 書</h1>

        <div class="name-section">
            氏名: {rirekisho.personal.name_kanji}
        </div>

        <h2>■ 職務要約</h2>
        <p>
            これまでの職務経験の要約をここに記載します。
            主な業務内容、得意分野、実績などを簡潔にまとめます。
        </p>

        <h2>■ 職務経歴</h2>
        {work_entries if work_entries else "<p>職歴なし</p>"}

        <h2>■ 保有資格・スキル</h2>
        <div class="skills-section">
            <div class="skill-list">
                {"".join(f'<span class="skill-item">{lic}</span>' for lic in rirekisho.licenses) if rirekisho.licenses else "<span>なし</span>"}
            </div>
        </div>

        <h2>■ 自己PR</h2>
        <p>
            {rirekisho.motivation or "自己PRをここに記載します。"}
        </p>
    </div>
</body>
</html>"""

    return html


# =============================================================================
# CLI
# =============================================================================


def dict_to_rirekisho(data: dict[str, Any]) -> Rirekisho:
    """Convierte diccionario a objeto Rirekisho."""
    personal_data = data.get("personal", {})
    personal = PersonalInfo(
        name_kanji=personal_data.get("name_kanji", ""),
        name_furigana=personal_data.get("name_furigana", ""),
        birth_date=personal_data.get("birth_date", ""),
        address=personal_data.get("address", ""),
        phone=personal_data.get("phone", ""),
        gender=personal_data.get("gender", "男"),
        nationality=personal_data.get("nationality", "日本"),
        name_romaji=personal_data.get("name_romaji"),
        email=personal_data.get("email"),
        photo_path=personal_data.get("photo_path"),
        zairyu_card=personal_data.get("zairyu_card"),
        visa_type=personal_data.get("visa_type"),
    )

    education = [
        RirekishoEntry(date=e.get("date", ""), event=e.get("event", ""))
        for e in data.get("education", [])
    ]

    work_history = [
        RirekishoEntry(date=e.get("date", ""), event=e.get("event", ""))
        for e in data.get("work_history", [])
    ]

    return Rirekisho(
        personal=personal,
        education=education,
        work_history=work_history,
        licenses=data.get("licenses", []),
        motivation=data.get("motivation", ""),
        preferences=data.get("preferences"),
    )


def main():
    parser = argparse.ArgumentParser(
        description="UNS-RIREKISHO - 履歴書生成システム",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Ejemplos:
  python rirekisho.py generate --input data.json --output rirekisho.html
  python rirekisho.py shokumu --input data.json --output shokumu.html
  python rirekisho.py full --input data.json --output-dir ./output/
  python rirekisho.py validate --input data.json
  python rirekisho.py wareki --date 1990-05-15
  python rirekisho.py demo
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Comando a ejecutar")

    # Generar履歴書
    gen_parser = subparsers.add_parser("generate", help="Generar履歴書")
    gen_parser.add_argument("--input", "-i", required=True, help="Archivo JSON de entrada")
    gen_parser.add_argument("--output", "-o", default="rirekisho.html", help="Archivo de salida")

    # Generar職務経歴書
    shokumu_parser = subparsers.add_parser("shokumu", help="Generar職務経歴書")
    shokumu_parser.add_argument("--input", "-i", required=True, help="Archivo JSON de entrada")
    shokumu_parser.add_argument(
        "--output", "-o", default="shokumu_keirekisho.html", help="Archivo de salida"
    )

    # Generar ambos
    full_parser = subparsers.add_parser("full", help="Generar履歴書 y職務経歴書")
    full_parser.add_argument("--input", "-i", required=True, help="Archivo JSON de entrada")
    full_parser.add_argument("--output-dir", "-d", default="./output", help="Directorio de salida")

    # Validar
    val_parser = subparsers.add_parser("validate", help="Validar datos")
    val_parser.add_argument("--input", "-i", required=True, help="Archivo JSON a validar")

    # Convertir fecha
    wareki_parser = subparsers.add_parser("wareki", help="Convertir fecha a 和暦")
    wareki_parser.add_argument("--date", "-d", required=True, help="Fecha en formato YYYY-MM-DD")

    # Demo
    subparsers.add_parser("demo", help="Generar ejemplo de demostración")

    args = parser.parse_args()

    if args.command == "generate":
        logger.info(f"Generando履歴書 desde {args.input}")
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)

        rirekisho = dict_to_rirekisho(data)
        html = generate_rirekisho_html(rirekisho)

        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"✅ 履歴書 generado: {args.output}")
        print(f"✅ 履歴書 generado: {args.output}")

    elif args.command == "shokumu":
        logger.info(f"Generando職務経歴書 desde {args.input}")
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)

        rirekisho = dict_to_rirekisho(data)
        html = generate_shokumu_keirekisho_html(rirekisho)

        with open(args.output, "w", encoding="utf-8") as f:
            f.write(html)

        logger.info(f"✅ 職務経歴書 generado: {args.output}")
        print(f"✅ 職務経歴書 generado: {args.output}")

    elif args.command == "full":
        logger.info(f"Generando documentos completos desde {args.input}")
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)

        rirekisho = dict_to_rirekisho(data)

        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generar履歴書
        html1 = generate_rirekisho_html(rirekisho)
        path1 = output_dir / "rirekisho.html"
        with open(path1, "w", encoding="utf-8") as f:
            f.write(html1)

        # Generar職務経歴書
        html2 = generate_shokumu_keirekisho_html(rirekisho)
        path2 = output_dir / "shokumu_keirekisho.html"
        with open(path2, "w", encoding="utf-8") as f:
            f.write(html2)

        logger.info(f"✅ Documentos generados en: {output_dir}")
        print(f"✅ 履歴書: {path1}")
        print(f"✅ 職務経歴書: {path2}")

    elif args.command == "validate":
        logger.info(f"Validando {args.input}")
        with open(args.input, encoding="utf-8") as f:
            data = json.load(f)

        errors = validate_rirekisho(data)

        if errors:
            print("❌ Errores encontrados:")
            for error in errors:
                print(f"  - {error}")
        else:
            print("✅ Datos válidos")

    elif args.command == "wareki":
        result = gregorian_to_wareki(args.date)
        print(f"{args.date} → {result}")

    elif args.command == "demo":
        logger.info("Generando demostración...")

        demo_data = {
            "personal": {
                "name_kanji": "グエン バン アイン",
                "name_furigana": "ぐえん ばん あいん",
                "name_romaji": "NGUYEN VAN ANH",
                "birth_date": "1990-05-15",
                "gender": "男",
                "nationality": "ベトナム",
                "address": "愛知県豊田市土橋町7-7-7 ユニバーサル寮101",
                "phone": "090-1234-5678",
                "email": "nguyen@example.com",
                "visa_type": "技能実習2号",
                "zairyu_card": "AB12345678CD",
            },
            "education": [
                {"date": "2005-04", "event": "ホーチミン工業高等学校 入学"},
                {"date": "2008-03", "event": "ホーチミン工業高等学校 卒業"},
                {"date": "2008-04", "event": "ホーチミン工科大学 入学"},
                {"date": "2012-03", "event": "ホーチミン工科大学 卒業"},
            ],
            "work_history": [
                {"date": "2012-04", "event": "ABC Manufacturing Co., Ltd. (ベトナム) 入社"},
                {"date": "2018-03", "event": "同社 退職"},
                {"date": "2018-04", "event": "日本渡航（技能実習生として）"},
                {"date": "2018-05", "event": "ユニバーサル企画株式会社 入社"},
                {"date": "現在", "event": "在職中"},
            ],
            "licenses": [
                "普通自動車第一種運転免許",
                "日本語能力試験 N2",
                "フォークリフト運転技能講習修了",
            ],
            "motivation": "日本の製造技術を学び、将来ベトナムの工業発展に貢献したいと考えています。"
            "これまでの経験を活かし、御社の生産効率向上に寄与できると確信しています。",
            "preferences": "勤務地：愛知県内希望\n通勤手段：自転車または公共交通機関",
        }

        rirekisho = dict_to_rirekisho(demo_data)

        # Crear directorio
        output_dir = Path("output")
        output_dir.mkdir(exist_ok=True)

        # Generar履歴書
        html1 = generate_rirekisho_html(rirekisho)
        path1 = output_dir / "demo_rirekisho.html"
        with open(path1, "w", encoding="utf-8") as f:
            f.write(html1)

        # Generar職務経歴書
        html2 = generate_shokumu_keirekisho_html(rirekisho)
        path2 = output_dir / "demo_shokumu_keirekisho.html"
        with open(path2, "w", encoding="utf-8") as f:
            f.write(html2)

        print(f"✅ Demo履歴書: {path1}")
        print(f"✅ Demo職務経歴書: {path2}")
        print("\n📄 Abre los archivos HTML en un navegador para ver el resultado.")

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
