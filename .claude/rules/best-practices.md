# Regla: Buenas Practicas de Desarrollo

Aplica a todo el código del repositorio actual.

## Arquitectura

- **MCP-first**: toda capacidad se expone y consume via MCP antes que por lectura directa de archivos.
- **4 capas**: Directiva, Contexto, Ejecucion, Observabilidad. No mezclar responsabilidades.
- **Backward compatible**: todo refactor debe mantener las interfaces publicas existentes.
- **Minimal blast radius**: preferir cambios pequenos y enfocados sobre rewrites masivos.

## Codigo Python

- Type hints en TODAS las funciones (parametros + return)
- Docstrings Google-style en funciones publicas
- `shell=False` siempre en subprocess — usar `shlex.split()`
- Validar inputs en los bordes del sistema (MCP handlers, CLI args)
- Logging estructurado: `logger = logging.getLogger(__name__)`
- Serialización segura: solo JSON o Pydantic (nunca formatos inseguros)

## Codigo TypeScript

- TypeScript strict — cero `any`
- Componentes funcionales con hooks
- Framer Motion variants FUERA de los componentes (archivos `*Variants.ts`)
- Tailwind utility-first — no inline styles
- IPC solo via `invoke()` de Tauri — nunca exponer Node APIs

## Seguridad

- NUNCA hardcodear tokens, passwords o API keys
- Validar paths con `validatePathAccess()` antes de I/O
- Sanitizar mensajes de error hacia el cliente (no exponer paths internos)
- Rate limiting en endpoints publicos
- CORS restrictivo: solo origenes conocidos

## Tests

- Coverage minimo 80% en core
- Tests para toda logica de seguridad (pairing, auth, path validation)
- Mocks solo para dependencias externas — preferir integracion real para SQLite
- Nombres descriptivos: `it('rejects expired pairing codes')`

## Git

- Commits en espanol, formato convencional: `tipo(scope): descripcion`
- No commitear `*.db`, `*.log`
- Excepcion documentada: `.env` SI se versiona porque el repo es privado
  (ver `.gitignore` lineas 151-153 y `.claude/rules/security.md`). Esta excepcion
  NO aplica a forks ni mirrors publicos.
- Feature branches para cambios grandes
- No force push a main

## Performance

- SQLite con WAL mode para concurrencia
- Transactions para operaciones multi-statement
- Lazy loading de subsistemas pesados
- Jitter en schedulers para evitar thundering herd
- Limits de concurrencia en ejecucion de skills (max 5)
