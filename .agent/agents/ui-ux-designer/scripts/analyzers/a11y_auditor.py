"""A11y auditor — WCAG 2.2 audit via axe-core en browser real (Playwright)."""
import logging
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

try:
    from playwright.sync_api import sync_playwright
    from axe_playwright_python.sync_playwright import Axe as _Axe
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False
    _Axe = None  # type: ignore[assignment, misc]
    logger.info("Playwright no disponible — modo static_only activo")

Axe: type | None = _Axe  # exists in namespace even when import fails

Axe: type | None = _Axe  # exists in namespace even when import fails


@dataclass
class A11yViolation:
    """Violación de accesibilidad detectada por axe-core."""

    rule_id: str
    impact: str
    selector: str
    description: str
    wcag_tags: list[str] = field(default_factory=list)


def audit_url(url: str, timeout_ms: int = 30_000) -> list[A11yViolation]:
    """Corre audit WCAG 2.2 sobre una URL usando axe-core en Chromium headless.

    Args:
        url: URL del dev server a auditar.
        timeout_ms: Timeout de navegación en milisegundos.

    Returns:
        Lista de A11yViolation. Vacía si Playwright no está disponible o la URL no responde.
    """
    if not PLAYWRIGHT_AVAILABLE:
        logger.warning("Playwright no disponible. Saltando audit live de accesibilidad.")
        return []

    violations: list[A11yViolation] = []
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            page = browser.new_page()
            page.goto(url, timeout=timeout_ms)
            page.wait_for_load_state("networkidle", timeout=timeout_ms)

            axe = Axe()
            results = axe.run(page)
            browser.close()

        for v in results.get("violations", []):
            for node in v.get("nodes", []):
                selector = ", ".join(node.get("target", ["unknown"]))
                violations.append(
                    A11yViolation(
                        rule_id=v["id"],
                        impact=v.get("impact", "unknown"),
                        selector=selector,
                        description=v.get("description", ""),
                        wcag_tags=v.get("tags", []),
                    )
                )
    except Exception as exc:
        logger.warning("Error durante audit de accesibilidad en %s: %s", url, exc)

    return violations
