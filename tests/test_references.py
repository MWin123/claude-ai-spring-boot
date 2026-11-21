"""References between the Claude files point at sections, files, steps, skills and agents that exist."""
import re
from pathlib import Path

import pytest

from helpers import (
    AGENTS, CLAUDE_FILES, CONFIG, DOCS, FOLDER_READMES, ROOT, SKILLS, code_blocks_blanked, headings,
    line_of, rel, slug,
)

AGENT_NAMES = {p.stem for p in AGENTS}
SKILL_NAMES = {p.name for p in SKILLS}
EXTERNAL_SKILLS = {"image-fetcher"}  # installed in the user's Claude environment, not shipped by this template
DOCS_BY_NAME: dict[str, list[Path]] = {}
for doc in DOCS:
    DOCS_BY_NAME.setdefault(doc.name, []).append(doc)


def prose(path: Path) -> str:
    """File text with code blocks blanked, so examples and templates are not checked as references."""
    return code_blocks_blanked(path.read_text())


def resolve(name: str, path: Path) -> Path | None:
    """A referenced Markdown file: a path relative to the repo, the citing skill, or a unique file name."""
    if name in ("AGENTS.md", "CLAUDE.md") and path in CLAUDE_FILES:
        return CONFIG / name  # the project's file, not this repository's
    for base in (ROOT, path.parent, path.parent.parent):
        if (base / name).is_file():
            return base / name
    if name == "SKILL.md":
        return SKILLS[0] / name  # a bare `SKILL.md` means every skill's entry file, not one of them
    matches = DOCS_BY_NAME.get(name.rsplit("/", 1)[-1], [])
    assert len(matches) <= 1, f"{rel(path)}: `{name}` is ambiguous: {[rel(m) for m in matches]}"
    return matches[0] if matches else None


@pytest.mark.parametrize("path", DOCS, ids=rel)
def test_section_references_exist(path: Path) -> None:
    """`"Section" in `file.md``, `"Section" below` and `"Section" above` name a heading (prefix match)."""
    text = prose(path)
    problems = []
    for m in re.finditer(r'"([A-Z][^"\n]{2,80})"\s+(?:in\s+`([\w./-]+\.md)`|(below)|(above))', text):
        section, ref, below, above = m.groups()
        target = resolve(ref, path) if ref else path
        if target is None:
            problems.append(f"line {line_of(text, m.start())}: `{ref}` not found")
            continue
        found = [off for off, title in headings(target.read_text()) if title.startswith(section)]
        if below:
            found = [off for off in found if off > m.start()]
        if above:
            found = [off for off in found if off < m.start()]
        if not found:
            where = ref or ("below" if below else "above")
            problems.append(f'line {line_of(text, m.start())}: no section "{section}" {where}')
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("path", DOCS, ids=rel)
def test_file_references_exist(path: Path) -> None:
    text = prose(path)
    missing = [
        f"line {line_of(text, m.start())}: `{m.group(1)}`"
        for m in re.finditer(r"`((?:references/)?[\w-]+\.md)`", text)
        if resolve(m.group(1), path) is None
    ]
    # Installed paths (`.claude/skills/java-modern/SKILL.md`) map to this repository's agents/ and skills/
    missing += [
        f"line {line_of(text, m.start())}: `{m.group(0).strip('`')}`"
        for m in re.finditer(r"`\.claude/((?:agents|skills)/[\w./-]+\.md)`", text)
        if not (ROOT / m.group(1)).is_file()
    ]
    # A file of another skill is cited with that skill: "`web.md` in the `spring-boot` skill"
    def skill_of(p: Path) -> Path | None:
        return next((s for s in SKILLS if s in p.parents), None)

    for m in re.finditer(r"(?<!` )`((?:references/)?[\w-]+\.md)`(?! (?:in|of) the `)", text):
        target = resolve(m.group(1), path)
        skill = skill_of(target) if target and target.name != "SKILL.md" else None
        if skill and skill != skill_of(path):
            missing.append(f"line {line_of(text, m.start())}: `{m.group(1)}` is in the `{skill.name}` skill; name it")
    assert not missing, "\n".join(missing)


@pytest.mark.parametrize("path", DOCS, ids=rel)
def test_skill_and_agent_references_exist(path: Path) -> None:
    text = prose(path)
    problems = []
    for m in re.finditer(r"`([a-z0-9-]+)` (skill|agent)s?\b", text):
        name, kind = m.groups()
        if name not in (SKILL_NAMES | EXTERNAL_SKILLS if kind == "skill" else AGENT_NAMES):
            problems.append(f"line {line_of(text, m.start())}: no {kind} `{name}`")
    # Agent names by their suffix, wherever they appear ("pass them to `devops-engineer`"); skills may share a suffix
    for m in re.finditer(r"`([a-z0-9-]+-(?:engineer|specialist|reviewer|migration))`", text):
        if m.group(1) not in AGENT_NAMES | SKILL_NAMES:
            problems.append(f"line {line_of(text, m.start())}: no agent `{m.group(1)}`")
    # "`spring-boot` `references/web.md`": the reference file belongs to that skill
    for m in re.finditer(r"`([a-z0-9-]+)` `(references/[\w-]+\.md)`", text):
        if not (ROOT / "skills" / m.group(1) / m.group(2)).is_file():
            problems.append(f"line {line_of(text, m.start())}: no skills/{m.group(1)}/{m.group(2)}")
    # "`web.md` in the `spring-boot` skill": the file is in that skill, not just somewhere
    for m in re.finditer(r"`(?:references/)?([\w-]+\.md)` (?:in|of) the `([a-z0-9-]+)` skill", text):
        file, skill = m.groups()
        if not any((ROOT / "skills" / skill / sub / file).is_file() for sub in ("", "references")):
            problems.append(f"line {line_of(text, m.start())}: no {file} in skills/{skill}")
    assert not problems, "\n".join(problems)


@pytest.mark.parametrize("path", AGENTS + [s / "SKILL.md" for s in SKILLS], ids=rel)
def test_workflow_step_references_exist(path: Path) -> None:
    text = path.read_text()
    workflow = re.split(r"^## (?:Core )?Workflow$", text, maxsplit=1, flags=re.M)
    steps = set(re.findall(r"^(\d+)\. ", workflow[1].split("\n## ", 1)[0], re.M)) if len(workflow) > 1 else set()
    missing = [n for n in re.findall(r"Workflow step (\d+)", text) if n not in steps]
    assert not missing, f"Workflow steps {missing} do not exist (steps: {sorted(steps, key=int)})"


@pytest.mark.parametrize("path", [s for s in SKILLS if (s / "references").is_dir()], ids=rel)
def test_reference_files_are_listed_in_their_skill(path: Path) -> None:
    """Claude only finds a reference file through its SKILL.md."""
    skill = (path / "SKILL.md").read_text()
    unlisted = [p.name for p in (path / "references").glob("*.md") if f"`references/{p.name}`" not in skill]
    assert not unlisted, f"not listed in SKILL.md: {unlisted}"


@pytest.mark.parametrize("skill", SKILLS, ids=lambda s: s.name)
def test_every_skill_is_referenced(skill: Path) -> None:
    """Besides its description, each skill is reachable from the project AGENTS.md, an agent or another skill."""
    others = [p for p in CLAUDE_FILES if skill not in p.parents]
    assert any(f"`{skill.name}`" in prose(p) for p in others), f"no other Claude file names `{skill.name}`"


def test_every_agent_is_routed_from_claude_md() -> None:
    subagents = (CONFIG / "AGENTS.md").read_text().split("## Subagents", 1)[1].split("\n## ", 1)[0]
    missing = sorted(name for name in AGENT_NAMES if f"`{name}`" not in subagents)
    assert not missing, f"config/AGENTS.md does not say when to use {missing}"


def test_every_skill_is_routed_from_claude_md() -> None:
    """The main loop loads skills from the AGENTS.md Skills section; review-checklist is preloaded by code-reviewer."""
    skills = (CONFIG / "AGENTS.md").read_text().split("## Skills", 1)[1].split("\n## ", 1)[0]
    missing = sorted(name for name in SKILL_NAMES - {"review-checklist"} if f"`{name}`" not in skills)
    assert not missing, f"config/AGENTS.md does not say when to use {missing}"


AGENTS_README = ROOT / "agents" / "README.md"
SKILLS_README = ROOT / "skills" / "README.md"
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


def test_readme_links_resolve() -> None:
    """Relative Markdown links in the READMEs point at existing files; a fragment on a Markdown file names a heading."""
    for readme in [ROOT / "README.md", *FOLDER_READMES]:
        links = re.findall(r"\]\((?!https?:|#)([^)#\s]+)(?:#([^)\s]*))?\)", code_blocks_blanked(readme.read_text()))
        for link, fragment in links:
            target = readme.parent / link
            assert target.exists(), f"{rel(readme)}: broken link {link}"
            if fragment and target.suffix == ".md":
                slugs = {slug(title) for _, title in headings(target.read_text())}
                assert fragment in slugs, f"{rel(readme)}: {link} has no heading #{fragment}"


def test_readme_line_anchors_match() -> None:
    """A link such as [`CHECKS`](guard-bash.py#L445) points at the line that defines that name; line links take no other form."""
    for readme in [ROOT / "README.md", *FOLDER_READMES]:
        text = readme.read_text()
        links = re.findall(r"\[`(\w+)`\]\(([^)#\s]+)#L(\d+)\)", text)
        assert len(links) == len(re.findall(r"\]\([^)\s]*#L\d", text)), f"{rel(readme)}: a line link needs a [`NAME`] text"
        for name, file, line in links:
            target = (readme.parent / file).read_text().splitlines()[int(line) - 1]
            defines = re.match(rf"(?:def |class )?{name}\b\s*[:=(]", target)
            assert defines, f"{rel(readme)}: line {line} of {file} does not define `{name}`: {target!r}"


def test_readme_reference_guide_count() -> None:
    readme = SKILLS_README.read_text()
    for skill in SKILLS:
        count = len(list((skill / "references").glob("*.md")))
        m = re.search(rf"^\| \[`{skill.name}`\]\([^)]+\) \|.*?(\d+) reference guides?\b", readme, re.M)
        stated = int(m.group(1)) if m else 0
        assert stated == count, f"README says {stated} reference guides for {skill.name}, found {count}"
