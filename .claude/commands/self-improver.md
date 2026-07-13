# /self-improver

Auto-mejora continua: detecta gaps en capacidades y genera nuevos skills automáticamente.

## Uso

```
/self-improver analyze    # Analizar gaps de capacidad
/self-improver generate   # Generar skill para un gap
/self-improver auto       # Ciclo completo de auto-mejora
```

## Descripción

Ejecuta el sistema de auto-mejora de Claude Code:
1. Analiza los gaps de capacidad vs los 815 skills existentes
2. Detecta gaps prioritarios (high/critical)
3. Genera nuevos skills automáticamente
4. Registra en el registry de self-improver

## Ejemplo

```
/self-improver auto
```

Output:
```
=== SELF-IMPROVER: CICLO DE AUTO-MEJORA ===

[1/3] Analizando gaps...
      Skills cargados: 815
      Gaps detectados: 3
[2/3] Filtrando gaps prioritarios...
      Gaps de alta prioridad: 2
[3/3] Generando skills...
      [OK] auto-context
      [OK] auto-skills

=== RESUMEN ===
Gaps analizados: 3
Skills generados: 2
```

## Skills generados

Los skills se guardan en `.agent/skills-custom/auto-*/` y son invocables inmediatamente.
