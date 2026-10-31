"""References between the Claude files point at sections, files, steps, skills and agents that exist."""
import re

import pytest

from helpers import (
    AGENTS, CLAUDE_FILES, CONFIG, DOCS, ROOT, SKILLS, code_blocks, code_blocks_blanked, headings, line_of, rel,
)

AGENT_NAMES = {p.stem for p in AGENTS}
SKILL_NAMES = {p.name for p in SKILLS}
DOCS_BY_NAME = {}
for doc in DOCS:
    DOCS_BY_NAME.setdefault(doc.name, []).append(doc)


def prose(path):
    """File text with code blocks blanked, so examples and templates are not checked as references."""
    return code_blocks_blanked(path.read_text())


def resolve(name, path):
    """A referenced Markdown file: a path relative to the repo, the citing skill, or a unique file name."""
    if name == "CLAUDE.md" and path in CLAUDE_FILES:
        return CONFIG / "CLAUDE.md"  # the project's CLAUDE.md, not this repository's
    for base in (ROOT, path.parent, path.parent.parent):
        if (base / name).is_file():
            return base / name
    matches = DOCS_BY_NAME.get(name.rsplit("/", 1)[-1], [])
    assert len(matches) <= 1, f"{rel(path)}: `{name}` is ambiguous: {[rel(m) for m in matches]}"
    return matches[0] if matches else None


@pytest.mark.parametrize("path", DOCS, ids=rel)
def test_section_references_exist(path):
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
def test_file_references_exist(path):
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
    assert not missing, "\n".join(missing)


@pytest.mark.parametrize("path", DOCS, ids=rel)
def test_skill_and_agent_references_exist(path):
    text = prose(path)
    problems = []
    for m in re.finditer(r"`([a-z0-9-]+)` (skill|agent)s?\b", text):
        name, kind = m.groups()
        if name not in (SKILL_NAMES if kind == "skill" else AGENT_NAMES):
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
def test_workflow_step_references_exist(path):
    text = path.read_text()
    workflow = re.split(r"^## (?:Core )?Workflow$", text, maxsplit=1, flags=re.M)
    steps = set(re.findall(r"^(\d+)\. ", workflow[1].split("\n## ", 1)[0], re.M)) if len(workflow) > 1 else set()
    missing = [n for n in re.findall(r"Workflow step (\d+)", text) if n not in steps]
    assert not missing, f"Workflow steps {missing} do not exist (steps: {sorted(steps, key=int)})"


@pytest.mark.parametrize("path", [s for s in SKILLS if (s / "references").is_dir()], ids=rel)
def test_reference_files_are_listed_in_their_skill(path):
    """Claude only finds a reference file through its SKILL.md."""
    skill = (path / "SKILL.md").read_text()
    unlisted = [p.name for p in (path / "references").glob("*.md") if f"`references/{p.name}`" not in skill]
    assert not unlisted, f"not listed in SKILL.md: {unlisted}"


@pytest.mark.parametrize("skill", SKILLS, ids=lambda s: s.name)
def test_every_skill_is_referenced(skill):
    """Besides its description, each skill is reachable from the project CLAUDE.md, an agent or another skill."""
    others = [p for p in CLAUDE_FILES if skill not in p.parents]
    assert any(f"`{skill.name}`" in prose(p) for p in others), f"no other Claude file names `{skill.name}`"


def test_every_agent_is_routed_from_claude_md():
    subagents = (CONFIG / "CLAUDE.md").read_text().split("## Subagents", 1)[1].split("\n## ", 1)[0]
    missing = sorted(name for name in AGENT_NAMES if f"`{name}`" not in subagents)
    assert not missing, f"config/CLAUDE.md does not say when to use {missing}"


def test_every_skill_is_routed_from_claude_md():
    """The main loop loads skills from the CLAUDE.md Skills section; review-checklist is preloaded by the reviewers."""
    skills = (CONFIG / "CLAUDE.md").read_text().split("## Skills", 1)[1].split("\n## ", 1)[0]
    missing = sorted(name for name in SKILL_NAMES - {"review-checklist"} if f"`{name}`" not in skills)
    assert not missing, f"config/CLAUDE.md does not say when to use {missing}"


def readme_section(title):
    text = (ROOT / "README.md").read_text()
    return text.split(f"### {title}", 1)[1].split("\n#", 1)[0]


def test_readme_lists_every_agent():
    listed = set(re.findall(r"^\| `([a-z0-9-]+)` \|", readme_section("Agents (`agents/`)"), re.M))
    assert listed == AGENT_NAMES


def test_readme_lists_every_skill():
    listed = set(re.findall(r"^\| `([a-z0-9-]+)` \|", readme_section("Skills (`skills/`)"), re.M))
    assert listed == SKILL_NAMES


def test_readme_directory_tree_matches():
    readme = (ROOT / "README.md").read_text()
    tree = next(b.body for b in code_blocks(readme) if "├── agents/" in b.body)
    expected = [f"{p.name}" for p in AGENTS] + [f"{p.name}/" for p in SKILLS]
    expected += [p.name for p in (ROOT / "skills").glob("*/references/*.md")]
    missing = [name for name in expected if name not in tree]
    assert not missing, f"missing from the README directory tree: {missing}"


def test_readme_reference_guide_count():
    readme = (ROOT / "README.md").read_text()
    for skill in SKILLS:
        count = len(list((skill / "references").glob("*.md")))
        m = re.search(rf"^\| `{skill.name}` \|.*?(\d+) reference guides", readme, re.M)
        if m:
            assert int(m.group(1)) == count, f"README says {m.group(1)} reference guides for {skill.name}, found {count}"
