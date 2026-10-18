# Spring Boot Plugin for Claude Code (v1.0)

A Claude Code plugin with production-ready skills and agents for building Spring Boot 4.x / Java 21+ applications. Install the plugin and start generating your app — the skills and agents guide Claude to follow best practices for REST APIs, JPA, security, testing, cloud-native deployment, and Kubernetes.

## Installation

```bash
# Install from marketplace
claude plugin install spring-boot

# Or install directly from repository
claude plugin install --url https://github.com/piomin/claude-ai-spring-boot
```

To test locally during development:

```bash
claude --plugin-dir /path/to/claude-ai-spring-boot
```

## What's Included

### Agents (`agents/`)

Specialized agents that Claude Code can invoke for specific tasks:

| Agent | Purpose |
|-------|---------|
| `spring-boot-engineer` | Build Spring Boot 4.x apps with layered architecture |
| `code-reviewer` | Review code for correctness, security, Spring Boot conventions |
| `kubernetes-specialist` | K8s deployments, probes, ConfigMap/Secret, Prometheus, Skaffold |
| `devops-engineer` | CI/CD pipelines, Paketo Buildpacks, Skaffold |
| `docker-expert` | Multi-stage Dockerfiles, Paketo Buildpacks, image optimization |
| `security-engineer` | Spring Security, OWASP, input validation, SSL Bundles |

### Skills (`skills/`)

Reusable knowledge that Claude loads contextually:

| Skill | What it teaches |
|-------|-----------------|
| `conventions` | Mandatory project rules: No Lombok, constructor injection, RestClient, testing standards |
| `spring-boot` | Core Spring Boot development with 5 reference guides (web, data, security, cloud, testing) |
| `code-quality` | Clean code principles, API contracts, null safety, exception handling |
| `design-patterns` | Classic patterns (Factory, Builder, Strategy) + enterprise (Saga, Outbox, CQRS) |
| `testing-patterns` | JUnit 5, Mockito, MockMvc, RestTestClient, Testcontainers with @ServiceConnection |
| `java-modern` | Java 21+ features: records, sealed classes, pattern matching, virtual threads |
| `jpa-patterns` | JPA/Hibernate pitfalls (N+1, lazy loading), Hibernate 6/7, optimistic locking |
| `logging-patterns` | Structured JSON logging, SLF4J, MDC, AI-friendly formats |

### Key Conventions

The plugin enforces these rules via the `conventions` skill:

- **No Lombok** — explicit constructors, getters/setters, `LoggerFactory.getLogger()`
- **Constructor injection** — no `@Autowired` on fields
- **RestClient** over RestTemplate/WebClient for blocking HTTP calls
- **RestTestClient** with `@AutoConfigureRestTestClient` for integration tests
- **Testcontainers** with `@ServiceConnection` (not `@DynamicPropertySource`)
- **Jakarta Persistence** (not `javax.persistence`)
- **Maven** with `pl.piomin.services` group ID
- **CI pipeline** — auto-detected from existing project config
- **Docker Compose** for local dependencies

### Cloud-Native Coverage

The `cloud.md` reference covers:

- Spring Cloud (Config Server, Eureka, Gateway, Resilience4j, LoadBalancer)
- Distributed tracing with OpenTelemetry (OTLP) and Micrometer Observation API
- Virtual Threads, HTTP Interface Clients (`@HttpExchange`), GraalVM Native Image
- Kubernetes: ConfigMap/Secret with `envFrom`, Prometheus annotations, startup/liveness/readiness probes, `preStop` hook, graceful shutdown
- TLS: cert-manager (Ingress TLS + pod-level mTLS), SSL Bundles with hot reload
- Config Tree for reading mounted secrets from files
- Paketo Buildpacks via `spring-boot:build-image`
- Skaffold for local K8s development loop

## Usage

After installing, describe what you want to build — Claude will use the skills and agents automatically:

```bash
cd my-project
claude
> "Build a REST API for managing orders with PostgreSQL"
```

You can also invoke skills and agents directly:

```bash
# Invoke a skill
> /spring-boot:jpa-patterns

# Use an agent
> @agent-spring-boot:code-reviewer
```

## Directory Structure

```
.
├── .claude-plugin/
│   └── plugin.json
├── agents/
│   ├── code-reviewer.md
│   ├── devops-engineer.md
│   ├── docker-expert.md
│   ├── kubernetes-specialist.md
│   ├── security-engineer.md
│   └── spring-boot-engineer.md
├── skills/
│   ├── conventions/SKILL.md
│   ├── code-quality/SKILL.md
│   ├── design-patterns/SKILL.md
│   ├── java-modern/SKILL.md
│   ├── jpa-patterns/SKILL.md
│   ├── logging-patterns/SKILL.md
│   ├── spring-boot/
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── cloud.md
│   │       ├── data.md
│   │       ├── security.md
│   │       ├── testing.md
│   │       └── web.md
│   └── testing-patterns/SKILL.md
├── README.md
└── LICENSE
```

## Blog Post

You can find a detailed explanation of this plugin in the post: [Claude Code Template for Spring Boot](https://piotrminkowski.com/2026/03/24/claude-code-template-for-spring-boot/).

## License

Apache License 2.0
