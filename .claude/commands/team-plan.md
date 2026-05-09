# /team-plan — Multi-agent planning pipeline

## Usage
- `/team-plan <goal>` — Run full team planning pipeline
- `/team-plan build login system`

## Description
Implements OMC's team planning pipeline:
- **team-plan**: Analyze goal, identify requirements gaps
- **team-prd**: Create detailed plan with acceptance criteria
- **team-exec**: Execute with executor agent
- **team-verify**: Verify implementation against spec
- **team-fix**: If verify fails, fix and re-verify (loop)

This is NOT automatic implementation — it's a structured planning
workflow that involves analyst → planner → executor → verifier
in a controlled pipeline.

## Pipeline Steps
1. **Analysis** (analyst agent): Identify gaps, hidden constraints
2. **Planning** (planner agent): Create work plan in `.omc/plans/`
3. **Execution** (executor agent): Implement changes
4. **Verification** (verifier agent): Check against acceptance criteria
5. **Fix** (if needed): Loop back to executor

## Examples
- `/team-plan build authentication` — Full pipeline for auth system
- `/team-plan refactor database` — Plan and execute refactor

## Trigger Keywords
- "team-plan", "build me a", "implement with team"
