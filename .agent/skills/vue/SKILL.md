---
name: vue
type: feature
description: "Desarrollo con Vue.js 3 - framework progresivo para construir interfaces de usuario. Composition API, Script Setup, reactivity system, Vue Router, Pinia state management, Vite integration, TypeScript support. Triggers: Vue.js, Vue 3, Composition API, Pinia, Vue Router, Vite, frontend framework."
---

# Vue.js

## Metadata
- **Name**: Vue.js
- **Category**: Frontend
- **Version**: 1.0.0
- **Author**: Antigravity Team

## Description
Skill para desarrollo con Vue.js 3 - framework progresivo para construir interfaces de usuario.

## Capabilities
- Composition API
- Script Setup
- Reactivity system
- Vue Router
- Pinia state management
- Vite integration
- TypeScript support

## Key Features
- **Composition API**: Lógica reutilizable con composables
- **Script Setup**: Sintaxis simplificada para SFCs
- **Reactivity**: Sistema reactivo granular
- **Ecosystem**: Router, Pinia, DevTools

## Usage
```bash
# Generar componente Vue
python scripts/vue.py component --name UserCard --composition

# Generar composable
python scripts/vue.py composable --name useAuth

# Generar store Pinia
python scripts/vue.py store --name user

# Setup proyecto
python scripts/vue.py setup --typescript --router --pinia

# Listar patterns
python scripts/vue.py patterns
```

## Inputs
- `component_name`: Nombre del componente
- `composition`: Usar Composition API (default: true)
- `typescript`: Usar TypeScript
- `store_name`: Nombre del store Pinia

## Outputs
- Single File Components (.vue)
- Composables (use*.ts)
- Pinia stores
- Router configuration

## Dependencies
- vue
- vue-router
- pinia
- vite
- @vitejs/plugin-vue

## Related Skills
- `vite-architect`
- `typescript-patterns`
- `frontend-patterns`
