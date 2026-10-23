---
name: review-checklist
description: Checklist of what to flag when reviewing Spring Boot code. Used by the code-reviewer and quick-reviewer agents; not needed when writing code.
---

# Review Checklist

Two sections. The quick review runs **Mechanical** only; the full feature review runs **Mechanical** and **Deep**. Rules themselves live in the `conventions`, `java-modern` and `spring-boot` (`references/boot4.md`) skills; this list says what to flag, not how to write code.

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
- Anything deeper (Spring Security config, CORS/CSRF, TLS, headers, dependency CVEs): recommend `security-engineer`

### Conventions
- Violations of the `conventions` skill: `@Autowired` on fields, DTOs that are not records, `@DynamicPropertySource` instead of `@ServiceConnection`, a pipeline or Compose file generated unprompted
- Violations of the Lombok rules in `java-modern`
- Old-style Java where modern Java fits: `Collectors.toList()` (use `.toList()`), `instanceof` plus cast, `switch` with `break`

### Deprecated / Outdated (Boot 4)
- `javax.persistence.*` (use `jakarta.persistence.*`); `WebSecurityConfigurerAdapter` (use a `SecurityFilterChain` bean); `@EnableWebSecurity` without `@Configuration`
- `spring-boot-starter-parent` below 4.x; classic `spring-boot-starter-web` (use `spring-boot-starter-webmvc` plus `-test` starters)
- `RestTemplate` (prefer `RestClient` or HTTP interface clients); `WebClient` for blocking calls; `TestRestTemplate` in new tests (prefer `RestTestClient` with `@AutoConfigureRestTestClient`; migrated tests may keep it, see `boot4.md`)
- `@MockBean`/`@SpyBean` (use `@MockitoBean`/`@MockitoSpyBean`)
- `com.fasterxml.jackson.databind` imports (Jackson 3 uses `tools.jackson.databind`)

## Deep

Needs the whole feature in view; skip in a quick review.

### Performance
- N+1 queries: lazy collections accessed in loops without `JOIN FETCH` or `@EntityGraph`
- Unbounded queries: `findAll()` without pagination on large tables
- Missing indexes: queries filtering on columns without an index

### Design
- Layering: Controller → Service → Repository; no business logic in controllers, no repository access from controllers
- Transaction boundaries across services: partial writes, calls that need a shared transaction, long transactions holding locks
- `@RestControllerAdvice` for global exception handling; no entities leaking through API responses
- API contract changes: removed or renamed fields, changed status codes, missing versioning
- Tests: new behavior covered by both positive and negative cases
