# Skills

Knowledge that Claude loads when the task needs it; "Skills" in `config/AGENTS.md` routes each task to its skill.

| Skill | What it teaches |
|-------|-----------------|
| [`conventions`](conventions/SKILL.md) | Mandatory project rules (Java, contract-first REST, HTTP, tests, build, infrastructure), loaded with the project's `AGENTS.md` |
| [`spring-boot`](spring-boot/SKILL.md) | Core workflow; 8 reference guides (OpenAPI, web, Swagger UI, data, security, cloud, Spring AI, Boot 4) |
| [`code-quality`](code-quality/SKILL.md) | Clean code principles and Java pitfalls |
| [`design-patterns`](design-patterns/SKILL.md) | Classic patterns in Spring; Outbox, Saga and CQRS |
| [`testing-patterns`](testing-patterns/SKILL.md) | JUnit 5, Mockito, MockMvc, RestTestClient, Testcontainers; 1 reference guide (integration tests) |
| [`java-modern`](java-modern/SKILL.md) | Records, Java 21+ features, virtual threads; 1 reference guide (Lombok) |
| [`jpa-patterns`](jpa-patterns/SKILL.md) | JPA/Hibernate pitfalls, Hibernate 7, optimistic locking |
| [`logging-patterns`](logging-patterns/SKILL.md) | Structured JSON logging, SLF4J, MDC |
| [`db-migrations`](db-migrations/SKILL.md) | Liquibase (default) or Flyway, consistent with the entities; 2 reference guides (liquibase, flyway) |
| [`boot-migration`](boot-migration/SKILL.md) | Upgrades Spring Boot 2.x/3.x projects to 4.x |
| [`deployment`](deployment/SKILL.md) | Containers, Docker Compose, CI/CD, Kubernetes; 3 reference guides (containers, kubernetes, helm) |
| [`git-workflow`](git-workflow/SKILL.md) | Commit and pull request rules, review findings as PR checkboxes |
| [`review-checklist`](review-checklist/SKILL.md) | What to flag in a review; preloaded by `code-reviewer`, hidden from the `/` menu |

## Example

`> "Add a products API: list, search by name, create. PostgreSQL."`: the `spring-boot` skill writes `openapi.yaml`, generates the `ProductsApi` interface, then adds the entity, migration, service, a controller implementing `ProductsApi`, a Problem Details handler, and tests that the `tests` agent runs. To change the API later, edit the spec and rebuild.
