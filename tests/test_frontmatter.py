"""Agent and skill frontmatter is complete and valid for Claude Code."""
import json
import re

import pytest

from helpers import AGENTS, CONFIG, ROOT, SKILLS, frontmatter, rel

NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MODELS = {"opus", "sonnet", "haiku", "fable", "inherit"}
EFFORTS = {"low", "medium", "high", "xhigh", "max"}
COLORS = {"red", "blue", "green", "yellow", "purple", "orange", "pink", "cyan"}
TOOLS = {
    "Agent", "Bash", "Edit", "Glob", "Grep", "LS", "MultiEdit", "NotebookEdit", "Read",
    "Skill", "Task", "TodoWrite", "WebFetch", "WebSearch", "Write",
}
# Claude Code ignores unknown frontmatter fields without an error, so a typo would silently do nothing
AGENT_FIELDS = {
    "name", "description", "tools", "disallowedTools", "model", "permissionMode", "maxTurns",
    "autoCompactWindow", "skills", "mcpServers", "hooks", "memory", "background", "omitClaudeMd",
    "effort", "isolation", "color", "initialPrompt", "experimental",
}
SKILL_FIELDS = {
    "name", "description", "when_to_use", "argument-hint", "arguments", "disable-model-invocation",
    "user-invocable", "allowed-tools", "disallowed-tools", "model", "effort", "context", "agent",
    "background", "hooks", "paths", "shell", "metadata", "license", "compatibility",
}
LISTING_LIMIT = 1536  # description + when_to_use are cut at this length in the skill listing
SKILL_MAX_LINES = 500  # longer content belongs in references/


@pytest.mark.parametrize("path", AGENTS, ids=rel)
def test_agent_frontmatter(path):
    meta = frontmatter(path)

    unknown = sorted(set(meta) - AGENT_FIELDS)
    assert not unknown, f"fields Claude Code does not know: {unknown}"
    assert meta.get("name") == path.stem, "name must match the file name"
    assert NAME.match(meta["name"]) and len(meta["name"]) <= 64
    assert isinstance(meta.get("description"), str) and meta["description"].strip()
    model = meta.get("model")
    assert model in MODELS or str(model).startswith("claude-"), f"model {model!r} not in {sorted(MODELS)}"
    if "effort" in meta:
        assert meta["effort"] in EFFORTS, f"effort {meta['effort']!r} not in {sorted(EFFORTS)}"
    if "color" in meta:
        assert meta["color"] in COLORS, f"color {meta['color']!r} not in {sorted(COLORS)}"
    tools = [t.strip() for t in meta.get("tools", "").split(",") if t.strip()]
    unknown = [t for t in tools if t not in TOOLS and not t.startswith("mcp__")]
    assert not unknown, f"unknown tools: {unknown}"
    assert len(tools) == len(set(tools)), "duplicate tools"
    # Claude Code skips a missing preloaded skill silently, so a renamed skill must fail here
    skills = meta.get("skills", [])
    assert isinstance(skills, list) and len(skills) == len(set(skills)), "skills must be a list of unique names"
    for name in skills:
        assert name in {p.name for p in SKILLS}, f"preloaded skill {name!r} does not exist"
        assert not frontmatter(ROOT / "skills" / name / "SKILL.md").get("disable-model-invocation"), (
            f"preloaded skill {name!r} sets disable-model-invocation, so it can't be preloaded"
        )


@pytest.mark.parametrize("path", SKILLS, ids=rel)
def test_skill_frontmatter(path):
    meta = frontmatter(path / "SKILL.md")

    unknown = sorted(set(meta) - SKILL_FIELDS)
    assert not unknown, f"fields Claude Code does not know: {unknown}"
    assert meta.get("name") == path.name, "name must match the directory name"
    assert NAME.match(meta["name"]) and len(meta["name"]) <= 64
    assert isinstance(meta.get("description"), str) and 0 < len(meta["description"]) <= 1024
    listing = meta["description"] + meta.get("when_to_use", "")
    assert len(listing) <= LISTING_LIMIT, f"description + when_to_use is {len(listing)} characters"
    version = (meta.get("metadata") or {}).get("version")
    if version is not None:
        assert re.fullmatch(r"\d+\.\d+\.\d+", str(version)), f"metadata.version {version!r} is not semver"


@pytest.mark.parametrize("path", SKILLS, ids=rel)
def test_skill_stays_short(path):
    lines = len((path / "SKILL.md").read_text().splitlines())
    assert lines <= SKILL_MAX_LINES, f"{lines} lines; move details to references/"


@pytest.mark.parametrize("path", SKILLS, ids=rel)
def test_trigger_phrases_live_in_when_to_use(path):
    """A "When to Use" body section is read only after the skill loaded, so it can't trigger it."""
    assert "\n## When to Use\n" not in (path / "SKILL.md").read_text(), "move the list into when_to_use"


def test_settings_json_is_valid():
    settings = json.loads((CONFIG / "settings.json").read_text())
    assert isinstance(settings, dict)
