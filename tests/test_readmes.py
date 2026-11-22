"""The READMEs list every agent and skill, and their links and line anchors point at what exists."""
import re
from pathlib import Path

import pytest

from helpers import AGENT_NAMES, FOLDER_READMES, ROOT, SKILL_NAMES, SKILLS, code_blocks_blanked, headings, rel, slug

AGENTS_README = ROOT / "agents" / "README.md"
SKILLS_README = ROOT / "skills" / "README.md"
README_FILES = [ROOT / "README.md", *FOLDER_READMES]
TABLE_ROW = re.compile(r"^\| \[`([a-z0-9-]+)`\]\(([^)]+)\) \|", re.M)


@pytest.mark.parametrize(("readme", "names", "link"),
                         [(AGENTS_README, AGENT_NAMES, "{}.md"), (SKILLS_README, SKILL_NAMES, "{}/SKILL.md")],
                         ids=["agents", "skills"])
def test_readme_table_lists_every_entry(readme: Path, names: set[str], link: str) -> None:
    """Each agent or skill has one row, which links to its own file."""
    rows = TABLE_ROW.findall(readme.read_text())
    assert sorted(name for name, _ in rows) == sorted(names)
    wrong = [f"{name} -> {target}" for name, target in rows if target != link.format(name)]
    assert not wrong, f"{rel(readme)}: rows link to another file: {wrong}"


@pytest.mark.parametrize("readme", README_FILES, ids=rel)
def test_readme_links_resolve(readme: Path) -> None:
    """Relative Markdown links point at existing files; a fragment on a Markdown file names a heading."""
    links = re.findall(r"\]\((?!https?:|#)([^)#\s]+)(?:#([^)\s]*))?\)", code_blocks_blanked(readme.read_text()))
    for link, fragment in links:
        target = readme.parent / link
        assert target.exists(), f"broken link {link}"
        if fragment and target.suffix == ".md":
            slugs = {slug(title) for _, title in headings(target.read_text())}
            assert fragment in slugs, f"{link} has no heading #{fragment}"


@pytest.mark.parametrize("readme", README_FILES, ids=rel)
def test_readme_line_anchors_match(readme: Path) -> None:
    """A link such as [`CHECKS`](guard-bash.py#L445) points at the line that defines that name; line links take no other form."""
    text = readme.read_text()
    links = re.findall(r"\[`(\w+)`\]\(([^)#\s]+)#L(\d+)\)", text)
    assert len(links) == len(re.findall(r"\]\([^)\s]*#L\d", text)), "a line link needs a [`NAME`] text"
    for name, file, line in links:
        target = (readme.parent / file).read_text().splitlines()[int(line) - 1]
        assert re.match(rf"(?:def |class )?{name}\b\s*[:=(]", target), f"line {line} of {file} does not define `{name}`: {target!r}"


@pytest.mark.parametrize("skill", SKILLS, ids=lambda skill: skill.name)
def test_readme_reference_guide_count(skill: Path) -> None:
    count = len(list((skill / "references").glob("*.md")))
    m = re.search(rf"^\| \[`{skill.name}`\]\([^)]+\) \|.*?(\d+) reference guides?\b", SKILLS_README.read_text(), re.M)
    stated = int(m.group(1)) if m else 0
    assert stated == count, f"README says {stated} reference guides for {skill.name}, found {count}"
