# Spring Boot Template for Claude Code

Production-ready skills and agents for building Spring Boot 4.x / Java 21+ applications with Claude Code. Copy them into your project and start generating your app — the skills and agents guide Claude to follow best practices for REST APIs, JPA, security, testing, cloud-native deployment, and Kubernetes.

## Installation

Copy the files into an existing Spring Boot project (or a new one, next to its `pom.xml`):

```bash
cd my-project
mkdir -p .claude
cp -r /path/to/claude-ai-spring-boot/agents  .claude/agents
cp -r /path/to/claude-ai-spring-boot/skills  .claude/skills
cp /path/to/claude-ai-spring-boot/CLAUDE.md  CLAUDE.md
```

Claude Code loads `.claude/agents/` and `.claude/skills/` from the project automatically, and `CLAUDE.md` from the project root. Start `claude` in the project directory to use them.

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
| `tests` | Runs the test suite, returns only failing tests (max 20 lines) |

### Skills (`skills/`)

Reusable knowledge that Claude loads contextually:

| Skill | What it teaches |
|-------|-----------------|
| `conventions` | Mandatory project rules: records first, targeted Lombok, constructor injection, RestClient, testing standards |
| `spring-boot` | Core Spring Boot development with 6 reference guides (web, data, security, cloud, testing, Boot 4 changes) |
| `code-quality` | Clean code principles, API contracts, null safety, exception handling |
| `design-patterns` | Classic patterns (Factory, Builder, Strategy) + enterprise (Saga, Outbox, CQRS) |
| `testing-patterns` | JUnit 5, Mockito, MockMvc, RestTestClient, Testcontainers with @ServiceConnection |
| `java-modern` | Java 21+ features: records, Lombok rules, sealed classes, pattern matching, virtual threads |
| `jpa-patterns` | JPA/Hibernate pitfalls (N+1, lazy loading), Hibernate 7, optimistic locking |
| `logging-patterns` | Structured JSON logging, SLF4J, MDC, AI-friendly formats |

### Key Conventions

The `conventions` skill enforces these rules:

- **Modern Java first, Lombok targeted** — records for DTOs and value types; Lombok only for `@Slf4j` (always), `@RequiredArgsConstructor`, `@Getter`/`@Setter` and `@Builder` where useful; on JPA entities only the safe subset (never `@Data`/`@EqualsAndHashCode`/`@ToString`/`@Value`; `@Builder` needs `@NoArgsConstructor`)
- **Constructor injection** — no `@Autowired` on fields
- **RestClient** over RestTemplate/WebClient for blocking HTTP calls
- **RestTestClient** with `@AutoConfigureRestTestClient` for integration tests
- **Testcontainers** with `@ServiceConnection` (not `@DynamicPropertySource`)
- **Jakarta Persistence** (not `javax.persistence`)
- **Maven**; base Java package = group ID from `pom.xml` (asked for if missing); `artifactId` should match the folder name (asked about if it differs)
- **CI pipeline** — not generated unless asked; an existing setup is detected and extended
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

After copying the files, describe what you want to build — Claude will use the skills and agents automatically:

```bash
cd my-project
claude
> "Build a REST API for managing orders with PostgreSQL"
```

You can also invoke skills and agents directly:

```bash
# Invoke a skill
> /jpa-patterns

# Use an agent
> @agent-code-reviewer
```

## Directory Structure

```
.
├── agents/
│   ├── code-reviewer.md
│   ├── devops-engineer.md
│   ├── docker-expert.md
│   ├── kubernetes-specialist.md
│   ├── security-engineer.md
│   ├── spring-boot-engineer.md
│   └── tests.md
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
│   │       ├── boot4.md
│   │       ├── cloud.md
│   │       ├── data.md
│   │       ├── security.md
│   │       ├── testing.md
│   │       └── web.md
│   └── testing-patterns/SKILL.md
├── CLAUDE.md
├── README.md
└── LICENSE
```

## Blog Post

You can find a detailed explanation of this plugin in the post: [Claude Code Template for Spring Boot](https://piotrminkowski.com/2026/03/24/claude-code-template-for-spring-boot/).

## License

Apache License 2.0
