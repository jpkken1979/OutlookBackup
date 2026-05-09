---
name: clean-code-karpathy
description: Principios cognitivos y quirúrgicos de código (Inspirado en Andrej Karpathy) para reducir alucinaciones, código innecesario y deuda técnica durante la asistencia de IA.
type: feature
---

# clean-code-karpathy

Estas guías imponen una mentalidad defensiva en la IA durante la escritura de código. Se enfoca en precaución, testeo y cambios asilados en lugar de velocidad ciega.

## 1. Piensa Antes de Codificar (Think Before Coding)
**No asumas. No ocultes tu confusión. Menciona alternativas (tradeoffs).**
- Antes de implementar:
  - Expón tus presuposiciones. Si algo es dudoso, pausa y pregunta.
  - Si hay varias interpretaciones admisibles, preséntalas; NO elijas en silencio.
  - Si existe un enfoque simple, destácalo. Levanta objeciones si el prompt pide algo irracionalmente complejo.
  - Si no lo tienes claro, *detente*. Menciona exactamente qué confunde y pregunta.

## 2. Simplicidad Primero (Simplicity First)
**El mínimo código para solucionar el problema. Nada "por si acaso".**
- Cero funcionalidades si no fueron solicitadas ("YAGNI").
- Cero abstracciones (clases, factorías) para un código que solo se usa 1 vez.
- Cero "flexibilidad" que no haya pedido el usuario.
- Cero manejo de errores para escenarios matemáticamente imposibles.
- Si puedes expresarlo de forma limpia en 50 líneas, borra tu código de 200 líneas.
- Pregunta de oro: "¿Diría un Ingeniero Senior que esto es demasiado complicado para el problema expuesto?". Si la respuesta es sí, simplifícalo.

## 3. Cambios Quirúrgicos (Surgical Changes)
**Toca solo lo indispensable. Limpia exclusivamente lo que alteraste.**
- Al editar código existente:
  - NO "mejores" bloques perimetrales, comentarios o su formato.
  - NO refactorices cosas aledañas que "huelen mal" si ya funcionan.
  - Iguala el estilo sintáctico presente, por más que personalmente usarías otro.
  - Si ves "dead code", menciónalo verbalmente al usuario pero NO LO BORRES sin permiso expreso.
- Al generar "código huérfano" tras tus alteraciones:
  - Si reemplazaste una función, elimínela si tus propios cambios la dejaron inútil.
  - La prueba de fuego: *Cada línea eliminada o agregada debe rastrearse quirúrgicamente al objetivo original del usuario.*

## 4. Ejecución Orientada a Objetivos (Goal-Driven Execution)
**Define métricas de éxito. Itera hasta verificarlo.**
- Transforma intenciones o tareas informales en hitos verificables para que tu bucle de codificación tenga sentido:
  - *"Agrega reglas de validación"* → *"Escribe un `test_` para inputs inválidos, y luego haz que pasen verde."*
  - *"Arregla el bug XYZ"* → *"Escribe un test que logre replicar XYZ fallando, e implementa la solución para pasarlo."*
  - *"Refactoriza X"* → *"Asegúrate ejecutando la suite que todo pasa antes de tocar y después de tocarlo."*
- Antes de un multi-paso, traza tu micro-plan:
  ```markdown
  1. [Paso] → Verificar: [condición técnica observable]
  2. [Paso] → Verificar: [condición técnica observable]
  ```
- No asumas el éxito. Comprúebalo objetivamente con el entorno.
