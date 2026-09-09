# Reglas operativas de OpenAntigravity

Estas reglas aplican a cualquier IA o persona que trabaje en este repositorio.
El objetivo es proteger el ecosistema real, evitar documentación divergente y
dejar cambios verificables.

## 1. Orden de autoridad

Cuando dos fuentes discrepen, decidir en este orden:

1. Código, configuración y tests ejecutables actuales.
2. `AGENTS.md` y la guía más cercana al área modificada.
3. `ESTADO_PROYECTO.md` y `docs/CURRENT_STATUS.md`.
4. Este archivo, `WORKFLOW_RULES.md` y `CLAUDE.md`.
5. Memorias, auditorías, planes e informes con fecha.

Las cifras dinámicas de agentes, skills, servidores y Brain viven solamente en
el bloque **Inventario del Ecosistema** de `CLAUDE.md`, generado por
`.agent/scripts/refresh_claude_md.py`. No copiarlas a otras guías.

## 2. Qué es el repositorio

OpenAntigravity es un ecosistema de inteligencia aumentada, no una aplicación
de negocio única. Sus superficies principales son:

| Superficie | Propietario |
|---|---|
| Runtime, agentes, skills, Brain y broker | `.agent/` |
| Gateway MCP portable | `mcp-server/` |
| Bot TypeScript | `src/` |
| Escritorio Nexus (Tauri 2 + React) | `nexus-app/` |
| Cliente móvil/PWA | `nexus-app/pwa/` |

No mover lógica entre superficies ni crear una segunda implementación sin
demostrar primero que no existe una capacidad equivalente.

## 3. MCP primero

Antes de leer archivos masivamente o inventar herramientas, consultar las
capacidades disponibles por MCP, agentes, skills y Brain.

La configuración actual de clientes usa una sola entrada `antigravity` en
`.mcp.json`. Esa entrada conecta `core.mcp_stdio_proxy` con `:4747/mcp`; el
broker publica seis meta-tools. Los nombres granulares históricos
`antigravity-agents`, `antigravity-skills` o `antigravity-brain` no deben
reintroducirse en configuraciones nuevas.

Si el gateway no está disponible, documentar el fallback usado y verificar la
realidad directamente en el repositorio.

## 4. Antes de modificar

Leer, en orden:

1. `AGENTS.md`.
2. `ESTADO_PROYECTO.md`.
3. `WORKFLOW_RULES.md`.
4. `CLAUDE.md`.
5. La guía del dominio, por ejemplo `nexus-app/CLAUDE.md`.

Además:

- comprobar `git status --short` y preservar cambios ajenos;
- buscar consumidores, registros, tests y generación antes de borrar;
- usar NotebookLM auto-recall cuando lo ordene `AGENTS.md`, pero contrastar su
  salida con el estado vivo;
- tratar `.agent/brain/`, `.claude/memory/`, planes, auditorías y reportes como
  evidencia histórica, no como instrucciones actuales.

## 5. Implementación

- Mantener cambios estrechos, reversibles y fáciles de revisar.
- Código, identificadores y logs en inglés; comunicación del equipo en español.
- No “simplificar” ramas raras sin entender el bug o contrato que preservan.
- No usar datos falsos, mocks o fallback silencioso en rutas productivas.
- No editar artefactos generados antes de identificar y corregir su fuente.
- No añadir dependencias, servicios o abstracciones si el repositorio ya ofrece
  la capacidad.
- Un archivo existente no demuestra una función activa: seguir imports,
  registros, IPC, rutas y empaquetado hasta su entry point.

## 6. Seguridad y datos

- Nunca imprimir, copiar a documentación ni commitear secretos nuevos.
- No asumir que un archivo sensible es prescindible: verificar la política
  específica del repositorio y su historial antes de tocarlo.
- Validar paths, entradas externas, límites de red y permisos en los bordes.
- Evitar `shell=True` y comandos construidos con texto no confiable.
- No borrar archivos completos ni contratos dinámicos por una búsqueda textual
  aislada.
- Las acciones destructivas o externas requieren un objetivo exacto y evidencia
  de que están dentro del pedido del usuario.

## 7. Verificación proporcional

Ejecutar primero el gate estrecho y ampliar según riesgo:

| Área | Checks rápidos |
|---|---|
| Runtime Python | `make test-quick`, `make lint`, `make typecheck` |
| Contrato MCP | `make test-mcp-contract` |
| Bot raíz | `npm test`, `npm run health` |
| Nexus | `cd nexus-app; npm run ts:app; npm run lint; npm test` |

Los comandos y umbrales exactos de CI son autoridad en `.github/workflows/`.
La cobertura global tiene un objetivo de mejora y un piso de regresión distinto;
no inventar porcentajes por módulo. Consultar
`.github/workflows/test-coverage-mutation.yml` y `docs/CURRENT_STATUS.md`.

Antes de entregar:

- ejecutar `git diff --check`;
- revisar el diff completo;
- registrar PASS, FAIL y SKIP con el comando y la razón;
- comprobar que la documentación modificada no contiene enlaces rotos;
- actualizar `ESTADO_PROYECTO.md` cuando cambie estado operativo relevante.

## 8. Git

- Usar commits convencionales y descriptivos.
- No atribuir trabajo a otra persona o IA que no haya participado realmente.
- No hacer force-push ni reescribir historia compartida sin permiso explícito.
- No mezclar cambios ajenos del worktree.
- Commit, push, merge y publicación son pasos distintos: ejecutar solo los que
  el usuario haya pedido.

## 9. Higiene documental

- `docs/CURRENT_STATUS.md` indica qué documentos son vigentes.
- Un documento histórico conserva sus cifras y decisiones originales; se marca
  como histórico en el índice en lugar de maquillarlo como estado actual.
- Los pendientes activos viven en `.claude/rules/PENDING_TASKS.md`; los cerrados
  se registran en `ESTADO_PROYECTO.md` o memoria fechada.
- Cuando una regla se despliega en otros proyectos, corregir primero
  `.agent/templates/injection-rules/` y después sincronizar la copia local.
- No mantener directorios de backup como una segunda fuente activa. Cualquier
  retiro de backups exige demostrar consumidores y aprobar el objetivo exacto.

## 10. Criterio de finalización

Una tarea termina cuando el comportamiento pedido está implementado, los gates
relevantes están verdes o claramente explicados, el diff no incluye residuos y
la siguiente IA puede distinguir sin ambigüedad entre estado actual, pendiente e
historia.
