# Regla: commits

Formato convencional:

```text
<type>(<scope>): <descripción breve en español>

<cuerpo opcional con motivo, riesgo y verificación>
```

Tipos habituales: `feat`, `fix`, `docs`, `refactor`, `test`, `chore`, `style`.

- Scope en inglés y título breve.
- No mezclar cambios no relacionados ni cambios ajenos del worktree.
- No atribuir coautoría a una persona o IA que no participó realmente.
- No incluir secretos, logs sensibles o artefactos generados accidentales.
- Revisar el diff y ejecutar gates antes de commitear.
- Commit, push, merge y release son acciones diferentes; hacer solo las pedidas.
