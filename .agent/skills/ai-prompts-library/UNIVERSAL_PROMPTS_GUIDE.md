# Guía Universal de Prompts

> Guía de diseño de prompts compatibles con: Claude, GPT-4, Gemini, Codex, Llama, Mistral

---

## Principios de Diseño Universal

### 1. Estructura Imperativa (No Declarativa)

```markdown
# INCORRECTO (declarativo)
"Soy un asistente que ayuda con código..."
"Mi rol es analizar problemas..."

# CORRECTO (imperativo)
"Actúa como un desarrollador senior..."
"Analiza el siguiente código y..."
"Responde como experto en..."
```

**Por qué:** Los modelos interpretan mejor instrucciones directas.

---

### 2. Formato de Prompt Universal

```markdown
# [NOMBRE] - Prompt Universal

## Rol
Actúa como [rol específico]. Tu responsabilidad es:
1. [Tarea principal]
2. [Tarea secundaria]

## Contexto
[Información relevante para la tarea]

## Instrucciones
1. [Paso 1]
2. [Paso 2]
3. [Paso 3]

## Formato de Respuesta
[Especificar estructura exacta de salida]

## Restricciones
- NO hacer: [lista]
- SÍ hacer: [lista]

## Ejemplos
Input: "[ejemplo]"
Output: "[resultado esperado]"
```

---

### 3. Patrones Probados

#### Patrón: Experto en Dominio

```markdown
Actúa como [rol] con 10+ años de experiencia en [dominio].

Tu expertise incluye:
- [Área 1]
- [Área 2]
- [Área 3]

Cuando respondas:
1. Sé preciso y técnico
2. Incluye ejemplos prácticos
3. Menciona trade-offs cuando aplique
```

#### Patrón: Analizador

```markdown
Analiza el siguiente [tipo de contenido]:

\`\`\`
[contenido a analizar]
\`\`\`

Proporciona:
1. Resumen (2-3 oraciones)
2. Puntos clave (lista)
3. Recomendaciones (si aplica)
4. Riesgos/Issues (si aplica)
```

#### Patrón: Generador

```markdown
Genera [tipo de output] con las siguientes características:

Requisitos:
- [Requisito 1]
- [Requisito 2]

Formato de salida:
\`\`\`[lenguaje]
[estructura esperada]
\`\`\`

Restricciones:
- Máximo [X] líneas/palabras
- Estilo: [descripción]
```

#### Patrón: Revisor

```markdown
Revisa el siguiente [código/texto/documento]:

\`\`\`
[contenido]
\`\`\`

Evalúa:
1. [Criterio 1]: [escala 1-10]
2. [Criterio 2]: [escala 1-10]
3. [Criterio 3]: [escala 1-10]

Sugerencias de mejora:
- [Mejora 1]
- [Mejora 2]
```

---

### 4. Especificación de Formato

#### Markdown (Universal)

```markdown
Responde usando Markdown con:
- Títulos con ## para secciones
- Listas con - para items
- Código con \`\`\` para bloques
- **negrita** para énfasis
- Tablas para comparaciones
```

#### JSON (Estructurado)

```markdown
Responde en JSON válido con esta estructura:
{
    "status": "success|error",
    "data": { ... },
    "metadata": { ... }
}
```

#### Lista Numerada (Pasos)

```markdown
Responde con pasos numerados:
1. [Primer paso]
2. [Segundo paso]
...
```

---

### 5. Evitar Anti-Patrones

| Anti-Patrón | Problema | Solución |
|-------------|----------|----------|
| Prompts vagos | Respuestas imprecisas | Ser específico |
| Sin ejemplos | Modelo adivina formato | Incluir ejemplos |
| Demasiado largo | Modelo pierde contexto | Condensar |
| Jerga de modelo | No portable | Usar lenguaje neutral |
| Sin restricciones | Output impredecible | Definir límites |

#### Ejemplos de Anti-Patrones

```markdown
# MAL: Vago
"Ayúdame con mi código"

# BIEN: Específico
"Revisa este código Python y sugiere mejoras de rendimiento"

# MAL: Sin formato
"Analiza esto"

# BIEN: Con formato
"Analiza esto y responde con:
1. Resumen
2. Issues encontrados
3. Recomendaciones"

# MAL: Específico de modelo
"Usa tus capacidades de Claude para..."
"Como GPT-4, deberías..."

# BIEN: Neutral
"Actúa como experto en..."
"Analiza desde la perspectiva de..."
```

---

### 6. Técnicas Avanzadas

#### Chain of Thought (CoT)

```markdown
Resuelve paso a paso:

1. Primero, identifica [X]
2. Luego, analiza [Y]
3. Finalmente, concluye [Z]

Muestra tu razonamiento en cada paso.
```

#### Few-Shot Learning

```markdown
Ejemplos de formato deseado:

Ejemplo 1:
Input: "función que suma"
Output: `def suma(a, b): return a + b`

Ejemplo 2:
Input: "función que resta"
Output: `def resta(a, b): return a - b`

Ahora, genera:
Input: "función que multiplica"
Output: [tu respuesta]
```

#### Self-Consistency

```markdown
Proporciona 3 soluciones diferentes al problema.
Luego, identifica cuál es la mejor y por qué.

Solución 1: [...]
Solución 2: [...]
Solución 3: [...]

Mejor solución: [número] porque [justificación]
```

---

### 7. Idioma y Localización

```markdown
## Especificación de Idioma

Responde en: [idioma]
Código/variables en: inglés (estándar internacional)
Comentarios en: [idioma del usuario]

## Para Contenido Japonés (派遣/HR)

Documentos oficiales: 日本語
Explicaciones: Español
Términos técnicos: Mantener en japonés con traducción
Ejemplo: 源泉徴収票 (Certificado de Retención Fiscal)
```

---

### 8. Template de Prompt Completo

```markdown
# [NOMBRE DEL PROMPT]

> Prompt universal compatible con: Claude, GPT-4, Gemini, Codex

## Rol
Actúa como [rol con experiencia específica].

## Objetivo
[Descripción clara del objetivo en 1-2 oraciones]

## Contexto
- [Contexto relevante 1]
- [Contexto relevante 2]

## Instrucciones
1. [Instrucción específica 1]
2. [Instrucción específica 2]
3. [Instrucción específica 3]

## Formato de Respuesta
\`\`\`
[Estructura exacta esperada]
\`\`\`

## Restricciones
✅ HACER:
- [Acción permitida 1]
- [Acción permitida 2]

❌ NO HACER:
- [Acción prohibida 1]
- [Acción prohibida 2]

## Ejemplos

### Ejemplo 1
**Input:**
\`\`\`
[entrada de ejemplo]
\`\`\`

**Output:**
\`\`\`
[salida esperada]
\`\`\`

## Manejo de Errores
- Si [condición]: [acción]
- Si falta información: [solicitar específicamente]

## Notas Adicionales
[Cualquier información extra relevante]
```

---

### 9. Checklist de Universalidad

Antes de usar un prompt, verifica:

- [ ] ¿Usa lenguaje imperativo ("Actúa como..." vs "Soy...")?
- [ ] ¿Especifica el formato de salida claramente?
- [ ] ¿Incluye al menos un ejemplo?
- [ ] ¿Define restricciones (qué NO hacer)?
- [ ] ¿Evita jerga específica de un modelo?
- [ ] ¿Es lo suficientemente específico?
- [ ] ¿Es lo suficientemente conciso?
- [ ] ¿Especifica el idioma de respuesta?

---

### 10. Migración de Prompts Existentes

Para hacer un prompt existente más universal:

1. **Cambiar voz pasiva a activa**
   - Antes: "El análisis debe incluir..."
   - Después: "Incluye en tu análisis..."

2. **Eliminar referencias a modelos**
   - Antes: "Como Claude, tú..."
   - Después: "Actúa como..."

3. **Agregar estructura de salida**
   - Especificar exactamente qué formato esperas

4. **Incluir ejemplos**
   - Mínimo 1-2 ejemplos de input/output

5. **Definir límites**
   - Qué debe y qué no debe hacer

---

## Biblioteca de Prompts por Categoría

### Desarrollo
- `code-review.md` - Revisión de código
- `debug-assistant.md` - Debugging
- `architecture-design.md` - Diseño de arquitectura

### Documentación
- `readme-generator.md` - Generar READMEs
- `api-docs.md` - Documentar APIs
- `changelog.md` - Generar changelogs

### Testing
- `test-generator.md` - Generar tests
- `test-review.md` - Revisar tests
- `coverage-analysis.md` - Analizar cobertura

### Seguridad
- `security-audit.md` - Auditoría de seguridad
- `vulnerability-check.md` - Buscar vulnerabilidades

### Productividad
- `summarize.md` - Resumir contenido
- `brainstorm.md` - Generar ideas
- `plan.md` - Crear planes

---

*Guía Universal de Prompts v1.0 - Ecosistema Antigravity*
