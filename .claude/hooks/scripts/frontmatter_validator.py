#!/usr/bin/env python3
"""Hook: Valida frontmatter YAML de SKILL.md / IDENTITY.md (Python port of frontmatter-validator.sh)
Triggered by: PostToolUse on Edit|Write|MultiEdit
Cost: 0 tokens (local)
"""
import json, re, sys, os

def main():
    raw = sys.stdin.read().strip()
    if not raw:
        print('{"suppressOutput": true}')
        sys.exit(0)
    try:
        data = json.loads(raw)
        fp = data.get("tool_input", {}).get("file_path", "") or data.get("tool_response", {}).get("filePath", "")
    except Exception:
        print('{"suppressOutput": true}')
        sys.exit(0)

    if not fp:
        print('{"suppressOutput": true}')
        sys.exit(0)

    basename = os.path.basename(fp)
    if basename not in ("SKILL.md", "IDENTITY.md"):
        print('{"suppressOutput": true}')
        sys.exit(0)

    if not os.path.isfile(fp):
        print('{"suppressOutput": true}')
        sys.exit(0)

    try:
        content = open(fp, encoding="utf-8").read()
    except OSError:
        print('{"suppressOutput": true}')
        sys.exit(0)

    m = re.match(r"^---\n(.*?)\n---", content, re.DOTALL)
    if not m:
        print('{"suppressOutput": true}')
        sys.exit(0)

    fm = m.group(1)
    problems = []

    if re.search(r"^description:\s*[|>][+-]?\s*$", fm, re.MULTILINE):
        problems.append("description: usa block scalar (| o >-) pero quedo VACIO")

    if re.search(r"^examples:\s*$", fm, re.MULTILINE):
        problems.append("examples: esta DENTRO del frontmatter; movelo al body")

    try:
        import yaml
        try:
            d = yaml.safe_load(fm)
            if not isinstance(d, dict):
                problems.append("el frontmatter no parsea como mapping YAML")
            elif not (d.get("description") or "").strip():
                problems.append("falta 'description' o esta vacia")
        except yaml.YAMLError as e:
            prob = getattr(e, "problem", str(e))
            problems.append(f"YAML invalido: {prob}")
    except ImportError:
        md = re.search(r'^description:\s*(?![|>\'\"])(.*:.*)$', fm, re.MULTILINE)
        if md:
            problems.append("description tiene ':' sin comillas")

    if not problems:
        print('{"suppressOutput": true}')
    else:
        dirname = os.path.basename(os.path.dirname(fp))
        msg = f"frontmatter-validator: {dirname}/{basename} -> {' | '.join(problems)}"
        print(json.dumps({"systemMessage": msg}))

if __name__ == "__main__":
    main()
