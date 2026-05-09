# Regla: Estándares TypeScript / React

Aplica a todos los archivos `.ts` y `.tsx` en `nexus-app/`.

## Requisitos TypeScript

- **TypeScript strict** habilitado (`noUnusedLocals`, `noUnusedParameters`, `erasableSyntaxOnly`)
- **tsconfigs separados** por proceso: `tsconfig.app.json` (renderer), `tsconfig.electron.json` (main)
- No usar `any` — tipar correctamente o usar `unknown`

## Requisitos React

- **Componentes funcionales** con hooks (`useCallback`, `useRef`, `useMemo`)
- Extraer variantes de Framer Motion **fuera** de los componentes para evitar re-creación
- **Tailwind CSS v4** utility-first (configurado via `@theme` en `index.css`, sin `tailwind.config.js`)

## Requisitos Electron

- `contextIsolation: true`, `nodeIntegration: false`, `frame: false` siempre
- Llamadas IPC solo a través del bridge de preload — nunca exponer Node APIs directamente
- Inputs IPC validados en el preload antes de llegar al proceso principal

## Build de Nexus

- Después de compilar con `npm run tauri:build`, **siempre** copiar los instaladores generados a `nexus-app/Compilacion/`:
  - `src-tauri/target/release/bundle/nsis/*.exe` → `nexus-app/Compilacion/`
  - `src-tauri/target/release/bundle/msi/*.msi` → `nexus-app/Compilacion/`

## Path-scoping

Esta regla aplica **solo** a archivos dentro de `nexus-app/`.
