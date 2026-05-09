---
description: Generación de documentación técnica. Workflow universal compatible con cualquier LLM.
universal: true
---

# /docs - Generación de Documentación

> Workflow universal compatible con: Claude, GPT-4, Gemini, Codex, Llama, Mistral

## Documentación Requerida

$ARGUMENTS

---

## Proceso de Documentación

### Fase 1: Análisis

```markdown
## Análisis de Documentación

### Tipo de Documentación
- [ ] README del proyecto
- [ ] Documentación de API
- [ ] Guía de contribución
- [ ] Guía de instalación
- [ ] Arquitectura técnica
- [ ] Changelog
- [ ] Docstrings/JSDoc

### Audiencia
- [ ] Desarrolladores (internos)
- [ ] Desarrolladores (externos/API)
- [ ] Usuarios finales
- [ ] DevOps/SRE
- [ ] Stakeholders

### Estado Actual
| Documento | Existe | Actualizado | Completo |
|-----------|--------|-------------|----------|
| README | [Sí/No] | [Sí/No] | [%] |
| API Docs | [Sí/No] | [Sí/No] | [%] |
| CONTRIBUTING | [Sí/No] | [Sí/No] | [%] |
```

---

### Fase 2: Generación

#### Template: README.md

```markdown
# Nombre del Proyecto

> Descripción breve y clara del proyecto (1-2 oraciones)

[![Build Status](badge-url)](link)
[![License](badge-url)](link)
[![Version](badge-url)](link)

## Características

- ✅ Característica 1
- ✅ Característica 2
- ✅ Característica 3

## Inicio Rápido

### Requisitos

- Node.js 18+
- PostgreSQL 15+

### Instalación

\`\`\`bash
# Clonar repositorio
git clone https://github.com/user/project.git
cd project

# Instalar dependencias
npm install

# Configurar variables de entorno
cp .env.example .env

# Iniciar desarrollo
npm run dev
\`\`\`

### Uso Básico

\`\`\`javascript
import { Client } from 'project';

const client = new Client({ apiKey: 'your-key' });
const result = await client.doSomething();
\`\`\`

## Documentación

- [Guía Completa](docs/guide.md)
- [API Reference](docs/api.md)
- [Ejemplos](examples/)

## Contribuir

Ver [CONTRIBUTING.md](CONTRIBUTING.md) para guías de contribución.

## Licencia

[MIT](LICENSE)
```

---

#### Template: API Documentation

```markdown
# API Reference

## Base URL

\`\`\`
https://api.example.com/v1
\`\`\`

## Autenticación

Todas las requests requieren un token en el header:

\`\`\`
Authorization: Bearer <token>
\`\`\`

---

## Endpoints

### Users

#### GET /users

Lista todos los usuarios.

**Query Parameters:**

| Parámetro | Tipo | Requerido | Default | Descripción |
|-----------|------|-----------|---------|-------------|
| page | integer | No | 1 | Número de página |
| limit | integer | No | 20 | Items por página |
| status | string | No | active | Filtrar por estado |

**Response:**

\`\`\`json
{
  "data": [
    {
      "id": "123",
      "name": "John Doe",
      "email": "john@example.com",
      "created_at": "2024-01-15T10:30:00Z"
    }
  ],
  "meta": {
    "page": 1,
    "per_page": 20,
    "total": 150
  }
}
\`\`\`

**Errors:**

| Código | Mensaje | Descripción |
|--------|---------|-------------|
| 401 | Unauthorized | Token inválido o expirado |
| 403 | Forbidden | Sin permisos |

---

#### POST /users

Crea un nuevo usuario.

**Request Body:**

\`\`\`json
{
  "name": "John Doe",
  "email": "john@example.com",
  "password": "securePassword123"
}
\`\`\`

**Response (201):**

\`\`\`json
{
  "id": "123",
  "name": "John Doe",
  "email": "john@example.com",
  "created_at": "2024-01-15T10:30:00Z"
}
\`\`\`
```

---

#### Template: CONTRIBUTING.md

```markdown
# Guía de Contribución

¡Gracias por tu interés en contribuir!

## Cómo Contribuir

### Reportar Bugs

1. Verifica que el bug no esté reportado
2. Abre un issue con:
   - Descripción clara del problema
   - Pasos para reproducir
   - Comportamiento esperado vs actual
   - Ambiente (OS, versión, etc.)

### Proponer Features

1. Abre un issue de tipo "Feature Request"
2. Describe el caso de uso
3. Espera feedback antes de implementar

### Pull Requests

1. Fork el repositorio
2. Crea un branch: \`git checkout -b feature/mi-feature\`
3. Haz cambios siguiendo el style guide
4. Escribe/actualiza tests
5. Commit: \`git commit -m 'feat: agregar mi feature'\`
6. Push: \`git push origin feature/mi-feature\`
7. Abre un Pull Request

## Style Guide

### Commits

Usamos [Conventional Commits](https://conventionalcommits.org/):

\`\`\`
feat: nueva funcionalidad
fix: corrección de bug
docs: cambios en documentación
style: formato, sin cambios de lógica
refactor: refactorización de código
test: agregar o modificar tests
chore: tareas de mantenimiento
\`\`\`

### Código

- Usar ESLint/Prettier configurado
- Tests para nueva funcionalidad
- Documentar funciones públicas

## Desarrollo Local

\`\`\`bash
# Setup
npm install

# Tests
npm test

# Lint
npm run lint

# Build
npm run build
\`\`\`

## Código de Conducta

Este proyecto sigue el [Contributor Covenant](CODE_OF_CONDUCT.md).
```

---

#### Template: Architecture Decision Record (ADR)

```markdown
# ADR-001: [Título de la Decisión]

**Estado:** [Propuesta | Aceptada | Rechazada | Deprecada | Supersedida]
**Fecha:** YYYY-MM-DD
**Autores:** [nombres]
**Supersede:** [ADR anterior si aplica]

## Contexto

[Describir la situación, el problema, o la oportunidad que motiva esta decisión]

## Decisión

[Describir la decisión tomada y por qué]

## Opciones Consideradas

### Opción 1: [Nombre]
**Pros:**
- [pro 1]
- [pro 2]

**Contras:**
- [contra 1]
- [contra 2]

### Opción 2: [Nombre]
[Análisis similar]

## Consecuencias

### Positivas
- [consecuencia positiva 1]
- [consecuencia positiva 2]

### Negativas
- [consecuencia negativa 1]
- [consecuencia negativa 2]

### Riesgos
- [riesgo 1]
- [riesgo 2]

## Referencias

- [Link 1]
- [Link 2]
```

---

#### Template: Docstrings Python

```python
def calculate_total(
    items: list[Item],
    discount_code: str | None = None,
    include_tax: bool = True
) -> Decimal:
    """
    Calcula el total de una lista de items con descuento opcional.

    Esta función suma los precios de todos los items, aplica un descuento
    si se proporciona un código válido, y opcionalmente agrega impuestos.

    Args:
        items: Lista de items a calcular. Cada item debe tener
            atributos `price` y `quantity`.
        discount_code: Código de descuento opcional. Si es inválido,
            se ignora silenciosamente.
        include_tax: Si es True (default), agrega 21% de IVA al total.

    Returns:
        El total calculado como Decimal con 2 decimales de precisión.

    Raises:
        ValueError: Si la lista de items está vacía.
        InvalidItemError: Si algún item tiene precio negativo.

    Example:
        >>> items = [Item(price=10.00, quantity=2), Item(price=5.00, quantity=1)]
        >>> calculate_total(items, discount_code="SAVE10")
        Decimal('22.99')

    Note:
        Los descuentos se aplican antes de los impuestos.
    """
    if not items:
        raise ValueError("La lista de items no puede estar vacía")

    subtotal = sum(item.price * item.quantity for item in items)
    discount = get_discount_amount(discount_code, subtotal)
    total = subtotal - discount

    if include_tax:
        total *= Decimal("1.21")

    return total.quantize(Decimal("0.01"))
```

---

### Fase 3: Verificación

```markdown
## Checklist de Documentación

### Completitud
- [ ] Instalación documentada
- [ ] Uso básico explicado
- [ ] API completamente documentada
- [ ] Ejemplos incluidos
- [ ] Errores comunes cubiertos

### Claridad
- [ ] Lenguaje claro y conciso
- [ ] Sin jerga innecesaria
- [ ] Estructura lógica
- [ ] Navegación fácil

### Actualización
- [ ] Coincide con código actual
- [ ] Versiones especificadas
- [ ] Fecha de última actualización
- [ ] Links funcionan
```

---

## Tipos de Documentación

| Tipo | Audiencia | Contenido |
|------|-----------|-----------|
| **README** | Todos | Visión general, quickstart |
| **API Reference** | Desarrolladores | Endpoints, parámetros |
| **Guides** | Usuarios | Tutoriales paso a paso |
| **Architecture** | Equipo interno | Decisiones técnicas |
| **Changelog** | Usuarios | Historial de cambios |
| **Runbook** | Ops | Procedimientos operativos |

---

*Workflow de Documentación v1.0 - Compatible con cualquier LLM*
