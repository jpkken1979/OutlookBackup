# [SKILL NAME] - Skill Template

> Template universal compatible con: Claude, GPT-4, Gemini, Codex, Llama, Mistral

---

## Metadata

```yaml
name: skill-name
version: 1.0.0
author: [tu nombre]
created: YYYY-MM-DD
updated: YYYY-MM-DD
category: [development|automation|documentation|testing|security|ai]
complexity: [low|medium|high]
universal: true  # Funciona en cualquier LLM
```

---

## Descripción

[Descripción clara y concisa de qué hace esta skill en 2-3 oraciones]

---

## Capacidades

### PUEDE hacer:
- [Capacidad 1]
- [Capacidad 2]
- [Capacidad 3]

### NO PUEDE hacer:
- [Limitación 1]
- [Limitación 2]

---

## Uso Rápido

### Comando CLI
```bash
python scripts/main.py [argumentos]
```

### Como Prompt
```
[Instrucción directa para usar esta skill]
```

---

## Parámetros de Entrada

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| `input` | string | Sí | - | Descripción del parámetro |
| `format` | string | No | "json" | Formato de salida |
| `verbose` | bool | No | false | Modo detallado |

---

## Formato de Salida

### Estructura

```json
{
    "status": "success|error",
    "data": {
        // Resultado principal
    },
    "metadata": {
        "timestamp": "ISO-8601",
        "duration_ms": 123
    }
}
```

### Ejemplo de Salida

```json
{
    "status": "success",
    "data": {
        "result": "ejemplo"
    },
    "metadata": {
        "timestamp": "2026-02-01T10:30:00Z",
        "duration_ms": 150
    }
}
```

---

## Ejemplos

### Ejemplo 1: Caso Básico

**Input:**
```
[Entrada de ejemplo]
```

**Output:**
```
[Salida esperada]
```

### Ejemplo 2: Caso Avanzado

**Input:**
```
[Entrada más compleja]
```

**Output:**
```
[Salida correspondiente]
```

---

## Integración

### Con Otras Skills
```
Esta skill se integra con:
- [skill-relacionada-1]: Para [propósito]
- [skill-relacionada-2]: Para [propósito]
```

### En Workflows
```
Esta skill se usa en:
- /workflow-1: Paso [n]
- /workflow-2: Paso [n]
```

---

## Dependencias

### Externas
- Python 3.11+
- [paquete-1]: `pip install paquete-1`
- [paquete-2]: `pip install paquete-2`

### Internas
- `.agent/scripts/logging_config.py`

---

## Configuración

### Variables de Entorno
```bash
export SKILL_CONFIG_VAR="value"
```

### Archivo de Configuración
```yaml
# config.yaml
setting1: value1
setting2: value2
```

---

## Manejo de Errores

| Error | Causa | Solución |
|-------|-------|----------|
| `InputError` | Parámetro inválido | Verificar formato de entrada |
| `TimeoutError` | Operación muy larga | Aumentar timeout o reducir input |
| `ConfigError` | Configuración faltante | Verificar variables de entorno |

---

## Testing

### Ejecutar Tests
```bash
python -m pytest tests/ -v
```

### Cobertura
```bash
python -m pytest tests/ --cov=scripts --cov-report=html
```

---

## Changelog

### v1.0.0 (YYYY-MM-DD)
- Versión inicial
- [Feature 1]
- [Feature 2]

---

## Notas para LLMs

### Cuándo Usar Esta Skill
- Cuando el usuario pide: [patrones de solicitud]
- Para tareas de: [categoría de tareas]

### Cuándo NO Usar
- Para: [tareas fuera de scope]
- Si: [condiciones de exclusión]

### Tips de Optimización
- [Consejo 1 para mejor rendimiento]
- [Consejo 2 para mejor calidad]

---

*Skill creada con el Template Antigravity v1.0*
