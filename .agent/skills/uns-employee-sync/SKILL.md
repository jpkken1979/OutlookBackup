---
name: uns-employee-sync
type: feature
description: "Sincronización masiva de datos de empleados entre Excel y base de datos. Triggers: sync empleados, sincronizar, employee sync, 社員同期, importar Excel, data sync, bulk import."
source: uns
---
# UNS Employee Sync Skill

Esta habilidad permite la gestión inteligente y sincronización masiva de datos de empleados del ecosistema **UNS-Kikaku** (Universal Planning). Se especializa en la interoperabilidad entre archivos Excel maestros japoneses complejos y bases de datos SQLite/PostgreSQL.

## Capacidades

1.  **Mapeo Dinámico de Columnas (Smart Column Mapping)**:
    *   Detecta automáticamente campos clave como `社員no`, `氏名`, `派遣先`, `請負業務`.
    *   Es resiliente a cambios en el formato o el orden de las columnas del archivo maestro `【新】社員台帳(UNS)T`.

2.  **Normalización de Nombres Inteligente**:
    *   **Extranjeros**: Conversión automática a **KATAKANA** para uniformidad en búsquedas y reportes.
    *   **Japoneses**: Preservación de **KANJI** original para validez legal y respeto corporativo.

3.  **Gestión de Tiers de Empleados**:
    *   **Genzai (派遣社員)**: Procesamiento de altos volúmenes de empleados externos (~1000 registros).
    *   **Ukeoi (請負社員)**: Asignación inteligente por defecto a '高雄工業岡山工場' cuando no hay planta definida.
    *   **Staff (スタッフ)**: Importación de personal administrativo desde hojas `DBStaffX`.

4.  **Lógica de Negocio UNS**:
    *   Filtrado automático de empleados activos (`在職中`) vs totales.
    *   Manejo de caracteres corruptos con fallback a Romaji o ID de empleado.
    *   Generación de estadísticas en tiempo real (Activos / Total).

## Uso Técnicos

*   **Punto de Entrada**: `.agent/skills/uns-employee-sync/scripts/sync_engine.py`
*   **Formato de Datos**: Excel (.xlsx) con hojas `DBGenzaiX`, `DBUkeoiX`, `DBStaffX`.
*   **Base de Datos**: SQLite nativo (`uns_employees.db`) o PostgreSQL via SQLAlchemy.

---
*Desarrollado para Universal Kikaku por Antigravity AI.*
