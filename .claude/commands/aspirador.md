# /aspirador — limpieza segura con comprensión arquitectónica

Usa `$aspirador` como política canónica. Empieza en modo `audit`, comprende cada
superficie y trata los scanners como hipótesis. No retires nada salvo que el usuario
haya indicado `--retire <exact-relative-target>` y pasen todos los gates de evidencia.

Argumentos del usuario:

```text
$ARGUMENTS
```

Preserva el worktree y devuelve evidencia real con matriz `PASS / FAIL / SKIP`.
