---
name: conventions
description: Spring Boot project conventions and mandatory rules. Auto-loads when working with Spring Boot, Java, or Maven projects. Enforces No-Lombok, constructor injection, RestClient, and other standards.
metadata:
  version: "1.0.0"
  domain: backend
  triggers: Spring Boot, Java, Maven, Spring Framework, REST API, JPA, Hibernate, microservices
  role: guide
  scope: conventions
  output-format: code
---

# Spring Boot Project Conventions

These conventions apply to ALL code generated or reviewed in the project. Follow them strictly.

## Mandatory Rules

- **No Lombok** — write explicit constructors, getters, setters; use `LoggerFactory.getLogger()` for loggers
- **Constructor injection** — no `@Autowired` on fields
- **RestClient** over RestTemplate/WebClient for blocking HTTP calls
- **RestTestClient** with `@AutoConfigureRestTestClient` for integration tests
- **Testcontainers** with `@ServiceConnection` (not `@DynamicPropertySource`)
- **Jakarta Persistence** (not `javax.persistence`)
- **Java records** for DTOs (request/response objects)
- **Maven** for dependency management
- **Group ID**: `pl.piomin.services`
- **Artifact name** = parent directory name
- **Semantic versioning** — bump PATCH on each new version
- **Docker Compose** for local dependencies
- **CI pipeline** — generate CI/CD config; detect existing CI setup (`.github/workflows/`, `.circleci/`, `.gitlab-ci.yml`) and match it, or default to a sensible choice
- **Tests** — always write both positive and negative test cases
- Update `README.md` on each new version

## Code Quality Standards

- Use latest Spring Boot 4.x and Java 21+
- `@Transactional(readOnly = true)` at service class level, `@Transactional` on mutating methods
- `@Valid @RequestBody` on all POST/PUT endpoints
- `@RestControllerAdvice` for global exception handling
- Return `ResponseEntity` with proper status codes (201 Created, 204 No Content)
- `@ConfigurationProperties` for type-safe config (no raw `@Value` for groups)
- `@HttpExchange` interfaces for declarative HTTP clients
- Virtual threads enabled by default (`spring.threads.virtual.enabled: true`)
- Problem Details enabled (`spring.mvc.problemdetails.enabled: true`)
- Graceful shutdown configured (`server.shutdown: graceful`)
