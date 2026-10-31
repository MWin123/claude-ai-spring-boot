"""Code examples parse and don't bring back patterns the skills tell Claude to avoid."""
import json
import re

import pytest
import yaml

from helpers import CLAUDE_FILES, ROOT, code_blocks, code_blocks_blanked, rel

# Recommended code must not contain these.
BANNED = {
    r"@MockBean\b": "removed in Boot 4, use @MockitoBean",
    r"@SpyBean\b": "removed in Boot 4, use @MockitoSpyBean",
    r"com\.fasterxml\.jackson\.databind": "Jackson 2, Boot 4 uses tools.jackson.databind",
    r"spring-boot-starter-web\b(?!mvc|flux|services|socket)": "use spring-boot-starter-webmvc",
    r"\bjavax\.(?:persistence|validation|servlet|annotation)\b": "use jakarta.*",
    r"new RestTemplate\b|\bRestTemplateBuilder\b": "use RestClient",
    r"@DynamicPropertySource\b": "use @ServiceConnection",
    r"/v3/api-docs\.yaml": "Swagger UI loads the hand-written /openapi.yaml",
    r"@ExceptionHandler\(Exception\.class\)": "catch-all turns Spring Security's 403 into a 500",
    r"@(?:Request|Get|Post|Put|Delete|Patch)Mapping\b": "contract-first: mappings come from the generated *Api interface",
    r"spring-boot-starter-aop\b": "Boot 4's starter is spring-boot-starter-aspectj",
    r"\bHttpServiceProxyFactory\b": "@ImportHttpServices registers the clients (boot4.md)",
    r"resilience4j-spring-boot3\b": "fails at startup on Boot 4",
    r"@(?:CircuitBreaker|Retry|RateLimiter|Bulkhead)\(name\b": "Resilience4j annotations need resilience4j-spring-boot3, which fails on Boot 4",
}
# Property keys that Boot 4 and Spring Cloud 2025.1 no longer bind, matched against the full dotted key
BANNED_KEYS = {
    r"management\.otlp\.tracing\b": "use management.opentelemetry.tracing.export.otlp.*",
    r"management\.zipkin\.tracing\b": "use management.tracing.export.zipkin.*",
    r"spring\.cloud\.gateway\.(?!server\b)": "use spring.cloud.gateway.server.webflux.*",
}
# Boot 4 API versioning on hand-written mappings (migrated projects), not application code
CONTRACT_FIRST_EXEMPT = {"skills/spring-boot/references/boot4.md"}
MAPPING = next(p for p in BANNED if "Mapping" in p)


def without_comments(line):
    """Drop // and # comments (they often say "not X"), keeping URLs like https://."""
    return re.split(r"(?:^|\s)(?://|#|<!--)", line, maxsplit=1)[0]


def blocks(langs):
    return [
        pytest.param(path, block, id=f"{rel(path)}:{block.line}")
        for path in CLAUDE_FILES
        for block in code_blocks(path.read_text())
        if block.lang in langs
    ]


@pytest.mark.parametrize("path,block", [p for p in blocks({"yaml", "yml"}) if "{{" not in p.values[1].body])
def test_yaml_blocks_parse(path, block):  # Helm templates ({{ }}) are not YAML until rendered
    list(yaml.safe_load_all(block.body))


def config_keys(block):
    """Every dotted key of a YAML or properties block, parents included."""
    if block.lang == "properties":
        return [l.split("=", 1)[0].strip() for l in block.body.splitlines() if "=" in l and not l.lstrip().startswith("#")]
    keys = []

    def walk(node, prefix):
        for key, value in node.items() if isinstance(node, dict) else ():
            keys.append(f"{prefix}{key}")
            walk(value, f"{prefix}{key}.")

    for document in yaml.safe_load_all(block.body):
        walk(document, "")
    return keys


@pytest.mark.parametrize("path,block", [p for p in blocks({"yaml", "yml", "properties"}) if "{{" not in p.values[1].body])
def test_no_banned_config_keys(path, block):
    found = [f"{key} ({reason})" for key in config_keys(block) for pattern, reason in BANNED_KEYS.items() if re.match(pattern, key)]
    assert not found, "\n".join(found)


@pytest.mark.parametrize("path", CLAUDE_FILES, ids=rel)
def test_java_blocks_hold_no_config(path):
    """YAML or properties inside a java block escape the YAML parse and key checks."""
    found = []
    for block in code_blocks(path.read_text()):
        if block.lang == "java":
            for offset, line in enumerate(block.body.splitlines()):
                if re.match(r"[a-z][\w-]*:\s*(#.*)?$|[a-z][\w-]*(\.[\w-]+)+\s*=", line):
                    found.append(f"line {block.line + offset}: {line.strip()}")
    assert not found, "\n".join(found)


@pytest.mark.parametrize("path,block", blocks({"json"}))
def test_json_blocks_parse(path, block):
    json.loads(block.body)


@pytest.mark.parametrize("path,block", [p for p in blocks({"yaml"}) if "\nopenapi: " in "\n" + p.values[1].body])
def test_openapi_local_refs_resolve(path, block):
    spec = yaml.safe_load(block.body)
    missing = []
    for ref in re.findall(r"\$ref: '#/([^']+)'", block.body):
        node = spec
        for key in ref.split("/"):
            node = node.get(key) if isinstance(node, dict) else None
        if node is None:
            missing.append(ref)
    assert not missing, f"unresolved $refs: {missing}"


@pytest.mark.parametrize("path", CLAUDE_FILES, ids=rel)
def test_no_banned_patterns_in_code(path):
    found = []
    for block in code_blocks(path.read_text()):
        for offset, line in enumerate(block.body.splitlines()):
            code = without_comments(line)
            for pattern, reason in BANNED.items():
                if pattern == MAPPING and rel(path) in CONTRACT_FIRST_EXEMPT:
                    continue
                if re.search(pattern, code):
                    found.append(f"line {block.line + offset}: {line.strip()} ({reason})")
    assert not found, "\n".join(found)


@pytest.mark.parametrize("path", [p for p in CLAUDE_FILES if rel(p) not in CONTRACT_FIRST_EXEMPT], ids=rel)
def test_controllers_implement_generated_interfaces(path):
    """Contract-first: every @RestController example implements a generated *Api interface."""
    handwritten = []
    for block in code_blocks(path.read_text()):
        lines = block.body.splitlines()
        for n, line in enumerate(lines):
            if re.match(r"\s*@RestController\b", without_comments(line)):
                declaration = next((l for l in lines[n:] if re.search(r"\bclass\s+\w+", l)), "")
                if not re.search(r"\bimplements\b.*\b\w+Api\b", declaration):
                    handwritten.append(f"line {block.line + n}: {declaration.strip()}")
    assert not handwritten, "\n".join(handwritten)


@pytest.mark.parametrize("path", CLAUDE_FILES, ids=rel)
def test_exception_handlers_return_problem_details(path):
    """Errors are Problem Details: every @ExceptionHandler method returns ProblemDetail."""
    wrong = []
    for block in code_blocks(path.read_text()):
        lines = block.body.splitlines()
        for n, line in enumerate(lines):
            if re.match(r"\s*@ExceptionHandler\b", line):
                method = next((l for l in lines[n:] if re.match(r"\s*(public|protected)\s+\S", l)), "")
                if not re.match(r"\s*(public|protected)\s+ProblemDetail\s", method):
                    wrong.append(f"line {block.line + n}: {method.strip()}")
    assert not wrong, "\n".join(wrong)


# Besides the build, the tests agent runs only commands Claude Code allows without a permission rule
TESTS_AGENT_BANNED = {
    r"\b(?:mkdir|touch)\b": "no marker file: the start time comes from date",
    r"\s-l\s": "Maven ignores -l while target/ is missing",
    r"&&|;|\|": "chained or piped commands don't match permission rules",
    r"\bdate\b.*\s-u\b": "find -newermt reads the start time as local time",
    r"%dT%H": "BSD find (macOS) reads the T as a military time zone",
}


def test_tests_agent_commands_need_no_permission_rules():
    text = code_blocks_blanked((ROOT / "agents" / "tests.md").read_text())
    found = [
        f"`{span}`: {reason}"
        for span in re.findall(r"`([^`\n]+)`", text)
        for pattern, reason in TESTS_AGENT_BANNED.items()
        if re.search(pattern, span)
    ]
    assert not found, "\n".join(found)
