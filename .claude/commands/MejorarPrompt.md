Reescribe y mejora el prompt provisto aplicando ingeniería de prompts: **$ARGUMENTS**

Tomá el texto en `$ARGUMENTS` como el prompt a mejorar. Tu trabajo NO es ejecutar
ese prompt — es **transformarlo en una versión más clara, específica y accionable**,
y explicar qué cambiaste. Si `$ARGUMENTS` está vacío, pedile al usuario que pegue el
prompt (o ofrecé mejorar su último mensaje).

## 💎 Axiomas (principios que no se negocian)

1. **Intención antes que palabras**: primero entendé QUÉ quiere lograr el prompt; si
   no se deduce, preguntá — nunca inventes el objetivo.
2. **Especificidad mata ambigüedad**: reemplazá lo vago ("hacelo lindo", "analizá esto")
   por criterios concretos, medibles y verificables.
3. **Estructura el pedido**: rol + objetivo + contexto + restricciones + formato de
   salida + criterios de éxito. Lo que falte, agregalo o marcalo como pregunta.
4. **No infles**: un prompt mejor es más preciso, no más largo. Sacá relleno, no agregues.
5. **Preservá la voz del usuario**: mejorás su prompt, no lo reemplazás por el tuyo.

## 🛠️ Paso a paso

1. **Diagnóstico**: leé `$ARGUMENTS` y detectá qué le falta según esta grilla:
   - **Rol/Persona**: ¿define quién debe responder (experto en X, tono)?
   - **Objetivo**: ¿qué resultado concreto se busca? ¿es medible?
   - **Contexto**: ¿da la info necesaria (stack, audiencia, restricciones del dominio)?
   - **Restricciones**: ¿límites explícitos (longitud, qué evitar, qué priorizar)?
   - **Formato de salida**: ¿especifica estructura (JSON, tabla, bullets, código)?
   - **Criterios de éxito**: ¿cómo se sabe que la respuesta es buena?
   - **Ejemplos**: ¿un few-shot ayudaría a fijar el formato/estilo esperado?
   - **Descomposición**: si la tarea es compleja, ¿conviene pedir razonamiento por pasos?
2. **Preguntas (solo si es crítico)**: si falta info que cambia sustancialmente el
   resultado, hacé **máximo 2-3 preguntas** puntuales antes de reescribir. Si el prompt
   se entiende lo suficiente, NO preguntes — mejorá directo.
3. **Reescritura**: producí el prompt mejorado aplicando los axiomas. Mantené el idioma
   original del prompt del usuario.
4. **Explicación**: listá en bullets QUÉ cambiaste y POR QUÉ (mapeado a la grilla).
5. **Variante opcional**: si aporta, ofrecé una versión "conciso" y una "detallada".

## 🛡️ Checklist de calidad (antes de entregar)

- [ ] El objetivo del prompt mejorado es inequívoco y medible.
- [ ] Define rol, contexto, restricciones y formato de salida (o marca lo que falta).
- [ ] No quedó lenguaje vago ("mejor", "lindo", "optimizado") sin criterio concreto.
- [ ] No agregué requisitos que el usuario no pidió ni cambié su intención.
- [ ] El prompt mejorado está en un bloque listo para copiar/pegar.
- [ ] La explicación de cambios es breve y accionable, no un ensayo.

## 📤 Formato de salida (siempre este)

```
### Prompt mejorado
<bloque de código con el prompt reescrito, listo para copiar>

### Qué cambié y por qué
- <cambio 1> — <razón, mapeada a Rol/Objetivo/Contexto/Formato/...>
- <cambio 2> — <razón>

### (Opcional) Preguntas para afinar
1. <pregunta crítica solo si falta info que cambia el resultado>
```

## 📚 Ejemplos (Few-shot)

**Ejemplo 1 — prompt vago → específico**

Entrada (`$ARGUMENTS`): `escribime un email para un cliente`

Salida:
```
### Prompt mejorado
Actuá como account manager B2B. Escribí un email en español formal (máx 150
palabras) a un cliente cuyo contrato vence en 30 días, para proponerle renovar
con un 10% de descuento. Tono cordial y directo. Estructura: saludo, valor
entregado este año (1 línea), oferta concreta, CTA con fecha límite. No uses
emojis ni superlativos.

### Qué cambié y por qué
- Agregué rol (account manager B2B) — fija el tono y la expertise.
- Definí objetivo medible (renovar con 10% off) — antes no había meta.
- Agregué contexto (vence en 30 días) y restricciones (150 palabras, sin emojis).
- Especifiqué formato (estructura del email) y criterios de tono.
```

**Ejemplo 2 — falta info crítica → preguntar primero**

Entrada (`$ARGUMENTS`): `ayudame a elegir una base de datos`

Salida:
```
### Preguntas para afinar
1. ¿Qué tipo de datos y volumen esperás (relacional/documental, GB vs TB)?
2. ¿Prioridad: consistencia fuerte, escala horizontal, o simplicidad operativa?
3. ¿Hay restricciones (cloud, presupuesto, stack existente)?

(Con esas respuestas reescribo el prompt para que la recomendación sea accionable
y no genérica.)
```

---
*Comando: /MejorarPrompt v1.0 — ingeniería de prompts (estructura God Mode)*
