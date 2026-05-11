"""Tests E2E basicos del frontend con Playwright.

Validan que la app carga, los 7 tabs estan visibles, el orquestador
arranca correctamente con el mock de window.pywebview.api.
"""

from __future__ import annotations

import pytest

# Skip todo el modulo si playwright no esta disponible / chromium no instalado
pytestmark = pytest.mark.e2e


class TestAppBootstrap:
    """La app carga y los 7 tabs son visibles."""

    def test_page_title_contains_uns(self, page_with_app) -> None:
        assert "UNS" in page_with_app.title()

    def test_all_seven_tabs_visible(self, page_with_app) -> None:
        expected_tabs = ["backup", "restore", "history", "auto", "cache", "tools", "settings"]
        for tab_name in expected_tabs:
            tab = page_with_app.locator(f'.tab[data-tab="{tab_name}"]')
            assert tab.is_visible(), f"Tab '{tab_name}' no es visible"

    def test_backup_tab_is_active_by_default(self, page_with_app) -> None:
        backup_tab = page_with_app.locator('.tab[data-tab="backup"]')
        assert "active" in (backup_tab.get_attribute("class") or "")

    def test_connection_badge_present(self, page_with_app) -> None:
        badge = page_with_app.locator(".conn-badge")
        assert badge.is_visible()

    def test_app_calls_connect_outlook_on_load(self, page_with_app) -> None:
        """El orquestador debe llamar connect_outlook al arrancar."""
        # Dar tiempo a que el init async termine
        page_with_app.wait_for_function(
            "window.__mockApiCalls && window.__mockApiCalls.length > 0",
            timeout=3000,
        )
        calls = page_with_app.evaluate("window.__mockApiCalls.map(c => c.method)")
        assert "connect_outlook" in calls


class TestTabNavigation:
    """Navegacion entre tabs."""

    def test_clicking_tab_activates_it(self, page_with_app) -> None:
        page_with_app.locator('.tab[data-tab="restore"]').click()
        restore_tab = page_with_app.locator('.tab[data-tab="restore"]')
        assert "active" in (restore_tab.get_attribute("class") or "")

    def test_clicking_tab_shows_corresponding_content(self, page_with_app) -> None:
        page_with_app.locator('.tab[data-tab="history"]').click()
        content = page_with_app.locator('.tab-content[data-tab-content="history"]')
        assert "active" in (content.get_attribute("class") or "")

    def test_only_one_tab_active_at_a_time(self, page_with_app) -> None:
        page_with_app.locator('.tab[data-tab="auto"]').click()
        active_tabs = page_with_app.locator(".tab.active").count()
        assert active_tabs == 1


class TestConnectionFlow:
    """Flujo de conexion con Outlook (mockeado)."""

    def test_failing_connect_shows_offline_badge(self, page_with_app) -> None:
        """Si connect_outlook devuelve success=False, el badge queda offline.

        Setea el override + recarga con add_init_script para que persista.
        """
        page_with_app.add_init_script(r"""
            window.__mockApiOverrides = window.__mockApiOverrides || {};
            window.__mockApiOverrides.connect_outlook = () => Promise.resolve({
                success: false, error: "Outlook not running"
            });
        """)
        page_with_app.reload()
        page_with_app.wait_for_load_state("networkidle")

        badge = page_with_app.locator(".conn-badge")
        page_with_app.wait_for_function(
            "document.querySelector('.conn-badge').classList.contains('offline')",
            timeout=3000,
        )
        assert "offline" in (badge.get_attribute("class") or "")
