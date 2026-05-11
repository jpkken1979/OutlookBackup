"""Fixtures para tests E2E con Playwright contra el frontend HTML/JS.

Estrategia:
- `web_server` arranca un http.server local sirviendo src/web/ en un puerto
  random. Lo levanta una vez por sesion (scope=session).
- `mock_pywebview_init_script` devuelve el JS que se inyecta en cada page
  ANTES de los scripts del propio frontend. Reemplaza window.pywebview con
  un Proxy que retorna defaults razonables para cualquier metodo llamado.
- `page_with_app` es el helper principal — devuelve una Page de Playwright
  ya navegada al index.html con el mock activado.

Todos los tests E2E llevan @pytest.mark.e2e y se skipean si playwright no
esta importable o chromium no esta instalado.
"""

from __future__ import annotations

import http.server
import socket
import socketserver
import threading
from collections.abc import Iterator
from pathlib import Path
from typing import TYPE_CHECKING

import pytest

if TYPE_CHECKING:
    from playwright.sync_api import Page

# Skip todo el modulo si playwright no esta disponible
playwright = pytest.importorskip("playwright.sync_api")


WEB_DIR = Path(__file__).parent.parent.parent / "src" / "web"


def _find_free_port() -> int:
    """Busca un puerto libre y lo devuelve."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


class _QuietHandler(http.server.SimpleHTTPRequestHandler):
    """SimpleHTTPRequestHandler sin logging a stderr (pytest se confunde)."""

    def log_message(self, *args, **kwargs) -> None:  # noqa: ARG002
        pass


@pytest.fixture(scope="session")
def web_server() -> Iterator[str]:
    """Arranca http.server sirviendo src/web/ en puerto libre.

    Yields:
        URL base del servidor, ej "http://127.0.0.1:54321"
    """
    port = _find_free_port()

    class HandlerWithDir(_QuietHandler):
        def __init__(self, *args, **kwargs) -> None:
            super().__init__(*args, directory=str(WEB_DIR), **kwargs)

    httpd = socketserver.TCPServer(("127.0.0.1", port), HandlerWithDir)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()

    try:
        yield f"http://127.0.0.1:{port}"
    finally:
        httpd.shutdown()
        httpd.server_close()


# Script que se inyecta ANTES de cualquier <script> de la pagina.
# Reemplaza window.pywebview con un mock que retorna defaults sensatos.
MOCK_PYWEBVIEW_INIT = r"""
(function() {
    // Defaults por nombre de metodo. Se pueden override por test via
    // window.__mockApiOverrides = { method_name: () => Promise.resolve(...) }
    window.__mockApiOverrides = window.__mockApiOverrides || {};
    window.__mockApiCalls = [];

    const defaults = {
        connect_outlook: () => Promise.resolve({success: true}),
        detect_accounts: () => Promise.resolve({
            success: true,
            accounts: [
                {smtp: "kenji@uns-kikaku.com", name: "Kenji", type: "IMAP", selected: true},
            ]
        }),
        get_config: () => Promise.resolve({
            domain_filter: "uns-kikaku.com",
            default_format: "pst",
            default_backup_dir: "C:\\Backup",
            schedule_enabled: false
        }),
        update_config: () => Promise.resolve({success: true}),
        get_backup_progress: () => Promise.resolve({state: "idle", log: [], percent: 0}),
        get_import_progress: () => Promise.resolve({state: "idle", log: [], percent: 0}),
        get_cache_progress: () => Promise.resolve({state: "idle", log: [], percent: 0}),
        get_tools_progress: () => Promise.resolve({state: "idle", log: [], percent: 0}),
        scan_cache_files: () => Promise.resolve({success: true, files: []}),
        search_pst_files: () => Promise.resolve({success: true, files: []}),
        find_rar_files: () => Promise.resolve({success: true, files: []}),
        get_schedule_info: () => Promise.resolve({enabled: false}),
        load_history: () => Promise.resolve({success: true, backups: []}),
    };

    const handler = {
        get(_target, prop) {
            return function(...args) {
                window.__mockApiCalls.push({method: prop, args: args});
                if (window.__mockApiOverrides[prop]) {
                    return window.__mockApiOverrides[prop](...args);
                }
                if (defaults[prop]) {
                    return defaults[prop](...args);
                }
                // Default fallback: success vacio
                return Promise.resolve({success: true});
            };
        }
    };

    window.pywebview = {
        api: new Proxy({}, handler)
    };
})();
"""


@pytest.fixture
def page_with_app(page, web_server: str) -> Page:
    """Devuelve una Page de Playwright navegada al index con mock activo."""
    page.add_init_script(MOCK_PYWEBVIEW_INIT)
    page.goto(f"{web_server}/index.html")
    # Esperar a que el orquestador termine init (waits for pywebview)
    page.wait_for_load_state("networkidle")
    return page
