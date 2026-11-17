"""setup.sh copies agents, skills and config/ (.claude/settings.json, AGENTS.md, CLAUDE.md) into a project, and nothing else."""
import filecmp
import os
import re
import subprocess
from pathlib import Path

import pytest

from helpers import CONFIG, ROOT, code_blocks_blanked

SETUP = ROOT / "setup.sh"
IMPORT = re.compile(r"(?:^|\s)@((?:[^\s\\]|\\ )+)")  # Claude Code's own pattern for CLAUDE.md imports
MAX_HOPS = 4
POM = "<project><artifactId>demo</artifactId></project>"


def run_setup(*args, cwd=None):
    return subprocess.run(["bash", str(SETUP), *map(str, args)], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def project(tmp_path):
    (tmp_path / "pom.xml").write_text(POM)
    return tmp_path


def expected_agents_md(name):
    """config/AGENTS.md with its placeholder heading replaced by the project name."""
    return f"# {name}\n" + (CONFIG / "AGENTS.md").read_text().split("\n", 1)[1]


def expected(file):
    """The installed content of a root file for the project `demo`."""
    return expected_agents_md("demo") if file == "AGENTS.md" else (CONFIG / file).read_text()


ROOT_FILES = pytest.mark.parametrize("file", ["AGENTS.md", "CLAUDE.md"])


def assert_same_tree(source, target):
    diff = filecmp.dircmp(source, target)
    assert not (diff.left_only or diff.right_only or diff.diff_files or diff.funny_files), diff.report()
    for sub in diff.common_dirs:
        assert_same_tree(source / sub, target / sub)


@pytest.mark.parametrize(
    "build_file", ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"]
)
def test_copies_only_the_claude_files(tmp_path, build_file):
    (tmp_path / build_file).write_text(POM if build_file == "pom.xml" else "")

    result = run_setup(tmp_path)

    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([".claude", "AGENTS.md", "CLAUDE.md", build_file])
    assert sorted(p.name for p in (tmp_path / ".claude").iterdir()) == ["agents", "settings.json", "skills"]
    assert_same_tree(ROOT / "agents", tmp_path / ".claude" / "agents")
    assert_same_tree(ROOT / "skills", tmp_path / ".claude" / "skills")
    assert filecmp.cmp(CONFIG / ".claude" / "settings.json", tmp_path / ".claude" / "settings.json", shallow=False)
    assert (tmp_path / "AGENTS.md").read_text() == expected_agents_md("demo" if build_file == "pom.xml" else tmp_path.name)
    assert filecmp.cmp(CONFIG / "CLAUDE.md", tmp_path / "CLAUDE.md", shallow=False)


def test_leaves_an_existing_gitignore_alone(project):
    gitignore = project / ".gitignore"
    gitignore.write_text("target/\n")

    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert gitignore.read_text() == "target/\n"


def test_defaults_to_the_current_directory(project):
    result = run_setup(cwd=project)

    assert result.returncode == 0, result.stderr
    assert (project / ".claude" / "agents").is_dir()


def test_rejects_a_missing_directory(tmp_path):
    result = run_setup(tmp_path / "missing")

    assert result.returncode == 1
    assert "Project directory not found" in result.stderr


def test_rejects_a_directory_without_build_file(tmp_path):
    result = run_setup(tmp_path)

    assert result.returncode == 1
    assert "No pom.xml" in result.stderr
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("via_symlink", [False, True])
def test_rejects_this_repository_as_target(tmp_path, via_symlink):
    target = ROOT
    if via_symlink:
        target = tmp_path / "link"
        target.symlink_to(ROOT)

    result = run_setup(target)

    assert result.returncode == 1
    assert "Target is this repository itself" in result.stderr


def test_keeps_existing_settings(project):
    settings = project / ".claude" / "settings.json"
    settings.parent.mkdir()
    settings.write_text('{"permissions": {}}')

    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert settings.read_text() == '{"permissions": {}}'
    assert "Existing .claude/settings.json kept" in result.stdout


@ROOT_FILES
def test_backs_up_a_different_root_file(project, file):
    (project / file).write_text("project rules")

    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert (project / f"{file}.bak").read_text() == "project rules"
    assert f"Existing {file} saved as {file}.bak" in result.stdout
    assert (project / file).read_text() == expected(file)
    assert len(list(project.glob("*.bak"))) == 1, "only the different file is backed up"


@ROOT_FILES
def test_never_overwrites_an_earlier_backup(project, file):
    (project / file).write_text("original rules")
    run_setup(project)
    (project / file).write_text("edited rules")

    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert (project / f"{file}.bak").read_text() == "original rules"
    timestamped = list(project.glob(f"{file}.*.bak"))
    assert len(timestamped) == 1 and timestamped[0].read_text() == "edited rules"


def test_no_backup_for_identical_root_files(project):
    assert run_setup(project).returncode == 0

    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert not list(project.glob("*.bak"))


def test_config_agents_md_starts_with_the_placeholder():
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
def test_heading_is_the_project_name(tmp_path, build_file, content):
    (tmp_path / build_file).write_text(content)

    result = run_setup(tmp_path)

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "AGENTS.md").read_text() == expected_agents_md("order-service")
    assert "(project: order-service)" in result.stdout


@pytest.mark.parametrize("files", [{"settings.gradle": "include 'api'\n"}, {"build.gradle.kts": ""}])
def test_gradle_name_defaults_to_the_directory(tmp_path, files):
    project = tmp_path / "my-app"
    project.mkdir()
    for name, content in files.items():
        (project / name).write_text(content)

    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert (project / "AGENTS.md").read_text().startswith("# my-app\n")


def test_rejects_a_pom_without_artifact_id(tmp_path):
    (tmp_path / "pom.xml").write_text("<project><parent><artifactId>parent-pom</artifactId></parent></project>")

    result = run_setup(tmp_path)

    assert result.returncode == 1
    assert "No artifactId" in result.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == ["pom.xml"]


def imports(path):
    """The files a memory file imports, parsed as Claude Code does: `@path` outside frontmatter and code, relative to the file."""
    text = re.sub(r"\A---\n.*?\n---\n", "", path.read_text(), flags=re.S)
    text = re.sub(r"`[^`\n]*`", " ", code_blocks_blanked(text))
    for m in IMPORT.finditer(text):
        name = m.group(1).split("#", 1)[0].replace("\\ ", " ")
        if re.match(r"~/|/.|[a-zA-Z0-9._-]", name):  # what Claude Code accepts as a path
            yield name, Path(os.path.normpath(path.parent / Path(name).expanduser()))


def test_claude_md_imports_resolve(project):
    """Every import in the installed CLAUDE.md, and in the files it imports, is a file setup.sh installed."""
    assert run_setup(project).returncode == 0
    loaded, missing, todo = set(), [], [(project / "CLAUDE.md", 0)]
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
