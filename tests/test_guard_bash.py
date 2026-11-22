"""The guard-bash.py hook denies destructive Bash commands in any spelling and lets everything else pass."""
import json
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest
import yaml

from helpers import CONFIG

HOOK = CONFIG / ".claude" / "hooks" / "guard-bash.py"

CASES_FILE = Path(__file__).parent / "data" / "guard_bash.yaml"
COMMANDS = yaml.safe_load(CASES_FILE.read_text())
DENIED, ALLOWED = COMMANDS["denied"], COMMANDS["allowed"]


def run_hook(
    command: str, cwd: Path, home: Path, project: Path | None = None, tool: str = "Bash"
) -> dict[str, Any] | None:
    event = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"command": command}, "cwd": str(cwd)}
    env = {"HOME": str(home), "CLAUDE_PROJECT_DIR": str(project or cwd), "PATH": "/usr/local/bin:/usr/bin:/bin"}
    result = subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(event), capture_output=True, text=True, env=env
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"] if result.stdout else None


@pytest.fixture
def home(tmp_path: Path) -> Path:
    (tmp_path / "home").mkdir()
    return tmp_path / "home"


@pytest.fixture
def project(home: Path) -> Path:
    project = home / "code" / "demo"
    (project / "build").mkdir(parents=True)
    return project


def test_cases_are_strings_written_as_they_run() -> None:
    """YAML turns `- yes` into True and drops the comment of `- ls # rm -rf /`, so every case is quoted or a `|-` block."""
    for name, cases in COMMANDS.items():
        assert all(isinstance(case, str) for case in cases), f"{name}: a case is not a string"
        assert [case for case in cases if not case.strip()] == ([""] if name == "allowed" else []), f"{name}: empty case"
    unquoted = [line for line in CASES_FILE.read_text().splitlines() if re.match(r"  - (?![\'\"]|\|-$)", line)]
    assert not unquoted, f"quote these cases in {CASES_FILE.name}: {unquoted}"


@pytest.mark.parametrize("command", DENIED)
def test_denies(command: str, project: Path, home: Path) -> None:
    decision = run_hook(command, project, home)

    assert decision, "allowed"
    assert decision["permissionDecision"] == "deny"
    assert decision["permissionDecisionReason"].startswith("Denied by .claude/hooks/guard-bash.py: ")


@pytest.mark.parametrize("command", ALLOWED)
def test_allows(command: str, project: Path, home: Path) -> None:
    assert run_hook(command, project, home) is None


def test_paths_resolve_against_the_session_directory(project: Path, home: Path) -> None:
    """In a subdirectory `.` is not the project, but `..` is."""
    assert run_hook("rm -rf .", project / "build", home, project) is None
    assert run_hook("rm -rf *", project / "build", home, project) is None
    assert run_hook("rm -rf ..", project / "build", home, project)
    assert run_hook(f"rm -rf {project}", home, home, project)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                   check=True, capture_output=True)


@pytest.fixture
def repo(project: Path) -> Path:
    git(project, "init", "-b", "main")
    git(project, "commit", "--allow-empty", "-m", "init")
    return project


@pytest.mark.parametrize("command", ["git push", "git push origin", "git push origin HEAD", "git push -u origin HEAD"])
def test_a_plain_push_depends_on_the_current_branch(command: str, repo: Path, home: Path) -> None:
    assert run_hook(command, repo, home), "on main"

    git(repo, "switch", "-c", "feature/x")

    assert run_hook(command, repo, home) is None, "on a feature branch"


def test_a_plain_push_follows_the_upstream_branch(repo: Path, home: Path, tmp_path: Path) -> None:
    """A feature branch that tracks main pushes to main when push.default is upstream."""
    remote = tmp_path / "remote.git"
    git(repo, "init", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "origin", "main")
    git(repo, "config", "push.default", "upstream")
    git(repo, "switch", "-c", "feature/x", "--track", "origin/main")

    assert run_hook("git push", repo, home)


def test_git_dash_c_names_the_repository(repo: Path, home: Path, tmp_path: Path) -> None:
    assert run_hook(f"git -C {repo} push", tmp_path, home, tmp_path)
    assert run_hook(f"cd {repo} && git push", tmp_path, home, tmp_path)


def test_ignores_other_tools(project: Path, home: Path) -> None:
    assert run_hook("rm -rf /", project, home, tool="Write") is None
