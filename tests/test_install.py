"""install.py copies agents, skills and config/ (.claude/settings.json, .claude/hooks, AGENTS.md, CLAUDE.md) into a project,
and config/.claude/settings.user.json into the user's Claude directory, and nothing else. Existing settings are merged."""
import ast
import filecmp
import json
import os
import re
import shutil
import subprocess
import sys
from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest

from helpers import CONFIG, ROOT, code_blocks_blanked

INSTALL = ROOT / "install.py"
IMPORT = re.compile(r"(?:^|\s)@((?:[^\s\\]|\\ )+)")  # Claude Code's own pattern for CLAUDE.md imports
MAX_HOPS = 4
POM = "<project><artifactId>demo</artifactId></project>"


def run_install(*args: Path, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, str(INSTALL), *map(str, args)], cwd=cwd, capture_output=True, text=True)


def template(name: str) -> dict[str, Any]:
    settings: dict[str, Any] = json.loads((CONFIG / ".claude" / name).read_text())
    return settings


@pytest.fixture(autouse=True)
def user_settings(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Points install.py at a scratch Claude directory, so no test touches the real ~/.claude."""
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


def expected(file: str) -> str:
    """The installed content of a root file for the project `demo`."""
    return expected_agents_md("demo") if file == "AGENTS.md" else (CONFIG / file).read_text()


ROOT_FILES = pytest.mark.parametrize("file", ["AGENTS.md", "CLAUDE.md"])


def assert_same_tree(source: Path, target: Path, top: bool = True) -> None:
    """The trees match, except for the README.md of the top folder, which documents this repository."""
    diff = filecmp.dircmp(source, target, ignore=filecmp.DEFAULT_IGNORES + ["README.md"] * top)
    differs = {"missing": diff.left_only, "extra": diff.right_only,
               "different": diff.diff_files, "not compared": diff.funny_files}
    assert not any(differs.values()), f"{target}: " + ", ".join(
        f"{kind} {names}" for kind, names in differs.items() if names)
    for sub in diff.common_dirs:
        assert_same_tree(source / sub, target / sub, top=False)


def test_skips_only_the_top_readme(tmp_path: Path) -> None:
    """A README.md deeper in a copied folder belongs to a skill and is installed; install.py runs from a scratch template."""
    source, target = tmp_path / "template", tmp_path / "demo"
    shutil.copytree(CONFIG, source / "config")
    shutil.copy(INSTALL, source)
    for file in ["agents/README.md", "skills/README.md", "skills/demo/SKILL.md", "skills/demo/README.md"]:
        (source / file).parent.mkdir(parents=True, exist_ok=True)
        (source / file).write_text("demo")
    target.mkdir()
    (target / "pom.xml").write_text(POM)

    result = subprocess.run([sys.executable, str(source / "install.py"), str(target)], capture_output=True, text=True)

    assert result.returncode == 0, result.stderr
    claude = target / ".claude"
    assert sorted(str(p.relative_to(claude)) for p in claude.rglob("README.md")) == ["skills/demo/README.md"]


@pytest.mark.parametrize(
    "build_file", ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"]
)
def test_copies_only_the_claude_files(tmp_path: Path, build_file: str) -> None:
    (tmp_path / build_file).write_text(POM if build_file == "pom.xml" else "")

    result = run_install(tmp_path)

    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([".claude", "AGENTS.md", "CLAUDE.md", build_file])
    assert sorted(p.name for p in (tmp_path / ".claude").iterdir()) == ["agents", "hooks", "settings.json", "skills"]
    assert_same_tree(ROOT / "agents", tmp_path / ".claude" / "agents")
    assert_same_tree(ROOT / "skills", tmp_path / ".claude" / "skills")
    assert_same_tree(CONFIG / ".claude" / "hooks", tmp_path / ".claude" / "hooks")
    for folder in ["agents", "skills", "hooks"]:
        assert not (tmp_path / ".claude" / folder / "README.md").exists(), "folder READMEs document this repository only"
    assert filecmp.cmp(CONFIG / ".claude" / "settings.json", tmp_path / ".claude" / "settings.json", shallow=False)
    assert (tmp_path / "AGENTS.md").read_text() == expected_agents_md("demo" if build_file == "pom.xml" else tmp_path.name)
    assert filecmp.cmp(CONFIG / "CLAUDE.md", tmp_path / "CLAUDE.md", shallow=False)


def test_leaves_an_existing_gitignore_alone(project: Path) -> None:
    gitignore = project / ".gitignore"
    gitignore.write_text("target/\n")

    result = run_install(project)

    assert result.returncode == 0, result.stderr
    assert gitignore.read_text() == "target/\n"


def test_defaults_to_the_current_directory(project: Path) -> None:
    result = run_install(cwd=project)

    assert result.returncode == 0, result.stderr
    assert (project / ".claude" / "agents").is_dir()


def test_rejects_a_missing_directory(tmp_path: Path) -> None:
    result = run_install(tmp_path / "missing")

    assert result.returncode == 1
    assert "Project directory not found" in result.stderr


def test_rejects_a_directory_without_build_file(tmp_path: Path) -> None:
    result = run_install(tmp_path)

    assert result.returncode == 1
    assert "No pom.xml" in result.stderr
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("via_symlink", [False, True])
def test_rejects_this_repository_as_target(tmp_path: Path, via_symlink: bool) -> None:
    target = ROOT
    if via_symlink:
        target = tmp_path / "link"
        target.symlink_to(ROOT)

    result = run_install(target)

    assert result.returncode == 1
    assert "Target is this repository itself" in result.stderr


def test_merges_existing_settings(project: Path) -> None:
    settings = project / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"permissions": {"allow": ["Bash(ls)"]}}')

    result = run_install(project)

    assert result.returncode == 0, result.stderr
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

    result = run_install(project)

    assert result.returncode == 0, result.stderr
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
    assert run_install(project).returncode == 0
    contents = [settings.read_text(), user_settings.read_text()]

    result = run_install(project)

    assert result.returncode == 0, result.stderr
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
        result = run_install(project)

        assert result.returncode == 0, result.stderr
        assert json.loads(settings.read_text()) == wanted
        assert "Merged project settings" not in result.stdout
    assert not list(settings.parent.glob("*.bak"))


def test_keeps_a_replaced_auto_mode_list(project: Path, user_settings: Path) -> None:
    """A list without "$defaults" replaces the built-in rules; adding them back would loosen the classifier."""
    user_settings.parent.mkdir()
    user_settings.write_text('{"autoMode": {"allow": ["Only my rule"]}}')

    result = run_install(project)

    assert result.returncode == 0, result.stderr
    auto_mode = json.loads(user_settings.read_text())["autoMode"]
    assert auto_mode == {**template("settings.user.json")["autoMode"], "allow": ["Only my rule"]}
    assert f'Kept autoMode.allow = ["Only my rule"] (template: ' in result.stdout


def test_keeps_a_shorter_list(project: Path) -> None:
    settings = project / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"availableModels": ["claude-sonnet-5-5"]}')

    result = run_install(project)

    assert result.returncode == 0, result.stderr
    assert json.loads(settings.read_text())["availableModels"] == ["claude-sonnet-5-5"]
    assert f'Kept availableModels = ["claude-sonnet-5-5"] (template: ' in result.stdout


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

    result = run_install(project)

    assert result.returncode == 0, result.stderr
    assert user_settings.is_symlink()
    assert json.loads(dotfile.read_text()) == {"model": "sonnet", **template("settings.user.json")}


def test_reads_and_writes_utf8_under_any_locale(tmp_path: Path, user_settings: Path) -> None:
    """The template and the settings files are UTF-8, whatever the locale says (cp1252 on Windows, ASCII under C)."""
    (tmp_path / "settings.gradle").write_bytes("// Bestellübersicht\nrootProject.name = 'orders'\n".encode())
    settings = tmp_path / ".claude" / "settings.json"
    for path, key in [(settings, "permissions"), (user_settings, "autoMode")]:
        path.parent.mkdir()
        path.write_bytes(json.dumps({key: {"allow": ["Löschen → nie"]}}, ensure_ascii=False).encode())

    result = subprocess.run(
        [sys.executable, str(INSTALL), str(tmp_path)], capture_output=True, text=True,
        env={**os.environ, "LC_ALL": "C", "PYTHONUTF8": "0", "PYTHONCOERCECLOCALE": "0"})

    assert result.returncode == 0, result.stderr
    rules = (CONFIG / "AGENTS.md").read_bytes().split(b"\n", 1)[1]
    assert "→".encode() in rules, "config/AGENTS.md no longer has a non-ASCII character to test with"
    assert (tmp_path / "AGENTS.md").read_bytes() == b"# orders\n" + rules
    for path, key in [(settings, "permissions"), (user_settings, "autoMode")]:
        merged = json.loads(path.read_bytes().decode())
        assert merged[key]["allow"] == ["Löschen → nie"]
        assert len(merged) > 1, "the template was merged in"


def test_copies_user_settings(project: Path, user_settings: Path) -> None:
    result = run_install(project)

    assert result.returncode == 0, result.stderr
    assert filecmp.cmp(CONFIG / ".claude" / "settings.user.json", user_settings, shallow=False)


def test_defaults_to_the_home_directory(
    project: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path_factory.mktemp("home")
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    monkeypatch.setenv("HOME", str(home))

    result = run_install(project)

    assert result.returncode == 0, result.stderr
    assert filecmp.cmp(CONFIG / ".claude" / "settings.user.json", home / ".claude" / "settings.json", shallow=False)


def test_merges_existing_user_settings(project: Path, user_settings: Path) -> None:
    user_settings.parent.mkdir()
    user_settings.write_text('{"model": "sonnet"}')

    result = run_install(project)

    assert result.returncode == 0, result.stderr
    assert json.loads(user_settings.read_text()) == {"model": "sonnet", **template("settings.user.json")}
    assert (user_settings.parent / "settings.json.bak").read_text() == '{"model": "sonnet"}'
    assert f"Merged user settings (auto mode) into {user_settings}" in result.stdout


@ROOT_FILES
def test_backs_up_a_different_root_file(project: Path, file: str) -> None:
    (project / file).write_text("project rules")

    result = run_install(project)

    assert result.returncode == 0, result.stderr
    assert (project / f"{file}.bak").read_text() == "project rules"
    assert f"Existing {file} saved as {file}.bak" in result.stdout
    assert (project / file).read_text() == expected(file)
    assert len(list(project.glob("*.bak"))) == 1, "only the different file is backed up"


@pytest.mark.parametrize(("link", "file"), [("CLAUDE.md", "AGENTS.md"), ("AGENTS.md", "CLAUDE.md")])
def test_replaces_a_symlinked_root_file(project: Path, link: str, file: str) -> None:
    """Copying through the link would overwrite the other root file with this one's content."""
    (project / file).write_text("project rules")
    (project / link).symlink_to(file)

    result = run_install(project)

    assert result.returncode == 0, result.stderr
    assert f"Existing {link} was a symlink; replaced by a file" in result.stdout
    for name in (link, file):
        assert not (project / name).is_symlink()
        assert (project / name).read_text() == expected(name)
    assert [(b.name, b.read_text()) for b in project.glob("*.bak")] == [(f"{file}.bak", "project rules")]


def test_replaces_a_dangling_symlink(project: Path) -> None:
    (project / "CLAUDE.md").symlink_to("missing.md")

    assert run_install(project).returncode == 0

    assert not (project / "CLAUDE.md").is_symlink()
    assert not (project / "missing.md").exists()


@ROOT_FILES
def test_never_overwrites_an_earlier_backup(project: Path, file: str) -> None:
    (project / file).write_text("original rules")
    run_install(project)
    (project / file).write_text("edited rules")
    run_install(project)
    (project / file).write_text("rules edited again")

    result = run_install(project)

    assert result.returncode == 0, result.stderr
    assert f"Existing {file} saved as {file}.3.bak" in result.stdout
    backups = {b.name: b.read_text() for b in project.glob(f"{file}*.bak")}
    assert backups == {
        f"{file}.bak": "original rules", f"{file}.2.bak": "edited rules", f"{file}.3.bak": "rules edited again",
    }


def test_no_backup_for_identical_root_files(project: Path) -> None:
    assert run_install(project).returncode == 0

    result = run_install(project)

    assert result.returncode == 0, result.stderr
    assert not list(project.glob("*.bak"))


def test_config_agents_md_starts_with_the_placeholder() -> None:
    """install.py replaces this first line with the project name."""
    assert (CONFIG / "AGENTS.md").read_text().startswith("# <project-name>\n")


@pytest.mark.parametrize(
    ("build_file", "content"),
    [
        ("pom.xml", """<project>
  <parent>
    <groupId>org.springframework.boot</groupId>
    <artifactId>spring-boot-starter-parent</artifactId>
  </parent>
  <artifactId>order-service</artifactId>
</project>"""),
        ("pom.xml", "<project><parent><artifactId>parent-pom</artifactId></parent><artifactId>order-service</artifactId></project>"),
        ("pom.xml", """<project xmlns="http://maven.apache.org/POM/4.0.0">
  <!-- <artifactId>old-name</artifactId> -->
  <dependencies><dependency><artifactId>spring-boot-starter-web</artifactId></dependency></dependencies>
  <artifactId>
    order-service
  </artifactId>
</project>"""),
        ("settings.gradle", "pluginManagement {}\nrootProject.name = 'order-service'\n"),
        ("settings.gradle.kts", 'rootProject.name = "order-service"\n'),
    ],
    ids=["pom-multiline", "pom-one-line", "pom-namespace-comment-split", "settings.gradle", "settings.gradle.kts"],
)
def test_heading_is_the_project_name(tmp_path: Path, build_file: str, content: str) -> None:
    (tmp_path / build_file).write_text(content)

    result = run_install(tmp_path)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "AGENTS.md").read_text() == expected_agents_md("order-service")
    assert "(project: order-service)" in result.stdout


@pytest.mark.parametrize("files", [{"settings.gradle": "include 'api'\n"}, {"build.gradle.kts": ""}])
def test_gradle_name_defaults_to_the_directory(tmp_path: Path, files: dict[str, str]) -> None:
    project = tmp_path / "my-app"
    project.mkdir()
    for name, content in files.items():
        (project / name).write_text(content)

    result = run_install(project)

    assert result.returncode == 0, result.stderr
    assert (project / "AGENTS.md").read_text().startswith("# my-app\n")


def test_rejects_a_pom_without_artifact_id(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text("<project><parent><artifactId>parent-pom</artifactId></parent></project>")

    result = run_install(tmp_path)

    assert result.returncode == 1
    assert "No artifactId" in result.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["pom.xml"]


def test_rejects_an_unparsable_pom(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text("<project><artifactId>demo</project>")

    result = run_install(tmp_path)

    assert result.returncode == 1
    assert "Cannot parse" in result.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["pom.xml"]


def test_warns_when_the_hook_python_is_too_old(project: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    bin_dir = tmp_path_factory.mktemp("bin")
    (bin_dir / "python3").write_text("#!/bin/sh\nexit 1\n")
    (bin_dir / "python3").chmod(0o755)

    result = subprocess.run([sys.executable, str(INSTALL), str(project)], capture_output=True, text=True,
                            env={**os.environ, "PATH": str(bin_dir)})

    assert result.returncode == 0, result.stderr
    assert "python3 on the PATH is missing or older than 3.13" in result.stderr


def test_no_warning_with_a_current_hook_python(project: Path) -> None:
    assert "Warning" not in run_install(project).stderr


def test_install_runs_on_old_pythons_up_to_the_version_check() -> None:
    """`./install.py` must be executable, and older Pythons must parse it to show the version message."""
    assert os.access(INSTALL, os.X_OK)
    tree = ast.parse(INSTALL.read_text(), feature_version=(3, 8))
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.TypeAlias)]


def imports(path: Path) -> Iterator[tuple[str, Path]]:
    """The files a memory file imports, parsed as Claude Code does: `@path` outside frontmatter and code, relative to the file."""
    text = re.sub(r"\A---\n.*?\n---\n", "", path.read_text(), flags=re.S)
    text = re.sub(r"`[^`\n]*`", " ", code_blocks_blanked(text))
    for m in IMPORT.finditer(text):
        name = m.group(1).split("#", 1)[0].replace("\\ ", " ")
        if re.match(r"~/|/.|[a-zA-Z0-9._-]", name):  # what Claude Code accepts as a path
            yield name, Path(os.path.normpath(path.parent / Path(name).expanduser()))


def test_claude_md_imports_resolve(project: Path) -> None:
    """Every import in the installed CLAUDE.md, and in the files it imports, is a file install.py installed."""
    assert run_install(project).returncode == 0
    loaded: set[Path] = set()
    missing: list[str] = []
    todo = [(project / "CLAUDE.md", 0)]
    while todo:
        path, hops = todo.pop()
        for name, target in imports(path) if hops < MAX_HOPS else ():
            if not target.is_file():
                missing.append(f"{path.relative_to(project)}: @{name}")
            elif target not in loaded:
                loaded.add(target)
                todo.append((target, hops + 1))
    assert not missing, "\n".join(missing)
    assert project / "AGENTS.md" in loaded, "CLAUDE.md must import AGENTS.md"
    assert project / ".claude" / "skills" / "conventions" / "SKILL.md" in loaded, "AGENTS.md must import conventions"
