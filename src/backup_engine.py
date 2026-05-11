"""
UNS Outlook Backup - Motor de backup
=====================================
Maneja el proceso de backup con threading y genera reportes.
"""

from __future__ import annotations

import datetime
import json
import os
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from outlook.protocols import OutlookAccountInfo, OutlookClientProtocol


class BackupReport:
    """Genera reportes del proceso de backup."""

    def __init__(self):
        self.start_time = datetime.datetime.now()
        self.end_time: datetime.datetime | None = None
        self.accounts_processed = []
        self.errors = []
        self.total_emails = 0
        self.total_size_bytes = 0
        self.output_dir = ""

    def add_account(self, account_data: dict):
        self.accounts_processed.append(account_data)
        self.total_emails += account_data.get("emails", 0)

    def add_error(self, message: str):
        self.errors.append(
            {
                "time": datetime.datetime.now().isoformat(),
                "message": message,
            }
        )

    def finish(self):
        self.end_time = datetime.datetime.now()

    @property
    def duration_seconds(self) -> float:
        if self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0

    def to_dict(self) -> dict:
        return {
            "start_time": self.start_time.isoformat(),
            "end_time": self.end_time.isoformat() if self.end_time else None,
            "duration_seconds": self.duration_seconds,
            "accounts_processed": self.accounts_processed,
            "errors": self.errors,
            "total_emails": self.total_emails,
            "output_dir": self.output_dir,
        }

    def save_json(self, path: str):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(self.to_dict(), f, ensure_ascii=False, indent=2)

    def save_html(self, path: str):
        """Genera reporte HTML visual con branding UNS."""
        html = self._render_html()
        with open(path, "w", encoding="utf-8") as f:
            f.write(html)

    def _render_html(self) -> str:
        accounts_rows = ""
        for acc in self.accounts_processed:
            status_icon = "✅" if acc.get("success") else "❌"
            accounts_rows += f"""
            <tr>
                <td>{status_icon}</td>
                <td><strong>{acc.get("smtp", "")}</strong></td>
                <td>{acc.get("type", "")}</td>
                <td style="text-align:right">{acc.get("emails", 0):,}</td>
                <td style="text-align:right">{acc.get("size_mb", 0)} MB</td>
                <td><code>{acc.get("output_file", "")}</code></td>
            </tr>
            """

        errors_section = ""
        if self.errors:
            error_items = "".join(
                f"<li><code>{e['time']}</code> — {e['message']}</li>" for e in self.errors
            )
            errors_section = f"""
            <div class="card error-card">
                <h2>⚠️ Errores ({len(self.errors)})</h2>
                <ul>{error_items}</ul>
            </div>
            """

        duration = self.duration_seconds
        if duration < 60:
            duration_str = f"{duration:.1f} segundos"
        elif duration < 3600:
            duration_str = f"{duration / 60:.1f} minutos"
        else:
            duration_str = f"{duration / 3600:.1f} horas"

        return f"""<!DOCTYPE html>
<html lang="es">
<head>
<meta charset="UTF-8">
<title>UNS Backup Report</title>
<style>
* {{ margin: 0; padding: 0; box-sizing: border-box; }}
body {{
    font-family: 'Segoe UI', 'Yu Gothic', 'Meiryo', sans-serif;
    background: #f5f7fa; color: #1a1a1a; padding: 32px;
}}
.container {{ max-width: 1100px; margin: 0 auto; }}
header {{
    background: linear-gradient(135deg, #0052CC 0%, #003d99 100%);
    color: white; padding: 40px; border-radius: 16px;
    margin-bottom: 32px;
    box-shadow: 0 8px 24px rgba(0, 82, 204, 0.2);
}}
header h1 {{ font-size: 32px; margin-bottom: 8px; }}
header .subtitle {{ opacity: 0.9; font-size: 16px; }}
header .timestamp {{
    margin-top: 16px; opacity: 0.8; font-size: 14px;
    border-top: 1px solid rgba(255,255,255,0.2); padding-top: 12px;
}}
.stats {{
    display: grid; grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
    gap: 16px; margin-bottom: 24px;
}}
.stat-card {{
    background: white; padding: 24px; border-radius: 12px;
    box-shadow: 0 2px 8px rgba(0,0,0,0.06);
    border-left: 4px solid #0052CC;
}}
.stat-card .label {{
    font-size: 13px; color: #666; text-transform: uppercase;
    letter-spacing: 0.5px; margin-bottom: 8px;
}}
.stat-card .value {{ font-size: 32px; font-weight: 700; color: #0052CC; }}
.card {{
    background: white; padding: 28px; border-radius: 12px;
    margin-bottom: 24px; box-shadow: 0 2px 8px rgba(0,0,0,0.06);
}}
.card h2 {{
    color: #0052CC; margin-bottom: 16px; padding-bottom: 12px;
    border-bottom: 2px solid #f0f3f7;
}}
table {{ width: 100%; border-collapse: collapse; }}
th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #eee; }}
th {{
    background: #f8fafc; color: #555; font-weight: 600;
    font-size: 13px; text-transform: uppercase; letter-spacing: 0.5px;
}}
tr:hover {{ background: #fafbfd; }}
code {{
    background: #f4f5f7; padding: 2px 6px; border-radius: 4px;
    font-family: 'Cascadia Code', Consolas, monospace; font-size: 12px;
}}
.error-card {{ border-left: 4px solid #e74c3c; }}
.error-card h2 {{ color: #e74c3c; }}
ul {{ padding-left: 20px; }}
li {{ margin-bottom: 8px; }}
footer {{
    text-align: center; padding: 24px; color: #888; font-size: 13px;
    margin-top: 32px;
}}
</style>
</head>
<body>
<div class="container">
    <header>
        <h1>📦 UNS Outlook Backup Report</h1>
        <div class="subtitle">ユニバーサル企画株式会社 — Reporte de respaldo de correo</div>
        <div class="timestamp">
            Generado: {datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")}
        </div>
    </header>

    <div class="stats">
        <div class="stat-card">
            <div class="label">Cuentas procesadas</div>
            <div class="value">{len(self.accounts_processed)}</div>
        </div>
        <div class="stat-card">
            <div class="label">Total de correos</div>
            <div class="value">{self.total_emails:,}</div>
        </div>
        <div class="stat-card">
            <div class="label">Duración</div>
            <div class="value" style="font-size:24px">{duration_str}</div>
        </div>
        <div class="stat-card">
            <div class="label">Errores</div>
            <div class="value" style="color:{"#e74c3c" if self.errors else "#2ecc71"}">
                {len(self.errors)}
            </div>
        </div>
    </div>

    <div class="card">
        <h2>📧 Cuentas respaldadas</h2>
        <table>
            <thead>
                <tr>
                    <th></th>
                    <th>Cuenta</th>
                    <th>Tipo</th>
                    <th>Correos</th>
                    <th>Tamaño</th>
                    <th>Archivo</th>
                </tr>
            </thead>
            <tbody>
                {accounts_rows}
            </tbody>
        </table>
    </div>

    <div class="card">
        <h2>📂 Ubicación de los archivos</h2>
        <p><code>{self.output_dir}</code></p>
        <p style="margin-top:12px; color:#666; font-size:14px;">
            Para importar un PST en Outlook: <strong>File → Open & Export → Open Outlook Data File</strong>
        </p>
    </div>

    {errors_section}

    <footer>
        UNS Outlook Backup Tool · ユニバーサル企画株式会社<br>
        Si tienes problemas, contacta al administrador del sistema.
    </footer>
</div>
</body>
</html>
"""


class BackupEngine:
    """Motor que ejecuta el backup en un thread separado.

    Acepta cualquier objeto que cumpla `OutlookClientProtocol` (no solo el
    OutlookClient real). Esto permite tests con FakeOutlookClient sin Outlook.
    """

    def __init__(
        self,
        outlook_client: OutlookClientProtocol,
        output_dir: str,
        selected_accounts: list[OutlookAccountInfo],
        export_format: str = "pst",
    ):
        self.client = outlook_client
        self.output_dir = output_dir
        self.selected_accounts = selected_accounts
        self.export_format = export_format  # 'pst' o 'msg'
        self.report = BackupReport()
        self.report.output_dir = output_dir
        self._cancel_flag = threading.Event()
        self._thread: threading.Thread | None = None

    def run_async(self, progress_cb: Callable, finish_cb: Callable):
        """Ejecuta el backup en un thread separado."""
        self._thread = threading.Thread(
            target=self._run_internal,
            args=(progress_cb, finish_cb),
            daemon=True,
        )
        self._thread.start()

    def cancel(self):
        self._cancel_flag.set()

    def _run_internal(self, progress_cb: Callable, finish_cb: Callable):
        """Lógica principal del backup."""
        try:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
            session_dir = os.path.join(self.output_dir, f"backup_{timestamp}")
            os.makedirs(session_dir, exist_ok=True)
            self.report.output_dir = session_dir

            progress_cb(f"🚀 Iniciando backup de {len(self.selected_accounts)} cuenta(s)")
            progress_cb(f"📂 Carpeta destino: {session_dir}")
            progress_cb("─" * 60)

            for i, account in enumerate(self.selected_accounts, 1):
                if self._cancel_flag.is_set():
                    progress_cb("⛔ Backup cancelado por el usuario")
                    break

                progress_cb(f"\n[{i}/{len(self.selected_accounts)}] {account.smtp_address}")

                # Sanitizar nombre del archivo
                safe_name = account.smtp_address.replace("@", "_at_").replace(".", "_")

                acc_result = {
                    "smtp": account.smtp_address,
                    "name": account.display_name,
                    "type": account.account_type,
                    "success": False,
                    "emails": 0,
                    "size_mb": 0,
                    "output_file": "",
                }

                try:
                    if self.export_format == "pst":
                        output_file = os.path.join(session_dir, f"{safe_name}.pst")
                        success = self.client.export_account_to_pst(
                            account, output_file, progress_cb
                        )
                        acc_result["output_file"] = output_file
                        acc_result["success"] = success

                        if success and os.path.exists(output_file):
                            size = os.path.getsize(output_file)
                            acc_result["size_mb"] = round(size / (1024 * 1024), 2)

                    else:  # msg format
                        output_subdir = os.path.join(session_dir, safe_name)
                        count = self.client.export_folder_to_msg_files(
                            account, output_subdir, progress_cb
                        )
                        acc_result["emails"] = count
                        acc_result["output_file"] = output_subdir
                        acc_result["success"] = count > 0

                    # Contar emails después del backup
                    counts = self.client.count_emails_for_account(account)
                    if counts["total_emails"] > 0:
                        acc_result["emails"] = counts["total_emails"]

                except Exception as e:
                    error_msg = f"Error en cuenta {account.smtp_address}: {e}"
                    progress_cb(f"❌ {error_msg}")
                    self.report.add_error(error_msg)

                self.report.add_account(acc_result)

            self.report.finish()

            # Generar reportes
            progress_cb("\n📊 Generando reportes...")
            json_path = os.path.join(session_dir, "report.json")
            html_path = os.path.join(session_dir, "report.html")
            self.report.save_json(json_path)
            self.report.save_html(html_path)

            progress_cb(f"✅ Reporte HTML: {html_path}")
            progress_cb(f"✅ Reporte JSON: {json_path}")
            progress_cb("\n🎉 Backup completado")

            finish_cb(True, session_dir)

        except Exception as e:
            error_msg = f"Error fatal: {e}"
            progress_cb(f"❌ {error_msg}")
            self.report.add_error(error_msg)
            self.report.finish()
            finish_cb(False, str(e))
