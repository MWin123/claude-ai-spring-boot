"""Appends one JSONL line per prompt, subagent call and subagent stop to .claude/agent-log.jsonl.

Prompts give the denominator for subagent use: with `jq`, count `agent_call` lines per `subagent_type`
against `prompt` lines per session. Never blocks and prints nothing: on UserPromptSubmit, stdout would
be added to the model's context.
"""

import json
import os
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

BREADTHS = [("very thorough", r"very thorough"), ("medium", r"\bmedium\b"), ("quick", r"\bquick\b")]


def breadth(prompt: str) -> str | None:
    """The search breadth named in a subagent prompt, the broadest first."""
    return next((name for name, pattern in BREADTHS if re.search(pattern, prompt, re.IGNORECASE)), None)


def record(event: dict[str, Any]) -> dict[str, Any] | None:
    name = event.get("hook_event_name")
    line: dict[str, Any] = {"time": datetime.now(UTC).isoformat(timespec="seconds"), "session_id": event.get("session_id")}
    if event.get("agent_id"):
        line["agent_id"] = event["agent_id"]  # the hook fired inside a subagent
    match name:
        case "SessionStart":
            return line | {"event": "session", "source": event.get("source"), "model": event.get("model")}
        case "UserPromptSubmit":
            return line | {"event": "prompt", "prompt": event.get("prompt")}
        case "PreToolUse" if event.get("tool_name") == "Agent":
            tool_input = event.get("tool_input") or {}
            prompt = str(tool_input.get("prompt", ""))
            return line | {
                "event": "agent_call",
                "subagent_type": tool_input.get("subagent_type") or "general-purpose",
                "description": tool_input.get("description"),
                "breadth": breadth(prompt),
                "tool_use_id": event.get("tool_use_id"),
            }
        case "SubagentStop":
            return line | {
                "event": "agent_stop",
                "agent_id": event.get("agent_id"),
                "agent_type": event.get("agent_type"),
                # Claude Code's own helper calls (e.g. the next-prompt suggestion) stop without a type
                "internal": not event.get("agent_type"),
                "output": event.get("last_assistant_message"),
                "transcript": event.get("agent_transcript_path"),
            }
    return None


def main() -> None:
    try:
        event = json.load(sys.stdin)
        line = record(event)
        if line is None:
            return
        project = Path(os.environ.get("CLAUDE_PROJECT_DIR") or event.get("cwd") or ".")
        log = project / ".claude" / "agent-log.jsonl"
        log.parent.mkdir(parents=True, exist_ok=True)
        with log.open("a", encoding="utf-8") as file:
            file.write(json.dumps(line, ensure_ascii=False) + "\n")
    except Exception as error:  # logging must never get in the way of the session
        print(f"agent-log.py: {error}", file=sys.stderr)


if __name__ == "__main__":
    main()
