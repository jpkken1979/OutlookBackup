# Regla: Formato de Commits

## Estructura

```
<type>(<scope>): <descripción en español>

[cuerpo opcional]
```

## Tipos permitidos

| Tipo | Cuándo usarlo |
|------|---------------|
| `feat` | Nueva funcionalidad |
| `fix` | Corrección de bug |
| `docs` | Solo documentación |
| `style` | Formato, sin cambio lógico |
| `refactor` | Refactorización sin cambio de comportamiento |
| `test` | Añadir o corregir tests |
| `chore` | Mantenimiento, deps, configuración |

## Ejemplos

```
feat(auth): agregar login con OAuth2
fix(api): corregir timeout en requests externos
chore(deps): actualizar dependencias de seguridad
docs(readme): agregar instrucciones de instalación
```

## Reglas adicionales

- Descripción siempre en **español**
- Scope en inglés (nombre del módulo/directorio)
- Primera línea máximo 72 caracteres
