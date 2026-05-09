#!/usr/bin/env bash
# detect-project-type.sh — Detect frontend/framework project type from lockfiles and configs.
# Exits with 0 and prints one of: rails, next, vite, nuxt, astro, remix, sveltekit, procfile, unknown

set -euo pipefail

detect() {
    if [[ -f "Gemfile" ]] && grep -q "rails" Gemfile 2>/dev/null; then
        echo "rails"
        return 0
    fi
    if [[ -f "package.json" ]]; then
        if grep -q '"next"' package.json 2>/dev/null; then
            echo "next"
            return 0
        fi
        if grep -q '"vite"' package.json 2>/dev/null; then
            echo "vite"
            return 0
        fi
        if grep -q '"nuxt"' package.json 2>/dev/null; then
            echo "nuxt"
            return 0
        fi
        if grep -q '"astro"' package.json 2>/dev/null; then
            echo "astro"
            return 0
        fi
        if grep -q '"@remix-run/react"' package.json 2>/dev/null; then
            echo "remix"
            return 0
        fi
        if grep -q '"@sveltejs/kit"' package.json 2>/dev/null; then
            echo "sveltekit"
            return 0
        fi
    fi
    if [[ -f "Procfile" ]]; then
        echo "procfile"
        return 0
    fi
    echo "unknown"
}

PROJECT_DIR="${1:-.}"
cd "$PROJECT_DIR"
detect
