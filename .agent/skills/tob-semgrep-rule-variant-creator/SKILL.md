---
name: tob-semgrep-rule-variant-creator
type: feature
description: "Crea variantes de reglas Semgrep existentes. Extiende patterns para detectar más vulnerabilidades sin empezar desde cero. Incluye técnicas de generalización y especialización."
---

# Trail of Bits: Semgrep Rule Variant Creator

Crea variantes de reglas Semgrep existentes para ampliar cobertura de detección.

## Concepto

En lugar de escribir reglas desde cero, tomar una regla existente y crear variantes que:
- Cubran **más lenguajes**
- Detecten **variaciones del mismo pattern**
- Se **especialicen** para frameworks específicos
- **Generalicen** para capturar más casos

## Técnicas de Variación

### 1. Generalización de Pattern

```yaml
# Regla original — solo detecta subprocess.run
- id: python-shell-injection-v1
  pattern: subprocess.run(..., shell=True, ...)
  languages: [python]
  severity: ERROR

# Variante generalizada — detecta múltiples funciones
- id: python-shell-injection-v2
  patterns:
    - pattern-either:
        - pattern: subprocess.run(..., shell=True, ...)
        - pattern: subprocess.call(..., shell=True, ...)
        - pattern: subprocess.Popen(..., shell=True, ...)
        - pattern: os.system(...)
        - pattern: os.popen(...)
  languages: [python]
  severity: ERROR
```

### 2. Especialización por Framework

```yaml
# Regla base — SQL injection genérica
- id: sql-injection-generic
  pattern: |
    cursor.execute($QUERY % $VAR)
  languages: [python]

# Variante Django
- id: sql-injection-django
  patterns:
    - pattern-either:
        - pattern: |
            $MODEL.objects.raw($QUERY % $VAR)
        - pattern: |
            $MODEL.objects.extra(where=[$QUERY % $VAR])
        - pattern: |
            connection.cursor().execute($QUERY.format($VAR))
  languages: [python]
  metadata:
    framework: django

# Variante SQLAlchemy
- id: sql-injection-sqlalchemy
  patterns:
    - pattern-either:
        - pattern: |
            text($QUERY % $VAR)
        - pattern: |
            session.execute($QUERY.format($VAR))
  languages: [python]
  metadata:
    framework: sqlalchemy
```

### 3. Cross-Language Variants

```yaml
# Python version
- id: hardcoded-secret-python
  patterns:
    - pattern: |
        $KEY = "..."
    - metavariable-regex:
        metavariable: $KEY
        regex: (password|secret|token|api_key|apikey)
  languages: [python]
  severity: ERROR

# JavaScript version
- id: hardcoded-secret-javascript
  patterns:
    - pattern-either:
        - pattern: |
            const $KEY = "..."
        - pattern: |
            let $KEY = "..."
        - pattern: |
            var $KEY = "..."
    - metavariable-regex:
        metavariable: $KEY
        regex: (password|secret|token|apiKey|api_key)
  languages: [javascript, typescript]
  severity: ERROR

# YAML/Config version
- id: hardcoded-secret-yaml
  pattern: |
    $KEY: $VALUE
  metavariable-regex:
    metavariable: $KEY
    regex: (password|secret|token|api_key)
  metavariable-regex:
    metavariable: $VALUE
    regex: ^(?!(\$\{|<|ENV\[)).+
  languages: [yaml]
  severity: WARNING
```

### 4. Taint Analysis Variants

```yaml
# Básica — solo input directo
- id: xss-basic
  pattern: |
    Response($USER_INPUT)
  languages: [python]

# Con taint tracking — sigue el flujo de datos
- id: xss-taint
  mode: taint
  pattern-sources:
    - pattern: request.args.get(...)
    - pattern: request.form.get(...)
    - pattern: request.json[...]
  pattern-sinks:
    - pattern: Response(...)
    - pattern: render_template_string(...)
    - pattern: Markup(...)
  pattern-sanitizers:
    - pattern: escape(...)
    - pattern: bleach.clean(...)
  languages: [python]
  severity: ERROR
```

## Workflow de Creación

1. **Identificar regla base** — Buscar en Semgrep Registry o reglas existentes.
2. **Analizar limitaciones** — ¿Qué patterns no detecta?
3. **Elegir técnica** — Generalizar, especializar, cross-language o taint.
4. **Crear variante** — Escribir la nueva regla.
5. **Testear** — Validar con código de ejemplo (positivos y negativos).
6. **Documentar** — Metadata con relación a regla original.

## Testing de Reglas

```bash
# Test con archivo de ejemplo
semgrep --config my-rule.yml test-cases/

# Validar que no hay falsos positivos
semgrep --config my-rule.yml --test test-cases/

# Benchmark performance
semgrep --config my-rule.yml --time .
```

## Estructura de Test Cases

```python
# test-cases/test_shell_injection.py

# ruleid: python-shell-injection-v2
subprocess.run(cmd, shell=True)

# ruleid: python-shell-injection-v2
os.system(user_input)

# ok: python-shell-injection-v2
subprocess.run(shlex.split(cmd), shell=False)

# ok: python-shell-injection-v2
subprocess.run(["ls", "-la"])
```

## Recursos

- [Semgrep Rule Syntax](https://semgrep.dev/docs/writing-rules/rule-syntax/)
- [Semgrep Registry](https://semgrep.dev/explore)
- [Trail of Bits Semgrep Rules](https://github.com/trailofbits/semgrep-rules)
