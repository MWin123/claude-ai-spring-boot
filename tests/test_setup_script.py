"""setup.sh copies agents, skills and config/ (.claude/settings.json, .claude/hooks, AGENTS.md, CLAUDE.md) into a project, and
config/.claude/settings.user.json into the user's Claude directory, and nothing else."""
import filecmp
import os
import re
import subprocess
from collections.abc import Iterator
from pathlib import Path

import pytest

from helpers import CONFIG, ROOT, code_blocks_blanked

SETUP = ROOT / "setup.sh"
IMPORT = re.compile(r"(?:^|\s)@((?:[^\s\\]|\\ )+)")  # Claude Code's own pattern for CLAUDE.md imports
MAX_HOPS = 4
POM = "<project><artifactId>demo</artifactId></project>"


def run_setup(*args: Path, cwd: Path | None = None) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["bash", str(SETUP), *map(str, args)], cwd=cwd, capture_output=True, text=True)


@pytest.fixture(autouse=True)
def user_settings(tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Points setup.sh at a scratch Claude directory, so no test touches the real ~/.claude."""
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


def assert_same_tree(source: Path, target: Path) -> None:
    diff = filecmp.dircmp(source, target)
    differs = {"missing": diff.left_only, "extra": diff.right_only,
               "different": diff.diff_files, "not compared": diff.funny_files}
    assert not any(differs.values()), f"{target}: " + ", ".join(
        f"{kind} {names}" for kind, names in differs.items() if names)
    for sub in diff.common_dirs:
        assert_same_tree(source / sub, target / sub)


@pytest.mark.parametrize(
    "build_file", ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"]
)
def test_copies_only_the_claude_files(tmp_path: Path, build_file: str) -> None:
    (tmp_path / build_file).write_text(POM if build_file == "pom.xml" else "")

    result = run_setup(tmp_path)

    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([".claude", "AGENTS.md", "CLAUDE.md", build_file])
    assert sorted(p.name for p in (tmp_path / ".claude").iterdir()) == ["agents", "hooks", "settings.json", "skills"]
    assert_same_tree(ROOT / "agents", tmp_path / ".claude" / "agents")
    assert_same_tree(ROOT / "skills", tmp_path / ".claude" / "skills")
    assert_same_tree(CONFIG / ".claude" / "hooks", tmp_path / ".claude" / "hooks")
    assert filecmp.cmp(CONFIG / ".claude" / "settings.json", tmp_path / ".claude" / "settings.json", shallow=False)
    assert (tmp_path / "AGENTS.md").read_text() == expected_agents_md("demo" if build_file == "pom.xml" else tmp_path.name)
    assert filecmp.cmp(CONFIG / "CLAUDE.md", tmp_path / "CLAUDE.md", shallow=False)


def test_leaves_an_existing_gitignore_alone(project: Path) -> None:
    gitignore = project / ".gitignore"
    gitignore.write_text("target/\n")

    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert gitignore.read_text() == "target/\n"


def test_defaults_to_the_current_directory(project: Path) -> None:
    result = run_setup(cwd=project)

    assert result.returncode == 0, result.stderr
    assert (project / ".claude" / "agents").is_dir()


def test_rejects_a_missing_directory(tmp_path: Path) -> None:
    result = run_setup(tmp_path / "missing")

    assert result.returncode == 1
    assert "Project directory not found" in result.stderr


def test_rejects_a_directory_without_build_file(tmp_path: Path) -> None:
    result = run_setup(tmp_path)

    assert result.returncode == 1
    assert "No pom.xml" in result.stderr
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("via_symlink", [False, True])
def test_rejects_this_repository_as_target(tmp_path: Path, via_symlink: bool) -> None:
    target = ROOT
    if via_symlink:
        target = tmp_path / "link"
        target.symlink_to(ROOT)

    result = run_setup(target)

    assert result.returncode == 1
    assert "Target is this repository itself" in result.stderr


def test_keeps_existing_settings(project: Path) -> None:
    settings = project / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"permissions": {}}')

    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert settings.read_text() == '{"permissions": {}}'
    assert "Existing .claude/settings.json kept; merge the hooks block" in result.stdout
    assert (project / ".claude" / "hooks" / "guard-bash.py").is_file()


def test_copies_user_settings(project: Path, user_settings: Path) -> None:
    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert filecmp.cmp(CONFIG / ".claude" / "settings.user.json", user_settings, shallow=False)


def test_defaults_to_the_home_directory(
    project: Path, tmp_path_factory: pytest.TempPathFactory, monkeypatch: pytest.MonkeyPatch
) -> None:
    home = tmp_path_factory.mktemp("home")
    monkeypatch.delenv("CLAUDE_CONFIG_DIR")
    monkeypatch.setenv("HOME", str(home))

    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert filecmp.cmp(CONFIG / ".claude" / "settings.user.json", home / ".claude" / "settings.json", shallow=False)


def test_keeps_existing_user_settings(project: Path, user_settings: Path) -> None:
    user_settings.parent.mkdir()
    user_settings.write_text('{"model": "sonnet"}')

    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert user_settings.read_text() == '{"model": "sonnet"}'
    assert f"Existing {user_settings} kept" in result.stdout


@ROOT_FILES
def test_backs_up_a_different_root_file(project: Path, file: str) -> None:
    (project / file).write_text("project rules")

    result = run_setup(project)

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

    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert f"Existing {link} was a symlink; replaced by a file" in result.stdout
    for name in (link, file):
        assert not (project / name).is_symlink()
        assert (project / name).read_text() == expected(name)
    assert [(b.name, b.read_text()) for b in project.glob("*.bak")] == [(f"{file}.bak", "project rules")]


def test_replaces_a_dangling_symlink(project: Path) -> None:
    (project / "CLAUDE.md").symlink_to("missing.md")

    assert run_setup(project).returncode == 0

    assert not (project / "CLAUDE.md").is_symlink()
    assert not (project / "missing.md").exists()


@ROOT_FILES
def test_never_overwrites_an_earlier_backup(project: Path, file: str) -> None:
    (project / file).write_text("original rules")
    run_setup(project)
    (project / file).write_text("edited rules")
    run_setup(project)
    (project / file).write_text("rules edited again")

    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert f"Existing {file} saved as {file}.3.bak" in result.stdout
    backups = {b.name: b.read_text() for b in project.glob(f"{file}*.bak")}
    assert backups == {
        f"{file}.bak": "original rules", f"{file}.2.bak": "edited rules", f"{file}.3.bak": "rules edited again",
    }


def test_no_backup_for_identical_root_files(project: Path) -> None:
    assert run_setup(project).returncode == 0

    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert not list(project.glob("*.bak"))


def test_config_agents_md_starts_with_the_placeholder() -> None:
    """setup.sh replaces this first line with the project name."""
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
        ("settings.gradle", "pluginManagement {}\nrootProject.name = 'order-service'\n"),
        ("settings.gradle.kts", 'rootProject.name = "order-service"\n'),
    ],
    ids=["pom-multiline", "pom-one-line", "settings.gradle", "settings.gradle.kts"],
)
def test_heading_is_the_project_name(tmp_path: Path, build_file: str, content: str) -> None:
    (tmp_path / build_file).write_text(content)

    result = run_setup(tmp_path)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "AGENTS.md").read_text() == expected_agents_md("order-service")
    assert "(project: order-service)" in result.stdout


@pytest.mark.parametrize("files", [{"settings.gradle": "include 'api'\n"}, {"build.gradle.kts": ""}])
def test_gradle_name_defaults_to_the_directory(tmp_path: Path, files: dict[str, str]) -> None:
    project = tmp_path / "my-app"
    project.mkdir()
    for name, content in files.items():
        (project / name).write_text(content)

    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert (project / "AGENTS.md").read_text().startswith("# my-app\n")


def test_rejects_a_pom_without_artifact_id(tmp_path: Path) -> None:
    (tmp_path / "pom.xml").write_text("<project><parent><artifactId>parent-pom</artifactId></parent></project>")

    result = run_setup(tmp_path)

    assert result.returncode == 1
    assert "No artifactId" in result.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["pom.xml"]


def imports(path: Path) -> Iterator[tuple[str, Path]]:
    """The files a memory file imports, parsed as Claude Code does: `@path` outside frontmatter and code, relative to the file."""
    text = re.sub(r"\A---\n.*?\n---\n", "", path.read_text(), flags=re.S)
    text = re.sub(r"`[^`\n]*`", " ", code_blocks_blanked(text))
    for m in IMPORT.finditer(text):
        name = m.group(1).split("#", 1)[0].replace("\\ ", " ")
        if re.match(r"~/|/.|[a-zA-Z0-9._-]", name):  # what Claude Code accepts as a path
            yield name, Path(os.path.normpath(path.parent / Path(name).expanduser()))


def test_claude_md_imports_resolve(project: Path) -> None:
    """Every import in the installed CLAUDE.md, and in the files it imports, is a file setup.sh installed."""
    assert run_setup(project).returncode == 0
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
