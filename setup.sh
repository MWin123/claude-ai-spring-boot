#!/usr/bin/env bash
# Copies agents, skills, settings.json and CLAUDE.md into a Spring Boot project.
# Usage: ./setup.sh [project-dir]   (defaults to the current directory)
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)"
TARGET_DIR="${1:-.}"

if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Project directory not found: $TARGET_DIR" >&2
  exit 1
fi
TARGET_DIR="$(cd "$TARGET_DIR" && pwd -P)"

if [[ "$TARGET_DIR" == "$SOURCE_DIR" ]]; then
  echo "Target is this repository itself; pass your project directory." >&2
  exit 1
fi

mkdir -p "$TARGET_DIR/.claude/agents" "$TARGET_DIR/.claude/skills"
cp -r "$SOURCE_DIR/agents/." "$TARGET_DIR/.claude/agents/"
cp -r "$SOURCE_DIR/skills/." "$TARGET_DIR/.claude/skills/"
# Never overwrite existing settings: they may hold the project's permissions and hooks
if [[ -e "$TARGET_DIR/.claude/settings.json" ]]; then
  echo "Existing .claude/settings.json kept"
else
  cp "$SOURCE_DIR/settings.json" "$TARGET_DIR/.claude/settings.json"
fi
if [[ -f "$TARGET_DIR/CLAUDE.md" ]] && ! cmp -s "$SOURCE_DIR/CLAUDE.md" "$TARGET_DIR/CLAUDE.md"; then
  BACKUP="$TARGET_DIR/CLAUDE.md.bak"
  # Never overwrite an earlier backup: it may hold the project's original rules
  [[ -e "$BACKUP" ]] && BACKUP="$TARGET_DIR/CLAUDE.md.$(date +%Y%m%d%H%M%S).bak"
  cp "$TARGET_DIR/CLAUDE.md" "$BACKUP"
  echo "Existing CLAUDE.md saved as $(basename "$BACKUP")"
fi
cp "$SOURCE_DIR/CLAUDE.md" "$TARGET_DIR/CLAUDE.md"

echo "Copied agents, skills, settings.json and CLAUDE.md to $TARGET_DIR"
