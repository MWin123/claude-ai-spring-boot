"""install.py merges the template settings into existing project and user settings and never loosens them."""
import filecmp
import json
import os
from pathlib import Path
from typing import Any

import pytest

from helpers import CONFIG
from install_fixtures import install, run_install

pytestmark = pytest.mark.usefixtures("user_settings")  # install.py reads CLAUDE_CONFIG_DIR, so no test touches the real ~/.claude


def template(name: str) -> dict[str, Any]:
    settings: dict[str, Any] = json.loads((CONFIG / ".claude" / name).read_text())
    return settings


def test_merges_existing_settings(project: Path) -> None:
    settings = project / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"permissions": {"allow": ["Bash(ls)"]}}')

    result = install(project)

    merged = json.loads(settings.read_text())
    assert merged["permissions"]["allow"] == ["Bash(ls)"]
    assert merged["hooks"] == template("settings.json")["hooks"]
    assert merged["availableModels"] == template("settings.json")["availableModels"]
    assert (project / ".claude" / "settings.json.bak").read_text() == '{"permissions": {"allow": ["Bash(ls)"]}}'
    assert f"Merged project settings (Bash guard) into {settings} (backup: settings.json.bak)" in result.stdout
    assert "Kept" not in result.stdout, "a list that holds every template item is not reported"
    assert (project / ".claude" / "hooks" / "guard-bash.py").is_file()


def test_keeps_a_differing_setting(project: Path, user_settings: Path) -> None:
    user_settings.parent.mkdir()
    user_settings.write_text('{"permissions": {"defaultMode": "default"}}')

    result = install(project)

    merged = json.loads(user_settings.read_text())
    assert merged["permissions"] == {"defaultMode": "default"}
    assert merged["autoMode"] == template("settings.user.json")["autoMode"]
    assert f'Kept permissions.defaultMode = "default" (template: "auto") in {user_settings}' in result.stdout


def test_merging_twice_changes_nothing(project: Path, user_settings: Path) -> None:
    settings = project / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"hooks": {"PreToolUse": [{"matcher": "Edit", "hooks": []}]}}')
    user_settings.parent.mkdir()
    user_settings.write_text('{"model": "sonnet"}')
    install(project)
    contents = [settings.read_text(), user_settings.read_text()]

    result = install(project)

    assert [settings.read_text(), user_settings.read_text()] == contents
    assert json.loads(settings.read_text())["hooks"]["PreToolUse"] == [
        {"matcher": "Edit", "hooks": []}, *template("settings.json")["hooks"]["PreToolUse"]]
    assert "Merged" not in result.stdout
    assert len(list(settings.parent.glob("*.bak")) + list(user_settings.parent.glob("*.bak"))) == 2


@pytest.mark.parametrize("change", [
    {"timeout": 5}, {"command": 'python3.13 "${CLAUDE_PROJECT_DIR}/.claude/hooks/guard-bash.py"'}])
def test_keeps_a_customised_guard_hook(project: Path, change: dict[str, Any]) -> None:
    """A second entry would run the guard twice per Bash call."""
    wanted = template("settings.json")
    wanted["hooks"]["PreToolUse"][0]["hooks"][0].update(change)
    settings = project / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text(json.dumps(wanted))

    for _ in range(2):
        result = install(project)

        assert json.loads(settings.read_text()) == wanted
        assert "Merged project settings" not in result.stdout
    assert not list(settings.parent.glob("*.bak"))


def test_keeps_a_replaced_auto_mode_list(project: Path, user_settings: Path) -> None:
    """A list without "$defaults" replaces the built-in rules; adding them back would loosen the classifier."""
    user_settings.parent.mkdir()
    user_settings.write_text('{"autoMode": {"allow": ["Only my rule"]}}')

    result = install(project)

    auto_mode = json.loads(user_settings.read_text())["autoMode"]
    assert auto_mode == {**template("settings.user.json")["autoMode"], "allow": ["Only my rule"]}
    assert 'Kept autoMode.allow = ["Only my rule"] (template: ' in result.stdout


def test_keeps_a_shorter_list(project: Path) -> None:
    settings = project / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"availableModels": ["claude-sonnet-5-5"]}')

    result = install(project)

    assert json.loads(settings.read_text())["availableModels"] == ["claude-sonnet-5-5"]
    assert 'Kept availableModels = ["claude-sonnet-5-5"] (template: ' in result.stdout


@pytest.mark.parametrize("which", ["project", "user"])
@pytest.mark.parametrize("content", ["{not json", "[]"])
def test_rejects_unreadable_settings(project: Path, user_settings: Path, which: str, content: str) -> None:
    settings = project / ".claude" / "settings.json" if which == "project" else user_settings
    settings.parent.mkdir()
    settings.write_text(content)

    result = run_install(project)

    assert result.returncode == 1
    assert str(settings) in result.stderr
    assert settings.read_text() == content
    assert not (project / "AGENTS.md").exists()
    assert not (project / ".claude" / "agents").exists()


def test_merges_through_a_symlinked_user_settings_file(project: Path, user_settings: Path, tmp_path: Path) -> None:
    dotfile = tmp_path / "dotfiles-settings.json"
    dotfile.write_text('{"model": "sonnet"}')
    user_settings.parent.mkdir()
    user_settings.symlink_to(dotfile)

    install(project)

    assert user_settings.is_symlink()
    assert json.loads(dotfile.read_text()) == {"model": "sonnet", **template("settings.user.json")}


def test_reads_and_writes_utf8_under_any_locale(tmp_path: Path, user_settings: Path) -> None:
    """The template and the settings files are UTF-8, whatever the locale says (cp1252 on Windows, ASCII under C)."""
    (tmp_path / "settings.gradle").write_bytes("// Bestellübersicht\nrootProject.name = 'orders'\n".encode())
    settings = tmp_path / ".claude" / "settings.json"
    for path, key in [(settings, "permissions"), (user_settings, "autoMode")]:
        path.parent.mkdir()
        path.write_bytes(json.dumps({key: {"allow": ["Löschen → nie"]}}, ensure_ascii=False).encode())

    install(tmp_path, env={**os.environ, "LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"})

    rules = (CONFIG / "AGENTS.md").read_bytes().split(b"\n", 1)[1]
    assert "→".encode() in rules, "config/AGENTS.md no longer has a non-ASCII character to test with"
    assert (tmp_path / "AGENTS.md").read_bytes() == b"# orders\n" + rules
    for path, key in [(settings, "permissions"), (user_settings, "autoMode")]:
        merged = json.loads(path.read_bytes().decode())
        assert merged[key]["allow"] == ["Löschen → nie"]
        assert len(merged) > 1, "the template was merged in"


def test_copies_user_settings(project: Path, user_settings: Path) -> None:
    install(project)

    assert filecmp.cmp(CONFIG / ".claude" / "settings.user.json", user_settings, shallow=False)


def test_defaults_to_the_home_directory(
    project: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path_factory.mktemp("home")
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    monkeypatch.setenv("HOME", str(home))

    install(project)

    assert filecmp.cmp(CONFIG / ".claude" / "settings.user.json", home / ".claude" / "settings.json", shallow=False)


def test_merges_existing_user_settings(project: Path, user_settings: Path) -> None:
    user_settings.parent.mkdir()
    user_settings.write_text('{"model": "sonnet"}')

    result = install(project)

    assert json.loads(user_settings.read_text()) == {"model": "sonnet", **template("settings.user.json")}
    assert (user_settings.parent / "settings.json.bak").read_text() == '{"model": "sonnet"}'
    assert f"Merged user settings (auto mode) into {user_settings}" in result.stdout
