"""Facts repeated across files stay identical."""
import re

from helpers import CLAUDE_FILES, DOCS, ROOT, code_blocks, frontmatter, rel

SWAGGER_UI_MD = ROOT / "skills" / "spring-boot" / "references" / "swagger-ui.md"


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
    assert len(found) >= 2, f"expected the matchers in swagger-ui.md and security.md, found {list(found)}"
    assert len({tuple(paths) for paths in found.values()}) == 1, found


def test_prefixed_docs_matchers_match_the_defaults():
    base = next(iter(docs_matchers().values()))
    sentence = re.search(r"Prefix the security matchers the same way \(([^)]*)\)", SWAGGER_UI_MD.read_text()).group(1)
    assert re.findall(r"`(/[^`]+)`", sentence) == ["/api/users" + p for p in base]


def test_versions_agree():
    """A library's version is the same wherever it is spelled out (placeholders like 7.x.y are ignored)."""
    libraries = {
        "openapi-generator": r"openapi-generator|org\.openapi\.generator",
        "springdoc": r"springdoc",
        "Spring Cloud": r"spring-cloud-dependencies|spring-cloud\.version",
    }
    for library, pattern in libraries.items():
        versions = {}
        for path in CLAUDE_FILES:
            for n, line in enumerate(path.read_text().splitlines(), 1):
                if re.search(pattern, line):
                    for version in re.findall(r"(?<![\w.])(\d+\.\d+\.\d+)(?![\w.])", line):
                        versions.setdefault(version, []).append(f"{rel(path)}:{n}")
        assert len(versions) <= 1, f"{library} versions disagree: {versions}"


def test_boot_versions_agree():
    """Every spelled-out Spring Boot version (parent, Gradle plugin, "Boot 4.1.2") is the same."""
    pattern = re.compile(
        r"spring-boot-starter-parent</artifactId>\s*<version>(\d+\.\d+\.\d+)"
        r'|id\("org\.springframework\.boot"\) version "(\d+\.\d+\.\d+)"'
        r"|\bBoot:? (\d+\.\d+\.\d+)"
    )
    versions = {}
    for path in DOCS:
        for m in pattern.finditer(path.read_text()):
            versions.setdefault(next(g for g in m.groups() if g), []).append(rel(path))
    assert len(versions) <= 1, f"Spring Boot versions disagree: {versions}"


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


def test_code_review_findings_are_checkboxes():
    """The code-reviewer report is the PR comment whose checkboxes "Reviews" in config/CLAUDE.md tracks."""
    report = next(b for b in code_blocks((ROOT / "agents/code-reviewer.md").read_text()) if b.lang == "markdown")
    findings = [line for line in report.body.splitlines() if line.startswith("- ") and "✅" not in line]
    assert findings and all(line.startswith("- [ ] ") for line in findings), "code-reviewer findings need a checkbox"
    assert "## Reviews" in (ROOT / "config/CLAUDE.md").read_text(), "config/CLAUDE.md lost its Reviews section"


def test_docs_researcher_tool_order_matches_its_tools():
    """Every web tool the agent may call has a place in its Tool Order, and the order names no tool it lacks."""
    path = ROOT / "agents/docs-researcher.md"
    order = path.read_text().split("## Tool Order", 1)[1].split("\n## ", 1)[0]
    steps = [line for line in order.splitlines() if re.match(r"\d+\. ", line)]
    named = set(re.findall(r"`(\w+)`|\b(Web(?:Search|Fetch))\b", "\n".join(steps)))
    named = {mcp or builtin for mcp, builtin in named}
    tools = [t.strip() for t in frontmatter(path)["tools"].split(",")]
    web = {t.rsplit("__", 1)[-1] for t in tools if t.startswith("mcp__") or t.startswith("Web")}
    assert named == web, f"only in Tool Order: {sorted(named - web)}; only in tools: {sorted(web - named)}"
    assert "`firecrawl_developer_search`" in steps[0], "developer search comes first (Tools in CLAUDE.md)"
