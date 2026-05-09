Interactuar con el Brain Network — la red de inteligencia distribuida del ecosistema.

## Modos

| Comando | Alias | Descripcion |
|---|---|---|
| `/brain query <pregunta>` | `/bq <pregunta>` | Buscar conocimiento en toda la red |
| `/brain ingest` | `/bi` | Ingestar la sesion actual como nodo de conocimiento |
| `/brain lint` | `/bl` | Auditoria de salud del brain |
| `/brain stats` | `/bs` | Estadisticas de la red |
| `/brain traverse <slug>` | `/bt <slug>` | Navegar el grafo desde un nodo |
| `/brain promote` | | Promover conceptos emergentes cross-app |
| `/brain consolidate` | | Limpiar nodos viejos y huerfanos |
| `/brain conflicts` | | Detectar info contradictoria entre apps |
| `/brain register <app_id> <brain_dir>` | | Registrar un nuevo app brain |
| `/braind` | | Ejecutar /brain digest (resumen inteligente del estado actual) |

## API de referencia

```python
import sys; sys.path.insert(0, '.agent')
from core.brain import Brain
from pathlib import Path

brain = Brain(Path('.agent/brain'))
```

### Metodos disponibles

| Metodo | Parametros | Retorna | Uso |
|---|---|---|---|
| `brain.query(q, limit=5)` | query str, limit int | list[dict] | Busqueda full-text |
| `brain.stats()` | — | dict | Conteo nodos, tags, conexiones |
| `brain.lint()` | — | dict | Score salud, issues por severidad |
| `brain.ingest(title, context, area, tags, node_type, importance)` | todos requeridos menos importance | dict | Crear nodo |
| `brain.get_node(slug)` | slug str | dict/None | Obtener nodo completo |
| `brain.list_nodes(node_type, area, limit)` | filtros opcionales | list[dict] | Listar nodos |
| `brain.traverse(slug, depth=2)` | slug, depth | dict | Vecinos del nodo |
| `brain.get_neighborhood(slug, depth=3)` | slug, depth | dict | Alias de traverse |
| `brain.update_node(slug, **fields)` | slug + fields | dict | Actualizar nodo existente |
| `brain.rebuild_index()` | — | — | Regenerar index.md |

## Modo: query (default)

1. Ejecutar busqueda con el argumento como query:
```python
results = brain.query("<PREGUNTA>", limit=5)
```

2. Presentar resultados con formato enriquecido:
   - **Nodo**: titulo + tipo (badge de color)
   - **Brain**: nombre del directorio de origen
   - **Resumen**: primeras 200 chars del contexto
   - **Tags**: todos los tags del nodo
   - **Relevancia**: score 0-1 (mostrar barra visual)
   - **Frescura**: fecha de actualizacion (mostrar relative time)
   - **Accion**: `brain.get_node(slug)` si quiere ver completo

## Modo: ingest

1. Revisar `git status --short` y `git diff --stat` para entender cambios
2. Detectar archivos modificados, nuevos, eliminados
3. Generar titulo descriptivo (formato: "Sesion 2026-MM-DD — tema principal")
4. Determinar area: dev, ops, ux, business, security, arquitectura
5. Extraer tags de los archivos tocados y decisiones
6. Importancia: high si hay fixes criticos, normal si es sesion normal
7. Crear nodo y reportar:
   - Slug creado
   - Cross-refs detectadas automaticamente
   - Link a donde encontrarlo

## Modo: lint

1. Ejecutar `brain.lint()`
2. Presentar score global con barra de color
3. Si score < 80, listar issues criticos con accion sugerida
4. Si score >= 80, mostrar concepts emergentes

## Modo: stats

1. Ejecutar `brain.stats()`
2. Presentar:
   - Total nodos por tipo (sessions, concepts, patterns, decisions)
   - Top 10 tags por frecuencia
   - Nodos sin cross-refs (huerfanos)
   - Ultima actividad (nodo mas reciente)

## Modo: traverse

1. Ejecutar `brain.traverse("<SLUG>", depth=2)`
2. Mostrar nodo central con titulo, tipo, contexto completo
3. Vecinos nivel 1: titulo + tag mas relevante
4. Vecinos nivel 2: condensado (solo titulo)

## Modo: digest (/braind)

Resumen inteligente del estado actual del brain. Ejecuta stats + lint + ultimos
3 nodos session, y presenta un resumen ejecutivos de una sola pasada.

## Reglas

- Responder en espanol
- Si no se especifica modo, asumir `query` con el argumento como pregunta
- Si no hay argumento, mostrar stats de la red
- Para `/braind` y `/bi` verificar que git status tenga cambios antes de ingestar
- Nunca mostrar mas de 10 resultados en query (usar limit)