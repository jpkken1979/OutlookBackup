# Gateway y adapters MCP

La ruta recomendada para clientes es el broker único, no los servidores stdio
granulares históricos.

## Configuración de cliente

Usar la entrada versionada de `.mcp.json`:

```json
{
  "mcpServers": {
    "antigravity": {
      "command": "<python-del-entorno>",
      "args": ["-m", "core.mcp_stdio_proxy"],
      "env": {
        "ANTIGRAVITY_ROOT": ".",
        "ANTIGRAVITY_MCP_URL": "http://localhost:4747/mcp",
        "PYTHONPATH": ".agent"
      }
    }
  }
}
```

En Windows el path del intérprete puede ser absoluto por limitaciones del PATH
del cliente; los args y root siguen siendo portables.

## Gateway

```powershell
.\.venv\Scripts\python.exe start_gateway.py
```

El gateway concentra MCP, memoria, providers y observabilidad en `:4747`. El
servidor remoto `:3777` es opcional y separado.

Los archivos `agents-server.py`, `skills-server.py`, `brain-server.py` y otros
adapters siguen en el árbol para implementación/compatibilidad. No deben
copiarse como múltiples entradas nuevas.

## Verificación

```powershell
make test-mcp-contract
make test-mcp
```

Ver [`AGENTS.md`](AGENTS.md) para reglas de cambios y
[`../../docs/guides/IDE_AI_UNIFICACION_RAPIDA.md`](../../docs/guides/IDE_AI_UNIFICACION_RAPIDA.md)
para conectar clientes.
