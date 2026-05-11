# Memoria del Proyecto — UNS Outlook Backup v3.1

Indice de memorias persistentes del proyecto. Sincronizadas con git para multi-PC.

## Sesiones
- [Sesion 2026-05-08](session_2026-05-08.md) — Publicacion release v3.1.0 con .exe descargable
- [Sesion 2026-05-11 — Fase 1 quality toolchain](session_2026-05-11_fase1_quality_toolchain.md) — Setup uv+ruff+mypy+pytest+pre-commit, eliminar app.js legacy, fixear 4 bugs reales en main.py descubiertos por mypy

## Descubrimientos
- [PyInstaller SPECPATH](discovery_pyinstaller_specpath.md) — Paths del spec relativos al dir del spec, no al CWD
- [GH Actions release permissions](discovery_gh_actions_release_permissions.md) — `contents: write` necesario para crear releases
- **app.js legacy + orchestrator causaba handlers duplicados** (ver session 2026-05-11) — ambos archivos definian su propio init() y bindeaban listeners sobre los mismos botones. Borrado el 2026-05-11.

## Decisiones
- **Toolchain de calidad 2026** (ver session 2026-05-11): uv + ruff + mypy + pytest + pre-commit. pyproject.toml es la fuente unica de config. requirements.txt se mantiene para compat con build.yml.
- **Plan de refactor en 4 fases** (Fase 1 done, 2-4 pendientes). Foco: calidad > features. Compat se puede romper (uso interno).

## Bugfixes
- **ImportError en inventario modo auto** (ver session 2026-05-11) — main.py importaba funciones inexistentes `export_inventory_file` y `get_default_inventory_path`. Reemplazado por `save_inventory`. Tambien typo kwarg `selected_smtps` → `selected_smtp_addresses`.

## Patrones
- **Mock Win32 en tests con `patch.dict(sys.modules)`** (ver session 2026-05-11, tests/conftest.py) — fixture autouse session-scoped inyecta MagicMocks ANTES de cualquier import de src/. Permite correr tests en Linux sin pywin32.
- **`# noqa: F401` para Win32 availability probes** — imports dentro de `try/except ImportError` necesitan marcacion explicita porque ruff los ve como unused.

## Configuracion
- **pyproject.toml es la fuente unica** de config de ruff, mypy, pytest, coverage. Setup: `uv sync --extra dev && uv run pre-commit install`.
- **Mypy advisory en CI** (`continue-on-error: true` en .github/workflows/quality.yml job typecheck) hasta que Fase 2 limpie tipos por modulo.
