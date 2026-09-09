#!/usr/bin/env bash
# Verificacion final de la migracion al broker MCP unico.
# Para cada app comprueba: cuantos servers quedaron, que el interprete exista,
# y que NO apunte al .venv del propio target (el bug de Chingiv7).

ROOT="D:/BackupJp26.5.11/DesdelaAppBackup/Jpkken1979"
AG="$ROOT/OpenAntigravity26.3.30"
PY="$AG/.venv/Scripts/python.exe"

verificar_una() {
  "$PY" - "$1" <<'PYEOF'
import io, json, sys
from pathlib import Path

destino = Path(sys.argv[1])
cfg = destino / ".mcp.json"
try:
    servers = json.load(io.open(cfg, encoding="utf-8")).get("mcpServers", {})
except Exception as exc:
    print(f"ERROR  {destino.name}: no se pudo leer .mcp.json ({exc})")
    raise SystemExit(0)

broker = servers.get("antigravity")
if broker is None:
    print(f"ERROR  {destino.name}: sin entrada 'antigravity'")
    raise SystemExit(0)

legacy = [n for n in servers if n.startswith("antigravity-")]
command = str(broker.get("command", ""))
problemas = []

if legacy:
    problemas.append(f"quedaron {len(legacy)} servers legacy")
if "${" in command:
    problemas.append("interprete con plantilla sin resolver")
elif not Path(command).is_file():
    problemas.append("interprete inexistente")
if str(destino.resolve()).replace("\\", "/").lower() in command.replace("\\", "/").lower():
    if "/.venv/" in command.replace("\\", "/").lower():
        problemas.append("usa el .venv del propio target")
if broker.get("env", {}).get("ANTIGRAVITY_MCP_URL", "").endswith("/mcp") is False:
    problemas.append("ANTIGRAVITY_MCP_URL no apunta al broker")

estado = "OK    " if not problemas else "REVISAR"
detalle = f" [{'; '.join(problemas)}]" if problemas else ""
print(f"{estado} {destino.name}: {len(servers)} servers{detalle}")
PYEOF
}

echo "=== verificacion de la migracion al broker MCP ==="
total=0; revisar=0
for d in "$ROOT"/*/; do
  d="${d%/}"
  [ "$(basename "$d")" = "OpenAntigravity26.3.30" ] && continue
  [ -f "$d/.mcp.json" ] || continue
  linea="$(verificar_una "$d")"
  echo "$linea"
  total=$((total+1))
  case "$linea" in REVISAR*|ERROR*) revisar=$((revisar+1));; esac
done

if [ -f "/d/BackupJp26.5.11/KobetsuVsKonetsu/KobetsuV3/.mcp.json" ]; then
  linea="$(verificar_una "/d/BackupJp26.5.11/KobetsuVsKonetsu/KobetsuV3")"
  echo "$linea"
  total=$((total+1))
  case "$linea" in REVISAR*|ERROR*) revisar=$((revisar+1));; esac
fi

echo ""
echo "TOTAL: $total apps | a revisar: $revisar"
