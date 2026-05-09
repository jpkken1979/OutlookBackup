# /ralph — Verify until complete (don't stop)

## Usage
- `/ralph` — Activate Ralph: loop verify-fix until tests pass
- `/ralph <task>` — Verify specific task until completion
- `/ralph stop` — Stop the verification loop

## Description
Ralph is the OMC-inspired verification agent that LOOPS until completion.
It runs verification, fixes issues found, and repeats until:
- All tests pass
- OR max iterations reached (default: 5)
- OR user stops with `/ralph stop`

Ralph doesn't give up — "don't stop until verified."

## How it works
1. Runs tests / verification checks
2. If failures → fix them
3. Re-run verification
4. Repeat until clean OR max iterations

## Examples
- `/ralph` — Verify all tests in current session
- `/ralph run tests` — Run test suite with loop
- `/ralph verify build` — Verify build completes successfully

## Trigger Keywords
- "ralph", "don't stop", "verify until", "loop until done"
