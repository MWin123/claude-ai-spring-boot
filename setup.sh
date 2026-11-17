#!/usr/bin/env bash
# Copies agents, skills, config/.claude/settings.json, config/AGENTS.md and config/CLAUDE.md into a Spring Boot project.
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

BUILD_FILE=""
for f in pom.xml build.gradle build.gradle.kts settings.gradle settings.gradle.kts; do
  if [[ -f "$TARGET_DIR/$f" ]]; then BUILD_FILE="$f"; break; fi
done
if [[ -z "$BUILD_FILE" ]]; then
  echo "No pom.xml, build.gradle(.kts) or settings.gradle(.kts) in $TARGET_DIR; create the project first (e.g. with Spring Initializr)." >&2
  exit 1
fi

# Project name for the AGENTS.md heading: Maven artifactId (not the parent's), else Gradle rootProject.name, else the directory name (Gradle's default)
if [[ "$BUILD_FILE" == pom.xml ]]; then
  NAME="$(sed -e 's:<parent>.*</parent>::' -e '/<parent>/,/<\/parent>/d' "$TARGET_DIR/pom.xml" | sed -n 's:.*<artifactId>\([^<]*\)</artifactId>.*:\1:p' | head -n 1)"
  if [[ -z "$NAME" ]]; then
    echo "No artifactId in $TARGET_DIR/pom.xml" >&2
    exit 1
  fi
else
  NAME="$(cat "$TARGET_DIR"/settings.gradle "$TARGET_DIR"/settings.gradle.kts 2>/dev/null |
    sed -n "s/^[[:space:]]*rootProject\.name[[:space:]]*=[[:space:]]*[\"']\([^\"']*\)[\"'].*/\1/p" | head -n 1)" || true
  NAME="${NAME:-$(basename "$TARGET_DIR")}"
fi
PLACEHOLDER="# <project-name>"
if [[ "$(head -n 1 "$SOURCE_DIR/config/AGENTS.md")" != "$PLACEHOLDER" ]]; then
  echo "config/AGENTS.md must start with '$PLACEHOLDER'" >&2
  exit 1
fi
AGENTS_MD="$(mktemp)"
trap 'rm -f "$AGENTS_MD"' EXIT
{ printf '# %s\n' "$NAME"; tail -n +2 "$SOURCE_DIR/config/AGENTS.md"; } > "$AGENTS_MD"

# Copies $1 to the project root as $2; a different existing file is backed up first
install_root_file() {
  local source="$1" target="$TARGET_DIR/$2"
  if [[ -f "$target" ]] && ! cmp -s "$source" "$target"; then
    local backup="$target.bak"
    # Never overwrite an earlier backup: it may hold the project's original rules
    [[ -e "$backup" ]] && backup="$target.$(date +%Y%m%d%H%M%S).bak"
    cp "$target" "$backup"
    echo "Existing $2 saved as $(basename "$backup")"
  fi
  cp "$source" "$target"
}

mkdir -p "$TARGET_DIR/.claude/agents" "$TARGET_DIR/.claude/skills"
cp -r "$SOURCE_DIR/agents/." "$TARGET_DIR/.claude/agents/"
cp -r "$SOURCE_DIR/skills/." "$TARGET_DIR/.claude/skills/"
# Never overwrite existing settings: they may hold the project's permissions and hooks
if [[ -e "$TARGET_DIR/.claude/settings.json" ]]; then
  echo "Existing .claude/settings.json kept"
else
  cp "$SOURCE_DIR/config/.claude/settings.json" "$TARGET_DIR/.claude/settings.json"
fi
install_root_file "$AGENTS_MD" AGENTS.md
install_root_file "$SOURCE_DIR/config/CLAUDE.md" CLAUDE.md

echo "Copied agents, skills, settings.json, AGENTS.md and CLAUDE.md to $TARGET_DIR (project: $NAME)"
