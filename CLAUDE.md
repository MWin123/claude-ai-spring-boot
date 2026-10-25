## Workflow
- Use plan mode for non-trivial tasks (3+ steps or architectural decisions); write the spec upfront.
- After a user correction, record the pattern in `tasks/lessons.md`; review it at session start.
- Never mark a task done without proof: run tests, check logs, diff behavior against main when relevant.
- Make the simplest change that works; find root causes, no temporary fixes. For non-trivial changes look for the more elegant solution, but don't overengineer.

## Project Rules
- Spring Boot 4.x with Maven or Gradle (see Build Tool) and the latest stable dependency versions (Jackson 3, `@MockitoBean`, modular starters); see the Boot 4 reference in the `spring-boot` skill.
- Write positive and negative tests for generated code.
- Minimize generated code: records for DTOs/value types, pattern matching, switch expressions; Lombok only where a record can't replace the boilerplate (rules in the `java-modern` skill).
- Project name = parent directory name in lowercase kebab-case (`MyApp` → `my-app`); keep an existing name, and ask only if it doesn't match that form (never rename silently); base package = group ID.
- Semantic versioning: bump PATCH on each new version and update README.md.
- Docker Compose: extend an existing `compose.yaml`/`docker-compose.yml`, otherwise generate `compose.yaml` with all needed components.

## Build Tool
- Determine it once, before the first build command, and reuse it for the session: `pom.xml` → Maven (`./mvnw`, else `mvn`); `build.gradle(.kts)` or, in a multi-project build, only `settings.gradle(.kts)` → Gradle (`./gradlew`, else `gradle`). Both present: ask which one builds the app. Neither: stop and ask the user to add one.
- Name it in every subagent prompt (`Build tool: Gradle`).
- Name, group and version: Maven `artifactId`, `groupId`, `version` in `pom.xml`; Gradle `rootProject.name` in `settings.gradle(.kts)` (directory name if unset), `group` and `version` in `build.gradle(.kts)` or `gradle.properties` (`./gradlew -q properties` shows the resolved values). Bump the version where it is defined. If the group or version is not set, ask for it before generating code.

| Task | Maven | Gradle |
|------|-------|--------|
| Build with all tests | `./mvnw verify` | `./gradlew build` |
| Unit tests | `./mvnw test` | `./gradlew test` |
| Run | `./mvnw spring-boot:run` | `./gradlew bootRun` |
| Image (Buildpacks) | `./mvnw spring-boot:build-image` | `./gradlew bootBuildImage` |
| Output directory | `target/` | `build/` |

- Dependency snippets in the skills are Maven XML. In Gradle use the same coordinates in the existing DSL (Kotlin or Groovy): `implementation`, `runtimeOnly` for runtime scope, `testImplementation` for test scope, `compileOnly` plus `annotationProcessor` for annotation processors such as Lombok.

## Subagents
- Anything that runs tests goes to `tests`. Relay its summary, never raw output.
- Review a single commit or file with `quick-reviewer`.
- When `spring-boot-engineer` reports Docker Compose or CI needs, pass them to `devops-engineer`.
- Look up current or version-specific documentation (release notes, migration guides, library versions) with `docs-researcher` when the skills don't cover it; don't search the web yourself. Name the exact Boot and Java versions in the prompt (`Boot: 4.0.1, Java: 21`). Other subagents can't call it, so research first and pass the result in their prompt.
