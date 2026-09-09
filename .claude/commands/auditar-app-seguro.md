Usa `$safe-app-auditor` para comprender y auditar la aplicación indicada en:

`$ARGUMENTS`

Empieza en modo `audit`: protege el worktree, lee instrucciones y construye el mapa de
arquitectura, ownership, entry points, consumidores runtime, configuración, datos y
gates. Después presenta hallazgos con evidencia y aplica únicamente fixes pequeños y
reproducibles si el usuario pidió remediación. No borres, muevas ni reescribas código
por una señal estática; registra candidatos dudosos como `INVESTIGATE` o `QUARANTINE`.
Entra en modo `retire` sólo con autorización separada que nombre los targets exactos.
