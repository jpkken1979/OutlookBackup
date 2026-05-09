#!/bin/bash
set -euo pipefail

MESSAGE="${1:-chore(repo): update changes}"
MODE="${2:-}" # --group | --separate

if ! git rev-parse --is-inside-work-tree >/dev/null 2>&1; then
	echo "❌ Not a git repository."
	exit 1
fi

staged_files=$(git diff --cached --name-only)
unstaged_files=$(git diff --name-only)
untracked_files=$(git ls-files --others --exclude-standard)

staged_count=$(printf "%s\n" "$staged_files" | sed '/^$/d' | wc -l | tr -d ' ')
unstaged_count=$(printf "%s\n" "$unstaged_files" | sed '/^$/d' | wc -l | tr -d ' ')
untracked_count=$(printf "%s\n" "$untracked_files" | sed '/^$/d' | wc -l | tr -d ' ')

total_count=$((staged_count + unstaged_count + untracked_count))

if [ "$total_count" -eq 0 ]; then
	echo "ℹ️ No hay cambios para commitear."
	exit 0
fi

echo "📊 Estado detectado antes del commit:"
echo "  - staged:   $staged_count"
echo "  - unstaged: $unstaged_count"
echo "  - untracked:$untracked_count"

has_mixed_state=0
if [ "$staged_count" -gt 0 ] && { [ "$unstaged_count" -gt 0 ] || [ "$untracked_count" -gt 0 ]; }; then
	has_mixed_state=1
fi

if [ "$has_mixed_state" -eq 1 ] && [ -z "$MODE" ]; then
	if [ -t 0 ]; then
		echo "⚠️ Hay cambios staged y también unstaged/untracked."
		echo "¿Querés agrupar todo en un commit o separar (solo staged)?"
		echo "  [g] group   [s] separate   [c] cancel"
		read -r -p "> " answer
		case "$answer" in
			g|G) MODE="--group" ;;
			s|S) MODE="--separate" ;;
			*)
				echo "⏹️ Operación cancelada."
				exit 1
				;;
		esac
	else
		echo "❌ Mixed state detected. Re-run with --group or --separate."
		exit 1
	fi
fi

if [ "$MODE" = "--group" ] || [ -z "$MODE" ]; then
	git add -A
elif [ "$MODE" = "--separate" ]; then
	if [ "$staged_count" -eq 0 ]; then
		echo "❌ --separate requires staged files. Stage files first or use --group."
		exit 1
	fi
else
	echo "❌ Invalid mode '$MODE'. Use --group or --separate."
	exit 1
fi

if git diff --cached --quiet; then
	echo "ℹ️ No staged changes to commit after selection."
	exit 0
fi

git commit -m "$MESSAGE"

branch=$(git rev-parse --abbrev-ref HEAD)
git push -u origin "$branch"

echo "✅ Push completado en rama '$branch'."

post_status=$(git status --porcelain)
if [ -z "$post_status" ]; then
	echo "✅ Verificación post-push: git status limpio."
else
	echo "⚠️ Verificación post-push: todavía hay cambios locales."
	git status --short
fi
