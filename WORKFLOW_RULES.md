# Método de trabajo para cambios complejos

Este documento complementa `RULES.md`. Describe un flujo reproducible, sin
depender de una herramienta o proveedor de IA concreto.

## 1. Entender el resultado

Antes de editar, convertir el pedido en criterios observables:

- qué debe cambiar para el usuario;
- qué superficies están dentro del alcance;
- qué contratos no deben romperse;
- cómo se demostrará que terminó.

Si falta un dato que puede descubrirse de forma segura en el repo, investigarlo.
Preguntar solo cuando una elección no comprobable cambie materialmente el
resultado o requiera autoridad nueva.

## 2. Preflight

1. Leer `AGENTS.md`, `ESTADO_PROYECTO.md`, este workflow y la guía del dominio.
2. Consultar MCP/Brain/skills cuando estén disponibles.
3. Ejecutar NotebookLM auto-recall en los casos definidos por `AGENTS.md`.
4. Comprobar rama, HEAD, worktree y archivos no rastreados.
5. Identificar fuente de verdad, consumidores, tests y generadores.
6. Tomar un baseline estrecho antes de un refactor o limpieza masiva.

No considerar un error “preexistente” solo porque aparecía antes: registrar el
baseline y comparar el mismo comando contra el cambio.

## 3. Plan

Para tareas de varios pasos, mantener un plan visible con:

- un único paso en progreso;
- resultados verificables, no actividades vagas;
- riesgos y límites explícitos;
- actualización del estado al terminar cada bloque.

La delegación es opcional. Solo usar subagentes si el entorno lo admite, el
usuario o las reglas aplicables lo permiten y las tareas son independientes.
Cada tarea delegada necesita alcance, archivos, restricciones y gates propios.
La persona o agente principal revisa siempre el diff integrado.

## 4. Investigar antes de cambiar

Para cada hallazgo:

1. localizar definición y referencias;
2. seguir consumidores estáticos y dinámicos;
3. revisar tests, configuración, empaquetado y generación;
4. clasificarlo como activo, histórico, generado, contractual o candidato;
5. elegir la modificación mínima que resuelva la causa.

Una búsqueda sin referencias no autoriza borrar. En Python, MCP, Tauri, hooks,
skills y plugins existen registros y cargas dinámicas que una búsqueda simple no
ve.

## 5. Implementar en bloques verificables

- Hacer un cambio coherente por bloque.
- Corregir la fuente antes de sus proyecciones o artefactos.
- Agregar o adaptar tests cuando cambie comportamiento.
- Tras un refactor masivo, ejecutar también tipos, lint y formato: los tests no
  detectan todas las regresiones de anotaciones o imports.
- Preservar deliberadamente ramas de compatibilidad hasta demostrar que el
  contrato ya no existe.

## 6. Verificar

Orden recomendado:

1. test específico del comportamiento;
2. suite de la superficie;
3. lint, tipos, formato y checks contractuales;
4. suite amplia si el riesgo es transversal;
5. build o smoke real si cambia UI, IPC, instalación o release.

Para Nexus, seguir `nexus-app/CLAUDE.md` y
`.github/instructions/verification-nexus.instructions.md`. Para Python y bot,
usar las instrucciones correspondientes en `.github/instructions/`.

La cobertura canónica y sus umbrales se leen del workflow, no de documentos
copiados. No reemplazar una falla con un umbral menor sin justificarlo como piso
de regresión explícito.

## 7. Revisar como integración

Antes de declarar éxito:

- leer `git diff --stat` y `git diff` completos;
- buscar cambios accidentales, archivos generados y datos sensibles;
- confirmar que nombres, comandos, versiones y enlaces coinciden con fuentes
  ejecutables;
- comprobar que no quedaron dos caminos para la misma función;
- verificar que una UI nueva está montada desde su entry point y que cada IPC
  usado está registrado.

Si hubo trabajo paralelo, integrar primero y volver a ejecutar los gates sobre
el conjunto; los resultados aislados no prueban la combinación.

## 8. Cerrar y documentar

La entrega debe decir:

- resultado y beneficio práctico;
- archivos o superficies cambiados;
- pruebas ejecutadas con PASS/FAIL/SKIP;
- riesgos o pendientes reales;
- estado de Git solicitado por el usuario.

Actualizar `ESTADO_PROYECTO.md` para cambios operativos importantes. Mantener
`.claude/rules/PENDING_TASKS.md` corto: solo acciones abiertas y verificadas. El
detalle cerrado pertenece a memoria o historial, no a una regla auto-inyectada.

No declarar “todo listo” si falta un gate obligatorio, una credencial externa,
una validación instalada o una decisión del propietario. Nombrar exactamente qué
falta y qué evidencia existe.
