Alias de `/provider` para cambiar el backend IA rapidamente: **$ARGUMENTS**

Objetivo: permitir comandos cortos como:

```
/cambiar claude
/cambiar minimax
/cambiar glm
/cambiar zai
/cambiar
```

Reglas:

1. Si `$ARGUMENTS` esta vacio, comportarse igual que `/provider` sin argumentos:
   - mostrar estado actual (`active_provider`, `active_model`, `proxy_connected`).
2. Normalizar argumentos:
   - `glm` -> `zai`
   - trim + lowercase
3. Ejecutar exactamente el mismo flujo definido en `/provider` para conectar/hot-swap:
   - si `proxy_connected == false`: usar `POST /v1/provider/switch`
   - si `proxy_connected == true`: usar `POST /v1/provider/hotswap`
4. Reportar resultado final en lenguaje claro:
   - provider activo
   - modelo activo
   - si requiere reinicio (`needs_restart`) o no
5. Si hay error, mostrarlo textual (API key faltante, provider incompatible, gateway caido, etc.).

Nota:
- Este comando es solo un alias ergonomico. La logica de negocio canonica sigue siendo `/provider`.
