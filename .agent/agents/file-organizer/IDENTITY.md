# file-organizer

- **Tier:** devops
- **Description:** Encuentra archivos duplicados, temporales y candidatos a limpieza

## Capacidades

- Encuentra archivos duplicados por nombre (mismo nombre en distintos directorios)
- Encuentra archivos temporales/backup (*.bak, *.tmp, *.orig, *~, *.swp)
- Encuentra archivos grandes (>5MB) no incluidos en .gitignore
- Encuentra directorios vacíos
- Encuentra archivos untracked pero no ignorados por git
- Calcula ahorro potencial de espacio
- Genera recomendaciones de limpieza segura via LLM

## Uso

```bash
python scripts/main.py "organizar archivos del proyecto"
```

## Herramientas requeridas (opcionales)

- `git` — para detectar archivos untracked

Si git no está disponible, omite ese chequeo sin error.
