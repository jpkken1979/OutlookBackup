---
name: openai-develop-web-game
description: "Desarrolla juegos web con loop iterativo de Playwright testing. Usa canvas + render_game_to_text + advanceTime hook para validación automatizada."
type: feature
---

# Web Game Development

Skill para desarrollar juegos web interactivos con un loop iterativo de testing automatizado.

## Workflow Principal

1. **Diseñar juego** — Definir mecánicas, controles, win/lose conditions.
2. **Implementar** — HTML5 Canvas + JavaScript, estructura modular.
3. **Agregar hooks de testing** — `render_game_to_text()` y `advanceTime()`.
4. **Test loop** — Ejecutar Playwright tests iterativamente.
5. **Iterar** — Corregir bugs basado en test results, repetir.
6. **Tracking** — Mantener `progress.md` con estado de cada feature.

## Arquitectura del Juego

### Patrón Canvas + Hooks

```javascript
// render_game_to_text() — Serializa estado del juego para testing
function render_game_to_text() {
  return JSON.stringify({
    player: { x: player.x, y: player.y, health: player.health },
    enemies: enemies.map(e => ({ x: e.x, y: e.y, alive: e.alive })),
    score: score,
    state: gameState // "playing", "won", "lost", "paused"
  });
}

// advanceTime(ms) — Avanza el game loop manualmente
function advanceTime(ms) {
  const steps = Math.floor(ms / FRAME_TIME);
  for (let i = 0; i < steps; i++) {
    gameLoop();
  }
}

// Exponer globalmente para Playwright
window.render_game_to_text = render_game_to_text;
window.advanceTime = advanceTime;
```

### Estructura de Archivos

```
game/
├── index.html           # Entry point
├── game.js              # Game logic principal
├── renderer.js          # Canvas rendering
├── input.js             # Input handling
├── entities.js          # Game entities
├── progress.md          # Tracking de features
├── action_payloads.json # Test action definitions
└── tests/
    └── web_game_playwright_client.js
```

## Playwright Test Loop

```javascript
// web_game_playwright_client.js
const { chromium } = require('playwright');

async function testGame() {
  const browser = await chromium.launch();
  const page = await browser.newPage();
  await page.goto('http://localhost:3000');

  // Simular input
  await page.keyboard.press('ArrowRight');
  await page.evaluate(() => window.advanceTime(1000));

  // Leer estado
  const state = await page.evaluate(() => window.render_game_to_text());
  const parsed = JSON.parse(state);

  console.assert(parsed.player.x > 0, 'Player should move right');
  console.assert(parsed.state === 'playing', 'Game should be playing');

  await browser.close();
}
```

## Action Payloads

```json
{
  "actions": [
    { "type": "keypress", "key": "ArrowRight", "duration": 500 },
    { "type": "keypress", "key": "Space", "duration": 0 },
    { "type": "click", "x": 400, "y": 300 },
    { "type": "wait", "ms": 2000 }
  ]
}
```

## Progress Tracking

Mantener `progress.md` actualizado con cada iteración:

```markdown
# Game Progress

## Features
- [x] Player movement (WASD + arrows)
- [x] Collision detection
- [ ] Enemy AI pathfinding
- [x] Score system
- [ ] Sound effects

## Bugs
- [ ] Player clips through walls at high speed
- [x] Score resets on pause

## Test Coverage
- Movement: 5/5 passing
- Combat: 3/5 passing
- UI: 2/3 passing
```

## Recursos

- [Playwright Docs](https://playwright.dev/)
- [HTML5 Canvas Tutorial](https://developer.mozilla.org/en-US/docs/Web/API/Canvas_API/Tutorial)
