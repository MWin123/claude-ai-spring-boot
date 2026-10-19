#!/usr/bin/env bash
# Copies agents, skills and CLAUDE.md into a Spring Boot project.
# Usage: ./setup.sh [project-dir]   (defaults to the current directory)
set -euo pipefail

SOURCE_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
TARGET_DIR="${1:-.}"

if [[ ! -d "$TARGET_DIR" ]]; then
  echo "Project directory not found: $TARGET_DIR" >&2
  exit 1
fi
TARGET_DIR="$(cd "$TARGET_DIR" && pwd)"

if [[ "$TARGET_DIR" == "$SOURCE_DIR" ]]; then
  echo "Target is this repository itself; pass your project directory." >&2
  exit 1
fi

mkdir -p "$TARGET_DIR/.claude/agents" "$TARGET_DIR/.claude/skills"
cp -r "$SOURCE_DIR/agents/." "$TARGET_DIR/.claude/agents/"
cp -r "$SOURCE_DIR/skills/." "$TARGET_DIR/.claude/skills/"
cp "$SOURCE_DIR/CLAUDE.md" "$TARGET_DIR/CLAUDE.md"

echo "Copied agents, skills and CLAUDE.md to $TARGET_DIR"
