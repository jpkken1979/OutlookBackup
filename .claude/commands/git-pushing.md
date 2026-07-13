Stage, commit y push de cambios git con mensajes convencionales + auto-ingest al Brain.

## Flujo

1. Ejecuta `git status` para ver el estado actual
2. Ejecuta `git diff --stat` para ver los cambios
3. Si no hay cambios, informa y termina
4. Analiza los cambios y genera un mensaje de commit convencional en español
5. Stage los archivos relevantes (nunca `git add -A` ciegamente)
6. **Incluir siempre `.agent/brain/` si hay nodos nuevos/modificados**
7. Commit con formato: `tipo(scope): descripción en español`
8. Push a la rama actual
9. **Auto-ingest al Brain** (ver abajo)

## Auto-ingest al Brain

Despues de cada push exitoso, ingestar los cambios en el Brain Network:

```python
import sys; sys.path.insert(0, '.agent')
from core.brain import Brain
from pathlib import Path

brain = Brain(Path('.agent/brain'), app_id='nexus-mother')
brain.ingest(
    title="Commit: [mensaje del commit]",
    context="[descripcion de los cambios realizados]",
    area="[area segun los archivos tocados]",
    tags=["commit", "[scope]", "[archivos principales]"],
    node_type="session",
    importance="normal",
)
```

Si los cambios incluyen un **fix de bug**, usar importance="high" y node_type="pattern".
Si incluyen una **decision de arquitectura**, usar node_type="adr".

Agregar los nodos del brain al push:
```bash
git add .agent/brain/ && git commit -m "chore(brain): auto-ingest commit" && git push
```

## Reglas

- Mensajes de commit en **español**, scope en inglés
- Máximo 72 caracteres en la primera línea
- No commitear `.env`, secretos, o archivos grandes binarios
- Si hay cambios no relacionados, separar en commits distintos
- Agregar `Co-Authored-By: Claude <noreply@anthropic.com>` al final
- Si el push falla por divergencia, proponer `git pull --rebase`
- **Nunca** force push a main/master sin confirmación
- **Siempre** incluir `.agent/brain/` en el commit si hay nodos nuevos
