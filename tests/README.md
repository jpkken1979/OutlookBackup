# Tests — UNS Outlook Backup

## Setup

```bash
# Una vez por clone:
uv sync --extra dev
uv run pre-commit install
```

## Correr tests

```bash
# Suite completa (con coverage)
uv run pytest

# Solo tests que NO requieren Windows (para correr en Linux/Mac)
uv run pytest -m "not windows"

# Solo un archivo
uv run pytest tests/test_smoke.py

# Verbose con stop-on-first-failure
uv run pytest -xvs

# Con HTML coverage
uv run pytest --cov-report=html
# luego abrir htmlcov/index.html
```

## Estructura

```
tests/
├── conftest.py          # Fixtures globales (mock win32com, tmp_appdata)
├── test_smoke.py        # Tests de prueba de vida — imports basicos
├── unit/                # (Fase 2) Tests unitarios con fakes
├── integration/         # (Fase 2) Tests contra Outlook real (mark windows+outlook)
└── e2e/                 # (Fase 3) Playwright contra frontend
```

## Markers

| Marker | Significado |
|---|---|
| `@pytest.mark.windows` | Requiere Windows (pywin32 real). Skipear en Linux. |
| `@pytest.mark.outlook` | Requiere Outlook instalado y abierto. Skipear en CI. |
| `@pytest.mark.slow` | Tarda > 5s. Skipear en runs rapidos con `-m "not slow"`. |

## Como agregar un test

### Test que NO necesita Outlook (preferido)

Los modulos de src/ tienen `try/except ImportError` para pywin32. El fixture
autouse `mock_win32_modules` en conftest.py inyecta mocks antes de que
cualquier import resuelva, asi que podes importar sin Windows:

```python
def test_password_strength_returns_score():
    import crypto_utils

    score, _ = crypto_utils.estimate_password_strength("MyStr0ng!Pass")
    assert score > 50
```

### Test que necesita el namespace COM mockeado

Usa la fixture `fake_outlook_namespace`:

```python
def test_backup_engine_handles_empty_accounts(fake_outlook_namespace):
    fake_outlook_namespace.Accounts = []
    # ... pasar el namespace al engine
```

### Test que SI necesita Outlook real

```python
import pytest

pytestmark = [pytest.mark.windows, pytest.mark.outlook]

def test_real_dispatch():
    from win32com.client import Dispatch
    app = Dispatch("Outlook.Application")
    # ...
```

Estos tests solo corren en local con Windows + Outlook abierto.

## Coverage target

- **Fase 1**: smoke tests (este archivo). No exige coverage.
- **Fase 2**: 70%+ en `backup_engine`, `import_engine`, `cache_backup`, `crypto_utils`, `connection_tester`, `account_inventory`, `scheduler`.
- **Fase 3**: E2E coverage del frontend con Playwright.

## Troubleshooting

| Sintoma | Causa probable | Fix |
|---|---|---|
| `ModuleNotFoundError: win32com` | Fixture autouse no se cargo | Confirmar que el test esta en `tests/` y conftest.py existe |
| `ImportError: No module named 'crypto_utils'` | sys.path no tiene src/ | El smoke test inserta src/ en sys.path; copiar ese patron |
| Tests fallan solo en CI Linux | Codigo usa Win32 directamente | Refactorizar para usar Protocol (Fase 2) o agregar `@pytest.mark.windows` |
