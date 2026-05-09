# Type Validation - Quick Start Guide

## 🎯 Regla de Oro: ONE FILE AT A TIME

**NUNCA intentes:**
```
"Arregla todos los type errors"
"Haz que sea 100% type-safe"
```

**SIEMPRE haz:**
```
"Ejecuta mypy en backend/services/payroll_service.py"
"Arregla errores solo de ese archivo"
"Verifica que mypy dice: Success"
```

---

## 5 Pasos Secuenciales

### 1️⃣ Identifica UN Archivo
```
"Ejecuta mypy en: backend/services/user_service.py"
```

### 2️⃣ Ejecuta Mypy
```bash
python .agent/skills/type-validation/validate_types.py backend/services/user_service.py
```

**Output esperado:**
```
TYPE VALIDATION REPORT: backend/services/user_service.py
================================================

❌ Type errors found: 3

ERRORES ENCONTRADOS:
1. Line 15: error: Incompatible types in assignment
2. Line 42: error: "NoneType" has no attribute "split"
3. Line 78: error: Argument 1 to "process" has incompatible type
```

### 3️⃣ Crea TODO List
```
[ ] Error #1 (línea 15): Cambiar tipo var_name
[ ] Error #2 (línea 42): Validar None
[ ] Error #3 (línea 78): Convertir tipos
[ ] Ejecutar mypy nuevamente
[ ] Verificar Success
```

### 4️⃣ Corrige UN Error a la Vez

**Error #1:**
```python
# ANTES
user_id: int = get_user_id()  # Pero retorna str!

# DESPUÉS
user_id: str = get_user_id()
```

**Ejecuta mypy:**
```bash
python .agent/skills/type-validation/validate_types.py backend/services/user_service.py
```

**Resultado:**
```
Type errors found: 2  (was 3)  ✅
```

**Error #2:**
```python
# ANTES
parts = data.split(":")  # ¿Qué si data es None?

# DESPUÉS
if data is not None:
    parts = data.split(":")
else:
    parts = []
```

**Ejecuta mypy nuevamente:**
```
Type errors found: 1  (was 2)  ✅
```

**Error #3:**
```python
# Convertir o pasar tipo correcto
result = process([str(x) for x in my_list])
```

**Ejecuta mypy:**
```
Success: no issues found  ✅✅✅
```

### 5️⃣ Commit y Siguiente Archivo
```bash
git add backend/services/user_service.py
git commit -m "fix(types): resolve type errors in user_service

- Line 15: user_id type annotation
- Line 42: null safety check
- Line 78: list type conversion"

# AHORA: pasar al siguiente archivo
```

---

## Errores Comunes & Soluciones Rápidas

### ❌ "Incompatible types in assignment"
```python
# MALO
x: int = "hello"

# BUENO
x: str = "hello"
# o
x: int = 42
```

### ❌ "X has no attribute Y"
```python
# MALO (data puede ser None)
data.split(":")

# BUENO
if data:
    data.split(":")
```

### ❌ "Argument 1 has incompatible type"
```python
# MALO (pasas str, espera int)
my_function("42")

# BUENO
my_function(int("42"))
```

### ❌ "Optional" no manejado
```python
# MALO
def process(items: List[str] | None):
    print(items[0])  # ¿Qué si None?

# BUENO
def process(items: List[str] | None):
    if items:
        print(items[0])
```

---

## Herramientas

### Validar UN Archivo
```bash
python .agent/skills/type-validation/validate_types.py <archivo.py>
```

### Modo Strict (más exigente)
```bash
python .agent/skills/type-validation/validate_types.py <archivo.py> --strict
```

### Directamente con mypy
```bash
mypy <archivo.py> --show-error-codes --pretty
```

---

## Flujo Correcto vs Incorrecto

### ✅ CORRECTO
```
1. Archivo #1 (user_service.py)
   - mypy
   - Fix error 1
   - Fix error 2
   - Fix error 3
   - mypy → Success ✅
   - git commit

2. Archivo #2 (payroll_service.py)
   - mypy
   - Fix errors...
   - mypy → Success ✅
   - git commit

3. Archivo #3...
```

### ❌ INCORRECTO
```
"Arregla todos los type errors"
→ Intenta 20 archivos a la vez
→ Confusión, errores, abandono
```

---

## Checklist: Antes de Pasar al Siguiente

- [ ] ¿Ejecutaste mypy en el archivo?
- [ ] ¿Corregiste UN error a la vez?
- [ ] ¿Ejecutaste mypy después de cada fix?
- [ ] ¿El archivo ahora dice "Success"?
- [ ] ¿Commiteaste los cambios?
- [ ] ¿NO intentaste cambiar múltiples archivos?

**NO procedes al siguiente archivo hasta Success ✅**

---

## Próximos Archivos a Validar

Crea una lista en orden:
1. backend/services/user_service.py
2. backend/services/payroll_service.py
3. backend/services/data_service.py
4. frontend/utils/helpers.py
5. ... (siempre en orden)

**Completa UNO completamente antes de pasar al siguiente.**
