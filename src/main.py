"""
UNS Outlook Backup v3.0 — Entry point (pywebview)
==================================================
Modo normal: lanza la UI HTML/CSS/JS dentro de WebView2 nativo de Windows.
Modo auto:   `--auto` ejecuta backup desde config sin GUI (Task Scheduler).
"""

import argparse
import datetime
import logging
import os
import sys

SRC_DIR = os.path.dirname(os.path.abspath(__file__))
if SRC_DIR not in sys.path:
    sys.path.insert(0, SRC_DIR)


def get_resource_path(relative: str) -> str:
    """Resuelve path tanto en modo dev como en .exe empaquetado."""
    try:
        base = sys._MEIPASS  # type: ignore[attr-defined]  # PyInstaller runtime
    except AttributeError:
        base = SRC_DIR
    return os.path.join(base, relative)


def setup_logging(log_to_file: bool = False) -> None:
    """Configura logging via observability.setup_logger.

    Mantiene la misma API que la version anterior (log_to_file bool) pero
    ahora delega a structlog con sinks JSON (archivo) + consola formateada.
    """
    from observability import setup_logger

    json_file = None
    if log_to_file:
        from config import get_config_dir

        json_file = get_config_dir() / "auto.log"

    setup_logger(
        json_file=json_file,
        level=logging.INFO,
        add_console=True,
    )


def run_gui() -> int:
    """Lanza pywebview con la UI HTML/CSS/JS.

    Antes de abrir la ventana, valida que el runtime WebView2 este instalado
    (Fase 2 plan v3.2). En Win 10 < 22H2 puede faltar y la app abriria ventana
    en blanco sin error visible. `ensure_webview2_runtime` muestra un dialogo
    japones via tkinter y, si el usuario acepta, ejecuta el bootstrapper
    bundleado o lo descarga de Microsoft.

    Returns:
        0 en exit normal, 2 si el usuario rechazo instalar WebView2.
    """
    from runtime_check import ensure_webview2_runtime

    if not ensure_webview2_runtime(interactive=True):
        log = logging.getLogger("uns-backup-gui")
        log.error("WebView2 ausente y no se pudo instalar; la GUI no puede arrancar")
        return 2

    import webview

    from api import API
    from observability.logging import bind_context

    bind_context(operation="gui")
    api = API()

    # Path al index.html
    index_path = get_resource_path(os.path.join("web", "index.html"))
    if not os.path.exists(index_path):
        # Fallback: buscar en src/web
        index_path = os.path.join(SRC_DIR, "web", "index.html")

    window = webview.create_window(
        title="UNS Backup · ユニバーサル企画株式会社",
        url=index_path,
        js_api=api,
        width=1280,
        height=860,
        min_size=(1100, 720),
        background_color="#050714",
        easy_drag=False,
        text_select=True,
    )
    assert window is not None, "webview.create_window returned None"

    # Auto-detect Outlook al iniciar (con delay de 500ms para que UI cargue)
    def on_loaded() -> None:
        try:
            window.evaluate_js("if (window.app && window.app.onAppReady) window.app.onAppReady();")
        except Exception:
            pass

    window.events.loaded += on_loaded

    webview.start(debug=False, http_server=False)
    return 0


def run_auto_backup() -> int:
    """Modo auto: ejecuta backup desde config sin GUI."""
    setup_logging(log_to_file=True)
    from observability.logging import bind_context

    bind_context(operation="auto-backup")
    log = logging.getLogger("uns-backup-auto")
    log.info("=" * 60)
    log.info("🤖 自動バックアップ開始")
    log.info("=" * 60)

    try:
        from backup_engine import BackupEngine
        from config import Config
        from history_manager import BackupHistory
        from outlook_client import WIN32_AVAILABLE, OutlookClient

        if not WIN32_AVAILABLE:
            log.error("pywin32 no disponible")
            return 1

        config = Config()
        if not config.get("schedule_enabled"):
            log.warning("Schedule deshabilitado, saliendo")
            return 0

        log.info("📡 Outlookに接続中...")
        client = OutlookClient()
        accounts = client.list_accounts()
        log.info(f"✅ {len(accounts)}件のアカウント検出")

        scope = config.get("schedule_scope", "uns_only")
        domain = config.get("domain_filter", "uns-kikaku.com")

        if scope == "all":
            selected = accounts
        elif scope == "uns_only":
            selected = [a for a in accounts if a.matches_domain(domain)]
        else:
            custom = config.get("schedule_custom_accounts", [])
            selected = [a for a in accounts if a.smtp_address in custom]

        if not selected:
            log.warning("バックアップ対象アカウントがありません")
            return 0

        log.info(f"📦 バックアップ対象: {len(selected)}件")

        save_to = config.get("schedule_save_to") or config.get("default_backup_dir")
        os.makedirs(save_to, exist_ok=True)

        engine = BackupEngine(
            outlook_client=client,
            output_dir=save_to,
            selected_accounts=selected,
            export_format=config.get("default_format", "pst"),
        )

        import threading

        done_event = threading.Event()
        result = {"success": False, "info": ""}

        def progress_cb(msg: str) -> None:
            log.info(msg)

        def finish_cb(success: bool, info: str) -> None:
            result["success"] = success
            result["info"] = info
            done_event.set()

        engine.run_async(progress_cb, finish_cb)
        done_event.wait(timeout=3600)

        keep_last = config.get("schedule_keep_last", 0)
        if keep_last > 0:
            log.info(f"🧹 cleanup keep_last={keep_last}")
            history = BackupHistory(save_to)
            deleted = history.cleanup_old(keep_last)
            log.info(f"   削除: {len(deleted)}件")

        if result["success"] and config.get("inventory_enabled"):
            try:
                from account_inventory import build_inventory, save_inventory

                inv = build_inventory(
                    outlook_client=client,
                    selected_smtp_addresses=[a.smtp_address for a in selected],
                    include_servers=config.get("inventory_include_servers", True),
                    include_passwords=False,
                )
                if inv and isinstance(result["info"], str) and os.path.isdir(result["info"]):
                    saved = save_inventory(inv, result["info"], password=None)
                    log.info(f"   📋 inventario: {saved}")
            except Exception as e:
                log.warning(f"⚠️ inventario falló: {e}")

        config.set("last_run_time", datetime.datetime.now().isoformat())
        config.set("last_run_status", "success" if result["success"] else "failed")
        config.save()

        return 0 if result["success"] else 1

    except Exception as e:
        log.exception(f"❌ {e}")
        return 1


def main() -> None:
    # Crash handler PRIMERO — captura excepciones de bootstrap incluso antes
    # de setup_logging. Cualquier error no atrapado escribe crashdump JSON
    # sanitizado a %APPDATA%\UNS-Kikaku\Backup\crashdumps\.
    from observability import install_crash_handler

    install_crash_handler()

    parser = argparse.ArgumentParser()
    parser.add_argument("--auto", action="store_true", help="Modo auto sin GUI (Task Scheduler)")
    args = parser.parse_args()

    if args.auto:
        sys.exit(run_auto_backup())
    else:
        sys.exit(run_gui())


if __name__ == "__main__":
    main()
