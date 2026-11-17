"""The agent-log.py hook writes one JSONL line per prompt, subagent call and subagent stop, and never blocks."""
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from helpers import ROOT

HOOK = ROOT / ".claude" / "hooks" / "agent-log.py"


def run_hook(event: dict[str, Any] | str, project: Path) -> list[dict[str, Any]]:
    """Runs the hook on one event and returns every line of the log."""
    result = subprocess.run(
        [sys.executable, str(HOOK)],
        input=event if isinstance(event, str) else json.dumps({"session_id": "s1", **event}),
        capture_output=True, text=True, env={"CLAUDE_PROJECT_DIR": str(project)},
    )
    assert result.returncode == 0, result.stderr
    assert result.stdout == ""  # UserPromptSubmit would add stdout to the model's context
    log = project / ".claude" / "agent-log.jsonl"
    return [json.loads(line) for line in log.read_text().splitlines()] if log.exists() else []


def agent_call(prompt: str, **tool_input: str) -> dict[str, Any]:
    return {"hook_event_name": "PreToolUse", "tool_name": "Agent", "tool_use_id": "t1",
            "tool_input": {"description": "Find versions", "prompt": prompt, **tool_input}}


def test_logs_prompts_sessions_and_stops(tmp_path: Path) -> None:
    run_hook({"hook_event_name": "SessionStart", "source": "startup", "model": "claude-opus-5-5"}, tmp_path)
    run_hook({"hook_event_name": "UserPromptSubmit", "prompt": "Where are the Boot versions?"}, tmp_path)
    lines = run_hook({"hook_event_name": "SubagentStop", "agent_id": "a1", "agent_type": "Explore",
                      "last_assistant_message": "Found 3", "agent_transcript_path": "/t/a1.jsonl"}, tmp_path)

    assert [{k: v for k, v in line.items() if k != "time"} for line in lines] == [
        {"session_id": "s1", "event": "session", "source": "startup", "model": "claude-opus-5-5"},
        {"session_id": "s1", "event": "prompt", "prompt": "Where are the Boot versions?"},
        {"session_id": "s1", "agent_id": "a1", "event": "agent_stop", "agent_type": "Explore", "internal": False,
         "output": "Found 3", "transcript": "/t/a1.jsonl"},
    ]


@pytest.mark.parametrize("agent_type", ["", None])
def test_tags_stops_without_a_type_as_internal(agent_type: str | None, tmp_path: Path) -> None:
    """Claude Code's own helper calls, such as the next-prompt suggestion, stop without an agent type."""
    event = {"hook_event_name": "SubagentStop", "agent_id": "a2", "last_assistant_message": "create a PR"}
    [line] = run_hook(event | ({} if agent_type is None else {"agent_type": agent_type}), tmp_path)

    assert line["internal"] is True


@pytest.mark.parametrize(("prompt", "breadth"), [
    ("Search skills/, very thorough.", "very thorough"),
    ("Very Thorough: check every medium", "very thorough"),
    ("Medium search for matchers", "medium"),
    ("quick: find install.py", "quick"),
    ("Find the intermediate step quickly", None),
])
def test_logs_agent_calls_with_breadth(prompt: str, breadth: str | None, tmp_path: Path) -> None:
    [line] = run_hook(agent_call(prompt, subagent_type="Explore"), tmp_path)

    assert line["event"] == "agent_call"
    assert line["subagent_type"] == "Explore"
    assert line["breadth"] == breadth
    assert line["tool_use_id"] == "t1"


def test_agent_call_without_type_is_general_purpose(tmp_path: Path) -> None:
    [line] = run_hook(agent_call("Fix the hook"), tmp_path)

    assert line["subagent_type"] == "general-purpose"


def test_agent_call_inside_a_subagent_keeps_its_id(tmp_path: Path) -> None:
    [line] = run_hook(agent_call("Search", subagent_type="Explore") | {"agent_id": "parent"}, tmp_path)

    assert line["agent_id"] == "parent"


@pytest.mark.parametrize("event", [
    {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {"command": "ls"}},
    {"hook_event_name": "Stop"},
    "not json",
])
def test_ignores_other_events_and_bad_input(event: dict[str, Any] | str, tmp_path: Path) -> None:
    assert run_hook(event, tmp_path) == []


def test_settings_run_the_hook_for_each_logged_event() -> None:
    hooks = json.loads((ROOT / ".claude" / "settings.json").read_text())["hooks"]
    command = 'python3 "${CLAUDE_PROJECT_DIR}/.claude/hooks/agent-log.py"'

    def commands(event: str, matcher: str | None = None) -> list[str]:
        return [hook["command"] for group in hooks[event] if group.get("matcher") == matcher for hook in group["hooks"]]

    for event in ["SessionStart", "UserPromptSubmit", "SubagentStop"]:
        assert command in commands(event), event
    assert command in commands("PreToolUse", "Agent")
