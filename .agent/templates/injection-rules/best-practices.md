# Regla: Buenas Prácticas

## Código
- Type hints obligatorios en funciones públicas
- No usar `any` en TypeScript
- No hardcodear secrets — variables de entorno
- `shell=False` en subprocess (Python)
- Validar inputs en los bordes del sistema

## Seguridad
- Validar paths antes de I/O (prevenir path traversal)
- Sanitizar mensajes de error (no exponer paths internos)
- CORS restrictivo
- Rate limiting en endpoints públicos

## Tests
- Coverage mínimo 80%
- Tests para lógica de seguridad
- Nombres descriptivos

## Git
- Commits en español, formato convencional
- No commitear `.env`, `*.db`, `*.log`
- No force push a main
