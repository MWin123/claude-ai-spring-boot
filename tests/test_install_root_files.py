"""install.py backs up a different AGENTS.md or CLAUDE.md, replaces a symlink with a file and never loses an earlier backup."""
from pathlib import Path

import pytest

from helpers import CONFIG
from install_fixtures import expected_agents_md, install

pytestmark = pytest.mark.usefixtures("user_settings")  # install.py reads CLAUDE_CONFIG_DIR, so no test touches the real ~/.claude

ROOT_FILES = pytest.mark.parametrize("file", ["AGENTS.md", "CLAUDE.md"])


def expected(file: str) -> str:
    """The installed content of a root file for the project `demo`."""
    return expected_agents_md("demo") if file == "AGENTS.md" else (CONFIG / file).read_text()


@ROOT_FILES
def test_backs_up_a_different_root_file(project: Path, file: str) -> None:
    (project / file).write_text("project rules")

    result = install(project)

    assert (project / f"{file}.bak").read_text() == "project rules"
    assert f"Existing {file} saved as {file}.bak" in result.stdout
    assert (project / file).read_text() == expected(file)
    assert len(list(project.glob("*.bak"))) == 1, "only the different file is backed up"


@pytest.mark.parametrize(("link", "file"), [("CLAUDE.md", "AGENTS.md"), ("AGENTS.md", "CLAUDE.md")])
def test_replaces_a_symlinked_root_file(project: Path, link: str, file: str) -> None:
    """Copying through the link would overwrite the other root file with this one's content."""
    (project / file).write_text("project rules")
    (project / link).symlink_to(file)

    result = install(project)

    assert f"Existing {link} was a symlink; replaced by a file" in result.stdout
    for name in (link, file):
        assert not (project / name).is_symlink()
        assert (project / name).read_text() == expected(name)
    assert [(b.name, b.read_text()) for b in project.glob("*.bak")] == [(f"{file}.bak", "project rules")]


def test_replaces_a_dangling_symlink(project: Path) -> None:
    (project / "CLAUDE.md").symlink_to("missing.md")

    install(project)

    assert not (project / "CLAUDE.md").is_symlink()
    assert not (project / "missing.md").exists()


@ROOT_FILES
def test_never_overwrites_an_earlier_backup(project: Path, file: str) -> None:
    (project / file).write_text("original rules")
    install(project)
    (project / file).write_text("edited rules")
    install(project)
    (project / file).write_text("rules edited again")

    result = install(project)

    assert f"Existing {file} saved as {file}.3.bak" in result.stdout
    backups = {b.name: b.read_text() for b in project.glob(f"{file}*.bak")}
    assert backups == {
        f"{file}.bak": "original rules", f"{file}.2.bak": "edited rules", f"{file}.3.bak": "rules edited again",
    }


def test_no_backup_for_identical_root_files(project: Path) -> None:
    install(project)

    install(project)

    assert not list(project.glob("*.bak"))
