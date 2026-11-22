"""References between the Claude files point at sections, files, steps, skills and agents that exist."""
import re
from pathlib import Path

import pytest

from helpers import (
    AGENT_NAMES, AGENTS, CLAUDE_FILES, CONFIG, DOCS, ROOT, SKILL_NAMES, SKILLS, code_blocks_blanked, frontmatter,
    headings, line_of, rel,
)

EXTERNAL_SKILLS = {"image-fetcher"}  # installed in the user's Claude environment, not shipped by this template
PRELOADED_ONLY = {"review-checklist"}  # loaded by an agent's `skills:` frontmatter, so config/AGENTS.md need not route it
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


def test_every_agent_is_routed_from_claude_md() -> None:
    subagents = (CONFIG / "AGENTS.md").read_text().split("## Subagents", 1)[1].split("\n## ", 1)[0]
    missing = sorted(name for name in AGENT_NAMES if f"`{name}`" not in subagents)
    assert not missing, f"config/AGENTS.md does not say when to use {missing}"


def test_every_skill_is_routed_from_claude_md() -> None:
    """The main loop loads skills from the AGENTS.md Skills section; only the PRELOADED_ONLY skills need no routing."""
    skills = (CONFIG / "AGENTS.md").read_text().split("## Skills", 1)[1].split("\n## ", 1)[0]
    missing = sorted(name for name in SKILL_NAMES - PRELOADED_ONLY if f"`{name}`" not in skills)
    assert not missing, f"config/AGENTS.md does not say when to use {missing}"


def test_routing_exemptions_are_preloaded() -> None:
    """An exemption from routing holds only while some agent still preloads the skill."""
    preloaded = {name for agent in AGENTS for name in frontmatter(agent).get("skills", [])}
    assert PRELOADED_ONLY <= preloaded, f"no agent preloads {sorted(PRELOADED_ONLY - preloaded)}"
