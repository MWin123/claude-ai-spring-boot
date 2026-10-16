# Claude Code Template for Spring Boot (v1.0)

A production-ready template of Claude Code skills and agents for building Spring Boot 4.x / Java 21+ applications. Clone this repo and start generating your app with Claude Code — the skills and agents guide Claude to follow best practices for REST APIs, JPA, security, testing, cloud-native deployment, and Kubernetes.

## What's Included

### Agents (`.claude/agents/`)

Specialized agents that Claude Code can invoke for specific tasks:

| Agent | Purpose |
|-------|---------|
| `spring-boot-engineer` | Build Spring Boot 4.x apps with layered architecture |
| `code-reviewer` | Review code for correctness, security, Spring Boot conventions |
| `kubernetes-specialist` | K8s deployments, probes, ConfigMap/Secret, Prometheus, Skaffold |
| `devops-engineer` | CI/CD pipelines (CircleCI), Paketo Buildpacks, Skaffold |
| `docker-expert` | Multi-stage Dockerfiles, Paketo Buildpacks, image optimization |
| `security-engineer` | Spring Security, OWASP, input validation, SSL Bundles |

### Skills (`.claude/skills/`)

Reusable knowledge that Claude loads contextually:

| Skill | What it teaches |
|-------|-----------------|
| `spring-boot` | Core Spring Boot development with 5 reference guides (web, data, security, cloud, testing) |
| `code-quality` | Clean code principles, API contracts, null safety, exception handling |
| `design-patterns` | Classic patterns (Factory, Builder, Strategy) + enterprise (Saga, Outbox, CQRS) |
| `testing-patterns` | JUnit 5, Mockito, MockMvc, RestTestClient, Testcontainers with @ServiceConnection |
| `java-modern` | Java 21+ features: records, sealed classes, pattern matching, virtual threads |
| `jpa-patterns` | JPA/Hibernate pitfalls (N+1, lazy loading), Hibernate 6/7, optimistic locking |
| `logging-patterns` | Structured JSON logging, SLF4J, MDC, AI-friendly formats |

### Key Conventions

The template enforces these rules via `CLAUDE.md`:

- **No Lombok** — explicit constructors, getters/setters, `LoggerFactory.getLogger()`
- **Constructor injection** — no `@Autowired` on fields
- **RestClient** over RestTemplate/WebClient for blocking HTTP calls
- **RestTestClient** with `@AutoConfigureRestTestClient` for integration tests
- **Testcontainers** with `@ServiceConnection` (not `@DynamicPropertySource`)
- **Jakarta Persistence** (not `javax.persistence`)
- **Maven** with `pl.piomin.services` group ID
- **CircleCI** for CI/CD, Docker Compose for local dependencies

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

1. Clone this repository
2. Start Claude Code in the project directory
3. Describe what you want to build — Claude will use the skills and agents automatically

```bash
git clone https://github.com/piomin/claude-ai-spring-boot.git my-app
cd my-app
claude
```

## Directory Structure

```
.
├── .claude
│   ├── agents
│   │   ├── code-reviewer.md
│   │   ├── devops-engineer.md
│   │   ├── docker-expert.md
│   │   ├── kubernetes-specialist.md
│   │   ├── security-engineer.md
│   │   └── spring-boot-engineer.md
│   └── skills
│       ├── README.md
│       ├── code-quality/SKILL.md
│       ├── design-patterns/SKILL.md
│       ├── java-modern/SKILL.md
│       ├── jpa-patterns/SKILL.md
│       ├── logging-patterns/SKILL.md
│       ├── spring-boot
│       │   ├── SKILL.md
│       │   └── references
│       │       ├── cloud.md
│       │       ├── data.md
│       │       ├── security.md
│       │       ├── testing.md
│       │       └── web.md
│       └── testing-patterns/SKILL.md
├── CLAUDE.md
├── README.md
└── pom.xml
```

## Blog Post

You can find a detailed explanation of this template in the post: [Claude Code Template for Spring Boot](https://piotrminkowski.com/2026/03/24/claude-code-template-for-spring-boot/).
