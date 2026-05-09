---
name: inteligente-shain
description: Expert in UNS employee data synchronization, mapping Excel master files to SQLite databases with dynamic column detection and name normalization.
---

# Inteligente Shain Skill

Expert skill for managing and importing Universal Kikaku (UNS) employee records.

## Usage

Use this skill when you need to:
- Import data from `【新】社員台帳(UNS)T` Excel files.
- Handle `DBGenzaiX`, `DBUkeoiX`, or `DBStaffX` sheets.
- Normalize foreign names to Katakana and keep Japanese names in Kanji.
- Sync the web interface import status with reality.
- Map dynamic Excel columns to fixed database schemas.

## Technical Context
- **Primary DB**: `uns_employees.db`
- **Tables**: `genzai_employees`, `ukeoi_employees`, `staff_employees`.
- **Key Logic**: Dynamic column mapping, status filtering (`在職中`), and factory assignment for Ukeoi workers.
