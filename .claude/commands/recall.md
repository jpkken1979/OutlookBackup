Proactive Recall — traer contexto relevante del Brain para la tarea actual.

## Cuando usarlo

- Al empezar una sesion ("en que estabamos?")
- Antes de tocar un archivo ("que sabemos de este modulo?")
- Cuando aparece un error ("esto ya paso antes?")
- Al planificar una feature ("hay trabajo previo?")

## Uso

```
/recall                                   # contexto general reciente
/recall <tema>                            # buscar tema especifico
/recall error: <mensaje>                  # buscar errores similares
/recall archivo: <path>                   # contexto de un archivo
/recall feature: <descripcion>            # trabajo previo en feature
```

## Flujo

1. Analizar el argumento (si existe) y el contexto actual:
   - `git diff` y `git log -5` para cambios recientes
   - Archivos abiertos/editados en la sesion

2. Ejecutar query al Brain segun el modo:

```python
import sys; sys.path.insert(0, '.agent')
from core.brain import Brain
from pathlib import Path

brain = Brain(Path('.agent/brain'), app_id='nexus-mother')

# Modo general: traer nodos recientes + criticos
if sin_argumento:
    recent = brain.list_nodes(node_type='session', status='active')[:5]
    critical = [n for n in brain.list_nodes(status='active') if n.importance == 'critical'][:10]

# Modo especifico: search + traverse del top result
elif argumento:
    results = brain.query(argumento, limit=5)
    if results:
        top = results[0]
        neighborhood = brain.get_neighborhood(top.slug, depth=2)
```

3. Presentar al usuario de forma estructurada:

```
## Contexto relevante

### Recientes
- [fecha] Sesion: <titulo>
- [fecha] Fix: <bug resuelto>

### Nodos criticos relacionados
- <titulo> [area]
- <titulo> [area]

### Conocimiento conectado (2 saltos desde top match)
→ <nodo a> → <nodo b>
→ <nodo c>

### Bugfixes previos similares
- <titulo> — root cause: <causa>

### Sugerencia
Basado en este contexto, <recomendacion>.
```

## Modo especial: error recurrente

Si el argumento empieza con `error:`, buscar nodos tipo `pattern` con tag `bugfix`:

```python
errors = [n for n in brain.query(f"bugfix {msg}", limit=10)
          if n.type == 'pattern' and 'bugfix' in n.tags]
```

Si encontras matches, presentar:
- Sintoma original
- Root cause
- Como se arreglo
- Prevencion

## Modo archivo

Si el argumento empieza con `archivo:`, extraer el nombre del archivo/modulo y buscar todo lo relacionado:

```python
results = brain.query(nombre_archivo, limit=10)
# + graph traversal desde el top
```

## Reglas

- Responder en espanol
- Maximo 15 items totales (no abrumar)
- Priorizar nodos con importance=critical o high
- Incluir fechas para que el usuario sepa que tan viejo es
- Al final, dar 1-2 oraciones de **sugerencia accionable**
- Si no hay resultados: decirlo honestamente, no inventar
