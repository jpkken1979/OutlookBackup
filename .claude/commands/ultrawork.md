# /ultrawork — Parallel execution mode

## Usage
- `/ultrawork <task1> + <task2> + <task3>` — Run tasks in parallel
- `/ultrawork analyze <module> + test <module> + document <module>`

## Description
Ultrawork enables MAXIMUM PARALLEL execution. Unlike OMC's `ultrawork`/`ulw`
magic keyword, this is a slash command that:
1. Parses the task list (split by `+`)
2. Dispatches each task to a separate subagent
3. Runs them in parallel (max 5 concurrent)
4. Collects results when all complete

WARNING: Ultrawork spawns multiple agents simultaneously. Use for
independent tasks only (e.g., analyze different modules).

## Examples
- `/ultrawork analyze frontend + analyze backend + analyze tests`
- `/ultrawork lint src/ + test src/ + build src/`
