---
name: review-checklist
description: Checklist of what to flag when reviewing Spring Boot code. Used by the code-reviewer and quick-reviewer agents; not needed when writing code.
user-invocable: false
---

# Review Checklist

Two sections. The quick review runs **Mechanical** only; the full feature review runs **Mechanical** and **Deep**. This list says what to flag, not how to write code. The rules themselves are in the `conventions` skill (loaded with `CLAUDE.md`), the Lombok rules in `.claude/skills/java-modern/SKILL.md` (section "Boilerplate: Modern Java First, Lombok Targeted") and the Boot 4 changes in `.claude/skills/spring-boot/references/boot4.md`; Read those files only when the change touches them.

## Mechanical

Fast, high-confidence checks that need only the changed lines.

### Correctness
- Null safety: chained calls without null checks, `Optional.get()` without `isPresent()`, returning null instead of Optional or empty collection
- Exception handling: empty catch blocks, catching `Exception`/`Throwable`, swallowed stack traces
- Resource leaks: manual `close()` instead of try-with-resources
- Self-invocation: `@Transactional` or `@Async` called via `this` (bypasses the proxy)
- Missing `@Transactional`/`readOnly = true` on an obvious multi-step write or read

### Security (quick flags)
- Missing `@Valid` on `@RequestBody`; string-concatenated `@Query`/JDBC; JPA entities returned from controllers; hardcoded secrets
- Anything deeper (Spring Security config, CORS/CSRF, TLS, headers, dependency CVEs) belongs to the full review (Deep, Security)

### Conventions
- Contract-first violations: a hand-written `@RequestMapping`/`@GetMapping` controller instead of implementing a generated `*Api` interface, edited generated code, an endpoint or API DTO missing from `openapi.yaml`, a spec change without the matching controller change, a spec `maxLength` that differs from the column length, a spec that breaks the "Spec Design Checklist" in `web.md` of the `spring-boot` skill (unbounded list operation, unbounded strings, one schema for request and response, missing error responses, a breaking change to a published API)
- Violations of the `conventions` skill: `@Autowired` on fields, non-generated DTOs that are not records, `@DynamicPropertySource` instead of `@ServiceConnection`, a CI pipeline generated unprompted, a second compose file next to an existing one
- Violations of the Lombok rules in `java-modern` (on entities: `@Data`, `@EqualsAndHashCode`, `@ToString`, `@Value`, or a class-level `@Builder`)
- Old-style Java where modern Java fits: `Collectors.toList()` (use `.toList()`), `instanceof` plus cast, `switch` with `break`

### Deprecated / Outdated (Boot 4)
- `javax.persistence.*` (use `jakarta.persistence.*`); `WebSecurityConfigurerAdapter` (use a `SecurityFilterChain` bean); `@EnableWebSecurity` without `@Configuration`
- `spring-boot-starter-parent` or the `org.springframework.boot` Gradle plugin below 4.x; classic `spring-boot-starter-web` (use `spring-boot-starter-webmvc` plus `-test` starters)
- `RestTemplate` (prefer `RestClient` or HTTP interface clients); `WebClient` for blocking calls; `TestRestTemplate` in new tests (prefer `RestTestClient` with `@AutoConfigureRestTestClient`; migrated tests may keep it, see `boot4.md`)
- `@MockBean`/`@SpyBean` (use `@MockitoBean`/`@MockitoSpyBean`)
- `com.fasterxml.jackson.databind` imports (Jackson 3 uses `tools.jackson.databind`)

## Deep

Needs the whole feature in view; skip in a quick review.

### Performance
- N+1 queries: lazy collections accessed in loops without `JOIN FETCH` or `@EntityGraph`
- Unbounded queries: `findAll()` without pagination on large tables
- Missing indexes: queries filtering on columns without an index

### Security
- Every item of the "Hardening Checklist" in `security.md` of the `spring-boot` skill that the change touches; for a security audit, all of them across `SecurityConfig`, filters, controllers and `application.yml`
- `grep -r` for common vulnerability patterns: hardcoded passwords or keys, string concatenation in queries, disabled CSRF or headers, `permitAll()` on non-public paths

### Design
- Layering: Controller → Service → Repository; no business logic in controllers, no repository access from controllers
- Transaction boundaries across services: partial writes, calls that need a shared transaction, long transactions holding locks
- `@RestControllerAdvice` for global exception handling; no entities leaking through API responses
- API contract changes: removed or renamed fields, changed status codes, missing versioning
- Tests: new behavior covered by both positive and negative cases
