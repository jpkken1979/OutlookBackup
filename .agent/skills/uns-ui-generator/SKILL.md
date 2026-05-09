---
name: uns-ui-generator
type: feature
description: "Generador de interfaces UI para sistemas UNS. Triggers: UNS UI, generar interfaz, dashboard UNS, 画面生成, UI generator, frontend UNS."
source: uns
---
# Skill: UNS-UI-GENERATOR

## Descripción
Esta habilidad genera sistemas de diseño completos basados en la identidad visual de **ユニバーサル企画株式会社 (UNS)**. Facilita la creación instantánea de archivos de estilo para apps web modernas.

## Capacidades
- **Token Generation**: Genera variables CSS (tokens) para colores, tipografía y espaciado.
- **Theme Injection**: Crea configuraciones de Tailwind CSS o temas de Shadcn/ui.
- **Responsive Layouts**: Plantillas pre-construidas para dashboards empresariales.

## Atributos de Marca
- **Azul Primario**: `#0052CC` (Profundidad: `hsl(218, 100%, 40%)`)
- **Rojo Acento**: `#DC143C` (Profundidad: `hsl(348, 83%, 47%)`)
- **Fuentes**: `Inter`, `Noto Sans JP`.

## Uso
Corre el script generador para obtener un `theme.css`:
`python .agent/skills/uns-ui-generator/scripts/generate_theme.py`
