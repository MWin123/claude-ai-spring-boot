"""setup.sh copies agents, skills and config/ (settings.json, CLAUDE.md) into a project, and nothing else."""
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


def run_setup(*args, cwd=None):
    return subprocess.run(["bash", str(SETUP), *map(str, args)], cwd=cwd, capture_output=True, text=True)


@pytest.fixture
def project(tmp_path):
    (tmp_path / "pom.xml").write_text("<project/>")
    return tmp_path


def assert_same_tree(source, target):
    diff = filecmp.dircmp(source, target)
    assert not (diff.left_only or diff.right_only or diff.diff_files or diff.funny_files), diff.report()
    for sub in diff.common_dirs:
        assert_same_tree(source / sub, target / sub)


@pytest.mark.parametrize(
    "build_file", ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"]
)
def test_copies_only_the_claude_files(tmp_path, build_file):
    (tmp_path / build_file).write_text("")

    result = run_setup(tmp_path)

    assert result.returncode == 0, result.stderr
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted([".claude", "CLAUDE.md", build_file])
    assert sorted(p.name for p in (tmp_path / ".claude").iterdir()) == ["agents", "settings.json", "skills"]
    assert_same_tree(ROOT / "agents", tmp_path / ".claude" / "agents")
    assert_same_tree(ROOT / "skills", tmp_path / ".claude" / "skills")
    assert filecmp.cmp(CONFIG / "settings.json", tmp_path / ".claude" / "settings.json", shallow=False)
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


def test_backs_up_a_different_claude_md(project):
    (project / "CLAUDE.md").write_text("project rules")

    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert (project / "CLAUDE.md.bak").read_text() == "project rules"
    assert "saved as CLAUDE.md.bak" in result.stdout
    assert filecmp.cmp(CONFIG / "CLAUDE.md", project / "CLAUDE.md", shallow=False)


def test_never_overwrites_an_earlier_backup(project):
    (project / "CLAUDE.md").write_text("original rules")
    run_setup(project)
    (project / "CLAUDE.md").write_text("edited rules")

    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert (project / "CLAUDE.md.bak").read_text() == "original rules"
    timestamped = list(project.glob("CLAUDE.md.*.bak"))
    assert len(timestamped) == 1 and timestamped[0].read_text() == "edited rules"


def test_no_backup_for_an_identical_claude_md(project):
    (project / "CLAUDE.md").write_text((CONFIG / "CLAUDE.md").read_text())

    result = run_setup(project)

    assert result.returncode == 0, result.stderr
    assert not list(project.glob("CLAUDE.md*.bak"))


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
    assert project / ".claude" / "skills" / "conventions" / "SKILL.md" in loaded, "CLAUDE.md must import conventions"
