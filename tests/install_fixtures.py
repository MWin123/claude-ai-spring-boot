"""Fixtures and helpers of the install.py tests; conftest.py registers this module as a plugin."""
import subprocess
import sys
from pathlib import Path

import pytest

from helpers import CONFIG, ROOT

INSTALL = ROOT / "install.py"
POM = "<project><artifactId>demo</artifactId></project>"


def run_install(
    *args: Path, cwd: Path | None = None, env: dict[str, str] | None = None, script: Path = INSTALL
) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(script), *map(str, args)], cwd=cwd, env=env, capture_output=True, text=True)


def install(
    *args: Path, cwd: Path | None = None, env: dict[str, str] | None = None, script: Path = INSTALL
) -> subprocess.CompletedProcess[str]:
    """run_install for a run that must succeed."""
    result = run_install(*args, cwd=cwd, env=env, script=script)
    assert result.returncode == 0, result.stderr
    return result


@pytest.fixture
def user_settings(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Points install.py at a scratch Claude directory, so a test does not touch the real ~/.claude; the install test modules use it."""
    claude_dir = tmp_path_factory.mktemp("home") / ".claude"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", str(claude_dir))
    return claude_dir / "settings.json"


@pytest.fixture
def project(tmp_path: Path) -> Path:
    (tmp_path / "pom.xml").write_text(POM)
    return tmp_path


def expected_agents_md(name: str) -> str:
    """config/AGENTS.md with its placeholder heading replaced by the project name."""
    return f"# {name}\n" + (CONFIG / "AGENTS.md").read_text().split("\n", 1)[1]
