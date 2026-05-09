---
name: documentation-writing
description: Skill para escribir documentación técnica de alta calidad, incluyendo READMEs, guías de API, tutoriales y documentación de arquitectura
type: feature
---

# documentation-writing

## Metadata
- **Name**: Documentation Writing
- **Category**: Documentation
- **Version**: 1.0.0
- **Author**: Antigravity Team

## Description
Skill para escribir documentación técnica de alta calidad. Genera READMEs, guías de API, tutoriales, y documentación de arquitectura siguiendo mejores prácticas.

## Capabilities
- Generación de README.md estructurados
- Documentación de APIs (OpenAPI/Swagger)
- Guías de instalación y configuración
- Tutoriales paso a paso
- Documentación de arquitectura (ADRs)
- Changelogs y release notes

## Inputs
- `project_path`: Ruta al proyecto a documentar
- `doc_type`: Tipo de documentación (readme, api, tutorial, architecture, changelog)
- `language`: Idioma (es, en, ja)
- `format`: Formato de salida (markdown, html, pdf)

## Outputs
- Archivos de documentación generados
- Estructura de directorios docs/
- Templates reutilizables

## Usage
```bash
python scripts/documentation_writer.py <project_path> --type readme
python scripts/documentation_writer.py <project_path> --type api --format openapi
python scripts/documentation_writer.py <project_path> --type changelog
```

## Dependencies
- markdown
- jinja2
- pyyaml

## Related Skills
- `documentation-generator`
- `api-documenter`
- `readme-generator`
