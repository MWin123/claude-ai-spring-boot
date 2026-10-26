"""Agent and skill frontmatter is complete and valid for Claude Code."""
import json
import re

import pytest

from helpers import AGENTS, CONFIG, SKILLS, frontmatter, rel

NAME = re.compile(r"^[a-z0-9]+(-[a-z0-9]+)*$")
MODELS = {"opus", "sonnet", "haiku", "inherit"}
EFFORTS = {"low", "medium", "high", "xhigh", "max"}
TOOLS = {
    "Agent", "Bash", "Edit", "Glob", "Grep", "LS", "MultiEdit", "NotebookEdit", "Read",
    "Skill", "Task", "TodoWrite", "WebFetch", "WebSearch", "Write",
}


@pytest.mark.parametrize("path", AGENTS, ids=rel)
def test_agent_frontmatter(path):
    meta = frontmatter(path)

    assert meta.get("name") == path.stem, "name must match the file name"
    assert NAME.match(meta["name"]) and len(meta["name"]) <= 64
    assert isinstance(meta.get("description"), str) and meta["description"].strip()
    assert meta.get("model") in MODELS, f"model {meta.get('model')!r} not in {sorted(MODELS)}"
    if "effort" in meta:
        assert meta["effort"] in EFFORTS, f"effort {meta['effort']!r} not in {sorted(EFFORTS)}"
    tools = [t.strip() for t in meta.get("tools", "").split(",") if t.strip()]
    unknown = [t for t in tools if t not in TOOLS and not t.startswith("mcp__")]
    assert not unknown, f"unknown tools: {unknown}"
    assert len(tools) == len(set(tools)), "duplicate tools"


@pytest.mark.parametrize("path", SKILLS, ids=rel)
def test_skill_frontmatter(path):
    meta = frontmatter(path / "SKILL.md")

    assert meta.get("name") == path.name, "name must match the directory name"
    assert NAME.match(meta["name"]) and len(meta["name"]) <= 64
    assert isinstance(meta.get("description"), str) and 0 < len(meta["description"]) <= 1024
    version = (meta.get("metadata") or {}).get("version")
    if version is not None:
        assert re.fullmatch(r"\d+\.\d+\.\d+", str(version)), f"metadata.version {version!r} is not semver"


def test_settings_json_is_valid():
    settings = json.loads((CONFIG / "settings.json").read_text())
    assert isinstance(settings, dict)
