# Regla: Descubrimiento de Skills via skills.sh

Aplica a todas las sesiones de Claude Code en este repositorio.

## Principio

Cuando necesites una capacidad que NO existe en el ecosistema local, buscar primero en skills.sh antes de implementar desde cero.

## Cuándo buscar

- El usuario pide algo que no sabés cómo hacer y no hay skill local
- Necesitás integración con una herramienta/servicio externo
- El usuario pregunta "cómo hago X" y X podría tener un skill existente
- Vas a crear un skill nuevo — verificar que no exista uno primero

## Cómo buscar

```bash
npx skills find "descripcion de lo que necesitas"
```

Esto busca en el registry de skills.sh y muestra resultados con install count.

## Cómo instalar

```bash
npx skills add <owner/repo> --skill <skill-name> --agent claude-code --yes
```

Para instalar globalmente (disponible en todos los proyectos):
```bash
npx skills add <owner/repo> --skill <skill-name> --agent claude-code --yes --global
```

## Otros comandos útiles

```bash
npx skills list              # Listar skills instalados
npx skills find "query"      # Buscar skills
npx skills check             # Verificar actualizaciones
npx skills update            # Actualizar skills
npx skills remove <skill>    # Remover un skill
```

## Criterios de selección

Al elegir un skill de skills.sh, preferir:
1. Mayor número de instalaciones (popularidad = confianza)
2. Fuente verificada (vercel-labs, anthropics, repos oficiales)
3. Auditoría de seguridad pasada (Socket, Snyk)
4. Compatibilidad con claude-code como agente

## Importante

- SIEMPRE revisar el contenido del skill antes de usarlo (pueden tener permisos amplios)
- Preferir skills de fuentes conocidas sobre skills de repositorios desconocidos
- Si un skill local del ecosistema Antigravity cubre el caso, usarlo primero
