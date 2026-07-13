Cambia el backend de IA de Claude Code al provider pedido: **$ARGUMENTS**

Modelo **proxy-always** (revisado 2026-07-05): TODOS los providers —incluido Claude—
pasan por el proxy local (`http://127.0.0.1:4747/claudeproxy`). El gateway hace
passthrough crudo a `https://api.anthropic.com` cuando el backend activo es Claude,
preservando el header de OAuth que Claude Code inyecta. `ANTHROPIC_BASE_URL` queda
**SIEMPRE** apuntando al proxy; cruzar `claude<->alternativo` es un hot-swap en
caliente (proxy_state.json se relee por request) y **NUNCA** requiere reiniciar
Claude Code. Comportamiento equivalente a OpenCode / Roo Code / Cursor: el cliente
nunca pierde contexto al cambiar de backend.

`needs_restart` solo es `true` la PRIMERA vez (instalación nueva / upgrade desde
versión vieja sin proxy-always) — después de UN reinicio para que Claude Code lea
la nueva env var, todos los switches son en caliente.

## Uso

```
/provider                          # muestra estado actual (provider activo + proxy)
/provider claude                   # volver a Claude (passthrough OAuth del gateway)
/provider glm                      # GLM (z.ai) — alias de zai
/provider zai                      # idem
/provider minimax                  # MiniMax
/provider ollama                   # Ollama local — auto-descubre el modelo cargado
/provider ollama llama3.2:3b       # Ollama local con modelo explícito
/provider lmstudio                 # LM Studio local — auto-descubre el modelo cargado
/provider nvidia                   # NVIDIA NIM (OpenAI remoto, traducido via proxy)
/provider openrouter               # OpenRouter
/provider opencode                 # OpenCode Zen (glm-5.2, kimi-k2.7, etc.)
```

Providers que se enrutan por el proxy: **claude, zai (glm), minimax** (formato
Anthropic directo) y **nvidia, ollama, lmstudio, openrouter, opencode** (OpenAI —
el proxy los traduce vía `core.openai_translator`). Los locales no requieren API
key; si no pasás modelo, se auto-descubre el primero cargado (Ollama `/api/tags`,
LM Studio `/v1/models`). NVIDIA / OpenRouter / OpenCode sí requieren API key en
`.env`.

## Flujo

1. **Parsear** `$ARGUMENTS`: el primer token es el provider; el segundo (opcional)
   es el modelo. Normalizar el provider: `glm` → `zai`; trim a minúsculas.
   - Si está vacío: hacer `GET http://127.0.0.1:4747/v1/provider/status`, reportar
     `active_provider`, `active_model` y `proxy_connected`, y terminar.
2. **Aceptar todos los providers routables** (`proxy_switch.PROXY_ROUTABLE`).
   Ya no hay ninguno rechazado por el proxy: nvidia, openrouter y opencode
   hablan OpenAI y el gateway los traduce.
3. **Leer la session key**: `~/.antigravity/session.key` esta CIFRADA en disco
   (Fernet o DPAPI, ver `.agent/mcp/session_key.py`) — un `cat` directo manda el
   ciphertext crudo y el gateway responde 403 "API key invalida". Usar siempre el
   CLI que descifra:
   ```bash
   python .agent/mcp/session_key.py
   ```
4. **Consultar estado** para decidir conectar vs hot-swap:
   ```bash
   curl -sS http://127.0.0.1:4747/v1/provider/status \
     -H "X-API-Key: $(python .agent/mcp/session_key.py)"
   ```
5. **Elegir endpoint** según `data.proxy_connected`:
   - `proxy_connected == true` → `POST /v1/provider/hotswap` (en caliente, sin reiniciar).
   - `proxy_connected == false` → `POST /v1/provider/switch` (conecta el proxy; primer reinicio si veníamos sin base URL).
   - En el modelo proxy-always ya no hay branch especial para claude: el gateway
     rutea al endpoint nativo de Anthropic cuando el backend activo es claude.
   ```bash
   curl -sS -X POST http://127.0.0.1:4747/v1/provider/<endpoint> \
     -H "Content-Type: application/json" \
     -H "X-API-Key: $(python .agent/mcp/session_key.py)" \
     -d '{"provider": "<id-normalizado>", "model": "<modelo-opcional>"}'
   ```
   **Mensaje según `data.needs_restart`** (NO lo hardcodees):
   - `needs_restart == true` → **"Una sola vez: reiniciá Claude Code para que lea la
     nueva `ANTHROPIC_BASE_URL`. Después, todo cambio será en caliente."**
   - `needs_restart == false` → **"Cambio en caliente — aplica en el próximo mensaje,
     misma conversación, sin reiniciar."**
6. **Reportar** backend activo y modelo. Si la respuesta trae `"ok": false` o `"error"`,
   mostrar el error tal cual (p. ej. API key faltante en `.env`).
7. Si `curl` falla (gateway caído): avisar que hay que arrancarlo con
   `python start_gateway.py` — el proxy necesita el gateway vivo.

## Notas

- **Todos los switches son en caliente** después del primer reinicio (cuando el
  usuario instala/actualiza el modelo proxy-always). El flujo normal NO toca
  `ANTHROPIC_BASE_URL` ni `~/.claude/settings.json`: solo escribe en
  `~/.antigravity/proxy/active_provider.json` que el gateway relee por request.
- **Claude via passthrough OAuth** del gateway: corre con su OAuth propio y tu
  modelo real (p. ej. Opus / Sonnet). El gateway preserva los headers de auth
  al retransmitir a `api.anthropic.com`. No hay diferencia funcional con Claude
  nativo, salvo que el gateway es ahora la única puerta de entrada (lo cual
  permite circuit breaker, failover, shadow mode y class routing sobre Claude).
- **Rollback total** (salir del ecosistema): `POST /v1/provider/disconnect` o el
  botón "Desconectar proxy" de Nexus. Esto SÍ quita `ANTHROPIC_BASE_URL` y
  siempre pide reiniciar — es el único caso donde se sale del modelo proxy-always.
- Si un provider necesita API key (`minimax`, `zai`, `nvidia`, `openrouter`,
  `opencode`) y no está en `.env`, el endpoint devuelve error con el nombre
  de la var faltante (`MINIMAX_API_KEY`, etc.).
- **Locales (`ollama`/`lmstudio`)** no requieren API key. El servicio local
  tiene que estar corriendo (Ollama `:11434`, LM Studio `:1234`). Los modelos
  locales (3B-35B) rinden bastante menos que Claude / MiniMax / GLM en el
  tooling pesado de agente — sirven para tareas simples, privacidad u offline.
