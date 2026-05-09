# Tareas Pendientes — Se auto-inyecta en CADA sesión

> Leer esto SIEMPRE al inicio de sesión. Son tareas NO completadas que no deben olvidarse.

## 🔴 CRÍTICO

### Cuenta Codex laboral
- Email: `viet.cuong@uns-kikaku.com` (cuenta laboral UNS)
- El snapshot **NO existe** en `C:\Users\Kenji\.codex\accounts\`
- Para resolverlo: hacer login con esa cuenta en la UI de Codex → el snapshot se genera automático
- Luego: verificar que `index.json` en `~/.codex/accounts/` incluye esa cuenta
- **Status**: PENDIENTE — requiere acción manual del usuario (login real)

## 🟡 RECORDATORIOS PERMANENTES

### `.env` en este repo ES VERSIONADO INTENCIONALMENTE
- El `.env` en la raíz de `OpenAntigravity26.3.30` **SÍ está en git** — es una decisión consciente
- El repo es **privado** — ver `.gitignore` líneas 151-153 y `.claude/rules/security.md`
- **NUNCA proponer borrar, mover o ignorar el `.env` de este repo**
- Esta excepción NO aplica a repos públicos ni forks

### Tokens activos en `.env`
- `MINIMAX_API_KEY` — presente y activo
- `ZAI_API_KEY` — presente y activo  
- `GH_TOKEN` — presente y activo

## ✅ COMPLETADO RECIENTEMENTE (referencia)

- Fix: `memory.rs` — inyección de `X-API-Key` en todos los calls mem0 → commit `ddc1f91c`
- Fix: `MinimaxToggleCard.tsx` + `ZaiToggleCard.tsx` — auto-refresh 15s + focus event
- Build Nexus v2.5.3 exitoso → instaladores en `nexus-app/Compilacion/`
