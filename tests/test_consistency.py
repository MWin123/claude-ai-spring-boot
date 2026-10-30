"""Facts repeated across files stay identical."""
import re

from helpers import CLAUDE_FILES, ROOT, code_blocks, rel

WEB_MD = ROOT / "skills" / "spring-boot" / "references" / "web.md"


def docs_matchers():
    """The permitted OpenAPI/Swagger UI paths of every security example, by location."""
    found = {}
    for path in CLAUDE_FILES:
        for block in code_blocks(path.read_text()):
            for offset, line in enumerate(block.body.splitlines()):
                if '"/openapi.yaml"' in line:
                    found[f"{rel(path)}:{block.line + offset}"] = re.findall(r'"(/[^"]*)"', line)
    return found


def test_security_examples_permit_the_same_docs_paths():
    found = docs_matchers()
    assert len(found) >= 3, f"expected the matchers in web.md and both security.md configs, found {list(found)}"
    assert len({tuple(paths) for paths in found.values()}) == 1, found


def test_prefixed_docs_matchers_match_the_defaults():
    base = next(iter(docs_matchers().values()))
    sentence = re.search(r"Prefix the security matchers the same way \(([^)]*)\)", WEB_MD.read_text()).group(1)
    assert re.findall(r"`(/[^`]+)`", sentence) == ["/api/users" + p for p in base]


def test_versions_agree():
    """A library's version is the same wherever it is spelled out (placeholders like 7.x.y are ignored)."""
    libraries = {
        "openapi-generator": r"openapi-generator|org\.openapi\.generator",
        "springdoc": r"springdoc",
    }
    for library, pattern in libraries.items():
        versions = {}
        for path in CLAUDE_FILES:
            for n, line in enumerate(path.read_text().splitlines(), 1):
                if re.search(pattern, line):
                    for version in re.findall(r"(?<![\w.])(\d+\.\d+\.\d+)(?![\w.])", line):
                        versions.setdefault(version, []).append(f"{rel(path)}:{n}")
        assert len(versions) <= 1, f"{library} versions disagree: {versions}"


def test_examples_use_spring_boot_4():
    old = []
    for path in CLAUDE_FILES:
        text = path.read_text()
        for block in code_blocks(text):
            parent = re.search(r"spring-boot-starter-parent</artifactId>\s*<version>([^<]+)", block.body)
            plugin = re.search(r'id\("org\.springframework\.boot"\) version "([^"]+)"', block.body)
            for m in filter(None, (parent, plugin)):
                if not m.group(1).startswith("4."):
                    old.append(f"{rel(path)}:{block.line}: Spring Boot {m.group(1)}")
    assert not old, "\n".join(old)
