"""Tests E2E para los tabs restore, cache, settings.

Cobertura del bindings basicos de cada page: click en el boton dispara
la API correspondiente, los radios actualizan estado, etc.
"""

from __future__ import annotations

import pytest

pytestmark = pytest.mark.e2e


def _switch_to_tab(page, tab_name: str) -> None:
    """Helper: click en el tab y espera a que sea active."""
    page.locator(f'.tab[data-tab="{tab_name}"]').click()
    page.wait_for_function(
        f'document.querySelector(\'.tab[data-tab="{tab_name}"]\').classList.contains("active")',
        timeout=2000,
    )


def _reset_calls(page, method: str) -> None:
    """Borra del log el metodo dado para asserts limpios."""
    page.evaluate(
        f'window.__mockApiCalls = window.__mockApiCalls.filter(c => c.method !== "{method}")'
    )


def _wait_for_call(page, method: str, timeout: int = 3000) -> int:
    """Espera a que aparezca una llamada al metodo y devuelve el count."""
    page.wait_for_function(
        f'window.__mockApiCalls.some(c => c.method === "{method}")',
        timeout=timeout,
    )
    return page.evaluate(f'window.__mockApiCalls.filter(c => c.method === "{method}").length')


class TestRestoreTab:
    """Tab Restore — search PST, import method selection."""

    def test_clicking_search_pst_calls_api(self, page_with_app) -> None:
        _switch_to_tab(page_with_app, "restore")
        # El path no puede estar vacio — setear folder primero
        page_with_app.evaluate('document.getElementById("restore-folder").value = "C:\\\\Backup"')
        _reset_calls(page_with_app, "search_pst_files")

        page_with_app.locator("#btn-restore-search").click()
        count = _wait_for_call(page_with_app, "search_pst_files")
        assert count >= 1

    def test_method_card_click_marks_active(self, page_with_app) -> None:
        _switch_to_tab(page_with_app, "restore")
        # Click en el card de merge — debe agregar clase selected
        page_with_app.locator('.method-card[data-method="merge"]').click()
        page_with_app.wait_for_function(
            'document.querySelector(\'.method-card[data-method="merge"]\').classList.contains("selected")',
            timeout=2000,
        )

    def test_method_change_persists_config(self, page_with_app) -> None:
        _switch_to_tab(page_with_app, "restore")
        _reset_calls(page_with_app, "update_config")

        page_with_app.locator('.method-card[data-method="new_files"]').click()

        # Esperar a que update_config se llame con default_import_mode
        page_with_app.wait_for_function(
            "window.__mockApiCalls.some(c => "
            'c.method === "update_config" && '
            "c.args && c.args[0] && c.args[0].default_import_mode)",
            timeout=2000,
        )


class TestCacheTab:
    """Tab Cache — scan + backup."""

    def test_clicking_scan_calls_api(self, page_with_app) -> None:
        _switch_to_tab(page_with_app, "cache")
        _reset_calls(page_with_app, "scan_cache_files")

        page_with_app.locator("#btn-cache-scan").click()
        count = _wait_for_call(page_with_app, "scan_cache_files")
        assert count >= 1

    def test_scan_with_results_renders_cache_list(self, page_with_app) -> None:
        """Cuando scan devuelve files, deben renderizarse en #cache-list."""
        # Override del default mock para incluir files
        page_with_app.evaluate("""
            window.__mockApiOverrides.scan_cache_files = () => Promise.resolve({
                success: true,
                files: [
                    {path: "C:\\\\AppData\\\\Outlook\\\\kenji.ost", filename: "kenji.ost",
                     size_mb: 250, account_smtp: "kenji@uns-kikaku.com"}
                ]
            });
        """)
        _switch_to_tab(page_with_app, "cache")
        page_with_app.locator("#btn-cache-scan").click()
        # Esperar a que el empty-state desaparezca y el archivo aparezca
        page_with_app.wait_for_selector("#cache-list .empty-state", state="detached", timeout=3000)


class TestSettingsTab:
    """Tab Settings — domain filter save, refresh accounts."""

    def test_refresh_accounts_calls_detect(self, page_with_app) -> None:
        _switch_to_tab(page_with_app, "settings")
        _reset_calls(page_with_app, "detect_accounts")

        page_with_app.locator("#btn-settings-refresh-accounts").click()
        count = _wait_for_call(page_with_app, "detect_accounts")
        assert count >= 1

    def test_save_domain_persists_config(self, page_with_app) -> None:
        """Click save-domain dispara update_config — no asserts especificos
        sobre que key se manda porque persistAccountSettings agrupa varios."""
        _switch_to_tab(page_with_app, "settings")
        page_with_app.wait_for_selector("#settings-domain-filter", timeout=2000)
        page_with_app.locator("#settings-domain-filter").fill("new-domain.com")
        _reset_calls(page_with_app, "update_config")

        page_with_app.locator("#btn-settings-save-domain").click()
        count = _wait_for_call(page_with_app, "update_config")
        assert count >= 1

    def test_format_radio_change_persists(self, page_with_app) -> None:
        _switch_to_tab(page_with_app, "settings")
        page_with_app.wait_for_selector('input[name="settings-format"][value="msg"]', timeout=2000)
        _reset_calls(page_with_app, "update_config")

        page_with_app.locator('input[name="settings-format"][value="msg"]').click(force=True)
        page_with_app.wait_for_function(
            'window.__mockApiCalls.some(c => c.method === "update_config")',
            timeout=2000,
        )
