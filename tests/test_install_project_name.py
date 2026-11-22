"""install.py puts the project name from the pom.xml or Gradle files into the heading of the installed AGENTS.md."""
from pathlib import Path

import pytest

from install_fixtures import expected_agents_md, install, run_install

pytestmark = pytest.mark.usefixtures("user_settings")  # install.py reads CLAUDE_CONFIG_DIR, so no test touches the real ~/.claude


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

    result = install(tmp_path)

    assert (tmp_path / "AGENTS.md").read_text() == expected_agents_md("order-service")
    assert "(project: order-service)" in result.stdout


@pytest.mark.parametrize("files", [{"settings.gradle": "include 'api'\n"}, {"build.gradle.kts": ""}])
def test_gradle_name_defaults_to_the_directory(tmp_path: Path, files: dict[str, str]) -> None:
    project = tmp_path / "my-app"
    project.mkdir()
    for name, content in files.items():
        (project / name).write_text(content)

    install(project)

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
