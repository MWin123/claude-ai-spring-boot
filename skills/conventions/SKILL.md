---
name: conventions
description: Spring Boot project conventions and mandatory rules. Auto-loads when working with Spring Boot, Java, or Maven projects. Enforces records-first/targeted Lombok, constructor injection, RestClient, and other standards.
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

- **Records first, Lombok targeted** — records for DTOs/value types; Lombok only where a record cannot replace the boilerplate, following the Lombok rules in the `java-modern` skill
- **Constructor injection** — no `@Autowired` on fields
- **OpenAPI spec** — add `springdoc-openapi-starter-webmvc-ui` if `spring-boot-starter-webmvc` is present, otherwise `springdoc-openapi-starter-webflux-ui` if `spring-boot-starter-webflux` is; skip if a springdoc starter is already there (details in `spring-boot` `references/web.md`)
- **RestClient** over RestTemplate/WebClient for blocking HTTP calls
- **RestTestClient** with `@AutoConfigureRestTestClient` for integration tests
- **Testcontainers** with `@ServiceConnection` (not `@DynamicPropertySource`)
- **Jakarta Persistence** (not `javax.persistence`)
- **Maven** for dependency management
- **Base Java package** = group ID from `pom.xml` (ask the user if there is no `pom.xml`)
- **Artifact name** = parent directory name in lowercase kebab-case (`MyApp` → `my-app`); keep an existing `artifactId`
- **Semantic versioning** — bump PATCH on each new version
- **Docker Compose** for local dependencies
- **CI pipeline** — never generate one unprompted; when asked (or when one exists), detect the existing CI setup (`.github/workflows/`, `.circleci/`, `.gitlab-ci.yml`) and match or extend it
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
