---
name: upgrade-stripe
type: feature
description: "Actualiza versiones de Stripe API, SDKs y Stripe.js. Versiones API basadas en fecha (2026-01-28.clover), guía para SDKs dinámicos y tipados, checklist de migración."
---

# Upgrade Stripe

Guía completa para actualizar versiones de la API, SDKs y Stripe.js de Stripe.

## API Versioning

Stripe usa versionamiento basado en fecha + codename:

| Versión | Codename | Fecha |
|---------|----------|-------|
| `2026-01-28` | Clover | Enero 2026 |
| `2025-09-15` | Basil | Septiembre 2025 |
| `2025-04-30` | Acacia | Abril 2025 |

### Fijar versión de API

```python
import stripe

stripe.api_version = "2026-01-28.clover"
```

```javascript
const stripe = require("stripe")("sk_xxx", {
  apiVersion: "2026-01-28.clover",
});
```

## SDK Versioning

### Dynamic Languages (Python, Ruby, PHP)

Los SDKs dinámicos incluyen la versión de API en la versión del paquete:

```bash
# Python — la versión del SDK determina la API version
pip install stripe==12.0.0  # Usa API 2026-01-28
pip install stripe==11.0.0  # Usa API 2025-09-15
```

**Regla:** Major version bumps del SDK = nueva API version con breaking changes.

### Strongly-Typed Languages (TypeScript, Java, Go, .NET)

Los SDKs tipados son más estrictos:

```bash
# TypeScript
npm install stripe@17.0.0

# Java
implementation 'com.stripe:stripe-java:28.0.0'

# .NET
dotnet add package Stripe.net --version 48.0.0

# Go
go get github.com/stripe/stripe-go/v81
```

**Regla:** Los tipos reflejan la API version exacta. Actualizar requiere actualizar types.

## Stripe.js Versioning

Stripe.js usa versionamiento por codename para `loadStripe`:

```javascript
// Antes (API version automática)
import { loadStripe } from "@stripe/stripe-js";
const stripe = await loadStripe("pk_xxx");

// Con versión específica
const stripe = await loadStripe("pk_xxx", {
  apiVersion: "2026-01-28",
});
```

### Versiones de Stripe.js

| Codename | API Version |
|----------|-------------|
| Clover | 2026-01-28 |
| Basil | 2025-09-15 |
| Acacia | 2025-04-30 |

## Mobile SDK Versioning

Mobile SDKs usan semver estándar:

```swift
// iOS (Swift Package Manager)
.package(url: "https://github.com/stripe/stripe-ios", from: "24.0.0")
```

```kotlin
// Android (Gradle)
implementation("com.stripe:stripe-android:21.0.0")
```

```dart
// Flutter
dependencies:
  stripe_flutter: ^11.0.0
```

## Upgrade Checklist

### Pre-Upgrade
- [ ] Leer changelog de la nueva versión
- [ ] Identificar breaking changes que afectan tu integración
- [ ] Revisar deprecation warnings en logs actuales
- [ ] Hacer backup de configuración actual

### Upgrade
- [ ] Actualizar SDK a nueva versión
- [ ] Actualizar `apiVersion` en configuración
- [ ] Actualizar tipos/interfaces si aplica
- [ ] Correr tests unitarios
- [ ] Correr tests de integración contra Stripe Test Mode

### Post-Upgrade
- [ ] Verificar webhooks con nueva versión de API
- [ ] Confirmar que event schemas coinciden
- [ ] Monitorear errores en Dashboard de Stripe
- [ ] Actualizar Stripe.js si aplica

## Webhooks

Los webhooks envían eventos en la versión de API configurada en el Dashboard.
Al actualizar, verificar que los event payloads siguen siendo compatibles:

```python
# Verificar versión del evento
event = stripe.Webhook.construct_event(
    payload, sig_header, endpoint_secret
)
print(f"Event API version: {event.api_version}")
```

## Testing

```bash
# Stripe CLI para testing local
stripe listen --forward-to localhost:4242/webhook

# Trigger eventos de prueba
stripe trigger payment_intent.succeeded

# Verificar con API version específica
stripe trigger payment_intent.succeeded --api-version 2026-01-28
```

## Recursos

- [Stripe API Changelog](https://stripe.com/docs/changelog)
- [Stripe Versioning](https://stripe.com/docs/api/versioning)
- [Stripe Upgrade Guide](https://stripe.com/docs/upgrades)
