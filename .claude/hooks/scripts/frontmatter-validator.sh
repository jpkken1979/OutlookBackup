#!/usr/bin/env bash
set -uo pipefail
# Hook: Valida el frontmatter YAML de SKILL.md / IDENTITY.md tras editarlos.
# Triggered by: PostToolUse on Edit|Write|MultiEdit
# Cost: 0 tokens (bash + python local)
#
# Atrapa al momento de editar los 3 bugs de frontmatter que rompen el discovery
# (verificados en el ecosistema: ~9% de skills afectadas):
#   1. description vacia (| o >-) con el texto fugado DESPUES del --- de cierre
#   2. ':' sin comillas dentro del valor de description (mapping values not allowed)
#   3. bloques largos (examples:) metidos en el frontmatter en vez del body
# No bloquea la edicion: solo avisa para que se corrija antes de commitear.

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "${SCRIPT_DIR}/common-utils.sh" 2>/dev/null || true

INPUT=$(cat)
FILE=$(echo "$INPUT" | python3 -c "import sys,json; d=json.load(sys.stdin); print(d.get('tool_input',{}).get('file_path',d.get('tool_response',{}).get('filePath','')))" 2>/dev/null)

[ -z "$FILE" ] && { echo '{"suppressOutput": true}'; exit 0; }

# Solo aplica a SKILL.md o IDENTITY.md
case "$(basename "$FILE")" in
  SKILL.md|IDENTITY.md) ;;
  *) echo '{"suppressOutput": true}'; exit 0 ;;
esac

[ -f "$FILE" ] || { echo '{"suppressOutput": true}'; exit 0; }

# Validar el frontmatter. Usa PyYAML si esta disponible; si no, hace un check
# heuristico de los patrones rotos conocidos. Nunca rompe la sesion.
RESULT=$(python3 - "$FILE" <<'PY' 2>/dev/null
import re, sys
path = sys.argv[1]
try:
    content = open(path, encoding="utf-8").read()
except OSError:
    print("OK"); sys.exit(0)

m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
if not m:
    print("OK"); sys.exit(0)  # sin frontmatter: no aplica
fm = m.group(1)

# Heuristica de bugs conocidos (no requiere PyYAML)
problems = []
# 1. description con block scalar vacio (| o >-) — el valor real quedo afuera
if re.search(r"^description:\s*[|>][+-]?\s*$", fm, re.MULTILINE):
    problems.append("description: usa block scalar (| o >-) pero quedo VACIO; el texto se fugo al body")
# 3. bloque examples: dentro del frontmatter (debe ir en el body)
if re.search(r"^examples:\s*$", fm, re.MULTILINE):
    problems.append("examples: esta DENTRO del frontmatter; movelo al body (despues del --- de cierre)")

# 2 + validacion real: intentar parsear con PyYAML si esta
try:
    import yaml
    try:
        data = yaml.safe_load(fm)
        if not isinstance(data, dict):
            problems.append("el frontmatter no parsea como un mapping YAML")
        elif not (data.get("description") or "").strip():
            problems.append("falta 'description' o esta vacia (requerida para el discovery)")
    except yaml.YAMLError as e:
        prob = getattr(e, "problem", str(e))
        problems.append(f"YAML invalido: {prob} (tip: si description tiene ':', entrecomilla el valor)")
except ImportError:
    # Sin PyYAML: heuristica de ':' sin comillas en description de una linea
    md = re.search(r'^description:\s*(?![|>\'"])(.*:.*)$', fm, re.MULTILINE)
    if md:
        problems.append("description tiene ':' sin comillas; entrecomilla el valor: description: '...'")

print("OK" if not problems else " | ".join(problems))
PY
)

if [ -z "$RESULT" ] || [ "$RESULT" = "OK" ]; then
  echo '{"suppressOutput": true}'
  exit 0
fi

MSG="frontmatter-validator: $(basename "$(dirname "$FILE")")/$(basename "$FILE") tiene frontmatter que rompe el discovery -> ${RESULT}"
echo "{\"systemMessage\": \"${MSG}\"}"
exit 0
