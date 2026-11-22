"""The installed CLAUDE.md imports AGENTS.md, which imports the conventions skill; every `@path` import resolves."""
import os
import re
from collections.abc import Iterator
from pathlib import Path

import pytest

from helpers import code_blocks_blanked
from install_fixtures import install

pytestmark = pytest.mark.usefixtures("user_settings")  # install.py reads CLAUDE_CONFIG_DIR, so no test touches the real ~/.claude

IMPORT = re.compile(r"(?:^|\s)@((?:[^\s\\]|\\ )+)")  # Claude Code's own pattern for CLAUDE.md imports
MAX_HOPS = 4


def imports(path: Path) -> Iterator[tuple[str, Path]]:
    """The files a memory file imports, parsed as Claude Code does: `@path` outside frontmatter and code, relative to the file."""
    text = re.sub(r"\A---\n.*?\n---\n", "", path.read_text(), flags=re.S)
    text = re.sub(r"`[^`\n]*`", " ", code_blocks_blanked(text))
    for m in IMPORT.finditer(text):
        name = m.group(1).split("#", 1)[0].replace("\\ ", " ")
        if re.match(r"~/|/.|[a-zA-Z0-9._-]", name):  # what Claude Code accepts as a path
            yield name, Path(os.path.normpath(path.parent / Path(name).expanduser()))


def test_claude_md_imports_resolve(project: Path) -> None:
    """Every import in the installed CLAUDE.md, and in the files it imports, is a file install.py installed."""
    install(project)
    loaded: set[Path] = set()
    missing: list[str] = []
    todo = [(project / "CLAUDE.md", 0)]
    while todo:
        path, hops = todo.pop()
        for name, target in imports(path) if hops < MAX_HOPS else ():
            if not target.is_file():
                missing.append(f"{path.relative_to(project)}: @{name}")
            elif target not in loaded:
                loaded.add(target)
                todo.append((target, hops + 1))
    assert not missing, "\n".join(missing)
    assert project / "AGENTS.md" in loaded, "CLAUDE.md must import AGENTS.md"
    assert project / ".claude" / "skills" / "conventions" / "SKILL.md" in loaded, "AGENTS.md must import conventions"
