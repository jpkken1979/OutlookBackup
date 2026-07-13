Ejecutar tests y corregir sistemáticamente todos los que fallen usando agrupación inteligente.

## Flujo

1. **Ejecutar tests**: `make test` o `python -m pytest tests/ -x --tb=short`
2. **Analizar fallos**: Contar total, identificar patrones
3. **Agrupar por tipo**: ImportError, AttributeError, AssertionError, etc.
4. **Priorizar**: Infraestructura primero, luego API, luego lógica

## Orden de corrección

1. **Infraestructura**: Import errors, dependencias faltantes, config
2. **Cambios de API**: Firmas de funciones, módulos renombrados
3. **Lógica**: Assertions fallidas, edge cases

## Proceso por grupo

1. Identificar causa raíz (leer código + `git diff`)
2. Implementar fix mínimo
3. Verificar con subset: `python -m pytest tests/path/test_file.py -v`
4. Confirmar que pasa antes de seguir al siguiente grupo

## Verificación final

Después de todos los fixes:
```bash
make test          # Suite completa
```

Confirmar cero regresiones antes de reportar como resuelto.
