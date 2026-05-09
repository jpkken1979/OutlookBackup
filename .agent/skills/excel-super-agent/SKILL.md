---
name: excel-super-agent
description: "The ultimate orchestrator for Excel processing on Windows/Japanese environments. Intelligently routes between 'Deep Parse' (for complex Japanese forms), 'Smart Parser' (for clean tables), and 'Pandas' (for massive datasets). Handles Shift-JIS/CP932 encoding, Japanese Era dates (Reiwa/Heisei), and localized headers."
type: feature
skills:
---
  - excel-deep-parse
  - excel-smart-parser
  - excel-router
---

# Excel Super Agent - Master Orchestrator 🗾

> **Status:** ACTIVE
> **Locale:** Windows / Japanese (Shift-JIS/CP932 Support)
> **Role:** The "Brain" that decides how to read an Excel file.

This agent acts as a unified interface for all Excel operations. users no longer need to choose which parser to use. The Super Agent analyzes the file and delegates to the specialist.

## 🧠 Routing Logic (The "Scout" Protocol)

1.  **File Integrity Check**: Validates path, locks, and extension.
2.  **Encoding Detection**: Automatically probes `utf-8-sig`, `cp932` (Shift-JIS), and `euc-jp` for CSVs.
3.  **Structural Analysis**:
    *   **Complex Form?** (Merged cells, labels like "氏名", no clear header row) -> **Deep Parser**
    *   **Clean Table?** (Row 1 has headers, consistent columns) -> **Smart Parser**
    *   **Big Data?** (>5000 rows, simple structure) -> **Pandas Fast Mode**

## 🛡️ Windows & Japanese Specifics

-   **Path Handling**: Uses `pathlib` robustly to handle Windows backslashes `\` correctly.
-   **Era Support**: Can parse `令和5年4月1日` into `2023-04-01`.
-   **Ghost Columns**: Cleans up "Unamed: X" columns often left by Excel export macros.

## 🚀 Usage

```python
from skills.excel_super_agent.scripts.orchestrator import process_excel

# Process anything - let the agent decide
result = process_excel("C:\\Users\\kenji\\Downloads\\給与明細_2024.xlsx")

if result["strategy"] == "deep_parse":
    print("Detected complex form. Basic Info:", result["data"]["basic_info"])
elif result["strategy"] == "smart_table":
    print("Detected table. Row count:", len(result["data"]))
```
