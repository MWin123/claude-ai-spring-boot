---
name: boot-migration
description: Upgrade an existing Spring Boot 2.x/3.x project to Spring Boot 4.x in small verified steps - starters, Jackson 3, test annotations, javax to jakarta, renamed properties and Spring Security 7. Use when the user asks to migrate or upgrade a project to Boot 4.
argument-hint: "[target Boot version, e.g. 4.1]"
---

# Boot Migration Skill

Upgrade existing projects to Spring Boot 4.x / Java 21+. The change list is the "Migration Checklist" below; follow it, do not improvise. Never add new features while migrating.

## Workflow

1. Read `references/boot4.md` in the `spring-boot` skill (what changed in Boot 4) before touching anything. The target is the version given with the request; otherwise ask `docs-researcher` for the latest 4.x release and its migration guide.
2. Establish a baseline: read the build file (`pom.xml`: Boot parent and Java version; `build.gradle(.kts)`: `org.springframework.boot` plugin version and Java toolchain), have the `tests` agent run the build with all tests, and record what passes. Do not start from a red build without telling the user.
3. Work through the Migration Checklist in order, one step at a time. After each step, have the `tests` agent run the build with all tests (`./mvnw verify`, Gradle: `./gradlew build`). Do not jump straight to 4.x from below 3.5. Boot 4 needs Gradle 8.14+ or 9.x; update the wrapper first if it is older (`./gradlew wrapper --gradle-version <version>`).
4. Fix root causes: no `@Disabled` tests, no pinned old versions to silence errors.
5. Finish with the steps completed, steps blocked (with the error), test results before and after, and follow-ups.

## Migration Checklist

1. On Boot 3.5 (go there first if lower; from Boot 2 that hop includes `javax.*` -> `jakarta.*`): replace `@MockBean`/`@SpyBean` with `@MockitoBean`/`@MockitoSpyBean` (available since 3.4). Boot 4 removes the old annotations, so tests would not compile after the parent bump.
2. Bump the parent/BOM (Gradle: the `org.springframework.boot` plugin) to 4.x and Java to 21+.
3. Replace classic starters with modular ones and add `-test` starters, plus `spring-boot-starter-restclient` or `-webclient` where the app injects those clients.
4. Run the OpenRewrite Jackson 2 -> 3 recipe; replace `ObjectMapper` injection with `JsonMapper`.
5. `TestRestTemplate` still works if the test class has `@AutoConfigureTestRestTemplate` and the project has the `spring-boot-resttestclient` (test) and `spring-boot-restclient` (runtime) dependencies. Moving to `RestTestClient` rewrites tests, so list it as a follow-up.
6. Renamed properties: add `spring-boot-properties-migrator` (runtime scope) for one run; it logs every renamed or removed property at startup. Fix them and remove the dependency. Then review the Spring Security 7 changes.
7. Add `@NullMarked` to packages incrementally (follow-up, not part of the migration).

## Rules

- Smallest diff that compiles and passes; do not reformat or restructure unrelated code.
- Do not convert classes to records, move controllers to contract-first or apply Lombok changes as part of the migration; mention them as follow-ups.
- One concern per step so each can be reviewed or reverted on its own. Do not commit unless asked.
- If a dependency has no Boot 4-compatible release, stop and tell the user the version found.
