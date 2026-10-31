---
name: boot-migration
description: Upgrade an existing Spring Boot 2.x/3.x project to Spring Boot 4.x in small verified steps - starters, Jackson 3, test annotations, javax to jakarta, renamed properties and Spring Security 7. Use when the user asks to migrate or upgrade a project to Boot 4.
argument-hint: "[target Boot version, e.g. 4.1]"
---

# Boot Migration Skill

Upgrade existing projects to Spring Boot 4.x / Java 21+. The change list is the "Migration Checklist" in `references/boot4.md` of the `spring-boot` skill; follow it, do not improvise. Never add new features while migrating.

## Workflow

1. Read `references/boot4.md` in the `spring-boot` skill before touching anything. The target is the version given with the request; otherwise ask `docs-researcher` for the latest 4.x release and its migration guide.
2. Establish a baseline: read the build file (`pom.xml`: Boot parent and Java version; `build.gradle(.kts)`: `org.springframework.boot` plugin version and Java toolchain), have the `tests` agent run the build with all tests, and record what passes. Do not start from a red build without telling the user.
3. Work through the Migration Checklist in order, one step at a time, with a `tests` run after each. Do not jump straight to 4.x from below 3.5. Boot 4 needs Gradle 8.14+ or 9.x; update the wrapper first if it is older (`./gradlew wrapper --gradle-version <version>`).
4. Fix root causes: no `@Disabled` tests, no pinned old versions to silence errors.
5. Finish with the steps completed, steps blocked (with the error), test results before and after, and follow-ups.

## Rules

- Smallest diff that compiles and passes; do not reformat or restructure unrelated code.
- Do not convert classes to records, move controllers to contract-first or apply Lombok changes as part of the migration; mention them as follow-ups.
- One concern per step so each can be reviewed or reverted on its own. Do not commit unless asked.
- If a dependency has no Boot 4-compatible release, stop and tell the user the version found.
