# Pendientes activos

> Verificado: 2026-08-03. Este archivo se inyecta en cada sesión; por eso solo
> contiene trabajo abierto y comprobado. El historial cerrado vive en
> `ESTADO_PROYECTO.md`, `.claude/memory/` y `.agent/brain/`.

## Estado de partida

- Rama operativa: `main`.
- GitHub: 0 issues abiertos y 0 pull requests abiertos en la verificación del
  2026-08-03.
- CI del HEAD anterior a esta limpieza: workflows principales en verde.
- Nexus activo: 2.8.15, con artefacto NSIS verificado.
- No reabrir tareas de versiones 2.8.14 o anteriores sin reproducir el problema
  contra el código actual.

## 1. Firma pública de Nexus — requiere al propietario

El instalador 2.8.15 es válido para distribución interna por SHA-256, pero no
tiene firma Authenticode. Para una publicación pública limpia y para habilitar
el updater hacen falta:

1. certificado de firma de código;
2. custodia segura de la clave fuera del repositorio;
3. firma con timestamp durante CI o bundle;
4. regeneración de hashes y manifests después de firmar;
5. smoke instalado del artefacto firmado.

No simular una firma ni marcar este punto cerrado con un binario `unsigned`.

## 2. Cobertura Python — mejora incremental

- Medición canónica del 2026-08-03: `62.2934328020798 %`.
- Piso de regresión actual: `62.2 %`.
- Objetivo: `80 %`.

La autoridad es `.github/workflows/test-coverage-mutation.yml`. Aumentar la
cobertura con tests de comportamiento útil; no excluir código, duplicar tests ni
bajar el piso para maquillar una regresión.

## 3. Rotación de credenciales — confirmación manual

El historial registra que `OPENROUTER_API_KEY` y `OPENCODE_API_KEY` se expusieron
en una conversación el 2026-06-26. El repositorio no puede demostrar si el
propietario ya las revocó en los paneles externos.

- Confirmar revocación/regeneración en cada proveedor.
- Actualizar solo el almacén local autorizado.
- No pegar valores ni fragmentos en issues, commits, logs o documentación.
- Marcar cerrado únicamente con confirmación del propietario; no inspeccionar ni
  mostrar el contenido de `.env` para “comprobarlo”.

## 4. NotebookLM auto-recall — diagnóstico no bloqueante

Durante la auditoría documental del 2026-08-03 el helper encontró el notebook
asignado. En la consola japonesa falló inicialmente por `cp932`; con
`PYTHONUTF8=1` terminó con código 0 pero no devolvió contexto útil.

Pendiente estrecho: reproducir con sesión autenticada y hacer que el helper
emita un diagnóstico explícito cuando no hay resultados. Hasta entonces,
NotebookLM es contexto auxiliar y el repositorio vivo prevalece.

## Reglas para mantener este archivo

- Añadir solo acciones abiertas, con evidencia y siguiente paso concreto.
- Eliminar de aquí una tarea al cerrarla y registrar el resultado en
  `ESTADO_PROYECTO.md` o una memoria fechada.
- No acumular transcripciones de sesiones, listas de PR mergeados ni bugs de
  releases antiguos.
- Antes de repetir un pendiente, verificar GitHub, workflows, código, tests y
  artefactos actuales.
