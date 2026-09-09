Gestiona el proveedor **enrutado** de Antigravity solicitado: **$ARGUMENTS**.

> Esta orden no convierte una sesión Claude nativa en GLM/GPT ni inicia o
> detiene Control remoto. Para esa diferencia, usar
> `docs/guides/PROVIDER_SWITCHING.md` como fuente de verdad.

## Uso

```text
/provider                         # estado del routing del gateway
/provider claude                  # Claude a través del gateway, no Claude nativo
/provider glm [modelo]            # GLM/ZAI
/provider minimax [modelo]        # MiniMax
/provider openrouter [modelo]     # OpenRouter
/provider opencode [modelo]       # OpenCode Go/Zen compatible
/provider ollama [modelo]         # Ollama local
/provider lmstudio [modelo]       # LM Studio local
```

## Flujo seguro

1. Si no hay argumentos, consultar el estado del gateway y mostrar proveedor,
   modelo, salud y si la sesión es enrutada.
2. Si hay proveedor, comprobar primero que `http://127.0.0.1:4747/v1/health`
   responda correctamente.
3. Validar el proveedor y modelo contra el catálogo disponible. `Auto` usa el
   catálogo dinámico; no inventar modelos ni exponer claves.
4. Ejecutar el cambio mediante el comando canónico del gateway y reportar su
   resultado exacto. Si requiere una sesión enrutada nueva, explicarlo; no
   editar `~/.claude/settings.json` ni caches de Claude manualmente.
5. Si el usuario necesita Control remoto de Claude, explicar que debe iniciar
   una sesión nativa separada:

   ```powershell
   claude --remote-control "D:\ruta\del\proyecto"
   ```

6. Para ordenar respaldos, dirigir a Nexus → Preferencias → Salud de providers
   → Ordenar. El comando `/provider` cambia el proveedor activo; no altera el
   orden de Auto-failover.
