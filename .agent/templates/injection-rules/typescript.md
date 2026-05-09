# Regla: Estándares TypeScript / React

## Requisitos TypeScript

- **TypeScript strict** habilitado — sin `any`, tipar correctamente o usar `unknown`
- Componentes funcionales con hooks (`useCallback`, `useRef`, `useMemo`)
- No inline styles — usar clases de utilidad (Tailwind u otro sistema)

## React

- Extraer variantes de animación (Framer Motion, etc.) **fuera** de los componentes
- Preferir composición sobre herencia
- Estado local con `useState`, estado derivado con `useMemo`

## Tauri / Electron

- `contextIsolation: true`, `nodeIntegration: false` siempre
- Llamadas IPC solo a través del bridge de preload
- Inputs IPC validados antes de llegar al proceso principal

## Tests

- Framework: Vitest o Jest
- Componentes: Testing Library
- Cobertura mínima: 80% en lógica de negocio
