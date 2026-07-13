---
description: Operaciones con la vault de Obsidian — crear notas, buscar, agregar ADRs, registrar sesiones
---

# Skill: /obsidian

Operar la vault de Obsidian desde Claude Code. Soporta lectura, escritura, búsqueda, ADRs y notas de sesión.

## Vault canónica

```
C:\Users\kenji\OneDrive\ドキュメント\Obsidian Vault\Antigravity\
```

## Estructura de carpetas

| Carpeta | Propósito |
|---|---|
| `00-Inbox/` | Notas rápidas, ideas sin clasificar |
| `01-Proyectos/` | Notas de proyectos activos |
| `02-Areas/` | Responsabilidades y áreas de trabajo |
| `03-Recursos/` | Referencias, links, material de estudio |
| `04-Archivo/` | Notas inactivas o completadas |
| `05-Sesiones/` | Notas de sesiones de trabajo diario |
| `06-Decisiones/` | ADRs y decisiones de arquitectura |
| `07-Templates/` | Plantillas reutilizables |

## Estrategia de escritura

### Prioridad 1 — Cliente Python via gateway (`:4747`)

Cuando el gateway Antigravity está activo, usar `ObsidianClient`:

```python
# Verificar disponibilidad del gateway
import asyncio
from core.obsidian_client import ObsidianClient

async def main():
    async with ObsidianClient() as client:
        if await client.health_check():
            # Operar via API
            ...
```

### Prioridad 2 — Escritura directa de archivos

Si el gateway no está activo o el plugin no responde, escribir directamente
a la vault con la herramienta Write/Edit usando la ruta absoluta del vault.

## Frontmatter estándar

Toda nota nueva debe incluir este frontmatter mínimo:

```markdown
---
title: "Título descriptivo"
date: 2026-01-15
tags:
  - tag1
  - tag2
status: active
---
```

## Instrucciones por operación

---

### 1. CREAR NOTA

**Trigger**: "crea una nota en obsidian sobre X", "agrega una nota a obsidian", "anota en obsidian que..."

**Pasos**:
1. Determinar la carpeta correcta según el contenido:
   - Idea/captura rápida → `00-Inbox/`
   - Relacionado a un proyecto activo → `01-Proyectos/<nombre-proyecto>/`
   - Referencia técnica → `03-Recursos/`
2. Generar nombre de archivo: `YYYY-MM-DD-slug-descriptivo.md`
3. Escribir con frontmatter completo (title, date, tags, status)
4. Agregar wikilinks relevantes al final: `## Ver también` con `[[links]]`
5. Si el gateway está activo: usar `ObsidianClient.create_note(path, content)`
6. Si no: usar la herramienta Write con la ruta absoluta del vault

**Ejemplo de nota generada**:
```markdown
---
title: "Integración de ChromaDB con el pipeline de memoria"
date: 2026-01-15
tags:
  - memoria
  - chromadb
  - antigravity
status: active
---

# Integración de ChromaDB con el pipeline de memoria

[contenido]

## Ver también
- [[05-Sesiones/session-2026-01-15]]
- [[06-Decisiones/adr-20260115-memoria-vectorial]]
```

---

### 2. BUSCAR EN OBSIDIAN

**Trigger**: "busca en obsidian X", "qué tengo en obsidian sobre X", "encontrá notas de X"

**Pasos**:
1. Si el gateway está activo: usar `ObsidianClient.search(query, limit=10)`
2. Si no: usar la herramienta Grep sobre la ruta del vault con el patrón buscado
3. Presentar resultados con: path de la nota, primer párrafo relevante, tags
4. Ofrecer abrir o leer el contenido completo de las notas encontradas

**Búsqueda directa sin gateway**:
```bash
# Grep sobre el vault
grep -r "término a buscar" "C:\Users\kenji\OneDrive\ドキュメント\Obsidian Vault\Antigravity\" --include="*.md" -l
```

---

### 3. CREAR ADR (Architecture Decision Record)

**Trigger**: "registra la decisión de X", "crea un ADR para X", "documenta la decisión sobre X"

**Pasos**:
1. Recopilar del usuario (o inferir del contexto):
   - **Contexto**: qué problema o situación motivó la decisión
   - **Decisión**: qué se decidió hacer y por qué
   - **Consecuencias**: impactos positivos y negativos esperados
2. Si el gateway está activo: usar `ObsidianClient.create_adr(title, context, decision, consequences)`
3. Si no: escribir directamente con este template:

```markdown
---
title: "ADR: [título]"
date: YYYY-MM-DD
status: accepted
tags:
  - adr
  - decision
---

# [Título de la decisión]

## Contexto

[Descripción del problema o situación]

## Decisión

[La decisión tomada y el razonamiento]

## Consecuencias

- [Consecuencia positiva 1]
- [Consecuencia negativa 1]
- [Trade-offs]

## Ver también
- [[nota-relacionada]]
```

4. Nombre del archivo: `06-Decisiones/adr-YYYYMMDD-slug.md`
5. Confirmar al usuario la ruta donde quedó guardado

---

### 4. REGISTRAR SESIÓN

**Trigger**: "guarda la sesión", "registra lo que hicimos hoy", "anota la sesión en obsidian", "cierra la sesión en obsidian"

**Pasos**:
1. Tomar del contexto de la conversación actual:
   - Resumen de las tareas completadas
   - Archivos creados o modificados (de los tool calls de la sesión)
   - Decisiones técnicas tomadas
2. Si el gateway está activo: usar `ObsidianClient.create_session_note(summary, files_changed, decisions)`
3. Si no: escribir directamente con este template:

```markdown
---
title: "Sesión YYYY-MM-DD"
date: YYYY-MM-DDTHH:MM:SS
tags:
  - session
  - antigravity
---

# Sesión de trabajo — YYYY-MM-DD

## Resumen

[Descripción de lo que se hizo]

## Archivos modificados

- `ruta/archivo1.py`
- `ruta/archivo2.ts`

## Decisiones tomadas

- [Decisión 1]
- [Decisión 2]

## Pendientes

- [ ] [Tarea pendiente 1]

## Ver también
- [[06-Decisiones/adr-relacionado]]
```

4. Nombre del archivo: `05-Sesiones/session-YYYY-MM-DD-HH-MM.md`
5. Reportar al usuario: path creado + resumen de 2-3 líneas de lo guardado

---

### 5. LEER NOTA

**Trigger**: "muéstrame la nota X", "abrí la nota X en obsidian", "leé el ADR de X"

**Pasos**:
1. Si el gateway está activo: usar `ObsidianClient.get_note(path)`
2. Si no: usar la herramienta Read con la ruta absoluta del vault + path relativo
3. Mostrar el contenido completo con el frontmatter parseado
4. Si la nota tiene wikilinks (`[[link]]`), ofrecer navegar a ellos

**Ruta absoluta de lectura directa**:
```
C:\Users\kenji\OneDrive\ドキュメント\Obsidian Vault\Antigravity\{path-relativo}
```

---

## Reglas de escritura de notas

1. **Frontmatter siempre presente**: title, date, tags, status son campos mínimos
2. **Tags en snake_case**: `memoria_vectorial` no `Memoria Vectorial`
3. **Wikilinks al final**: siempre una sección `## Ver también` con links relevantes
4. **Nombres de archivo**: usar kebab-case, con fecha al inicio si es temporal (`YYYY-MM-DD-titulo.md`)
5. **Carpeta correcta**: no dejar todo en Inbox — clasificar según la tabla de carpetas
6. **Sin hardcodear paths en código**: la ruta del vault se lee de env `OBSIDIAN_VAULT_PATH` o se usa la ruta canónica de arriba

## Uso del cliente Python

```python
import asyncio
from core.obsidian_client import ObsidianClient, VAULT_FOLDERS

async def ejemplo_completo():
    async with ObsidianClient() as client:
        # Verificar disponibilidad
        if not await client.health_check():
            print("Obsidian no disponible — usar escritura directa")
            return

        # Leer nota
        nota = await client.get_note("00-Inbox/ideas.md")
        print(nota.content)

        # Crear nota nueva
        await client.create_note(
            path="00-Inbox/nueva-idea.md",
            content="---\ntitle: Nueva idea\ndate: 2026-01-15\ntags:\n  - idea\n---\n\n# Nueva idea\n\nContenido aquí.",
            overwrite=False,
        )

        # Crear ADR
        path = await client.create_adr(
            title="Usar aiohttp sobre httpx para el gateway",
            context="El gateway necesita manejo async de múltiples conexiones concurrentes.",
            decision="Se eligió aiohttp por su integración nativa con asyncio y bajo overhead.",
            consequences=[
                "Mejor performance bajo carga",
                "API más verbosa que httpx",
                "Requiere gestión manual del ClientSession",
            ],
        )
        print(f"ADR creado en: {path}")

        # Registrar sesión
        path = await client.create_session_note(
            summary="Integración del cliente Obsidian con el ecosistema Antigravity",
            files_changed=[
                ".agent/core/obsidian_client.py",
                ".claude/commands/obsidian.md",
            ],
            decisions=["ObsidianClient usa aiohttp para consistencia con el resto del stack"],
        )
        print(f"Sesión guardada en: {path}")

asyncio.run(ejemplo_completo())
```

## Variables de entorno

| Variable | Descripción | Default |
|---|---|---|
| `OBSIDIAN_API_KEY` | Token del plugin Local REST API | Lee de `~/.antigravity/obsidian_token` |
| `OBSIDIAN_VAULT_PATH` | Ruta absoluta al vault | `C:\Users\kenji\OneDrive\ドキュメント\Obsidian Vault\Antigravity\` |

## Troubleshooting

| Problema | Causa probable | Solución |
|---|---|---|
| `ClientConnectorError` | Obsidian cerrado o plugin inactivo | Abrir Obsidian y habilitar plugin Local REST API |
| 401 Unauthorized | Token inválido o ausente | Definir `OBSIDIAN_API_KEY` o crear `~/.antigravity/obsidian_token` |
| 404 Not Found | Ruta de nota incorrecta | Verificar que la nota existe y la ruta es relativa al vault |
| 412 Precondition Failed | Nota ya existe con `overwrite=False` | Usar `overwrite=True` o cambiar el nombre |
