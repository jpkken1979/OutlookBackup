---
description: Crear nueva aplicación o funcionalidad desde cero. Workflow universal compatible con cualquier LLM.
universal: true
---

# /create - Crear Aplicación

> Workflow universal compatible con: Claude, GPT-4, Gemini, Codex, Llama, Mistral

## Solicitud

$ARGUMENTS

---

## Proceso de Creación

### Fase 1: Descubrimiento

Antes de crear, necesito entender claramente qué construir.

#### Preguntas de Clarificación (si la solicitud es ambigua)

```markdown
Para crear tu aplicación, necesito entender:

1. **Tipo de aplicación:**
   - [ ] Web app
   - [ ] API/Backend
   - [ ] CLI tool
   - [ ] Mobile app
   - [ ] Desktop app
   - [ ] Otro: ___

2. **Usuarios objetivo:**
   - ¿Quién usará esto?
   - ¿Cuántos usuarios esperados?

3. **Funcionalidades core:**
   - ¿Cuáles son las 3-5 features principales?

4. **Stack tecnológico (si tienes preferencia):**
   - Frontend: ___
   - Backend: ___
   - Database: ___
   - Hosting: ___

5. **Restricciones:**
   - ¿Hay limitaciones técnicas?
   - ¿Presupuesto de hosting?
   - ¿Timeline?
```

---

### Fase 2: Planificación

Una vez entendida la solicitud, crear el plan:

```markdown
## Plan de Desarrollo

### Resumen del Proyecto
- **Nombre:** [nombre descriptivo]
- **Tipo:** [web/api/cli/mobile]
- **Descripción:** [1-2 oraciones]

### Stack Tecnológico
| Componente | Tecnología | Justificación |
|------------|------------|---------------|
| Frontend | [tech] | [por qué] |
| Backend | [tech] | [por qué] |
| Database | [tech] | [por qué] |
| Hosting | [tech] | [por qué] |

### Arquitectura
\`\`\`
[Diagrama ASCII de componentes]
\`\`\`

### Estructura de Archivos
\`\`\`
project/
├── src/
│   ├── components/
│   ├── pages/
│   └── utils/
├── api/
├── tests/
├── package.json
└── README.md
\`\`\`

### Fases de Implementación

#### Fase 1: Fundación
- [ ] Setup del proyecto
- [ ] Configuración de entorno
- [ ] Estructura base

#### Fase 2: Core Features
- [ ] [Feature 1]
- [ ] [Feature 2]
- [ ] [Feature 3]

#### Fase 3: Polish
- [ ] Testing
- [ ] Documentación
- [ ] Deploy

### Estimación
- **Complejidad:** [Baja/Media/Alta]
- **Archivos a crear:** [número aproximado]
```

---

### Fase 3: Confirmación

```markdown
## Confirmación

He preparado el plan para crear: **[nombre]**

**Resumen:**
- [cantidad] archivos a crear
- Stack: [tecnologías principales]
- Features: [lista breve]

**¿Procedo con la implementación?**
- Responde "sí" o "adelante" para comenzar
- Responde "modificar [aspecto]" para ajustar el plan
- Responde "cancelar" para detener
```

---

### Fase 4: Implementación

Una vez aprobado, implementar siguiendo el plan:

```markdown
## Progreso de Implementación

### Archivos Creados
| Archivo | Estado | Descripción |
|---------|--------|-------------|
| `src/index.js` | ✅ | Punto de entrada |
| `src/App.jsx` | ✅ | Componente principal |
| ... | ... | ... |

### Features Implementadas
- [x] Feature 1: [descripción breve]
- [x] Feature 2: [descripción breve]
- [ ] Feature 3: [en progreso]

### Próximos Pasos
1. [Paso inmediato]
2. [Paso siguiente]
```

---

### Fase 5: Entrega

```markdown
## Proyecto Completado

### Resumen
- **Nombre:** [nombre]
- **Archivos creados:** [cantidad]
- **Features implementadas:** [lista]

### Cómo Ejecutar
\`\`\`bash
# Instalación
npm install  # o pip install -r requirements.txt

# Desarrollo
npm run dev  # o python main.py

# Producción
npm run build && npm start
\`\`\`

### Estructura Final
\`\`\`
[Árbol de archivos creados]
\`\`\`

### Documentación
- README.md incluido con instrucciones
- Comentarios en código para partes complejas

### Próximas Mejoras Sugeridas
1. [Mejora potencial 1]
2. [Mejora potencial 2]
3. [Mejora potencial 3]
```

---

## Ejemplos de Uso

```
/create blog personal con markdown
/create API REST para gestión de inventario
/create dashboard de analytics
/create sistema de reservas para restaurante
/create e-commerce básico con carrito
/create aplicación de notas con sincronización
```

---

## Principios de Creación

1. **Empezar simple** - MVP primero, features después
2. **Código limpio** - Legible, mantenible, documentado
3. **Testing incluido** - Al menos tests para features críticas
4. **Seguridad por defecto** - No hardcodear secrets, validar inputs
5. **Documentación** - README con instrucciones claras

---

## Checklist Pre-Entrega

- [ ] ¿El código corre sin errores?
- [ ] ¿Están las features principales implementadas?
- [ ] ¿Hay README con instrucciones?
- [ ] ¿Se siguen las convenciones del lenguaje?
- [ ] ¿No hay secrets hardcodeados?
- [ ] ¿Hay manejo básico de errores?

---

*Workflow de Creación Universal v2.0 - Compatible con cualquier LLM*
