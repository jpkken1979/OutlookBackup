# Antigravity MCP Server

Servidor MCP (Model Context Protocol) que expone las skills y agentes de Antigravity como herramientas para cualquier cliente MCP compatible.

## Guia de Seleccion de Servidor

Este directorio contiene 3 implementaciones de servidor MCP. Cada una tiene un caso de uso especifico:

### `server.py` - Servidor Principal (Recomendado)

**Cuando usarlo:**
- Instalaciones nuevas y produccion
- Clientes MCP que soportan la libreria `mcp` v1.26+
- Claude Desktop, Cursor, Continue, Zed, y la mayoria de IDEs modernas
- Cuando se necesita el API mas estable y mantenido

**Caracteristicas:**
- Usa la API oficial de la libreria `mcp` (`Server`, `stdio_server`)
- Transporte stdio estandar
- Descubrimiento automatico de skills y agentes
- Compatible con Python 3.13+

**Ejecucion:**
```bash
pip install mcp
python mcp-server/server.py
```

### `server_v2.py` - Compatibilidad Legacy (DEPRECADO)

**Cuando usarlo:**
- Clientes MCP antiguos que no soportan la libreria `mcp` moderna
- Clientes que usan JSON-RPC raw sobre stdin/stdout
- Debugging de problemas de protocolo (logs detallados a archivo)

**Caracteristicas:**
- Implementacion manual del protocolo MCP (sin dependencia de libreria `mcp`)
- Deteccion adaptativa de framing (Content-Length vs JSON raw)
- Logs a archivo (`mcp_server.log`) para evitar contaminar stdout
- Herramientas extra: `sequential_thinking`, `list_skills`, `search_skills`, `list_agents`

**Ejecucion:**
```bash
# No requiere la libreria mcp
python mcp-server/server_v2.py
```

> **Nota:** Este servidor esta deprecado. Migrar a `server.py` cuando sea posible.

### `server_uns.py` - Dominio UNS Enterprise

**Cuando usarlo:**
- Operaciones especificas del dominio UNS (gestion de personal en Japon)
- Consultas de empleados haken/ukeoi activos
- Consultas de legislacion laboral japonesa (Haken-ho, 36 Kyotei)

**Caracteristicas:**
- Usa `FastMCP` para definicion rapida de herramientas
- Herramientas especializadas: `get_active_employees_count`, `get_japanese_labor_rule`
- Se conecta al Excel maestro de empleados via `EmployeeLoader`
- Base de conocimiento legal en `docs/knowledge/KNOWLEDGE_LEGAL_JP.md`

**Ejecucion:**
```bash
pip install mcp
python mcp-server/server_uns.py
```

## Matriz de Compatibilidad con IDEs

| IDE | server.py | server_v2.py | server_uns.py | Notas |
|-----|-----------|-------------|---------------|-------|
| Claude Desktop | Si | Si | Si | Recomendado: server.py |
| Cursor | Si | Si | Si | Usar config en `.cursor/mcp.json` |
| Continue | Si | No | Si | Requiere mcp v1.26+ |
| Windsurf | Si | Si | Si | Usar config en `.windsurf/mcp.json` |
| Zed | Si | No | Si | Solo stdio moderno |
| VS Code (Copilot) | Si | Si | Si | Via extension o config MCP |
| Trae | Si | Si | Si | Usar config en `.trae/` |
| Roo Code | Si | Si | Si | Usar config en `.roo/` |
| OpenCode | Si | Si | No | Soporta SSE via Gateway |
| Cline | Si | Si | No | Soporta SSE via Gateway |

> **Nota:** Para clientes que soportan SSE/HTTP (OpenCode, Cline, etc.), usar el Universal Gateway
> en lugar de estos servidores stdio. Ver seccion "Gateway HTTP/SSE" mas abajo.

## Configuracion

### Claude Desktop

Agregar a `claude_desktop_config.json`:

**Windows:** `%APPDATA%\Claude\claude_desktop_config.json`
**macOS:** `~/Library/Application Support/Claude/claude_desktop_config.json`

```json
{
  "mcpServers": {
    "antigravity": {
      "command": "python3",
      "args": ["ruta/al/proyecto/mcp-server/server.py"]
    }
  }
}
```

Para UNS enterprise, agregar servidor adicional:

```json
{
  "mcpServers": {
    "antigravity": {
      "command": "python3",
      "args": ["ruta/al/proyecto/mcp-server/server.py"]
    },
    "uns-commander": {
      "command": "python3",
      "args": ["ruta/al/proyecto/mcp-server/server_uns.py"]
    }
  }
}
```

### Otros clientes MCP (stdio)

Todos los servidores usan transporte stdio estandar:

```bash
python3 mcp-server/server.py
```

### Gateway HTTP/SSE (clientes web/remotos)

Para clientes que soportan conexion remota (SSE o HTTP directo), usar el Universal Gateway (puerto 4747):

- **SSE:** `http://127.0.0.1:4747/v1/mcp/sse`
- **HTTP:** `http://127.0.0.1:4747/v1/mcp`

Ver `mcp-configs/` para templates de configuracion de 12+ IDEs.

## Herramientas Disponibles

### server.py - Herramientas automaticas

El servidor descubre automaticamente todas las skills y agentes:

- `skill_<nombre>` - Cada skill del ecosistema (731+)
- `agent_<nombre>` - Cada agente disponible (40 activos)
- `list_skills` - Lista todas las skills disponibles
- `list_agents` - Lista todos los agentes disponibles
- `search_skills` - Busca skills por palabra clave

### server_uns.py - Herramientas UNS

- `get_active_employees_count` - Conteo de empleados activos (haken/ukeoi)
- `get_japanese_labor_rule` - Consulta de legislacion laboral japonesa

## Ejemplo de Uso

Una vez configurado, en Claude Desktop:

> "Usa la skill api_patterns para validar mi API en src/api/"

> "Busca skills relacionadas con testing"

> "Dame el prompt del agente security_auditor"

> "Cuantos empleados activos hay?" (requiere server_uns.py)

## Verificacion

```bash
# Verificar que la configuracion MCP funciona
python3 mcp-server/verify_universal_mcp.py

# Probar servidor localmente
python3 mcp-server/server.py

# Ver logs (solo server_v2.py)
tail -f mcp-server/mcp_server.log
```

## Dependencias

| Servidor | Dependencias |
|----------|-------------|
| server.py | `mcp` >= 1.26 |
| server_v2.py | Ninguna (solo stdlib) |
| server_uns.py | `mcp` >= 1.26, `openpyxl` (para Excel) |

---

*Antigravity MCP Server - Compatible con 11+ IDEs via stdio, HTTP y SSE*
