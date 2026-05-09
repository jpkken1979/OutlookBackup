#!/usr/bin/env python3
"""
UNS Visa Tracker - Complete visa management system
"""

import argparse
import json
import sqlite3
import os
import csv
from datetime import datetime
from pathlib import Path
import urllib.request
import urllib.parse

# ============================================
# CONFIGURATION
# ============================================

DB_PATH = os.environ.get("UNS_DB", "uns_data.db")
LINE_NOTIFY_TOKEN = os.environ.get("LINE_NOTIFY_TOKEN", "")

# Visa types and their properties
VISA_TYPES = {
    "技能実習1号": {"duration_years": 1, "renewable": True, "next": "技能実習2号"},
    "技能実習2号": {"duration_years": 2, "renewable": True, "next": "技能実習3号"},
    "技能実習3号": {"duration_years": 2, "renewable": True, "next": "特定技能1号"},
    "特定技能1号": {"duration_years": 5, "renewable": True, "next": "特定技能2号"},
    "特定技能2号": {"duration_years": 0, "renewable": True, "next": None},  # Unlimited
    "技術・人文知識・国際業務": {"duration_years": 5, "renewable": True, "next": None},
    "定住者": {"duration_years": 5, "renewable": True, "next": None},
    "永住者": {"duration_years": 0, "renewable": False, "next": None},
}

# Required documents for renewal
RENEWAL_DOCUMENTS = {
    "技能実習": [
        "在留期間更新許可申請書",
        "パスポート（原本）",
        "在留カード（原本）",
        "技能実習計画認定通知書",
        "住民票",
        "写真（4×3cm）2枚",
        "手数料納付書（4,000円）",
    ],
    "特定技能1号": [
        "在留期間更新許可申請書",
        "パスポート（原本）",
        "在留カード（原本）",
        "特定技能雇用契約書",
        "1号特定技能外国人支援計画",
        "住民票",
        "課税証明書・納税証明書",
        "健康保険証のコピー",
        "年金記録",
        "写真（4×3cm）2枚",
        "手数料納付書（4,000円）",
    ],
    "特定技能2号": [
        "在留資格変更許可申請書",
        "パスポート（原本）",
        "在留カード（原本）",
        "特定技能2号評価試験合格証",
        "雇用契約書",
        "住民票",
        "課税証明書・納税証明書",
        "写真（4×3cm）2枚",
        "手数料納付書（4,000円）",
    ],
}

# Alert thresholds
ALERT_LEVELS = {
    "critical": 30,  # 🔴 30 days or less
    "warning": 60,  # 🟠 31-60 days
    "caution": 90,  # 🟡 61-90 days
    "normal": 9999,  # 🟢 More than 90 days
}

# ============================================
# DATABASE HELPERS
# ============================================


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def get_employees_with_visas() -> list[dict]:
    """Get all active employees with visa info"""
    conn = get_db()
    c = conn.cursor()

    employees = []

    try:
        c.execute("""
            SELECT
                id, name, name_kana, nationality,
                visa_type, visa_expiry, residence_card,
                client_id, phone, email
            FROM employees
            WHERE status = 'active'
            AND visa_expiry IS NOT NULL
            AND visa_expiry != ''
            ORDER BY visa_expiry ASC
        """)

        for row in c.fetchall():
            employees.append(dict(row))
    except Exception as e:
        print(f"DB Error: {e}")

    conn.close()
    return employees


# ============================================
# VISA CHECKING
# ============================================


def check_visa_status(visa_expiry: str) -> dict:
    """Check visa status and return alert level"""
    try:
        expiry = datetime.strptime(visa_expiry, "%Y-%m-%d").date()
        today = datetime.now().date()
        days_left = (expiry - today).days

        if days_left <= ALERT_LEVELS["critical"]:
            level = "critical"
            emoji = "🔴"
            action = "直ちに更新手続きを開始！"
        elif days_left <= ALERT_LEVELS["warning"]:
            level = "warning"
            emoji = "🟠"
            action = "書類準備を開始"
        elif days_left <= ALERT_LEVELS["caution"]:
            level = "caution"
            emoji = "🟡"
            action = "更新計画を立てる"
        else:
            level = "normal"
            emoji = "🟢"
            action = "定期監視"

        return {
            "expiry": visa_expiry,
            "days_left": days_left,
            "level": level,
            "emoji": emoji,
            "action": action,
            "is_expired": days_left < 0,
        }
    except Exception:
        return {
            "expiry": visa_expiry,
            "days_left": None,
            "level": "unknown",
            "emoji": "❓",
            "action": "日付形式を確認",
            "is_expired": False,
        }


def check_all_visas() -> list[dict]:
    """Check all employee visas"""
    employees = get_employees_with_visas()
    results = []

    for emp in employees:
        status = check_visa_status(emp.get("visa_expiry", ""))

        results.append(
            {
                "employee_id": emp.get("id"),
                "name": emp.get("name"),
                "name_kana": emp.get("name_kana"),
                "nationality": emp.get("nationality"),
                "visa_type": emp.get("visa_type"),
                "residence_card": emp.get("residence_card"),
                "client_id": emp.get("client_id"),
                **status,
            }
        )

    # Sort by days_left (None values at end)
    results.sort(key=lambda x: x.get("days_left") if x.get("days_left") is not None else 9999)

    return results


def get_alerts_by_level(results: list[dict] = None) -> dict[str, list[dict]]:
    """Group visa alerts by level"""
    if results is None:
        results = check_all_visas()

    grouped = {"critical": [], "warning": [], "caution": [], "normal": []}

    for r in results:
        level = r.get("level", "unknown")
        if level in grouped:
            grouped[level].append(r)

    return grouped


# ============================================
# DOCUMENT CHECKLIST
# ============================================


def get_document_checklist(visa_type: str) -> list[str]:
    """Get required documents for visa type"""
    # Find matching category
    for category, docs in RENEWAL_DOCUMENTS.items():
        if category in visa_type:
            return docs

    # Default documents
    return [
        "在留期間更新許可申請書",
        "パスポート（原本）",
        "在留カード（原本）",
        "住民票",
        "写真（4×3cm）2枚",
        "手数料納付書",
    ]


def format_checklist(visa_type: str) -> str:
    """Format document checklist as text"""
    docs = get_document_checklist(visa_type)

    output = f"\n📋 {visa_type} 更新必要書類 / Renewal Documents\n"
    output += "=" * 50 + "\n\n"

    for i, doc in enumerate(docs, 1):
        output += f"  ☐ {i:2}. {doc}\n"

    output += "\n" + "=" * 50
    output += "\n⚠️ 入管の要件は変更される場合があります。最新情報を確認してください。"

    return output


# ============================================
# NOTIFICATIONS
# ============================================


def send_line_notify(message: str) -> bool:
    """Send LINE notification"""
    if not LINE_NOTIFY_TOKEN:
        print("⚠️ LINE_NOTIFY_TOKEN not set")
        return False

    try:
        data = urllib.parse.urlencode({"message": message}).encode("utf-8")
        req = urllib.request.Request("https://notify-api.line.me/api/notify", data=data)
        req.add_header("Authorization", f"Bearer {LINE_NOTIFY_TOKEN}")

        with urllib.request.urlopen(req) as response:
            return response.status == 200
    except Exception as e:
        print(f"❌ LINE Error: {e}")
        return False


def format_notification_message(alerts: list[dict]) -> str:
    """Format alerts for notification"""
    if not alerts:
        return "✅ ビザアラートなし / No visa alerts"

    msg = f"\n🛂 UNS Visa Alert Report\n日付: {datetime.now().strftime('%Y-%m-%d')}\n"

    # Group by level
    grouped = get_alerts_by_level(alerts)

    if grouped["critical"]:
        msg += f"\n🔴 CRITICAL ({len(grouped['critical'])}):\n"
        for a in grouped["critical"][:5]:
            msg += f"  • {a['name']}: {a['days_left']}日 ({a['visa_expiry']})\n"

    if grouped["warning"]:
        msg += f"\n🟠 WARNING ({len(grouped['warning'])}):\n"
        for a in grouped["warning"][:5]:
            msg += f"  • {a['name']}: {a['days_left']}日\n"

    return msg


def send_alerts(channels: list[str] = None) -> dict:
    """Send alerts to specified channels"""
    if channels is None:
        channels = ["line"]

    # Get only alerts that need attention (not normal)
    all_visas = check_all_visas()
    alerts = [v for v in all_visas if v.get("level") in ["critical", "warning", "caution"]]

    if not alerts:
        print("✅ No alerts to send")
        return {"sent": 0, "alerts": 0}

    message = format_notification_message(alerts)
    sent = 0

    for channel in channels:
        if channel == "line":
            if send_line_notify(message):
                print("✅ LINE notification sent")
                sent += 1
            else:
                print("❌ LINE notification failed")

    return {"sent": sent, "alerts": len(alerts)}


# ============================================
# DASHBOARD
# ============================================


def generate_dashboard_html(results: list[dict] = None) -> str:
    """Generate visa dashboard HTML"""
    if results is None:
        results = check_all_visas()

    grouped = get_alerts_by_level(results)

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UNS Visa Dashboard</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}
        body {{ font-family: -apple-system, sans-serif; background: #f5f7fa; color: #1e293b; }}
        .header {{ background: linear-gradient(135deg, #059669 0%, #10b981 100%); color: white; padding: 24px 32px; }}
        .header h1 {{ font-size: 24px; }}
        .container {{ max-width: 1200px; margin: 0 auto; padding: 24px; }}
        .stats {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 24px; }}
        .stat {{ background: white; padding: 20px; border-radius: 12px; text-align: center; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        .stat .value {{ font-size: 32px; font-weight: 700; }}
        .stat .label {{ color: #64748b; font-size: 14px; margin-top: 4px; }}
        .stat.critical .value {{ color: #ef4444; }}
        .stat.warning .value {{ color: #f59e0b; }}
        .stat.caution .value {{ color: #eab308; }}
        .stat.normal .value {{ color: #10b981; }}
        .table-container {{ background: white; border-radius: 12px; overflow: hidden; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
        table {{ width: 100%; border-collapse: collapse; }}
        th, td {{ padding: 14px 16px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
        th {{ background: #f8fafc; font-weight: 600; font-size: 13px; text-transform: uppercase; color: #64748b; }}
        tr:hover {{ background: #f8fafc; }}
        .badge {{ padding: 4px 12px; border-radius: 20px; font-size: 12px; font-weight: 500; }}
        .badge.critical {{ background: #fef2f2; color: #dc2626; }}
        .badge.warning {{ background: #fffbeb; color: #d97706; }}
        .badge.caution {{ background: #fefce8; color: #ca8a04; }}
        .badge.normal {{ background: #f0fdf4; color: #16a34a; }}
        .days {{ font-weight: 600; }}
        .days.critical {{ color: #ef4444; }}
        .days.warning {{ color: #f59e0b; }}
        .days.caution {{ color: #eab308; }}
        .days.normal {{ color: #10b981; }}
        footer {{ text-align: center; padding: 32px; color: #64748b; }}
    </style>
</head>
<body>
    <div class="header">
        <h1>🛂 UNS Visa Dashboard</h1>
        <p>在留カード管理 | Updated: {datetime.now().strftime("%Y-%m-%d %H:%M")}</p>
    </div>

    <div class="container">
        <div class="stats">
            <div class="stat critical">
                <div class="value">{len(grouped["critical"])}</div>
                <div class="label">🔴 Critical (≤30日)</div>
            </div>
            <div class="stat warning">
                <div class="value">{len(grouped["warning"])}</div>
                <div class="label">🟠 Warning (31-60日)</div>
            </div>
            <div class="stat caution">
                <div class="value">{len(grouped["caution"])}</div>
                <div class="label">🟡 Caution (61-90日)</div>
            </div>
            <div class="stat normal">
                <div class="value">{len(grouped["normal"])}</div>
                <div class="label">🟢 Normal (>90日)</div>
            </div>
        </div>

        <div class="table-container">
            <table>
                <thead>
                    <tr>
                        <th>Status</th>
                        <th>従業員</th>
                        <th>在留資格</th>
                        <th>在留期限</th>
                        <th>残り日数</th>
                        <th>アクション</th>
                    </tr>
                </thead>
                <tbody>
"""

    for visa in results:
        level = visa.get("level", "normal")
        days = visa.get("days_left", "?")
        days_display = f"{days}日" if isinstance(days, int) else "?"

        html += f"""
                    <tr>
                        <td><span class="badge {level}">{visa.get("emoji", "?")} {level.upper()}</span></td>
                        <td><strong>{visa.get("name", "Unknown")}</strong></td>
                        <td>{visa.get("visa_type", "-")}</td>
                        <td>{visa.get("expiry", "-")}</td>
                        <td><span class="days {level}">{days_display}</span></td>
                        <td>{visa.get("action", "-")}</td>
                    </tr>
"""

    html += """
                </tbody>
            </table>
        </div>
    </div>

    <footer>
        UNS Visa Tracker | ユニバーサル企画株式会社
    </footer>
</body>
</html>"""

    return html


# ============================================
# EXPORT
# ============================================


def export_csv(results: list[dict], output_path: str) -> bool:
    """Export visa data to CSV"""
    try:
        with open(output_path, "w", newline="", encoding="utf-8-sig") as f:
            writer = csv.writer(f)
            writer.writerow(
                [
                    "社員番号",
                    "氏名",
                    "国籍",
                    "在留資格",
                    "在留期限",
                    "残り日数",
                    "ステータス",
                    "アクション",
                ]
            )

            for r in results:
                writer.writerow(
                    [
                        r.get("employee_id", ""),
                        r.get("name", ""),
                        r.get("nationality", ""),
                        r.get("visa_type", ""),
                        r.get("expiry", ""),
                        r.get("days_left", ""),
                        r.get("level", "").upper(),
                        r.get("action", ""),
                    ]
                )

        return True
    except Exception as e:
        print(f"❌ Export error: {e}")
        return False


# ============================================
# MAIN CLI
# ============================================


def main():
    parser = argparse.ArgumentParser(description="UNS Visa Tracker")
    subparsers = parser.add_subparsers(dest="command")

    # Check command
    check = subparsers.add_parser("check", help="Check all visas")
    check.add_argument("--json", action="store_true", help="Output as JSON")
    check.add_argument("--level", choices=["critical", "warning", "caution", "all"], default="all")

    # Dashboard command
    dash = subparsers.add_parser("dashboard", help="Generate HTML dashboard")
    dash.add_argument("--output", "-o", default="visa_dashboard.html")

    # Notify command
    notify = subparsers.add_parser("notify", help="Send notifications")
    notify.add_argument("--channel", choices=["line", "email"], default="line")
    notify.add_argument("--test", action="store_true")

    # Export command
    export = subparsers.add_parser("export", help="Export to CSV")
    export.add_argument("--output", "-o", default="visa_report.csv")

    # Checklist command
    checklist = subparsers.add_parser("checklist", help="Show document checklist")
    checklist.add_argument("--visa-type", required=True)

    args = parser.parse_args()

    if args.command == "check":
        results = check_all_visas()

        if args.level != "all":
            results = [r for r in results if r.get("level") == args.level]

        if args.json:
            print(json.dumps(results, ensure_ascii=False, indent=2))
        else:
            print(f"\n🛂 Visa Status Report ({len(results)} employees)\n")
            print("=" * 70)

            for r in results:
                emoji = r.get("emoji", "?")
                name = r.get("name", "Unknown")[:20]
                visa = r.get("visa_type", "-")[:15]
                days = r.get("days_left", "?")
                action = r.get("action", "")

                print(f"{emoji} {name:<20} | {visa:<15} | {days:>4}日 | {action}")

    elif args.command == "dashboard":
        results = check_all_visas()
        html = generate_dashboard_html(results)
        Path(args.output).write_text(html, encoding="utf-8")
        print(f"✅ Dashboard saved: {args.output}")

    elif args.command == "notify":
        if args.test:
            if send_line_notify("🧪 Test: UNS Visa Tracker notification"):
                print("✅ Test notification sent")
            else:
                print("❌ Test failed")
        else:
            result = send_alerts([args.channel])
            print(f"📤 Sent: {result['sent']}, Alerts: {result['alerts']}")

    elif args.command == "export":
        results = check_all_visas()
        if export_csv(results, args.output):
            print(f"✅ Exported to: {args.output}")

    elif args.command == "checklist":
        print(format_checklist(args.visa_type))

    else:
        # Default: show summary
        results = check_all_visas()
        grouped = get_alerts_by_level(results)

        print("\n🛂 UNS Visa Tracker Summary")
        print("=" * 40)
        print(f"  🔴 Critical (≤30日):  {len(grouped['critical']):3}")
        print(f"  🟠 Warning (31-60日): {len(grouped['warning']):3}")
        print(f"  🟡 Caution (61-90日): {len(grouped['caution']):3}")
        print(f"  🟢 Normal (>90日):    {len(grouped['normal']):3}")
        print("=" * 40)
        print(f"  Total: {len(results)}")
        print("\nUse 'check', 'dashboard', 'notify', or 'export' commands.")


if __name__ == "__main__":
    main()
