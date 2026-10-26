---
name: conventions
description: Spring Boot project conventions and mandatory rules. Auto-loads when working with Spring Boot, Java, Maven, or Gradle projects. Enforces records-first/targeted Lombok, constructor injection, RestClient, and other standards.
metadata:
  version: "1.0.0"
  domain: backend
  triggers: Spring Boot, Java, Maven, Gradle, Spring Framework, REST API, JPA, Hibernate, microservices
  role: guide
  scope: conventions
  output-format: code
---

# Spring Boot Project Conventions

These conventions apply to ALL code generated or reviewed in the project. Follow them strictly.

## Mandatory Rules

- **Records first, Lombok targeted** — records for DTOs/value types; Lombok only where a record cannot replace the boilerplate, following the Lombok rules in the `java-modern` skill. API request/response models are the exception: they are generated from the spec (see next rule)
- **Constructor injection** — no `@Autowired` on fields
- **Contract-first REST APIs** — a hand-written OpenAPI spec (`src/main/resources/static/openapi.yaml`) defines every endpoint. `openapi-generator` (`spring`, `interfaceOnly`, `useSpringBoot4`) generates the API interfaces and models at build time, and controllers implement those interfaces. Never hand-write `@RequestMapping` controllers or edit generated code; change the spec instead (details in `spring-boot` `references/web.md`)
- **Swagger UI** — add `springdoc-openapi-starter-webmvc-ui` if `spring-boot-starter-webmvc` is present, otherwise `springdoc-openapi-starter-webflux-ui` if `spring-boot-starter-webflux` is; skip if a springdoc starter is already there. Point it at the spec file (`springdoc.swagger-ui.url: /openapi.yaml`)
- **RestClient** over RestTemplate/WebClient for blocking HTTP calls
- **RestTestClient** with `@AutoConfigureRestTestClient` for integration tests
- **Testcontainers** with `@ServiceConnection` (not `@DynamicPropertySource`)
- **Jakarta Persistence** (not `javax.persistence`)
- **Maven or Gradle**, whichever build file the project has (detected once; see the Build Tool section in `CLAUDE.md`)
- **Base Java package** = group ID (`groupId` in `pom.xml`, `group` in `build.gradle(.kts)` or `gradle.properties`)
- **Project name** = parent directory name in lowercase kebab-case (`MyApp` → `my-app`); keep an existing `artifactId` or `rootProject.name`
- **Semantic versioning** — bump PATCH on each new version
- **Docker Compose** for local dependencies
- **CI pipeline** — never generate one unprompted; when asked (or when one exists), detect the existing CI setup (`.github/workflows/`, `.circleci/`, `.gitlab-ci.yml`) and match or extend it
- **Tests** — always write both positive and negative test cases
- Update `README.md` on each new version

## Code Quality Standards

- Use latest Spring Boot 4.x and Java 21+
- `@Transactional(readOnly = true)` at service class level, `@Transactional` on mutating methods
- Validation constraints in the spec (`required`, `minLength`, `maximum`, `pattern`, `format: email`); the generator puts `@Valid @RequestBody` and Bean Validation on the interfaces and models
- `@RestControllerAdvice` extending `ResponseEntityExceptionHandler`, so every error is a Problem Detail (RFC 7807), including `ConstraintViolationException` → 400 (the generated interfaces are `@Validated`)
- Return `ResponseEntity` with proper status codes (201 Created, 204 No Content)
- `@ConfigurationProperties` for type-safe config (no raw `@Value` for groups)
- `@HttpExchange` interfaces for declarative HTTP clients
- Virtual threads enabled by default (`spring.threads.virtual.enabled: true`)
- Problem Details enabled (`spring.mvc.problemdetails.enabled: true`)
- Graceful shutdown configured (`server.shutdown: graceful`)
