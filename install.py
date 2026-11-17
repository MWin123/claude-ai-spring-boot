#!/usr/bin/env python3
"""Installs the template into a Spring Boot project.

Copies agents, skills and config/.claude/hooks into .claude/, config/AGENTS.md and config/CLAUDE.md into the project
root, and merges config/.claude/settings.json into .claude/settings.json and config/.claude/settings.user.json into
~/.claude/settings.json. Usage: ./install.py [project-dir]   (defaults to the current directory)
"""
import sys

# Checked before anything else runs; the rest of the file must still parse on older versions (no `type` statements)
if sys.version_info < (3, 13):
    sys.exit(f"install.py needs Python 3.13 or later (found {sys.version.split()[0]}); run it with python3.13")

import copy
import json
import os
import re
import shutil
import subprocess
import xml.etree.ElementTree as ET
from pathlib import Path
from typing import Any, NoReturn

SOURCE = Path(__file__).resolve().parent
CONFIG = SOURCE / "config"
BUILD_FILES = ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"]
PLACEHOLDER = "# <project-name>"
GRADLE_NAME = re.compile(r"""^\s*rootProject\.name\s*=\s*["']([^"']*)["']""", re.M)
HOOK_SCRIPT = re.compile(r"hooks/([\w.-]+)")


def fail(message: str) -> NoReturn:
    print(message, file=sys.stderr)
    sys.exit(1)


def project_name(target: Path, build_file: str) -> str:
    """Maven artifactId (not the parent's), else Gradle rootProject.name, else the directory name (Gradle's default)."""
    if build_file == "pom.xml":
        try:
            root = ET.parse(target / "pom.xml").getroot()
        except ET.ParseError as e:
            fail(f"Cannot parse {target / 'pom.xml'}: {e}")
        for child in root:  # direct children only: <parent> and <dependencies> hold other artifactIds
            if child.tag.rsplit("}", 1)[-1] == "artifactId" and (text := (child.text or "").strip()):
                return text
        fail(f"No artifactId in {target / 'pom.xml'}")
    for name in ("settings.gradle", "settings.gradle.kts"):
        settings = target / name
        if settings.is_file() and (match := GRADLE_NAME.search(settings.read_text(encoding="utf-8"))):
            return match.group(1)
    return target.name


def read_settings(path: Path) -> dict[str, Any] | None:
    """The settings in `path`, or None if it doesn't exist; stops setup if it isn't a JSON object."""
    if not path.exists():
        return None
    try:
        settings = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        fail(f"Cannot read {path}: {e}; fix it, then run install.py again")
    if not isinstance(settings, dict):
        fail(f"{path} is not a JSON object; fix it, then run install.py again")
    return settings


def backup(path: Path) -> str:
    """Copies `path` to path.bak, or path.2.bak and so on: an earlier backup may hold the project's original rules."""
    target, n = path.with_name(path.name + ".bak"), 1
    while target.exists() or target.is_symlink():
        n += 1
        target = path.with_name(f"{path.name}.{n}.bak")
    shutil.copyfile(path, target)
    return target.name


def install_root_file(content: bytes, target: Path) -> None:
    """Writes `content` to `target` in the project root; a different existing file is backed up first."""
    # Writing would go through a symlink into the file it points to; that file stays as it is
    if target.is_symlink():
        target.unlink()
        print(f"Existing {target.name} was a symlink; replaced by a file")
    if target.is_file() and target.read_bytes() != content:
        print(f"Existing {target.name} saved as {backup(target)}")
    target.write_bytes(content)


def hook_scripts(entries: list[Any]) -> set[str]:
    """The file names of the hook scripts that the entries of a hook event run, such as guard-bash.py."""
    commands = [hook.get("command") for entry in entries if isinstance(entry, dict)
                for hook in entry.get("hooks") or [] if isinstance(hook, dict)]
    return {name for command in commands if isinstance(command, str) for name in HOOK_SCRIPT.findall(command)}


def merge(existing: dict[str, Any], template: dict[str, Any], kept: list[str], prefix: str = "") -> bool:
    """Adds what `existing` lacks from `template`: missing keys, and hook entries whose script no existing entry runs.
    Existing values and lists stay; each one that differs from the template is listed in `kept`. Returns whether
    anything was added."""
    changed = False
    for key, value in template.items():
        name = prefix + key
        if key not in existing:
            existing[key] = copy.deepcopy(value)
            changed = True
        elif isinstance(existing[key], dict) and isinstance(value, dict):
            changed |= merge(existing[key], value, kept, name + ".")
        elif prefix == "hooks." and isinstance(existing[key], list) and isinstance(value, list):
            # Compared by script, not as a whole: an entry with a changed timeout or interpreter is still the hook
            missing = [entry for entry in value
                       if entry not in existing[key] and not hook_scripts([entry]) & hook_scripts(existing[key])]
            existing[key].extend(copy.deepcopy(missing))
            changed |= bool(missing)
        elif isinstance(existing[key], list) and isinstance(value, list):
            if any(item not in existing[key] for item in value):
                kept.append(f"{name} = {json.dumps(existing[key])} (template: {json.dumps(value)})")
        elif existing[key] != value:
            kept.append(f"{name} = {json.dumps(existing[key])} (template: {json.dumps(value)})")
    return changed


def install_settings(template_path: Path, target: Path, existing: dict[str, Any] | None, label: str) -> None:
    """Copies the template to a missing settings file, else merges it in (written through a symlink, which dotfile
    setups use for ~/.claude/settings.json)."""
    if existing is None:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(template_path, target)
        print(f"Copied {label} to {target}")
        return
    kept: list[str] = []
    if merge(existing, json.loads(template_path.read_text(encoding="utf-8")), kept):
        name = backup(target)
        target.write_text(json.dumps(existing, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"Merged {label} into {target} (backup: {name})")
    for value in kept:
        print(f"Kept {value} in {target}")


def check_hook_python() -> None:
    """The hook runs `python3` from the PATH, which may be older than the interpreter running this script."""
    python = shutil.which("python3")
    ok = python is not None and subprocess.run(
        [python, "-c", "import sys; sys.exit(sys.version_info < (3, 13))"], capture_output=True).returncode == 0
    if not ok:
        print("Warning: python3 on the PATH is missing or older than 3.13, so the Bash guard hook won't run",
              file=sys.stderr)


def main(args: list[str]) -> None:
    target = Path(args[0] if args else ".")
    if not target.is_dir():
        fail(f"Project directory not found: {target}")
    target = target.resolve()
    if target == SOURCE:
        fail("Target is this repository itself; pass your project directory.")
    build_file = next((f for f in BUILD_FILES if (target / f).is_file()), None)
    if build_file is None:
        fail(f"No pom.xml, build.gradle(.kts) or settings.gradle(.kts) in {target}; "
             "create the project first (e.g. with Spring Initializr).")
    name = project_name(target, build_file)
    heading, _, rules = (CONFIG / "AGENTS.md").read_text(encoding="utf-8").partition("\n")
    if heading != PLACEHOLDER:
        fail(f"config/AGENTS.md must start with '{PLACEHOLDER}'")
    # Auto mode only works from user settings; Claude Code ignores it in project settings
    user_settings = Path(os.environ.get("CLAUDE_CONFIG_DIR") or Path.home() / ".claude") / "settings.json"
    project_settings = target / ".claude" / "settings.json"
    existing_project, existing_user = read_settings(project_settings), read_settings(user_settings)

    for source, dest in [(SOURCE / "agents", "agents"), (SOURCE / "skills", "skills"),
                         (CONFIG / ".claude" / "hooks", "hooks")]:
        shutil.copytree(source, target / ".claude" / dest, dirs_exist_ok=True)
    install_settings(CONFIG / ".claude" / "settings.json", project_settings, existing_project,
                     "project settings (Bash guard)")
    install_settings(CONFIG / ".claude" / "settings.user.json", user_settings, existing_user,
                     "user settings (auto mode)")
    install_root_file(f"# {name}\n{rules}".encode(), target / "AGENTS.md")
    install_root_file((CONFIG / "CLAUDE.md").read_bytes(), target / "CLAUDE.md")
    check_hook_python()
    print(f"Copied agents, skills, hooks, settings.json, AGENTS.md and CLAUDE.md to {target} (project: {name})")


if __name__ == "__main__":
    main(sys.argv[1:])
