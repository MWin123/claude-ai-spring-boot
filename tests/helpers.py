"""Shared helpers for the Claude file tests: repository layout and Markdown parsing."""
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
AGENTS = sorted((ROOT / "agents").glob("*.md"))
SKILLS = sorted(p.parent for p in (ROOT / "skills").glob("*/SKILL.md"))
CONFIG = ROOT / "config"  # CLAUDE.md and settings.json for Spring Boot projects
CLAUDE_FILES = AGENTS + sorted((ROOT / "skills").rglob("*.md")) + [CONFIG / "CLAUDE.md"]
DOCS = CLAUDE_FILES + [ROOT / "README.md", ROOT / "CLAUDE.md"]


def rel(path: Path) -> str:
    return str(path.relative_to(ROOT))


def frontmatter(path: Path) -> dict:
    match = re.match(r"---\n(.*?)\n---\n", path.read_text(), re.S)
    assert match, f"{rel(path)}: no YAML frontmatter"
    return yaml.safe_load(match.group(1))


def headings(text: str) -> list[tuple[int, str]]:
    """(offset, title) of every Markdown heading outside code blocks."""
    prose = code_blocks_blanked(text)
    return [(m.start(), m.group(1).strip()) for m in re.finditer(r"^#+\s+(.+)$", prose, re.M)]


@dataclass
class CodeBlock:
    lang: str
    body: str
    line: int  # line of the first body line in the file


def code_blocks(text: str) -> list[CodeBlock]:
    return [
        CodeBlock(m.group(1), m.group(2), text[: m.start()].count("\n") + 2)
        for m in re.finditer(r"^```(\w*)\n(.*?)^```", text, re.S | re.M)
    ]


def code_blocks_blanked(text: str) -> str:
    """The text with code blocks replaced by blank lines, so offsets and line numbers stay valid."""
    return re.sub(r"^```.*?^```", lambda m: re.sub(r"[^\n]", " ", m.group(0)), text, flags=re.S | re.M)


def line_of(text: str, offset: int) -> int:
    return text[:offset].count("\n") + 1
