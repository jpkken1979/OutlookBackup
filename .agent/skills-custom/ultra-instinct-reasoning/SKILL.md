---
name: "ultra-instinct-reasoning"
description: "Activa el estado cognitivo meta-analítico (Tree of Thoughts, Self-Reflection y Auto-Correction) para tareas críticas, similar a los modelos o1 o DeepMind agents."
category: "Intelligence"
version: "1.0.0"
---

# 🌌 Ultra Instinct Reasoning (Migatte no Gokui)

> **"No pienses. Deja que el sistema procese el entorno autónomamente."**
> Este skill fuerza al agente a abandonar la generación de respuestas lineales ("Zero-Shot") y adoptar un protocolo de procesamiento cognitivo profundo ("Systems-2 Thinking").

## 🛑 PROTOCOLO DE ACTIVACIÓN DE PODER MAXIMO

Cuando un usuario pide calidad "Super Saiyan", "Código Perfecto" o la tarea es extremadamente compleja, el agente DEBE suspender la acción directa y seguir este dogma:

### FASE 1: Deconstrucción Sub-Atómica (El Ki)
En lugar de codificar la solución, el agente primero debe imprimir un bloque de `[🧠 INTERNAL THOUGHT PROCESS]` donde:
1. Rompe el problema en 3 hipótesis completamente distintas de resolución.
2. Analiza los "Edge Cases" (casos donde todo explota o se rompe).
3. Evalúa la complejidad temporal y espacial (O(N), uso de memoria, llamadas a red).

### FASE 2: Shadow Execution (Pelea de Sombra)
Antes de modificar archivos, el agente debe imaginar la ejecución.
- ¿Qué pasa si la base de datos está caída?
- ¿Qué pasa si el JSON de entrada viene truncado o con caracteres raros?
- ¿Existen violaciones de seguridad? (SQL Injection, XSS, Path Traversal).

### FASE 3: Auto-Corrección Recursiva (La Evolución)
1. **Verificación Estricta:** NUNCA asumir que el primer intento funciona. 
2. Si el agente recibe un error en terminal o de un Linter, DEBE corregirse a sí mismo instantáneamente al menos 5 veces sin molestar al usuario.
3. El agente usa paralelismo. Si necesita contexto de 5 archivos, debe leerlos todos a la vez.

### FASE 4: Ejecución Quirúrgica
Una vez que el "árbol de pensamientos" converge en la solución ideal:
1. Eliminar código muerto (`technical debt`).
2. Aislar en funciones/módulos puros (SOLID principles).
3. Usar asincronismo y concurrencia donde sea posible para velocidad absoluta.

## 🔑 TRIGGER DE ACTIVACIÓN
Si el usuario menciona comandos como `/goku`, `/ultra-instinct`, `perfect-code`, o exige la máxima calidad del ecosistema, el Agente cargará esta directiva encima de cualquier otro prompt.
