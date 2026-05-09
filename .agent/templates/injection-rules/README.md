# Injection Rules Templates

Estas plantillas se despliegan automáticamente cuando el inyector MCP de Nexus configura un nuevo proyecto.

## Archivos

| Archivo | Destino en proyecto target | Propósito |
|---|---|---|
| `CLAUDE.md` | `./CLAUDE.md` (si no existe) | Guía base para Claude Code |
| `language.md` | `.claude/rules/language.md` | Política de idioma |
| `persona.md` | `.claude/rules/persona.md` | Persona y estilo de comunicación |
| `best-practices.md` | `.claude/rules/best-practices.md` | Buenas prácticas |
| `memory-sync.md` | `.claude/rules/memory-sync.md` | Sincronización de memorias |

## Uso

El inyector MCP de Nexus (`inject_mcp` command) debe:
1. Agregar servidores MCP a `.mcp.json` del proyecto target
2. Copiar estas plantillas a las rutas correspondientes (sin sobreescribir existentes)
3. Crear `.claude/rules/` si no existe
4. Crear `.claude/memory/` si no existe

## Integración con el comando Rust

El comando `inject_mcp` en `nexus-app/src-tauri/src/commands/ecosystem.rs` actualmente
delega toda la lógica al script Python `.agent/scripts/mcp_injector.py` y solo modifica
`.mcp.json` del proyecto target. Para desplegar reglas se necesitan los siguientes cambios:

### Opción A: Extender `mcp_injector.py` (recomendado)

Agregar un paso al script Python que, después de inyectar `.mcp.json`, copie los archivos
de este directorio al proyecto target:

```python
# En mcp_injector.py, después de escribir .mcp.json:

TEMPLATES_DIR = Path(__file__).parent.parent / "templates" / "injection-rules"

def deploy_rules(target_dir: Path) -> list[str]:
    """Despliega reglas base al proyecto target sin sobreescribir existentes."""
    deployed = []
    rules_dir = target_dir / ".claude" / "rules"
    memory_dir = target_dir / ".claude" / "memory"

    # Crear directorios
    rules_dir.mkdir(parents=True, exist_ok=True)
    memory_dir.mkdir(parents=True, exist_ok=True)

    # Mapeo de archivos template -> destino
    file_map = {
        "CLAUDE.md": target_dir / "CLAUDE.md",
        "language.md": rules_dir / "language.md",
        "best-practices.md": rules_dir / "best-practices.md",
        "memory-sync.md": rules_dir / "memory-sync.md",
    }

    for template_name, dest_path in file_map.items():
        if not dest_path.exists():
            src = TEMPLATES_DIR / template_name
            if src.exists():
                shutil.copy2(src, dest_path)
                deployed.append(str(dest_path))

    return deployed
```

### Opción B: Agregar paso en Rust (`ecosystem.rs`)

Agregar un segundo paso en el comando `inject_mcp` que copie los archivos directamente
desde Rust, después de que el script Python termine exitosamente:

```rust
// Después de verificar output.status.success() en inject_mcp:
if output.status.success() {
    let templates_dir = Path::new(&config.antigravity_root)
        .join(".agent/templates/injection-rules");
    let target = Path::new(&target_dir);

    // Crear .claude/rules/ y .claude/memory/
    let rules_dir = target.join(".claude/rules");
    let memory_dir = target.join(".claude/memory");
    let _ = std::fs::create_dir_all(&rules_dir);
    let _ = std::fs::create_dir_all(&memory_dir);

    // Copiar templates sin sobreescribir
    let file_map = [
        ("CLAUDE.md", target.join("CLAUDE.md")),
        ("language.md", rules_dir.join("language.md")),
        ("best-practices.md", rules_dir.join("best-practices.md")),
        ("memory-sync.md", rules_dir.join("memory-sync.md")),
    ];

    for (template, dest) in &file_map {
        if !dest.exists() {
            let src = templates_dir.join(template);
            if src.exists() {
                let _ = std::fs::copy(&src, dest);
            }
        }
    }
}
```

### Recomendación

La **Opción A** (Python) es preferible porque:
- El flujo ya está centralizado en `mcp_injector.py`
- No requiere recompilar Rust para ajustar la lógica de despliegue
- El script Python ya tiene acceso al filesystem y maneja errores
- Mantiene el comando Rust como thin wrapper (patrón actual)

### Notas adicionales

- Nunca sobreescribir archivos existentes en el proyecto target
- Los archivos template NO deben incluirse en `.gitignore` del proyecto target
- Si el proyecto ya tiene un `CLAUDE.md`, NO reemplazarlo — el usuario ya definió sus reglas
- Los archivos en `.claude/rules/` se auto-inyectan en cada sesión de Claude Code
