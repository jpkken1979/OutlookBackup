---
name: refactoring-patterns
description: "Implementa patrones de refactorización de Martin Fowler y otras técnicas probadas para mejorar la calidad del código sin cambiar su comportamiento. Detecta code smells (Long Method, Large Class, Duplicate Code, etc.) y sugiere refactorizaciones: Extract Method/Class/Variable, Inline, Rename, Move, Replace Conditional with Polymorphism. Triggers: refactoring, code smells, Martin Fowler, clean code, extract method, code quality."
type: feature
---

# refactoring-patterns

## Metadata
- **Name**: Refactoring Patterns
- **Category**: Code Quality
- **Version**: 1.0.0
- **Author**: Antigravity Team

## Description
Skill que implementa patrones de refactorización de Martin Fowler y otras técnicas probadas para mejorar la calidad del código sin cambiar su comportamiento.

## Capabilities
- Detección de code smells
- Sugerencias de refactorización
- Extract Method/Class/Variable
- Inline Method/Variable
- Rename refactorings
- Move Method/Field
- Replace Conditional with Polymorphism
- Introduce Parameter Object
- Replace Magic Number with Symbolic Constant

## Inputs
- `file_path`: Archivo a analizar
- `pattern`: Patrón específico a aplicar
- `language`: Lenguaje del código (python, javascript, typescript)

## Outputs
- Lista de code smells detectados
- Sugerencias de refactorización priorizadas
- Código refactorizado (opcional)

## Usage
```bash
python scripts/refactoring_patterns.py analyze src/
python scripts/refactoring_patterns.py detect-smells file.py
python scripts/refactoring_patterns.py suggest file.py --pattern extract-method
python scripts/refactoring_patterns.py --list-patterns
```

## Code Smells Detectados
- Long Method (>20 líneas)
- Large Class (>300 líneas)
- Long Parameter List (>4 parámetros)
- Duplicate Code
- Dead Code
- Feature Envy
- Data Clumps
- Primitive Obsession
- Switch Statements
- Parallel Inheritance

## Dependencies
- ast (builtin)
- radon (optional)

## Related Skills
- `refactoring-playbook`
- `code-reviewer`
- `clean-code`
