# Plan multi-fase: Hardening Win 10/11 + Features de competidores

> **Estado**: Fase 0 ✅ + Fase 1 ✅ + Fase 2 ✅ + Fase 3 ✅ (cerradas 2026-05-13). Proxima: Fase 4 (Outlook version compat) o Fase 5 (audit competidores).
> **Creado**: 2026-05-13
> **Aprobado**: 2026-05-13 por K. Kaneshiro
> **Owner**: K. Kaneshiro (UNS-Kikaku)
> **Version actual del producto**: v3.1.1
> **Version objetivo del ciclo**: v3.2.0

## Contexto

UNS Outlook Backup v3.1.1 esta en produccion y funciona en la maquina de desarrollo (Win 11 + Outlook M365).
La suite de tests cubre los engines (`backup_engine`, `cache_backup`, `import_engine`), observability,
i18n y E2E con Playwright. Mypy strict global y ruff configurados. CI corre en Linux + Windows.

Sin embargo hay tres riesgos no cubiertos para soporte real en produccion:

1. **WebView2 ausente en Win 10 < 22H2** → la app abre ventana en blanco sin runtime. Hoy NO hay
   deteccion ni mensaje claro al usuario.
2. **Long paths con caracteres japoneses** → el codigo NO usa el prefijo `\\?\` ni valida MAX_PATH.
   Backups con paths como `デスクトップ\バックアップ\2026年5月` pueden fallar silenciosamente.
3. **Diferencias entre Outlook M365 (Click-to-Run) vs Outlook 2019/2021 perpetual** → registry
   busca solo `16.0/15.0/14.0` y `Dispatch("Outlook.Application")` no distingue patches.
   `AddStoreEx` puede colgarse en cached mode sin internet (M365 caso comun).

## Objetivo

Cerrar el ciclo v3.1 → v3.2 con:

1. **Cobertura de tests para los 3 escenarios target** (Win 10 sin WebView2, Outlook M365 C2R, Outlook 2019/2021 perpetual).
2. **Hardening del runtime** para que la app falle elegante (con mensaje en japones) en vez de silencioso.
3. **2-3 features seleccionados** de competidores que aporten valor concreto a UNS-Kikaku.

## Targets de soporte (confirmados con el usuario 2026-05-13)

| Plataforma | Outlook | Prioridad |
|---|---|---|
| Windows 11 22H2+ | M365 Click-to-Run | **P0** (entorno actual) |
| Windows 11 22H2+ | Outlook 2019 / 2021 perpetual | **P0** (clientes UNS) |
| Windows 10 22H2 | M365 Click-to-Run | **P1** (clientes con PCs viejas) |
| Windows 10 21H2 (sin WebView2) | Cualquiera | **P1** (caso edge a manejar elegante) |

NO target en este ciclo: Outlook 2016, Win 10 < 21H2, Win 7/8.

## Gaps detectados en el codebase actual

Verificados con grep el 2026-05-13:

| Gap | Evidencia | Riesgo |
|---|---|---|
| Sin deteccion de WebView2 | `grep -r "WebView2"` solo aparece en `CLAUDE.md` y `tests/e2e/test_other_pages.py` | App abre en blanco en Win 10 fresh |
| Sin manejo de long paths | `grep -r "\\\\\\\\?\\\\\\\\"` no devuelve nada en `src/` | Falla silenciosa con paths > 260 chars |
| Outlook version hardcoded | `account_inventory.py` registry paths para `16.0, 15.0, 14.0` solamente | Outlook futuro (17.0) no detectado |
| `Dispatch("Outlook.Application")` sin distinguir flavor | `outlook/real.py:50`, `outlook_client.py:78`, `cache_backup.py:402` | Sin info para reportar bug "Outlook M365 vs 2019" |
| Sin VSS snapshot para OST hot-copy | `cache_backup.py` requiere cerrar Outlook | UX peor que competidores |
| Sin sanity check de Outlook version al boot | `main.py` no chequea `app.Version` | No podemos warnear "Outlook 2016 no soportado" |

## Investigacion de competidores (resumen preliminar — ampliar en Fase 5)

Conocimiento previo del entrenamiento, requiere validacion via WebSearch en Fase 5:

| Producto | Stack | Features destacados | Aplicable a UNS? |
|---|---|---|---|
| **MailStore Home** (free) | .NET WPF, MAPI directo | Indexed search across multiple mailboxes, dedup automatico, exporta a PST/EML/MSG | **Si** — indexed search es ROI alto |
| **Stellar Outlook PST Repair** (paid) | Qt | Recovery de PST corruptos, preview before restore, split de PST > 50GB | **Parcial** — preview es util |
| **SysTools Outlook PST Recovery** (paid) | .NET | Multi-format export (PDF, HTML, EML, MBOX), filter por fecha/sender | **Parcial** — filter por fecha es util |
| **Veeam Backup for M365** (enterprise) | C#/PowerShell | Incremental backup, multi-tenant, restore granular | **No** — overkill para UNS |
| **CodeTwo Backup for Office 365** (enterprise) | C# | Cloud-to-local backup, scheduled, encryption at rest | **No** — overkill |

**Open-source relevante en GitHub** (a explorar con WebSearch en Fase 5):
- `libpff` / `libpst` — C libs para leer PST sin Outlook (potencial fallback cuando COM falla)
- `pypff` — bindings Python de libpff
- `pst-utils` — CLI tools

**Top 3 features candidatos a implementar en Fase 6** (sujeto a Fase 5):
1. **Backup incremental** (solo emails nuevos desde el ultimo backup) — ahorra horas por dia, ROI altisimo
2. **Filter por fecha de backup** (ej: "solo ultimos 6 meses") — reduce tamanos de PST
3. **Preview antes de restore** (mostrar 5 emails de muestra antes de importar) — evita restore accidental

## Fases del plan

Cada fase es **cerrable** en su propia sesion. El criterio para cerrar una fase es: codigo en main,
tests pasando, doc actualizado, commit con `feat/test/docs(scope): descripcion en espanol`.

### Fase 0 — Planificacion (ESTA SESION) ✅

- **Deliverable**: este documento (`docs/PLAN_HARDENING_WIN10_11.md`).
- **Criterio de exito**: usuario aprueba el plan o pide ajustes.
- **Handoff**: commit con tag `[plan]` para que la proxima sesion arranque desde aqui.

### Fase 1 — Test infrastructure hardening ✅ CERRADA 2026-05-13

**Objetivo**: que la suite actual capture regressions en los 3 entornos target SIN tener que probar
manualmente cada release.

**Scope completado**:
- ✅ Matrix expandida en `quality.yml` agregando `windows-2019` (Win 10 baseline) ademas de `ubuntu-latest` y `windows-latest` (Win 11).
- ✅ Markers nuevos en `pyproject.toml`: `outlook_version`, `webview2`, `long_paths`.
- ✅ `tests/test_outlook_version_detection.py` (8 tests):
  - Verifica que `_read_registry_servers` enumera 16.0/15.0/14.0.
  - Verifica que retorna None sin SMTP o en non-Windows.
  - Verifica contrato de `Dispatch().Version` parseable.
  - 3 xfail/skip placeholders para Fase 4 (detect M365 vs perpetual, version 17.0, supported flag).
- ✅ `tests/test_long_paths.py` (7 tests):
  - Smoke test de path japones corto (sanity Unicode).
  - Constants check de MAX_PATH y LONG_PATH_LIMIT.
  - 5 xfail/skip placeholders para Fase 3 (`safe_path`, `validate_backup_dir`).
- ✅ `tests/test_webview2_detection.py` (7 tests):
  - Constant check del registry GUID canonico de Microsoft.
  - Documentacion del estado actual (main.py NO importa runtime_check).
  - 5 xfail/skip placeholders para Fase 2 (`is_webview2_installed`, `ensure_webview2_runtime`, bundling en installer.iss).

**Deliverable real**: 3 archivos de test nuevos (22 tests, 9 PASSED + 9 SKIP + 4 XFAIL) + matrix expandida.
**Criterio de exito alcanzado localmente**: `uv run pytest -m "not e2e"` → 103 passed, 0 failed, 9 skipped, 4 xfailed.
**Pendiente validar en CI**: el matrix `windows-2019` se verifica al hacer push (no se puede testear local).
**Tiempo real**: ~1.5h (estimado 4h, mas rapido por reuso de patrones existentes).
**Handoff**: commit `test(ci): matrix Win 10 + tests xfail para Fases 2/3/4 (Fase 1 cerrada)`.

### Fase 2 — WebView2 detection + bootstrap + bundling ✅ CERRADA 2026-05-13

**Objetivo**: que la app NO abra ventana en blanco si WebView2 falta. Detectar al boot, ofrecer
descarga del runtime, Y bundlear el installer en el `.exe` setup.

**Implementacion completada**:
- ✅ `src/runtime_check.py` — modulo nuevo, mypy strict, 7 funciones publicas:
  `is_webview2_installed`, `get_bundled_installer_path`, `download_bootstrapper`,
  `run_installer_silent`, `show_japanese_install_dialog`, `ensure_webview2_runtime`.
- ✅ `tests/test_runtime_check.py` — 18 tests, todos verdes (mock de winreg, urllib, subprocess).
- ✅ `src/main.py` — integracion en `run_gui()` antes de `webview.create_window`.
  `run_gui()` cambio retorno de None → int (exit code 2 si WebView2 falta).
  `main()` ahora hace `sys.exit(run_gui())`.
- ✅ `build/installer.iss` — bundling completo:
  - Removido el `[Tasks]` `webview2` placeholder (era confuso UX).
  - Agregado `[Files]` con `Source: ..\redist\MicrosoftEdgeWebview2Setup.exe; DestDir: {tmp}; Flags: deleteafterinstall`.
  - Agregada funcion `WebView2NeedsInstall` en `[Code]` que lee 3 ubicaciones de registry.
  - Agregada linea en `[Run]` con `/silent /install` antes del launch del programa.
- ✅ `redist/` — directorio nuevo con `.gitkeep` + `README.md` con instrucciones de descarga.
  Bootstrapper NO commiteado (cubierto por `*.exe` en `.gitignore`).
- ✅ `tests/test_webview2_detection.py` — refactorizado, ahora solo cubre el contrato del installer.iss
  (4 tests, todos verdes).
- ✅ `pyproject.toml` — agregado `runtime_check` a mypy strict overrides.

**Validacion local**: 123 passed, 0 failed, 6 skipped, 2 xfailed (sin regresiones).
**Validacion pendiente** (requiere VM Win 10 sin WebView2):
- Smoke manual: instalar el .exe en Win 10 21H2 sin runtime → verificar que el installer corre el bootstrapper silenciosamente.
- Smoke manual: ejecutar la app dev (run.bat) en Win 10 sin runtime → verificar dialogo japones.
**Tiempo real**: ~2h (estimado 3-4h, mas rapido por reuso del patron de tests xfail).
**Handoff**: commit `feat(runtime): WebView2 detection + bundle bootstrapper en installer (Fase 2)`.

**Scope**:
- Agregar `src/runtime_check.py` con funcion `ensure_webview2_runtime()`:
  - Lee `HKLM\SOFTWARE\WOW6432Node\Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}` y `HKCU\...`.
  - Si NO existe, abre dialogo nativo (tkinter, no WebView2 obvio) en japones:
    "WebView2 ランタイムが必要です。ダウンロードしますか?".
  - Si usuario acepta y existe el bundle local: ejecutar `MicrosoftEdgeWebview2Setup.exe /silent /install`.
  - Si no hay bundle local (modo dev / installer no usado): descargar de URL oficial de Microsoft.
  - Si usuario rechaza, sale con codigo 2 y log claro.
- Llamar `ensure_webview2_runtime()` en `main.py:run_gui()` ANTES de `webview.create_window`.
- En `--auto` mode, NO interactivo: log warning y continuar (auto backup no necesita GUI).
- **Bundling en installer** (decision aprobada 2026-05-13):
  - Descargar `MicrosoftEdgeWebview2Setup.exe` (~1.7MB, evergreen bootstrapper) — NO el offline standalone (~150MB).
  - Agregar a `build/installer.iss` seccion `[Files]`: `Source: "redist\MicrosoftEdgeWebview2Setup.exe"; DestDir: {tmp}`.
  - En `[Run]`: ejecutar con `/silent /install` solo si Inno detecta runtime ausente (check via `[Code]` con `RegQueryStringValue`).
  - Esto agrega ~2MB al installer (no 100MB — el bootstrapper descarga el resto on-demand).
  - **Correccion vs estimacion preliminar**: el impacto real es ~2MB, no ~100MB.

**Deliverable**: `src/runtime_check.py` + tests + integracion en `main.py` + cambios en `installer.iss` + descarga del bootstrapper.
**Criterio de exito**:
- Tests verifican deteccion en ambos casos (presente/ausente).
- Smoke manual en VM Win 10 sin WebView2: el installer instala WebView2 silenciosamente y la app arranca normal.
- Smoke manual en VM Win 11 con WebView2 ya instalado: installer NO toca WebView2.
**Tiempo estimado**: 1 sesion media (3-4h, mas que antes por el bundling en Inno Setup).
**Handoff**: commit `feat(runtime): detectar WebView2 + bundle bootstrapper en installer`.

### Fase 3 — Long path support + Japanese path tests ✅ CERRADA 2026-05-13

**Objetivo**: backups con paths japoneses largos NO fallan silenciosamente.

**Implementacion completada**:
- ✅ `src/path_utils.py` — modulo nuevo, mypy strict, 3 funciones publicas:
  `is_long_path`, `safe_path`, `validate_backup_dir` + constants (MAX_PATH=260,
  LONG_PATH_THRESHOLD=240, LONG_PATH_LIMIT=32_767, LONG_PATH_PREFIX, LONG_PATH_PREFIX_UNC).
- ✅ `tests/test_long_paths.py` — reescrito de xfail/skip a 13 tests reales
  (paths cortos, paths largos, UNC, no-double-prefix, validate writeability, validate length).
- ✅ Refactor incremental de 4 engines:
  - `src/cache_backup.py` — `safe_path()` en `open()` (3 lugares: copia + sha256) + `shutil.copystat`.
  - `src/outlook_client.py` — `safe_path()` en `AddStoreEx(output_path)` para crear PST.
  - `src/import_engine.py` — `safe_path()` en 4 calls de `AddStore`/`AddStoreEx`
    (separate_folder, new_files, fallback, merge).
  - `src/pst_inspector.py` — `safe_path()` en `AddStore(pst_path)` para preview.
- ✅ `pyproject.toml` — agregado `path_utils` a mypy strict overrides.

**Validacion local**: 134 passed, 0 failed, 2 skipped, 1 xfailed (sin regresiones).
**Validacion pendiente** (requiere Outlook + path > 260 chars en Windows):
- Smoke manual: backup con `output_dir` japones de ~250 chars → verificar PST creado.
- Smoke manual: import PST con path > 260 chars → verificar AddStore funciona.

**Decision conservadora**: `safe_path()` solo activa el prefijo cuando length > 240
(passthrough para paths cortos), preservando compat con APIs viejas que no soportan
el prefijo. Validable con `LONG_PATH_THRESHOLD` overrideable en config futura si hace falta.

**Tiempo real**: ~2.5h (estimado 4h, mas rapido por reuso de patron path-aware).
**Handoff**: commit `feat(paths): soporte long paths con prefijo \\\\?\\\\ (Fase 3)`.

**Scope**:
- Crear `src/path_utils.py`:
  - `safe_path(p: Path) -> str` — devuelve string con prefijo `\\?\` si len > 240.
  - `validate_backup_dir(p: Path) -> tuple[bool, str]` — verifica writability + length + permisos.
- Refactorizar `backup_engine.py`, `cache_backup.py`, `import_engine.py` para usar `safe_path()` en
  todos los `AddStoreEx`, `shutil.copy`, etc.
- Agregar test `tests/test_long_paths.py` con cases hypothesis-generated.
- Agregar test integracion `tests/test_backup_japanese_path.py` con tmpdir nested 10 niveles + nombres jp.

**Deliverable**: `src/path_utils.py` + refactors + tests.
**Criterio de exito**:
- Test con path 270 chars + jp pasa sin warnings.
- Mensaje de error util cuando length > 32767 (limite de `\\?\`).
**Tiempo estimado**: 1 sesion media (4h).
**Handoff**: commit `feat(paths): soporte long paths con prefijo \\?\\`.

### Fase 4 — Outlook version compat layer

**Objetivo**: detectar al boot que version de Outlook esta instalada y warnear si no soportada.
Adaptar comportamiento de `AddStoreEx` segun flavor.

**Scope**:
- Crear `src/outlook/version.py`:
  - `detect_outlook_version() -> OutlookVersion` (dataclass: version, flavor, install_path, supported).
  - Lee registry `HKLM\SOFTWARE\Microsoft\Office\ClickToRun\Configuration` para detectar M365.
  - Lee `HKLM\SOFTWARE\WOW6432Node\Microsoft\Office\{ver}\Outlook\InstallRoot\Path` para perpetual.
  - Si version < 16.0: marca `supported=False`, retorna mensaje en japones.
- Modificar `main.py` para llamar `detect_outlook_version()` y warnear si no soportada.
- Modificar `account_inventory.py` para incluir `outlook_version` en el JSON generado.
- Modificar reporte HTML/JSON de backup para incluir version detectada (debugging).
- Agregar tests por flavor (mock registry para M365 vs 2019 vs 2021).

**Deliverable**: `src/outlook/version.py` + integraciones + tests.
**Criterio de exito**:
- En la maquina de desarrollo `detect_outlook_version()` retorna `M365 / 16.x.x / supported=True`.
- Tests cubren los 3 flavors (M365/2019/2021) con mocks de registry.
**Tiempo estimado**: 1 sesion media (4h).
**Handoff**: commit `feat(outlook): detectar version y flavor (M365/perpetual)`.

### Fase 5 — Competitor feature audit (research formal)

**Objetivo**: validar la lista preliminar de la seccion "Investigacion de competidores" con
busquedas reales en GitHub y la web. Filtrar segun criterios concretos.

**Scope**:
- WebSearch + WebFetch a:
  - `MailStore Home features list` + `mailstore-software/mailstore-home` en GitHub.
  - `Stellar Outlook PST Repair vs MailStore` comparativas.
  - `libpff python bindings example`.
  - `outlook backup incremental open source github`.
- Crear `docs/COMPETITOR_AUDIT.md` con:
  - Por cada producto: features, precio, stack, licencia, ultima release.
  - Tabla cruzada: feature x producto x aplicable-a-UNS (yes/no/parcial) + razon.
  - Top 3-5 features candidatos justificados por ROI para UNS.
- Sesion de decision con el usuario: cuales features ir a Fase 6.

**Deliverable**: `docs/COMPETITOR_AUDIT.md`.
**Criterio de exito**: usuario elige top 3 features a implementar.
**Tiempo estimado**: 1 sesion media (4h, mas si hace falta probar productos en VM).
**Handoff**: commit `docs(research): auditoria de competidores y seleccion de features`.

### Fase 6 — Implementacion features seleccionados + VSS + release v3.2.0

**Objetivo**: implementar 2-3 features de Fase 5, agregar VSS hot-copy de OST, hacer release v3.2.0.

**Scope** (placeholder — la lista real sale de Fase 5):
- Feature A (ej: backup incremental).
- Feature B (ej: filter por fecha).
- Feature C (ej: preview antes de restore).
- **VSS hot-copy de OST** (decision aprobada 2026-05-13):
  - Nueva funcion `vss_copy(src: Path, dest: Path) -> bool` en `cache_backup.py`.
  - Detecta si proceso corre como admin (`ctypes.windll.shell32.IsUserAnAdmin`).
  - Si admin: crea VSS shadow via `wmi` (`Win32_ShadowCopy.Create`) y copia desde el shadow.
  - Si NO admin: fallback al comportamiento actual (cierra Outlook, copia, reabre).
  - UI: checkbox "OST のホットコピー (管理者権限が必要)" en tab cache, default off.
  - Tests: mock de WMI + admin check en ambos paths.
  - Si no entra en sesion: bajar a v3.2.1 (no bloquea release v3.2.0).
- Por cada feature: codigo + tests unitarios + test E2E + i18n strings (japones).
- Bump version en `pyproject.toml`, `installer.iss`, `api.py:get_app_info`.
- CHANGELOG.md con highlights.
- `git tag v3.2.0` → triggers release CI.

**Deliverable**: 2-3 features + VSS (si entra) + release publicado.
**Criterio de exito**:
- Release v3.2.0 visible en GitHub Releases con `.exe` + installer adjuntos.
- Quality CI verde en main.
- Smoke test manual en VM Win 11 + M365 (con admin para validar VSS).
- Smoke test manual en VM Win 10 sin admin (validar fallback).
**Tiempo estimado**: 2-3 sesiones medias (+1 si VSS resulta complejo).
**Handoff**: tag de release + nota en `ESTADO_PROYECTO.md`.

## Criterios globales de exito del ciclo v3.1 → v3.2

| Criterio | Como se mide |
|---|---|
| App no abre en blanco en Win 10 sin WebView2 | Smoke manual en VM + test mockeado |
| Backup con path japones de 270 chars funciona | Test integracion en suite |
| App detecta y reporta Outlook M365 vs 2019/2021 | Inspeccion del `report.json` generado |
| 3 features de competidores implementados | Release notes v3.2.0 |
| Coverage de `src/` no baja vs v3.1 | `pytest --cov` comparativo |
| Mypy strict sigue verde en TODOS los modulos | `uv run mypy src` sin errores |
| Quality CI verde en `windows-2019` Y `windows-2022` | Badge en README |

## Riesgos y mitigaciones

| Riesgo | Probabilidad | Impacto | Mitigacion |
|---|---|---|---|
| GitHub Actions no tiene `windows-2019` con Outlook instalado | Alta | Tests Outlook-real solo en local | Marcar `@pytest.mark.outlook` y skipear en CI; documentar checklist manual |
| WebView2 download URL cambia | Baja | Fase 2 rota | Hardcodear URL + checksum, logear "verificar en docs.microsoft.com si falla" |
| `\\?\` rompe APIs viejas que esperan path normal | Media | Refactor de Fase 3 grande | `safe_path()` solo activa prefijo si len > 240, no globalmente |
| Outlook M365 update remoto rompe COM bindings | Baja | App rota sin advertir | Fase 4 detecta version al boot, log con cada backup |
| Feature seleccionada en Fase 5 requiere reescritura grande | Media | Fase 6 no entra en 2-3 sesiones | Cap de scope: si feature no entra en 1 sesion, bajar al backlog |

## Decisiones (confirmadas 2026-05-13)

1. ✅ **WebView2 bundling**: SI bundlear el runtime en el installer Inno Setup. Aprox +100MB al installer final
   (de ~30MB → ~130MB). Elimina la friccion del primer run en Win 10 fresh.
   - Implementacion: agregar `MicrosoftEdgeWebview2Setup.exe` a `[Files]` del `installer.iss` y correr en
     silencio (`/silent /install`) en `[Run]` solo si la deteccion de Fase 2 detecta runtime ausente.
   - Esto se hace en **Fase 2** (junto a la deteccion).
2. ✅ **VSS snapshot para hot-copy de OST**: SI implementar. Permite copiar OST sin cerrar Outlook (admin requerido).
   - Implementacion: nueva funcion `vss_copy(src, dest)` en `cache_backup.py` usando `wmi` o llamada a `vssadmin`.
   - Si admin: usar VSS. Si no admin: fallback al comportamiento actual (cerrar Outlook).
   - Esto entra como **Fase 6 feature opcional** (no bloquea release v3.2.0; si no entra, v3.2.1).

## Decisiones pendientes (sin definir aun)

1. **Soporte Outlook 2016**: el plan asume NO soportado, pero el usuario aun no lo confirmo formalmente.
   Default: descartado para este ciclo. Si un cliente UNS lo pide, evaluar parche puntual en v3.2.x.
2. **Code signing certificate**: el .exe dispara antivirus. Comprar cert (~$300/year) esta fuera del scope
   de este plan — tracking aparte cuando el usuario lo decida.

## Workflow recomendado por sesion

1. Leer este plan + ultima entrada de `.claude/memory/session_*.md`.
2. Identificar fase a trabajar.
3. Crear branch `feat/fase-N-<scope>` (ej: `feat/fase-2-webview2-bootstrap`).
4. Ejecutar deliverables de la fase.
5. Tests verdes localmente + en CI.
6. Commit + push.
7. Actualizar este plan marcando la fase como ✅.
8. Cerrar sesion con `/finalize` (memoria + brain ingest + commit final).

## Referencias

- Codebase actual: `CLAUDE.md` (v3.1.1, refactor pywebview)
- Reglas del proyecto: `.claude/rules/`
- Memoria previa: `.claude/memory/MEMORY.md`
- Ultima sesion documentada: `.claude/memory/session_2026-05-12_fase2_fase4.md`

---

**Aprobacion**: pendiente del usuario. Modificar este plan in-place hasta que sea aprobado, despues
solo agregar entries `## Cambio YYYY-MM-DD` al final del archivo.
