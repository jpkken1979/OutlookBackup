# Scripts Documentation

Validation and utility scripts for Vercel Agent Skills best practices.

## validate_skill.py

**Purpose**: Automated validation of agent skill packages against Vercel Agent Skills specification.

### Features

- ✅ SKILL.md existence and format validation
- ✅ YAML frontmatter parsing and validation
- ✅ Name pattern compliance (`^[a-z0-9]+(-[a-z0-9]+)*$`)
- ✅ Directory name matching
- ✅ Required metadata fields check
- ✅ Recommended metadata fields check
- ✅ Markdown structure validation
- ✅ Scripts directory validation
- ✅ References directory validation
- ✅ Examples directory validation
- ✅ Grep pattern usage detection

### Usage

#### Single Skill Validation

```bash
# Basic usage
python validate_skill.py path/to/skill-directory/

# Example
python validate_skill.py .agent/skills/api-error-handling/
```

#### Batch Validation

```bash
# Validate all skills in directory
python validate_skill.py --batch .agent/skills/*/

# Example output for batch mode
# Validates multiple skills sequentially
```

#### Report Generation

```bash
# Generate markdown report
python validate_skill.py --report path/to/skill/ > validation_report.md
```

### Exit Codes

- **0**: Validation passed (all checks OK or warnings only)
- **1**: Validation failed (critical errors detected)

### Validation Output

#### Success (No Warnings)

```
[*] Validating skill: example-skill

[OK] SKILL.md exists
[OK] YAML frontmatter valid
[OK] Name pattern valid: 'example-skill'
[OK] Directory name matches skill name: 'example-skill'
[OK] Required field 'name' present
[OK] Required field 'description' present
[OK] Recommended field 'version' present
[OK] Recommended field 'tags' present
[OK] Recommended field 'author' present
...

==================================================
Summary:
  [OK] Passed: 20
  [WARN]  Warnings: 0
  [FAIL] Errors: 0
==================================================

[OK] Validation PASSED
```

#### Success (With Warnings)

```
[*] Validating skill: another-skill

[OK] SKILL.md exists
[OK] YAML frontmatter valid
...
[WARN]  Recommended field 'version' missing
[WARN]  scripts/README.md missing (recommended for documentation)
...

==================================================
Summary:
  [OK] Passed: 15
  [WARN]  Warnings: 2
  [FAIL] Errors: 0
==================================================

[WARN]  Validation PASSED (with warnings)
```

#### Failure

```
[*] Validating skill: broken-skill

[OK] SKILL.md exists
[FAIL] YAML frontmatter invalid
[FAIL] Name 'Broken_Skill' must match pattern: ^[a-z0-9]+(-[a-z0-9]+)*$
[FAIL] Directory name 'broken-skill' must match skill name 'Broken_Skill'
[FAIL] Required field 'description' missing
...

==================================================
Summary:
  [OK] Passed: 5
  [WARN]  Warnings: 1
  [FAIL] Errors: 4
==================================================

[FAIL] Validation FAILED
```

### Validation Rules

#### Critical (Must Pass)

1. **SKILL.md existence**: File must exist
2. **YAML frontmatter**: Valid YAML between `---` markers
3. **Name pattern**: Matches `^[a-z0-9]+(-[a-z0-9]+)*$`
4. **Directory match**: Directory name equals skill name
5. **Required fields**: `name` and `description` present

#### Warnings (Best Practices)

1. **Recommended fields**: `version`, `tags`, `author`
2. **Markdown sections**: "Use this skill when", "Do not use this skill when", "Instructions", "Safety"
3. **Extended thinking**: Present in skill description
4. **Scripts README**: Documentation for scripts/ directory
5. **Grep patterns**: References to references/ directory

### CI/CD Integration

#### GitHub Actions

```yaml
name: Validate Skills

on:
  pull_request:
    paths:
      - '.agent/skills/**'

jobs:
  validate:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Set up Python
        uses: actions/setup-python@v4
        with:
          python-version: '3.11'

      - name: Install dependencies
        run: |
          pip install pyyaml

      - name: Validate skills
        run: |
          python .agent/skills/vercel-agent-skills-best-practices/scripts/validate_skill.py \
            --batch .agent/skills/*/

          if [ $? -ne 0 ]; then
            echo "❌ Skill validation failed"
            exit 1
          fi
```

#### Pre-commit Hook

```bash
#!/bin/bash
# .git/hooks/pre-commit

# Validate modified skills before commit
MODIFIED_SKILLS=$(git diff --cached --name-only | grep "^.agent/skills/" | cut -d/ -f1-3 | sort -u)

if [ -n "$MODIFIED_SKILLS" ]; then
  echo "Validating modified skills..."

  for skill in $MODIFIED_SKILLS; do
    python .agent/skills/vercel-agent-skills-best-practices/scripts/validate_skill.py "$skill"

    if [ $? -ne 0 ]; then
      echo "❌ Validation failed for $skill"
      exit 1
    fi
  done

  echo "✅ All skills validated successfully"
fi
```

### Extending the Validator

To add custom validation rules:

```python
# In SkillValidator class

def _check_custom_rule(self):
    """Check custom organizational requirement."""
    if not hasattr(self, 'frontmatter'):
        return

    # Custom logic here
    custom_field = self.frontmatter.get('custom_field')

    if custom_field:
        self.results.append(ValidationResult(
            passed=True,
            message="[OK] Custom field present",
            severity="info"
        ))
    else:
        self.results.append(ValidationResult(
            passed=False,
            message="[WARN] Custom field missing",
            severity="warning"
        ))
```

Then add to `validate()` method:

```python
def validate(self) -> bool:
    # ... existing checks ...
    self._check_custom_rule()  # Add custom check
    return self._print_results()
```

### Dependencies

**Required**:
- Python 3.11+
- PyYAML (`pip install pyyaml`)

**Optional**:
- None (standalone script)

### Troubleshooting

#### Issue: "UnicodeEncodeError" on Windows

**Solution**: Script uses ASCII symbols ([OK], [FAIL], [WARN]) for Windows compatibility.

#### Issue: "No module named 'yaml'"

**Solution**: Install PyYAML:
```bash
pip install pyyaml
```

#### Issue: False positives on warnings

**Solution**: Warnings are informational and don't fail validation. To suppress specific warnings, modify severity thresholds in the script.

## Future Scripts (Planned)

### generate_skill.py (Coming Soon)

Interactive skill generator using templates:

```bash
python generate_skill.py --name my-new-skill --type simple
```

### migrate_skill.py (Coming Soon)

Migrate skills from other formats to Vercel specification:

```bash
python migrate_skill.py --from antigravity --to vercel my-skill/
```

### publish_skill.py (Coming Soon)

Publish validated skills to skills.sh registry:

```bash
python publish_skill.py --skill my-skill/ --registry skills.sh
```

---

**Maintained by**: Antigravity Team
**Last Updated**: 2026-02-05
**Version**: 1.0.0
