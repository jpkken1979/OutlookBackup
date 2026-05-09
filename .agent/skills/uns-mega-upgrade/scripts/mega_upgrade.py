#!/usr/bin/env python3
"""
UNS MEGA UPGRADE - Enhancement for all UNS skills
Includes: Notifications, Dashboard, API, Analytics, Google Sheets sync
"""

import argparse
import json
import sqlite3
import os
from datetime import datetime
from pathlib import Path
import urllib.request
import urllib.parse

# ============================================
# CONFIGURATION
# ============================================

VERSION = "3.0.0"
DB_PATH = os.environ.get("UNS_DB", "uns_data.db")

# LINE Notify
LINE_NOTIFY_TOKEN = os.environ.get("LINE_NOTIFY_TOKEN", "")
LINE_NOTIFY_URL = "https://notify-api.line.me/api/notify"

# Slack (optional)
SLACK_WEBHOOK_URL = os.environ.get("SLACK_WEBHOOK_URL", "")

# Email (optional - using environment vars)
SMTP_HOST = os.environ.get("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.environ.get("SMTP_PORT", "587"))
SMTP_USER = os.environ.get("SMTP_USER", "")
SMTP_PASS = os.environ.get("SMTP_PASS", "")

# ============================================
# DATABASE HELPERS
# ============================================


def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def ensure_tables():
    """Ensure all required tables exist"""
    conn = get_db()
    c = conn.cursor()

    # Notifications log
    c.execute("""CREATE TABLE IF NOT EXISTS notification_log (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        timestamp TEXT DEFAULT CURRENT_TIMESTAMP,
        type TEXT,
        channel TEXT,
        recipient TEXT,
        subject TEXT,
        message TEXT,
        status TEXT,
        error TEXT
    )""")

    # Analytics cache
    c.execute("""CREATE TABLE IF NOT EXISTS analytics_cache (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        metric TEXT,
        period TEXT,
        value REAL,
        data TEXT,
        calculated_at TEXT DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(metric, period)
    )""")

    conn.commit()
    conn.close()


# ============================================
# NOTIFICATION SYSTEM
# ============================================


def send_line_notify(message: str, token: str = None) -> bool:
    """Send LINE notification"""
    token = token or LINE_NOTIFY_TOKEN
    if not token:
        print("⚠️ LINE_NOTIFY_TOKEN not set")
        return False

    try:
        data = urllib.parse.urlencode({"message": message}).encode("utf-8")
        req = urllib.request.Request(LINE_NOTIFY_URL, data=data)
        req.add_header("Authorization", f"Bearer {token}")

        with urllib.request.urlopen(req) as response:
            return response.status == 200
    except Exception as e:
        print(f"❌ LINE Error: {e}")
        return False


def send_slack_webhook(message: str, webhook_url: str = None) -> bool:
    """Send Slack notification"""
    webhook_url = webhook_url or SLACK_WEBHOOK_URL
    if not webhook_url:
        return False

    try:
        data = json.dumps({"text": message}).encode("utf-8")
        req = urllib.request.Request(webhook_url, data=data)
        req.add_header("Content-Type", "application/json")

        with urllib.request.urlopen(req) as response:
            return response.status == 200
    except Exception as e:
        print(f"❌ Slack Error: {e}")
        return False


def send_email(to: str, subject: str, body: str, html: bool = False) -> bool:
    """Send email notification"""
    if not SMTP_USER or not SMTP_PASS:
        print("⚠️ SMTP credentials not set")
        return False

    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = SMTP_USER
        msg["To"] = to

        content_type = "html" if html else "plain"
        msg.attach(MIMEText(body, content_type, "utf-8"))

        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASS)
            server.send_message(msg)

        return True
    except Exception as e:
        print(f"❌ Email Error: {e}")
        return False


# ============================================
# ALERT CHECKS
# ============================================


def check_visa_alerts() -> list[dict]:
    """Check for expiring visas"""
    conn = get_db()
    c = conn.cursor()

    alerts = []
    today = datetime.now().date()

    try:
        c.execute("""
            SELECT id, name, visa_type, visa_expiry
            FROM employees
            WHERE status = 'active'
            AND visa_expiry IS NOT NULL
            AND visa_expiry != ''
        """)

        for row in c.fetchall():
            try:
                expiry = datetime.strptime(row["visa_expiry"], "%Y-%m-%d").date()
                days = (expiry - today).days

                if days <= 90:
                    level = "critical" if days <= 30 else "warning" if days <= 60 else "info"
                    emoji = "🔴" if days <= 30 else "🟠" if days <= 60 else "🟡"

                    alerts.append(
                        {
                            "type": "visa",
                            "level": level,
                            "employee_id": row["id"],
                            "employee_name": row["name"],
                            "visa_type": row["visa_type"],
                            "expiry": row["visa_expiry"],
                            "days_left": days,
                            "emoji": emoji,
                            "message": f"{emoji} {row['name']}: {row['visa_type']} vence en {days} días ({row['visa_expiry']})",
                        }
                    )
            except Exception:
                pass
    except Exception:
        pass

    conn.close()
    return sorted(alerts, key=lambda x: x.get("days_left", 999))


def check_overtime_alerts(period: str = None) -> list[dict]:
    """Check 36協定 violations"""
    if not period:
        period = datetime.now().strftime("%Y-%m")

    conn = get_db()
    c = conn.cursor()
    alerts = []

    try:
        c.execute(
            """
            SELECT a.employee_id, e.name, a.overtime_hours
            FROM attendance a
            JOIN employees e ON a.employee_id = e.id
            WHERE a.period = ?
        """,
            (period,),
        )

        for row in c.fetchall():
            ot = row["overtime_hours"] or 0
            if ot >= 35:
                level = "critical" if ot >= 45 else "warning" if ot >= 40 else "info"
                emoji = "🔴" if ot >= 45 else "🟠" if ot >= 40 else "🟡"

                alerts.append(
                    {
                        "type": "overtime",
                        "level": level,
                        "employee_id": row["employee_id"],
                        "employee_name": row["name"],
                        "overtime": ot,
                        "limit": 45,
                        "emoji": emoji,
                        "message": f"{emoji} {row['name']}: {ot}h残業 (上限45h)",
                    }
                )
    except Exception:
        pass

    conn.close()
    return sorted(alerts, key=lambda x: x.get("overtime", 0), reverse=True)


def check_advance_alerts() -> list[dict]:
    """Check high advance balances"""
    conn = get_db()
    c = conn.cursor()
    alerts = []

    try:
        c.execute("""
            SELECT
                a.employee_id,
                e.name,
                SUM(a.amount - COALESCE(a.recovered_amount, 0)) as balance
            FROM advances a
            JOIN employees e ON a.employee_id = e.id
            WHERE a.status IN ('approved', 'paid')
            GROUP BY a.employee_id
            HAVING balance > 30000
        """)

        for row in c.fetchall():
            balance = row["balance"]
            level = "critical" if balance >= 100000 else "warning" if balance >= 50000 else "info"
            emoji = "🔴" if balance >= 100000 else "🟠" if balance >= 50000 else "🟡"

            alerts.append(
                {
                    "type": "advance",
                    "level": level,
                    "employee_id": row["employee_id"],
                    "employee_name": row["name"],
                    "balance": balance,
                    "emoji": emoji,
                    "message": f"{emoji} {row['name']}: 前貸残高 ¥{balance:,}",
                }
            )
    except Exception:
        pass

    conn.close()
    return sorted(alerts, key=lambda x: x.get("balance", 0), reverse=True)


def check_all_alerts(period: str = None) -> dict[str, list[dict]]:
    """Run all alert checks"""
    return {
        "visa": check_visa_alerts(),
        "overtime": check_overtime_alerts(period),
        "advance": check_advance_alerts(),
    }


# ============================================
# ANALYTICS ENGINE
# ============================================


def calculate_profit_trends(months: int = 6) -> list[dict]:
    """Calculate粗利 trends"""
    conn = get_db()
    c = conn.cursor()

    trends = []

    try:
        c.execute(
            """
            SELECT
                period,
                SUM(billing_amount) as billing,
                SUM(total_earnings) as earnings,
                SUM(total_company_cost) as company_cost,
                SUM(billing_amount - total_earnings - total_company_cost) as profit
            FROM payroll
            GROUP BY period
            ORDER BY period DESC
            LIMIT ?
        """,
            (months,),
        )

        for row in c.fetchall():
            billing = row["billing"] or 0
            profit = row["profit"] or 0
            rate = (profit / billing * 100) if billing > 0 else 0

            trends.append(
                {
                    "period": row["period"],
                    "billing": billing,
                    "earnings": row["earnings"] or 0,
                    "company_cost": row["company_cost"] or 0,
                    "profit": profit,
                    "profit_rate": round(rate, 1),
                }
            )
    except Exception:
        pass

    conn.close()
    return list(reversed(trends))


def calculate_client_comparison() -> list[dict]:
    """Compare profitability by派遣先"""
    conn = get_db()
    c = conn.cursor()

    comparison = []

    try:
        c.execute("""
            SELECT
                e.client_id,
                c.name as client_name,
                COUNT(DISTINCT p.employee_id) as employee_count,
                SUM(p.billing_amount) as total_billing,
                SUM(p.gross_profit) as total_profit,
                AVG(p.profit_rate) as avg_profit_rate
            FROM payroll p
            JOIN employees e ON p.employee_id = e.id
            LEFT JOIN clients c ON e.client_id = c.id
            WHERE p.period = strftime('%Y-%m', 'now', '-1 month')
            GROUP BY e.client_id
            ORDER BY total_profit DESC
        """)

        for row in c.fetchall():
            comparison.append(
                {
                    "client_id": row["client_id"],
                    "client_name": row["client_name"] or row["client_id"],
                    "employee_count": row["employee_count"],
                    "total_billing": row["total_billing"] or 0,
                    "total_profit": row["total_profit"] or 0,
                    "avg_profit_rate": round(row["avg_profit_rate"] or 0, 1),
                }
            )
    except Exception:
        pass

    conn.close()
    return comparison


def calculate_overtime_heatmap(year: int = None) -> dict:
    """Generate overtime heatmap by employee/month"""
    if not year:
        year = datetime.now().year

    conn = get_db()
    c = conn.cursor()

    heatmap = {}

    try:
        c.execute(
            """
            SELECT
                a.employee_id,
                e.name,
                a.period,
                a.overtime_hours
            FROM attendance a
            JOIN employees e ON a.employee_id = e.id
            WHERE a.period LIKE ?
            ORDER BY a.employee_id, a.period
        """,
            (f"{year}-%",),
        )

        for row in c.fetchall():
            emp_id = row["employee_id"]
            if emp_id not in heatmap:
                heatmap[emp_id] = {"name": row["name"], "months": {}}
            heatmap[emp_id]["months"][row["period"]] = row["overtime_hours"] or 0
    except Exception:
        pass

    conn.close()
    return heatmap


# ============================================
# UNIFIED DASHBOARD GENERATOR
# ============================================


def generate_unified_dashboard(period: str = None) -> str:
    """Generate complete unified dashboard HTML"""

    if not period:
        period = datetime.now().strftime("%Y-%m")

    # Gather all data
    all_alerts = check_all_alerts(period)
    profit_trends = calculate_profit_trends(6)
    client_comparison = calculate_client_comparison()

    # Count alerts by level
    critical_count = sum(
        1 for cat in all_alerts.values() for a in cat if a.get("level") == "critical"
    )
    warning_count = sum(
        1 for cat in all_alerts.values() for a in cat if a.get("level") == "warning"
    )

    # Flatten alerts for display
    all_alerts_flat = []
    for category, alerts in all_alerts.items():
        for a in alerts:
            a["category"] = category
            all_alerts_flat.append(a)

    # Sort by level
    level_order = {"critical": 0, "warning": 1, "info": 2}
    all_alerts_flat.sort(key=lambda x: level_order.get(x.get("level"), 3))

    # Generate chart data
    trend_labels = json.dumps([t["period"] for t in profit_trends])
    trend_billing = json.dumps([t["billing"] for t in profit_trends])
    trend_profit = json.dumps([t["profit"] for t in profit_trends])
    trend_rate = json.dumps([t["profit_rate"] for t in profit_trends])

    client_labels = json.dumps([c["client_name"][:10] for c in client_comparison[:10]])
    json.dumps([c["total_profit"] for c in client_comparison[:10]])
    client_rates = json.dumps([c["avg_profit_rate"] for c in client_comparison[:10]])

    html = f"""<!DOCTYPE html>
<html lang="ja">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>UNS Unified Dashboard</title>
    <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>
    <style>
        :root {{
            --primary: #4f46e5;
            --success: #10b981;
            --warning: #f59e0b;
            --danger: #ef4444;
            --bg: #f8fafc;
            --card: #ffffff;
            --text: #1e293b;
            --muted: #64748b;
        }}

        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: var(--bg);
            color: var(--text);
            line-height: 1.6;
        }}

        .header {{
            background: linear-gradient(135deg, var(--primary) 0%, #7c3aed 100%);
            color: white;
            padding: 24px 32px;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }}

        .header h1 {{ font-size: 24px; font-weight: 600; }}
        .header .meta {{ opacity: 0.9; font-size: 14px; }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 24px;
        }}

        .tabs {{
            display: flex;
            gap: 8px;
            margin-bottom: 24px;
            border-bottom: 2px solid #e2e8f0;
            padding-bottom: 8px;
        }}

        .tab {{
            padding: 12px 24px;
            border: none;
            background: transparent;
            cursor: pointer;
            font-size: 14px;
            font-weight: 500;
            color: var(--muted);
            border-radius: 8px 8px 0 0;
            transition: all 0.2s;
        }}

        .tab:hover {{ background: #f1f5f9; color: var(--text); }}
        .tab.active {{ background: var(--primary); color: white; }}

        .tab-content {{ display: none; }}
        .tab-content.active {{ display: block; }}

        .grid {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(240px, 1fr));
            gap: 20px;
            margin-bottom: 24px;
        }}

        .card {{
            background: var(--card);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        .card h3 {{
            font-size: 13px;
            text-transform: uppercase;
            color: var(--muted);
            margin-bottom: 8px;
            letter-spacing: 0.5px;
        }}

        .card .value {{
            font-size: 28px;
            font-weight: 700;
        }}

        .card .value.success {{ color: var(--success); }}
        .card .value.warning {{ color: var(--warning); }}
        .card .value.danger {{ color: var(--danger); }}
        .card .value.primary {{ color: var(--primary); }}

        .alerts-list {{
            display: flex;
            flex-direction: column;
            gap: 12px;
        }}

        .alert {{
            display: flex;
            align-items: center;
            gap: 16px;
            padding: 16px 20px;
            border-radius: 10px;
            background: var(--card);
            border-left: 4px solid;
        }}

        .alert.critical {{ border-color: var(--danger); background: #fef2f2; }}
        .alert.warning {{ border-color: var(--warning); background: #fffbeb; }}
        .alert.info {{ border-color: var(--primary); background: #eef2ff; }}

        .alert .icon {{ font-size: 24px; }}
        .alert .content {{ flex: 1; }}
        .alert .title {{ font-weight: 600; color: var(--text); }}
        .alert .message {{ font-size: 14px; color: var(--muted); margin-top: 4px; }}
        .alert .badge {{
            padding: 4px 12px;
            border-radius: 20px;
            font-size: 12px;
            font-weight: 500;
            text-transform: uppercase;
        }}
        .alert.critical .badge {{ background: var(--danger); color: white; }}
        .alert.warning .badge {{ background: var(--warning); color: white; }}
        .alert.info .badge {{ background: var(--primary); color: white; }}

        .charts {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(450px, 1fr));
            gap: 24px;
        }}

        .chart-card {{
            background: var(--card);
            border-radius: 12px;
            padding: 24px;
            box-shadow: 0 1px 3px rgba(0,0,0,0.1);
        }}

        .chart-card h3 {{
            font-size: 16px;
            margin-bottom: 16px;
            color: var(--text);
        }}

        table {{
            width: 100%;
            border-collapse: collapse;
        }}

        th, td {{
            padding: 12px 16px;
            text-align: left;
            border-bottom: 1px solid #e2e8f0;
        }}

        th {{
            background: #f8fafc;
            font-weight: 600;
            font-size: 13px;
            text-transform: uppercase;
            color: var(--muted);
        }}

        tr:hover {{ background: #f8fafc; }}

        .progress-bar {{
            width: 100%;
            height: 8px;
            background: #e2e8f0;
            border-radius: 4px;
            overflow: hidden;
        }}

        .progress-bar .fill {{
            height: 100%;
            border-radius: 4px;
            transition: width 0.3s;
        }}

        .progress-bar .fill.success {{ background: var(--success); }}
        .progress-bar .fill.warning {{ background: var(--warning); }}
        .progress-bar .fill.danger {{ background: var(--danger); }}

        footer {{
            text-align: center;
            padding: 32px;
            color: var(--muted);
            font-size: 14px;
        }}

        @media (max-width: 768px) {{
            .header {{ flex-direction: column; gap: 12px; text-align: center; }}
            .tabs {{ overflow-x: auto; }}
            .charts {{ grid-template-columns: 1fr; }}
        }}
    </style>
</head>
<body>
    <div class="header">
        <div>
            <h1>🏢 UNS Unified Dashboard</h1>
            <div class="meta">ユニバーサル企画株式会社</div>
        </div>
        <div class="meta">
            期間: {period} | 更新: {datetime.now().strftime("%Y-%m-%d %H:%M")}
        </div>
    </div>

    <div class="container">
        <div class="tabs">
            <button class="tab active" onclick="showTab('overview')">📊 Overview</button>
            <button class="tab" onclick="showTab('alerts')">⚠️ Alerts ({critical_count + warning_count})</button>
            <button class="tab" onclick="showTab('analytics')">📈 Analytics</button>
            <button class="tab" onclick="showTab('clients')">🏭 派遣先</button>
        </div>

        <!-- Overview Tab -->
        <div id="overview" class="tab-content active">
            <div class="grid">
                <div class="card">
                    <h3>🔴 Critical Alerts</h3>
                    <div class="value danger">{critical_count}</div>
                </div>
                <div class="card">
                    <h3>🟠 Warnings</h3>
                    <div class="value warning">{warning_count}</div>
                </div>
                <div class="card">
                    <h3>🛂 Visa Alerts</h3>
                    <div class="value primary">{len(all_alerts.get("visa", []))}</div>
                </div>
                <div class="card">
                    <h3>⏰ Overtime Alerts</h3>
                    <div class="value primary">{len(all_alerts.get("overtime", []))}</div>
                </div>
            </div>

            <div class="charts">
                <div class="chart-card">
                    <h3>📈 粗利 Trend (6 months)</h3>
                    <canvas id="profitTrendChart"></canvas>
                </div>
                <div class="chart-card">
                    <h3>📊 Billing vs Profit</h3>
                    <canvas id="billingProfitChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Alerts Tab -->
        <div id="alerts" class="tab-content">
            <h2 style="margin-bottom: 20px;">⚠️ Active Alerts</h2>
            <div class="alerts-list">
"""

    # Add alerts
    for alert in all_alerts_flat[:20]:
        level = alert.get("level", "info")
        html += f"""
                <div class="alert {level}">
                    <div class="icon">{alert.get("emoji", "📋")}</div>
                    <div class="content">
                        <div class="title">[{alert.get("category", "").upper()}] {alert.get("employee_name", "Unknown")}</div>
                        <div class="message">{alert.get("message", "")}</div>
                    </div>
                    <span class="badge">{level}</span>
                </div>
"""

    if not all_alerts_flat:
        html += '<div class="alert info"><div class="icon">✅</div><div class="content"><div class="title">No active alerts</div></div></div>'

    html += """
            </div>
        </div>

        <!-- Analytics Tab -->
        <div id="analytics" class="tab-content">
            <div class="charts">
                <div class="chart-card">
                    <h3>📈 Profit Rate Trend</h3>
                    <canvas id="profitRateChart"></canvas>
                </div>
                <div class="chart-card">
                    <h3>🏭 派遣先 Comparison</h3>
                    <canvas id="clientCompareChart"></canvas>
                </div>
            </div>
        </div>

        <!-- Clients Tab -->
        <div id="clients" class="tab-content">
            <div class="card">
                <h3 style="margin-bottom: 16px;">🏭 派遣先 Profitability</h3>
                <table>
                    <thead>
                        <tr>
                            <th>派遣先</th>
                            <th>従業員</th>
                            <th>請求額</th>
                            <th>粗利</th>
                            <th>粗利率</th>
                        </tr>
                    </thead>
                    <tbody>
"""

    for client in client_comparison[:10]:
        rate = client.get("avg_profit_rate", 0)
        color = "success" if rate >= 25 else "warning" if rate >= 15 else "danger"
        html += f"""
                        <tr>
                            <td><strong>{client.get("client_name", "Unknown")}</strong></td>
                            <td>{client.get("employee_count", 0)}名</td>
                            <td>¥{client.get("total_billing", 0):,}</td>
                            <td>¥{client.get("total_profit", 0):,}</td>
                            <td>
                                <div style="display: flex; align-items: center; gap: 8px;">
                                    <div class="progress-bar" style="width: 80px;">
                                        <div class="fill {color}" style="width: {min(rate * 2, 100)}%;"></div>
                                    </div>
                                    <span>{rate}%</span>
                                </div>
                            </td>
                        </tr>
"""

    html += f"""
                    </tbody>
                </table>
            </div>
        </div>
    </div>

    <footer>
        UNS MEGA UPGRADE v{VERSION} | ユニバーサル企画株式会社 | Generated {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
    </footer>

    <script>
        // Tab switching
        function showTab(tabId) {{
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab').forEach(el => el.classList.remove('active'));
            document.getElementById(tabId).classList.add('active');
            event.target.classList.add('active');
        }}

        // Profit Trend Chart
        new Chart(document.getElementById('profitTrendChart'), {{
            type: 'line',
            data: {{
                labels: {trend_labels},
                datasets: [{{
                    label: '粗利',
                    data: {trend_profit},
                    borderColor: '#10b981',
                    backgroundColor: 'rgba(16, 185, 129, 0.1)',
                    fill: true,
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{ y: {{ beginAtZero: true }} }}
            }}
        }});

        // Billing vs Profit Chart
        new Chart(document.getElementById('billingProfitChart'), {{
            type: 'bar',
            data: {{
                labels: {trend_labels},
                datasets: [
                    {{
                        label: '請求額',
                        data: {trend_billing},
                        backgroundColor: '#4f46e5'
                    }},
                    {{
                        label: '粗利',
                        data: {trend_profit},
                        backgroundColor: '#10b981'
                    }}
                ]
            }},
            options: {{
                responsive: true,
                scales: {{ y: {{ beginAtZero: true }} }}
            }}
        }});

        // Profit Rate Chart
        new Chart(document.getElementById('profitRateChart'), {{
            type: 'line',
            data: {{
                labels: {trend_labels},
                datasets: [{{
                    label: '粗利率 (%)',
                    data: {trend_rate},
                    borderColor: '#f59e0b',
                    backgroundColor: 'rgba(245, 158, 11, 0.1)',
                    fill: true,
                    tension: 0.4
                }}]
            }},
            options: {{
                responsive: true,
                plugins: {{ legend: {{ display: false }} }},
                scales: {{ y: {{ min: 0, max: 50 }} }}
            }}
        }});

        // Client Comparison Chart
        new Chart(document.getElementById('clientCompareChart'), {{
            type: 'bar',
            data: {{
                labels: {client_labels},
                datasets: [{{
                    label: '粗利率 (%)',
                    data: {client_rates},
                    backgroundColor: [
                        '#4f46e5', '#7c3aed', '#10b981', '#f59e0b', '#ef4444',
                        '#06b6d4', '#8b5cf6', '#14b8a6', '#f97316', '#ec4899'
                    ]
                }}]
            }},
            options: {{
                responsive: true,
                indexAxis: 'y',
                scales: {{ x: {{ min: 0, max: 50 }} }}
            }}
        }});
    </script>
</body>
</html>"""

    return html


# ============================================
# NOTIFICATIONS RUNNER
# ============================================


def run_daily_notifications(channels: list[str] = None):
    """Run daily notification checks"""
    if channels is None:
        channels = ["line"]

    all_alerts = check_all_alerts()

    # Prepare message
    critical = []
    warning = []

    for category, alerts in all_alerts.items():
        for a in alerts:
            if a.get("level") == "critical":
                critical.append(a.get("message", ""))
            elif a.get("level") == "warning":
                warning.append(a.get("message", ""))

    if not critical and not warning:
        print("✅ No alerts to send")
        return

    # Build message
    msg = f"\n📋 UNS Daily Alert Report\n日付: {datetime.now().strftime('%Y-%m-%d')}\n"

    if critical:
        msg += f"\n🔴 CRITICAL ({len(critical)}):\n"
        for m in critical[:5]:
            msg += f"  • {m}\n"

    if warning:
        msg += f"\n🟠 WARNING ({len(warning)}):\n"
        for m in warning[:5]:
            msg += f"  • {m}\n"

    # Send to channels
    for channel in channels:
        if channel == "line":
            if send_line_notify(msg):
                print("✅ LINE notification sent")
            else:
                print("❌ LINE notification failed")
        elif channel == "slack":
            if send_slack_webhook(msg):
                print("✅ Slack notification sent")
            else:
                print("❌ Slack notification failed")


# ============================================
# MAIN CLI
# ============================================


def main():
    parser = argparse.ArgumentParser(description=f"UNS MEGA UPGRADE v{VERSION}")
    subparsers = parser.add_subparsers(dest="command")

    # Init
    subparsers.add_parser("init", help="Initialize tables")

    # Dashboard
    dash = subparsers.add_parser("dashboard", help="Generate dashboard")
    dash.add_argument("--month", help="Period")
    dash.add_argument("--output", "-o", default="dashboard.html")

    # Alerts
    alerts_cmd = subparsers.add_parser("alerts", help="Check alerts")
    alerts_cmd.add_argument("--month", help="Period")
    alerts_cmd.add_argument("--json", action="store_true")

    # Notify
    notify = subparsers.add_parser("notify", help="Send notifications")
    notify.add_argument("--channels", nargs="+", default=["line"])
    notify.add_argument("--test", action="store_true")

    # Analytics
    analytics = subparsers.add_parser("analytics", help="Run analytics")
    analytics.add_argument("--type", choices=["profit", "clients", "overtime"], default="profit")
    analytics.add_argument("--json", action="store_true")

    args = parser.parse_args()

    if args.command == "init":
        ensure_tables()
        print("✅ Tables initialized")

    elif args.command == "dashboard":
        html = generate_unified_dashboard(args.month)
        Path(args.output).write_text(html, encoding="utf-8")
        print(f"✅ Dashboard saved: {args.output}")

    elif args.command == "alerts":
        all_alerts = check_all_alerts(args.month)

        if args.json:
            print(json.dumps(all_alerts, ensure_ascii=False, indent=2))
        else:
            for category, alerts in all_alerts.items():
                if alerts:
                    print(f"\n{category.upper()} ALERTS:")
                    for a in alerts:
                        print(f"  {a.get('message', '')}")

    elif args.command == "notify":
        if args.test:
            if send_line_notify("🧪 Test notification from UNS MEGA UPGRADE"):
                print("✅ Test notification sent")
            else:
                print("❌ Test failed - check LINE_NOTIFY_TOKEN")
        else:
            run_daily_notifications(args.channels)

    elif args.command == "analytics":
        if args.type == "profit":
            data = calculate_profit_trends()
        elif args.type == "clients":
            data = calculate_client_comparison()
        elif args.type == "overtime":
            data = calculate_overtime_heatmap()

        if args.json:
            print(json.dumps(data, ensure_ascii=False, indent=2))
        else:
            print(json.dumps(data, ensure_ascii=False, indent=2))

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
