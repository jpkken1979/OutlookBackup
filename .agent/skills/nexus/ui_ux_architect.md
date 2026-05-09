# Skill: Nexus Figma & Stitch Architect
> Inyeccion automatica de diseño desde Figma a React con Stitches.

## Descripcion
Convierte metadatos de diseño JSON provenientes de Figma en componentes React estilizados usando Stitches o Styled-components.

## Uso
1. Lee el JSON de Figma (via MCP o archivo).
2. Mapea `fills`, `strokes` y `effects` a CSS Properties.
3. Genera el componente React `styled(component, { ... })`.

## Reglas de Experto en CSS
- **Uso de Flex/Grid**: Nunca uses `position: absolute` a menos que sea un overlay.
- **Backdrop-filter**: Para lograr el Glassmorphism de Antigravity.
- **Animaciones**: Usa `framer-motion` o CSS Keyframes para efectos de entrada suaves.

## Como llamar
Si el usuario dice \"mejorá el diseño\", el agente debe llamar a esta Skill y seguir el `DESIGN_SYSTEM.md`.
