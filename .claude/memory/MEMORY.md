# Memoria del Proyecto — UNS Outlook Backup v3.1

Indice de memorias persistentes del proyecto. Sincronizadas con git para multi-PC.

## Sesiones
- [Sesion 2026-05-08](session_2026-05-08.md) — Publicacion release v3.1.0 con .exe descargable
- [Sesion 2026-05-11 — Fase 1 quality toolchain](session_2026-05-11_fase1_quality_toolchain.md) — Setup uv+ruff+mypy+pytest+pre-commit, eliminar app.js legacy, fixear 4 bugs reales en main.py descubiertos por mypy. Incluye Fase 2 batches 1 y 2 (Protocols + fakes + real adapter, 32 tests).
- [Sesion 2026-05-12 — Fase 2 batch 3 + Fase 4](session_2026-05-12_fase2_fase4.md) — Refactor engines (backup+import) con OutlookClientProtocol + FakeOutlookClient, tests core con 70%+ coverage. Capa observability/ con structlog + crash reporter + GitHub release checker. 87 tests total, 4 commits pusheados a main.
- **Sesion 2026-05-13 — /init + plan v3.2** — Actualizacion de CLAUDE.md (corregir "no hay tests" + agregar uv/ruff/mypy/pytest, sub-packages outlook/ y observability/, dos workflows CI). Plan multi-fase aprobado para llevar a v3.2.0: hardening Win 10/11 + WebView2 bundle + VSS hot-copy + features de competidores. Ver `docs/PLAN_HARDENING_WIN10_11.md`.
- [Sesion 2026-05-13 jp haz-todo](session_2026-05-13.md) — **12 commits, 5/6 fases del plan v3.2 + Features A y C end-to-end de Fase 6.** 87 → 187 tests (+100). Modulos nuevos: runtime_check, path_utils, outlook/version, date_filter, incremental_state. Refactor de 8 modulos. Pendiente para release v3.2.0: Feature B (indexed search), VSS hot-copy, smoke manual, bump version.

## Descubrimientos
- [PyInstaller SPECPATH](discovery_pyinstaller_specpath.md) — Paths del spec relativos al dir del spec, no al CWD
- [GH Actions release permissions](discovery_gh_actions_release_permissions.md) — `contents: write` necesario para crear releases
- **app.js legacy + orchestrator causaba handlers duplicados** (ver session 2026-05-11) — ambos archivos definian su propio init() y bindeaban listeners sobre los mismos botones. Borrado el 2026-05-11.

## Decisiones
- **Toolchain de calidad 2026** (ver session 2026-05-11): uv + ruff + mypy + pytest + pre-commit. pyproject.toml es la fuente unica de config. requirements.txt se mantiene para compat con build.yml.
- **Plan de refactor en 4 fases** (Fase 1 done, 2-4 pendientes). Foco: calidad > features. Compat se puede romper (uso interno).
- [Plan hardening v3.2 aprobado 2026-05-13](decision_plan_hardening_v3.2.md) — 6 fases para llevar a v3.2.0. Targets: Win 10/11 + Outlook M365/2019/2021. Decisiones aprobadas: WebView2 bundlear bootstrapper en installer (~2MB extra) + VSS hot-copy de OST en Fase 6. Plan completo en `docs/PLAN_HARDENING_WIN10_11.md`.

## Bugfixes
- **ImportError en inventario modo auto** (ver session 2026-05-11) — main.py importaba funciones inexistentes `export_inventory_file` y `get_default_inventory_path`. Reemplazado por `save_inventory`. Tambien typo kwarg `selected_smtps` → `selected_smtp_addresses`.

## Patrones
- **Mock Win32 en tests con `patch.dict(sys.modules)`** (ver session 2026-05-11, tests/conftest.py) — fixture autouse session-scoped inyecta MagicMocks ANTES de cualquier import de src/. Permite correr tests en Linux sin pywin32.
- **`# noqa: F401` para Win32 availability probes** — imports dentro de `try/except ImportError` necesitan marcacion explicita porque ruff los ve como unused.

## Configuracion
- **pyproject.toml es la fuente unica** de config de ruff, mypy, pytest, coverage. Setup: `uv sync --extra dev && uv run pre-commit install`.
- **Mypy advisory en CI** (`continue-on-error: true` en .github/workflows/quality.yml job typecheck) hasta que Fase 2 limpie tipos por modulo.
