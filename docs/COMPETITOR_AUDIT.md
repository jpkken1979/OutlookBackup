# Auditoria de competidores — UNS Outlook Backup v3.2

> **Fase 5 del plan** `docs/PLAN_HARDENING_WIN10_11.md`
> **Fecha**: 2026-05-13
> **Owner**: K. Kaneshiro (UNS-Kikaku)
> **Status**: ✅ Investigacion completada. Pendiente: usuario elige top 3 features para Fase 6.

## Objetivo del documento

Identificar features de competidores reales que aporten valor concreto a UNS-Kikaku
y que sean implementables en Fase 6 del plan v3.2. NO clonar productos enteros —
solo extraer features con ROI claro para el caso de uso UNS (dispatch japones, M365).

## Productos analizados

| Producto | Stack | Licencia | Ultima release | Modelo |
|---|---|---|---|---|
| **MailStore Home** | .NET WPF + MAPI | Free (uso personal) | v25.1 (ene 2025) | Freeware con upsell a MailStore Server |
| **Stellar Repair for Outlook** | C++/Qt | Comercial $79-199 | activo | Recovery focused (corrupted PST) |
| **HoffmannTom/outlookbackupaddin** | C# Add-In | OSS (GitHub) | activo | Outlook add-in simple, scheduled copy |
| **PSTTool/PstMerger** | C# CLI | OSS (GitHub) | activo | Specialized: merge PSTs > 50GB |
| **libratom (Python)** | Python | Apache 2.0 | activo | Wraps libpff. Lee PST sin Outlook |
| **libpff (C lib)** | C | LGPL | activo | Lee/parsea PST/OST sin pywin32. PRO |
| **libpst** | C | GPL | activo | Convierte PST → maildir |
| **Veeam Backup for M365** | C#/PowerShell | Enterprise (caro) | activo | Cloud-to-local, multi-tenant |

Fuentes: ver seccion al final.

## Tabla cruzada de features

### Leyenda
- ✅ Yes — feature presente
- ❌ No — no soportado
- 🟢 ROI alto para UNS
- 🟡 ROI medio
- 🔴 ROI bajo / no aplica
- ✓ Ya implementado en v3.1.1

### Features

| Feature | UNS v3.1.1 | MailStore Home | Stellar | OutlookAddIn | libpff/libratom | ROI UNS | Notas |
|---|---|---|---|---|---|---|---|
| Backup PST multi-cuenta via COM | ✓ | ✅ | ❌ (recovery only) | ✅ | ❌ (read-only) | — | Ya nuestro |
| Cache backup OST directo (servidor caido) | ✓ | ❌ | ❌ | ❌ | ✅ | — | Ya nuestro (v3.1) |
| Export MSG individual | ✓ | ✅ | ✅ | ❌ | ✅ | — | Ya nuestro |
| Restore PST 3 modos | ✓ | ❌ (solo restore al mismo source) | ✅ | ❌ | ❌ | — | Ya nuestro |
| Inventario encriptado de cuentas | ✓ | ❌ | ❌ | ❌ | ❌ | — | Diferenciador UNS |
| Schedule Windows Task | ✓ | ✅ | ❌ | ✅ | ❌ | — | Ya nuestro |
| **Indexed search across backups** | ❌ | ✅ (potente) | ❌ | ❌ | parcial | 🟢 ALTO | Ver feature A |
| **Backup incremental** (solo emails nuevos) | ❌ | ✅ (al re-archivar) | ❌ | ❌ | parcial | 🟢 ALTO | Ver feature B |
| **Filter por fecha** ("solo ult 6 meses") | ❌ | ✅ (filtros archivado) | ❌ | ❌ | ❌ | 🟡 MEDIO | Ver feature C |
| Preview PST antes de restore | ✓ (pst_inspector) | ✅ | ✅ | ❌ | ✅ | — | Ya parcial v3.1 |
| Recovery PST corrupto | ❌ | ❌ | ✅ (core) | ❌ | parcial | 🔴 BAJO | Outlook nativo lo intenta |
| Split PST > 50GB | ❌ | ❌ | parcial | ❌ | ❌ | 🔴 BAJO | Raro en UNS |
| Multi-format export (PDF, EML, HTML) | parcial (PST/MSG) | ✅ (EML, MSG) | ✅ (5 formatos) | ❌ | ✅ | 🟡 MEDIO | Ver feature D |
| Cloud upload (OneDrive, S3) | ❌ | ❌ | ❌ (manual) | ❌ | ❌ | 🟡 MEDIO | Ver feature E |
| VSS hot-copy de OST sin cerrar Outlook | ❌ | ❌ | ❌ | ❌ | ❌ | 🟡 MEDIO | YA EN FASE 6 (decision 2026-05-13) |
| Multi-language UI (EN/ES) | ❌ (solo JA) | ✅ (multilang) | ✅ | parcial | n/a | 🔴 BAJO | UNS solo opera en JP |
| Code signing certificate (no AV warning) | ❌ | ✅ | ✅ | ❌ | n/a | 🟡 MEDIO | Tracking aparte plan v3.2 |

## Top 3 features candidatos para Fase 6

Ordenados por ROI / esfuerzo:

### Feature A — Indexed search across backup history 🟢 ALTO ROI

**Problema que resuelve**: usuarios UNS hoy NO pueden buscar emails en backups historicos
sin restaurar el PST a Outlook. Si un cliente pregunta "¿el backup de marzo tiene el email
del proveedor X?", hoy hay que importar el PST a Outlook y buscar manualmente.

**Inspiracion**: MailStore Home tiene indexed search potente como feature flagship.

**Implementacion sugerida**:
- Al hacer backup, ademas de generar `.pst`, indexar metadatos (subject, from, to, date,
  body excerpt) en `backup_{timestamp}/index.db` (SQLite con FTS5).
- Nueva tab en la GUI: "履歴検索" (busqueda en historial). Search box que ejecuta FTS5
  query sobre `index.db` de TODOS los backups.
- Resultado: lista clickeable que abre el PST original en Outlook + selecciona el email.

**Esfuerzo estimado**: 1-2 sesiones medias (modulo indexer + UI tab).
**Dependencias**: ninguna — usa SQLite stdlib.
**Risk**: bajo. No toca el flow de backup, solo agrega artifact paralelo.

**Codigo nuevo**:
- `src/email_indexer.py` (nuevo): genera `index.db` durante el backup
- `src/web/js/pages/search.js` (nuevo): UI tab
- API methods nuevos en `api.py`: `search_history(query, date_range?)`

### Feature B — Backup incremental 🟢 ALTO ROI

**Problema que resuelve**: hoy cada backup es full. Cliente con mailbox de 30GB tarda ~40min
por backup. Si el schedule corre semanal, son 40min/sem por cuenta — friccion alta.
Backup incremental: solo emails NUEVOS desde el ultimo backup → ~2min subsecuentes.

**Inspiracion**: feature estandar en Veeam/MailStore. UNS hoy no la tiene.

**Implementacion sugerida**:
- `BackupEngine.run_incremental()` (nuevo metodo, opt-in en config).
- En el primer backup: full + persistir `last_backup.json` con `{account_smtp: timestamp}`.
- En backups subsecuentes: filtrar `email.ReceivedTime > last_backup` antes de copiar.
- Output: PST mas chico con solo nuevos. Nombre: `backup_{ts}_incremental.pst` para distinguir.
- Restore: para reconstruir estado completo, mergear el ultimo full + todos los incrementales
  via PstMerger style (o instruir al usuario que importe en orden).

**Esfuerzo estimado**: 2-3 sesiones medias (logica + tests + UI checkbox + restore-incremental).
**Dependencias**: ninguna nueva (COM `email.ReceivedTime` ya disponible).
**Risk**: medio. Logica de "ultimo backup" tiene edge cases (cancelado a mitad, multi-account).

**Codigo nuevo**:
- `src/incremental_state.py` (nuevo): persistencia de last_backup por cuenta
- Cambios en `backup_engine.py`: branch incremental
- UI: checkbox "前回からの差分のみ" en tab backup
- Tests integration: full → modify → incremental → verify

### Feature C — Filter por fecha 🟡 MEDIO ROI

**Problema que resuelve**: cuentas con 10+ años de history generan PSTs gigantes. Si solo
necesitas backup de "ultimos 12 meses para auditoria fiscal japonesa", hoy hay que hacer
backup full + filter manual en Outlook.

**Inspiracion**: SysTools y Stellar tienen date-range filter en sus exports.

**Implementacion sugerida**:
- Agregar al `BackupEngine.__init__` parametro `date_range: tuple[date, date] | None`.
- Si presente, en `_copy_folder_recursive` filtrar items por `email.ReceivedTime`.
- UI: 2 date pickers (desde, hasta) opcional en tab backup. Default vacio = sin filtro.

**Esfuerzo estimado**: 1 sesion media.
**Dependencias**: ninguna.
**Risk**: bajo. Solo agrega un filter a la copia de items.

**Codigo nuevo**:
- Modificacion `backup_engine.py`: filter en CopyTo loop
- UI: 2 date inputs en `src/web/js/pages/backup.js`
- Tests: backup con/sin filter, verify count

## Top 3 — recomendacion priorizada

| Feature | Prioridad | Razon |
|---|---|---|
| **B. Backup incremental** | 1 | Mayor ROI: ahorra ~95% del tiempo en backups subsecuentes. Pega directo en UX semanal del usuario. |
| **A. Indexed search** | 2 | Diferenciador competitivo vs Stellar. UNS lo necesita para casos legales/auditoria. |
| **C. Filter por fecha** | 3 | Quick win. Bajo esfuerzo, util para nuevas cuentas o cleanups. |

## Features descartadas (con razon)

| Feature | Razon de descarte |
|---|---|
| Recovery de PST corrupto | Outlook nativo lo intenta. UNS rara vez tiene PSTs corruptos (control del entorno). |
| Split PST > 50GB | Ningun cliente UNS tiene mailboxes > 50GB historicamente. |
| Multi-language UI | UNS opera 100% en japones. Esfuerzo no justificado. |
| Cloud upload | Friccion regulatoria con datos UNS (privacidad japonesa). Mejor que el cliente lo haga manualmente. |
| Outlook add-in | Cambia el modelo de distribucion. La app standalone es preferida por UNS. |
| Recovery libpff fallback | Cache_backup ya cubre el caso "Outlook caido" copiando OST directo. |

## Decisiones pendientes para Fase 6

Cuando arranque Fase 6, el usuario debe confirmar:

1. **Top 3 features**: ¿agarrar las 3 (A+B+C) o solo las top 2 (A+B)?
2. **VSS hot-copy de OST**: ya decidido SI implementar (decision 2026-05-13). Confirmar prioridad
   relativa: ¿antes o despues de las features nuevas?
3. **Code signing**: ¿comprar cert ahora ($300/year) para release v3.2.0 sin AV warnings?
4. **Numero de version**: v3.2.0 si entra todo top 3 + VSS, o v3.2.0 con top 2 y v3.2.1 con C+VSS?

## Sources

- [MailStore Home — Free Email Archiving & Backup](https://www.mailstore.com/en/products/mailstore-home/)
- [MailStore Version 25.1 Release Notes](https://www.mailstore.com/en/press/2025/01/15/mailstore-version-25-1-now-available/)
- [Stellar Repair for Outlook Pricing](https://www.stellarinfo.com/email-repair/outlook-pst-repair/buy-now.php)
- [Stellar Phoenix Outlook PST Repair on Capterra](https://www.capterra.com/p/174645/Outlook-PST-Repair/)
- [libyal/libpff on GitHub](https://github.com/libyal/libpff)
- [pst-format/libpst on GitHub](https://github.com/pst-format/libpst)
- [libratom on PyPI](https://pypi.org/project/libratom/)
- [libratom/libratom on GitHub](https://github.com/libratom/libratom)
- [HoffmannTom/outlookbackupaddin](https://github.com/HoffmannTom/outlookbackupaddin)
- [PSTTool/PstMerger](https://github.com/PSTTool/PstMerger)
- [DCourtel/Pst_Backup](https://github.com/DCourtel/Pst_Backup)
- [MarekOtulakowski/backupmymail](https://github.com/MarekOtulakowski/backupmymail)
- [Safe PST Backup — incremental backup features](https://www.safepstbackup.com/backup-pst-files-incrementally.aspx)
