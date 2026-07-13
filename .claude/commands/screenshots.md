Generar screenshots de marketing de la app usando Playwright.

Captura screenshots en resolución retina (2x HiDPI, 2880x1800px) para Product Hunt, redes sociales, landing pages o documentación.

## Flujo

1. Determinar la URL de la app (preguntar si no se proporciona)
2. Preguntar cuántos screenshots, propósito, y si requiere login
3. Analizar el codebase para descubrir rutas y features
4. Planificar screenshots con el usuario
5. Generar script Playwright y ejecutar
6. Verificar y reportar resultados

## Uso

```bash
# Ejecutar el script del skill directamente
bash .agent/skills/screenshots/scripts/main.py
```

O indicar la URL: `/screenshots http://localhost:5173`

## Opciones de captura

- **Viewport**: 1440x900 con `deviceScaleFactor: 2`
- **Full page**: Para contenido scrollable
- **Elemento**: Focus en un componente específico
- **Dark mode**: Con `colorScheme: 'dark'`
- **Auth**: Login automático con credenciales

## Naming

Archivos en `screenshots/` con prefijo numérico: `01-dashboard.png`, `02-settings.png`
