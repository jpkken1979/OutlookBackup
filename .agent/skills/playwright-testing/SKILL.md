---
name: playwright-testing
description: "Automatización de testing E2E con Playwright. Genera, ejecuta y analiza tests de browser automation."
type: feature
category: testing
version: "1.0.0"
author: Antigravity Team
source: internal
dependencies: [playwright, pytest-playwright]
related_skills: [e2e-testing-patterns, webapp-testing]
keywords: [playwright, e2e, testing, browser, automation, web]
tier: 3
---

# Playwright Testing Skill

Skill avanzado para automatización de tests end-to-end usando Playwright.

## Capacidades

### Testing E2E
- Generación automática de tests desde user flows
- Ejecución paralela multi-browser (Chromium, Firefox, WebKit)
- Screenshots y videos automáticos en fallos
- Tracing para debugging

### Selectors Inteligentes
- Auto-generación de selectors robustos
- Soporte para data-testid, aria-labels, text content
- Selector healing automático

### Integración CI/CD
- Configuración para GitHub Actions
- Reportes HTML/JSON
- Sharding para ejecución paralela

## Uso

### Generar tests desde flujo de usuario

```bash
python scripts/playwright_testing.py generate \
  --url "https://example.com" \
  --flow "login,dashboard,logout"
```

### Ejecutar tests

```bash
python scripts/playwright_testing.py run \
  --browser chromium \
  --parallel 4
```

### Analizar resultados

```bash
python scripts/playwright_testing.py analyze \
  --report-dir ./playwright-report
```

## Estructura de Tests Generados

```python
import pytest
from playwright.sync_api import Page, expect

class TestUserFlow:
    def test_login_flow(self, page: Page):
        # Navigate
        page.goto("https://example.com/login")

        # Fill form
        page.get_by_label("Email").fill("user@example.com")
        page.get_by_label("Password").fill("password")

        # Submit
        page.get_by_role("button", name="Login").click()

        # Assert
        expect(page).to_have_url("/dashboard")
        expect(page.get_by_text("Welcome")).to_be_visible()
```

## Configuración

### pytest.ini
```ini
[pytest]
addopts = --browser chromium --browser firefox
testpaths = tests/e2e
```

### playwright.config.py
```python
from playwright.sync_api import Playwright

def configure(playwright: Playwright):
    return {
        "timeout": 30000,
        "screenshot": "only-on-failure",
        "video": "retain-on-failure",
        "trace": "retain-on-failure"
    }
```

## Integración con Agentes

- `test-engineer` - Para generación de tests
- `qa-specialist` - Para revisión de coverage
- `debugger` - Para análisis de fallos

## Mejores Prácticas

1. **Selectors robustos**: Preferir `data-testid` sobre selectores CSS
2. **Timeouts explícitos**: Usar `expect().to_be_visible(timeout=5000)`
3. **Isolation**: Cada test debe ser independiente
4. **Page Object Model**: Abstraer páginas en clases reutilizables

---

*Skill basado en Playwright MCP Server y mejores prácticas de Microsoft*
