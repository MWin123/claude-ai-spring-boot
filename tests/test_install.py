"""install.py copies agents, skills and config/ (.claude/settings.json, .claude/hooks, AGENTS.md, CLAUDE.md) into a project
and config/.claude/settings.user.json into the user's Claude directory, and nothing else."""
import ast
import filecmp
import os
import shutil
from pathlib import Path

import pytest

from helpers import CONFIG, ROOT
from install_fixtures import INSTALL, POM, expected_agents_md, install, run_install

pytestmark = pytest.mark.usefixtures("user_settings")  # install.py reads CLAUDE_CONFIG_DIR, so no test touches the real ~/.claude


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

    install(target, script=source / "install.py")

    claude = target / ".claude"
    assert sorted(str(p.relative_to(claude)) for p in claude.rglob("README.md")) == ["skills/demo/README.md"]


@pytest.mark.parametrize(
    "build_file", ["pom.xml", "build.gradle", "build.gradle.kts", "settings.gradle", "settings.gradle.kts"]
)
def test_copies_only_the_claude_files(tmp_path: Path, build_file: str) -> None:
    (tmp_path / build_file).write_text(POM if build_file == "pom.xml" else "")

    install(tmp_path)

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

    install(project)

    assert gitignore.read_text() == "target/\n"


def test_defaults_to_the_current_directory(project: Path) -> None:
    install(cwd=project)

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


def test_warns_when_the_hook_python_is_too_old(project: Path, tmp_path_factory: pytest.TempPathFactory) -> None:
    bin_dir = tmp_path_factory.mktemp("bin")
    (bin_dir / "python3").write_text("#!/bin/sh\nexit 1\n")
    (bin_dir / "python3").chmod(0o755)

    result = install(project, env={**os.environ, "PATH": str(bin_dir)})

    assert "python3 on the PATH is missing or older than 3.13" in result.stderr


def test_no_warning_with_a_current_hook_python(project: Path) -> None:
    assert "Warning" not in install(project).stderr


def test_install_runs_on_old_pythons_up_to_the_version_check() -> None:
    """`./install.py` must be executable, and older Pythons must parse it to show the version message."""
    assert os.access(INSTALL, os.X_OK)
    tree = ast.parse(INSTALL.read_text(), feature_version=(3, 8))
    assert not [node for node in ast.walk(tree) if isinstance(node, ast.TypeAlias)]
