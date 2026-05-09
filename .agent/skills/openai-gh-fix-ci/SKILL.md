---
name: openai-gh-fix-ci
description: >
type: feature
---
  Debug and fix failing GitHub Actions CI checks on pull requests.
  Fetches PR check status, pulls Actions logs, extracts failure snippets,
  and drafts fix plans. Use when CI is failing on a PR and you need to
  diagnose and resolve the issue.
source: OpenAI (codex-universal)
type: feature
---

# Fix Failing CI Checks

Debug and resolve failing GitHub Actions checks on pull requests.

## Workflow

### Step 1: Identify Failing Checks
```bash
# List all checks for current PR
gh pr checks

# Get detailed check info
gh pr checks --json name,state,conclusion,detailsUrl

# Or for a specific PR
gh pr checks <pr-number> --json name,state,conclusion
```

### Step 2: Fetch Failure Logs
```bash
# List workflow runs for current branch
gh run list --branch $(git branch --show-current)

# View specific run logs
gh run view <run-id> --log-failed

# Download logs for offline analysis
gh run view <run-id> --log-failed > ci_failure.log
```

### Step 3: Extract Failure Snippets
Parse logs to find:
- **Error messages**: Lines with `Error:`, `FAILED`, `error[`, `✗`
- **Test failures**: `FAIL`, `AssertionError`, `Expected X got Y`
- **Build errors**: Compiler errors, missing imports, type errors
- **Lint errors**: Ruff, ESLint, mypy violations
- **Timeout**: `The operation was canceled`

### Step 4: Diagnose Root Cause

| Failure Type | Common Causes | Investigation |
|-------------|---------------|---------------|
| Test failure | Logic bug, flaky test, env difference | Read test + source, check recent changes |
| Build error | Missing dep, type error, syntax | Check imports, version compatibility |
| Lint error | Style violation, unused import | Run linter locally to reproduce |
| Timeout | Slow test, infinite loop, resource leak | Check test duration, look for unbounded loops |
| Auth/permissions | Token expired, missing secret | Check workflow secrets configuration |

### Step 5: Draft Fix Plan
For each failure:
1. **Reproduce locally** if possible
2. **Identify the exact change** that caused it
3. **Write the minimal fix**
4. **Verify fix resolves the failure**
5. **Push and monitor CI**

## Common Fixes

### Test Failures
```bash
# Run the specific failing test locally
pytest tests/path/to/test.py::test_name -v

# With verbose output to see assertions
pytest tests/path/to/test.py::test_name -v --tb=long
```

### Lint Failures
```bash
# Auto-fix lint errors
ruff check --fix .
black .

# TypeScript
npx eslint --fix src/
```

### Type Errors
```bash
# Check specific file
mypy path/to/file.py
npx tsc --noEmit
```

### Dependency Issues
```bash
# Ensure lockfile is up to date
pip install -e ".[dev]"
npm ci
```

## Tips
- Always check if the failure exists on `main` (pre-existing vs introduced)
- Use `gh run rerun <run-id> --failed` to rerun only failed jobs
- Check for flaky tests by looking at CI history: `gh run list --limit 20`
- For environment-specific failures, compare CI env with local env
