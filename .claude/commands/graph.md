Visualizar el Brain Network como grafo force-directed y obtener estadísticas de la red.

## Modos

| Comando | Alias | Descripcion |
|---|---|---|
| `/graph` | | Vista general del grafo completo (D3 force-directed) |
| `/graph <slug>` | | Enfocar el grafo en un nodo especifico |
| `/graph stats` | `/gs` | Estadisticas del grafo: nodos, edges, distribucion por tipo |
| `/graph neighbors <slug>` | `/gn <slug>` | Nodos relacionados directos (1 salto) |
| `/graph search <tag>` | `/gst <tag>` | Buscar nodos por tag |

## API de referencia (MCP tools)

```bash
# tools disponibles en antigravity-brain-graph:
brain_graph(center_slug?, depth=2)  -> {nodes, edges, tags, areas, totalNodes, totalEdges}
brain_graph_stats()                 -> {total_nodes, total_connections, typeCounts, topTags, ...}
brain_graph_neighbors(slug)         -> {neighbors: [{id, title, type, area, tags, importance}]}
brain_graph_search_tag(tag)         -> {nodes: [{id, title, type, area, tags}]}
```

## Modo: default (sin argumentos)

1. Invocar `brain_graph()` sin center_slug para obtener el grafo completo
2. Presentar:
   - Total nodos / edges
   - Distribucion por tipo (session, concept, adr, entity, decision, pattern)
   - Top 10 tags con frecuencia
   - Top 5 nodos mas conectados (por related_count)
   - Instruccion: "Abrir en Nexus pestana Brain Graph para visualizacion interactiva D3"

## Modo: stats

1. Invocar `brain_graph_stats()`
2. Presentar:
   - Total nodos y conexiones
   - Barra visual por tipo (color segun TYPE_COLORS)
   - Top 10 tags
   - Areas presentes
   - Paleta de colores del grafo

## Modo: neighbors

1. Invocar `brain_graph_neighbors("<SLUG>")`
2. Presentar nodos ordenados por importancia y access_count
3. Mostrar titulo, tipo, area, tags de cada vecino
4. Sugerir: "Usa /graph <slug> para ver el subgraph centrado"

## Modo: search

1. Invocar `brain_graph_search_tag("<TAG>")`
2. Presentar todos los nodos con ese tag
3. Sugerir click para enfocar

## Reglas

- Responder en espanol
- Si no se especifica modo, asumir `graph` con el argumento como center_slug
- Usar TYPE_COLORS para badges de color en la presentacion
- Para Nexus, indicar siempre la pestana "Brain Graph" en Knowledge Panel