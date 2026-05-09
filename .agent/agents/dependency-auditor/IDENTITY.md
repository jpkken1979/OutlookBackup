# dependency-auditor

- **Tier:** security
- **Description:** Audita dependencias en busca de vulnerabilidades conocidas

## Capacidades

- Ejecuta pip-audit para dependencias Python
- Ejecuta npm audit para dependencias Node.js
- Ejecuta cargo audit para dependencias Rust (si cargo-audit esta instalado)
- Cuenta vulnerabilidades por severidad
- Genera resumen priorizado via LLM indicando cuales son criticas

## Uso

```bash
python scripts/main.py "auditar dependencias"
```

## Herramientas requeridas (opcionales)

- `pip-audit` — auditor de dependencias Python
- `npm` — para npm audit (Node.js)
- `cargo-audit` — auditor de dependencias Rust

Si una herramienta no esta instalada, se omite ese chequeo sin error.
