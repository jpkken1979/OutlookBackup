Buscar bugs, vulnerabilidades de seguridad y problemas de calidad en los cambios de la rama actual.

## Flujo

1. Obtener el diff completo: `git diff main...HEAD`
2. Si no hay diff (estamos en main), usar `git diff HEAD~3...HEAD`
3. Listar todos los archivos modificados

## Para cada archivo, verificar

- Inputs de usuario (params, headers, body)
- Queries a base de datos
- Checks de autenticación/autorización
- Operaciones de sesión/estado
- Llamadas externas
- Operaciones criptográficas

## Checklist de seguridad

- [ ] Injection (SQL, command, template)
- [ ] XSS (outputs escapados?)
- [ ] Authentication (checks en operaciones protegidas?)
- [ ] Authorization/IDOR (control de acceso verificado?)
- [ ] CSRF (operaciones de estado protegidas?)
- [ ] Race conditions (TOCTOU en read-then-write?)
- [ ] Information disclosure (errores, logs, timing?)
- [ ] DoS (operaciones sin límite, rate limiting?)
- [ ] Business logic (edge cases, overflow?)

## Output

Por cada issue encontrado:
- **Archivo:Línea** — Descripción breve
- **Severidad**: Critical/High/Medium/Low
- **Problema**: Qué está mal
- **Fix**: Sugerencia concreta

Solo reportar — no hacer cambios. Priorizar: seguridad > bugs > calidad.
