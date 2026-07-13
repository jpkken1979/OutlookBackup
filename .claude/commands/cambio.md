Alias corto de `/provider` (equivalente funcional): **$ARGUMENTS**

Uso rapido:

```
/cambio claude
/cambio minimax
/cambio glm
/cambio zai
/cambio
```

Comportamiento esperado:

1. Sin argumentos -> mostrar estado actual (igual que `/provider`).
2. Con argumentos -> misma logica que `/provider`:
   - normalizar `glm` a `zai`
   - conectar con `switch` si el proxy no esta conectado
   - hot-swap con `hotswap` si el proxy ya esta conectado
3. Informar provider/modelo activo y si hay que reiniciar.
4. Propagar errores tal cual para troubleshooting rapido.

Nota:
- `cambio` es alias de conveniencia. `/provider` sigue siendo la referencia principal.
