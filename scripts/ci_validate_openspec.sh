#!/usr/bin/env bash
# Strictly validate every main spec and every in-flight change that carries delta specs.
# Planning-only drafts (a change directory without specs/) are listed and skipped so an
# unrelated draft cannot fail CI; they are validated once they gain specs.
# Usage: ci_validate_openspec.sh [openspec-binary]
set -euo pipefail

openspec="${1:-openspec}"
"$openspec" validate --specs --strict --no-interactive
for dir in openspec/changes/*/; do
  name="$(basename "$dir")"
  [ "$name" = "archive" ] && continue
  if [ -d "$dir/specs" ]; then
    "$openspec" validate "$name" --type change --strict --no-interactive
  else
    echo "skipping draft change without specs: $name"
  fi
done
