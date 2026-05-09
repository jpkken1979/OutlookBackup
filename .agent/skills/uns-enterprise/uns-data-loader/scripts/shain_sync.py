#!/usr/bin/env python3
import sys
import logging
from data_loader import EmployeeLoader, UNS_FILES

# Setup logging
logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("shain-sync")


def main():
    print("🚀 Iniciando Sincronización de 社員台帳 (UNS Master Registry)...")

    # 1. Initialize Loader
    loader = EmployeeLoader()
    if not loader.excel_path.exists():
        print(f"❌ Error: No se encontró el archivo en {loader.excel_path}")
        print("Por favor, coloca una copia del Excel o verifica el acceso a la red.")
        sys.exit(1)

    # 2. Configure Sheets
    haken_sheet = UNS_FILES["shain_sheets"]["haken"]
    ukeoi_sheet = UNS_FILES["shain_sheets"]["ukeoi"]
    staff_sheet = UNS_FILES["shain_sheets"]["staff"]

    # Ask for Staff Import (Handle EOF for piped inputs)
    try:
        if "--yes" in sys.argv:
            import_staff = True
        else:
            import_staff = (
                input(f"❓ ¿Deseas importar también la hoja '{staff_sheet}'? (s/n) [n]: ").lower()
                == "s"
            )
    except EOFError:
        import_staff = False

    print("-" * 50)

    # 3. Process Haken
    print(f"⏳ Procesando Haken ({haken_sheet})...")
    haken_raw = loader.load_sheet(haken_sheet, header_row=1)
    haken_processed = loader.process_haken(haken_raw)
    active_haken = [e for e in haken_processed if e["is_active"]]
    print(f"✅ Haken: {len(haken_processed)} total | {len(active_haken)} activos (在職中)")

    # 4. Process Ukeoi
    print(f"⏳ Procesando Ukeoi ({ukeoi_sheet})...")
    ukeoi_raw = loader.load_sheet(ukeoi_sheet, header_row=2)
    ukeoi_processed = loader.process_ukeoi(ukeoi_raw)
    active_ukeoi = [e for e in ukeoi_processed if e["is_active"]]
    print(f"✅ Ukeoi: {len(ukeoi_processed)} total | {len(active_ukeoi)} activos (在職中)")

    # 5. Process Staff
    if import_staff:
        print(f"⏳ Procesando Staff ({staff_sheet})...")
        staff_raw = loader.load_sheet(staff_sheet, header_row=2)
        staff_processed = [
            {"name_kanji": r.get("氏名"), "name_katakana": loader.to_katakana(r.get("氏名"))}
            for r in staff_raw
            if r.get("氏名")
        ]
        print(f"✅ Staff: {len(staff_processed)} importados")

    print("-" * 50)
    print("✨ Sincronización completada exitosamente.")
    print(
        "💡 Nota: Los nombres han sido formateados en KATAKANA y las fábricas abreviadas según lo solicitado."
    )
    print(f"📊 Total Activos (Haken + Ukeoi): {len(active_haken) + len(active_ukeoi)}")


if __name__ == "__main__":
    main()
