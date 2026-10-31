---
name: conventions
description: Mandatory coding rules for this Spring Boot 4.x project - records first with targeted Lombok, constructor injection, contract-first REST APIs, RestClient, Testcontainers with @ServiceConnection, transactions, Problem Details and the default application.yml. Load before writing, changing or reviewing Java code, build files or the OpenAPI spec.
when_to_use: Any code change in the project - new feature, endpoint, entity, service, test, configuration or dependency - and every code review.
---

# Spring Boot Project Conventions

These conventions apply to ALL code generated or reviewed in the project. Follow them strictly.

## Mandatory Rules

- **Records first, Lombok targeted** — modern Java (records, pattern matching, switch expressions); records for DTOs/value types; Lombok only where a record cannot replace the boilerplate, following the Lombok rules in the `java-modern` skill. API request/response models are the exception: they are generated from the spec (see next rule)
- **Constructor injection** — no `@Autowired` on fields
- **Contract-first REST APIs** — a hand-written OpenAPI spec (`src/main/resources/static/openapi.yaml`) defines every endpoint. `openapi-generator` (`spring`, `interfaceOnly`, `useSpringBoot4`) generates the API interfaces and models at build time, and controllers implement those interfaces. Never hand-write `@RequestMapping` controllers or edit generated code; change the spec instead (details in `spring-boot` `references/web.md`)
- **Swagger UI** — add `springdoc-openapi-starter-webmvc-ui` if `spring-boot-starter-webmvc` is present, otherwise `springdoc-openapi-starter-webflux-ui` if `spring-boot-starter-webflux` is; skip if a springdoc starter is already there. Point it at the spec file (`springdoc.swagger-ui.url: /openapi.yaml`)
- **No Boot 3 leftovers** — Jackson 3, `@MockitoBean`, modular starters (list in `spring-boot` `references/boot4.md`)
- **RestClient** (`spring-boot-starter-restclient`) over RestTemplate/WebClient for blocking HTTP calls
- **RestTestClient** with `@AutoConfigureRestTestClient` for integration tests
- **Testcontainers** with `@ServiceConnection` (not `@DynamicPropertySource`)
- **Jakarta Persistence** (not `javax.persistence`)
- **Maven or Gradle**, whichever build file the project has (detected once; see the Build Tool section in `CLAUDE.md`)
- **Docker Compose** (`compose.yaml`) for local dependencies; extend an existing compose file (details in the `deployment` skill)
- **CI pipeline** — never generate one unprompted; when asked (or when one exists), detect the existing CI setup (`.github/workflows/`, `.circleci/`, `.gitlab-ci.yml`) and match or extend it; if there is none, ask which CI system to use
- **Tests** — always write both positive and negative test cases

## Code Quality Standards

- `@Transactional(readOnly = true)` at service class level, `@Transactional` on mutating methods
- Validation constraints in the spec (`required`, `minLength`, `maximum`, `pattern`, `format: email`); the generator puts `@Valid @RequestBody` and Bean Validation on the interfaces and models
- `@RestControllerAdvice` extending `ResponseEntityExceptionHandler`, so every error is a Problem Detail (RFC 7807), including `ConstraintViolationException` → 400 (the generated interfaces are `@Validated`)
- Return `ResponseEntity` with proper status codes (201 Created, 204 No Content)
- `@ConfigurationProperties` for type-safe config (no raw `@Value` for groups)
- `@HttpExchange` interfaces for declarative HTTP clients; OpenFeign remains an option with service discovery (Eureka/Consul) and load balancing
- Map entities to the generated API models in a mapper; never return entities
- Secrets and environment-specific values (URLs, credentials) come from environment variables or mounted files, never from `application.yml` or code

## Default application.yml

Every new app starts with virtual threads, Problem Details, graceful shutdown and JSON console logs (plain text only in the `human-logs` profile, `logging-patterns` skill):

```yaml
spring:
  threads:
    virtual:
      enabled: true
  mvc:
    problemdetails:
      enabled: true
  lifecycle:
    timeout-per-shutdown-phase: 30s
server:
  shutdown: graceful
logging:
  structured:
    format:
      console: logstash
```
