# <project-name>

## Project
- Spring Boot 4.x and Java 21+ with Maven or Gradle (see Build Tool), latest stable dependency versions.
- Project name = the top heading (from `artifactId` or `rootProject.name`); if it isn't lowercase kebab-case, ask before using it for image or Kubernetes names (never rename silently); base package = group ID.
- Semantic versioning: bump PATCH on each new version and update README.md.

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

## Workflow
- Use plan mode for changes with design choices or trade-offs the user should decide.
- After a user correction, add the rule to the matching section of this file, or sharpen the rule that is there; one line, no duplicates.
- Never mark a task done without proof: run tests, check logs, diff behavior against main when relevant.
- Make the simplest change that works; find root causes, no temporary fixes.

## Skills
- The `conventions` skill holds the rules for all code in this project and loads with this file; if its rules aren't in your context, load the skill before writing or reviewing code: @.claude/skills/conventions/SKILL.md
- Features, endpoints and entities follow the Core Workflow of the `spring-boot` skill. Schema changes: `db-migrations`. Images, Compose, CI, Kubernetes and Helm: `deployment`. Tests: `testing-patterns`. Upgrades to Boot 4: `boot-migration`.
- Other skills: `java-modern` for modern Java features, `jpa-patterns` for fetching and N+1 problems, `logging-patterns` for structured logs and MDC, `design-patterns` for Outbox, Saga, CQRS and the classic patterns, `code-quality` for clean-code rules.
- Before a commit, push or pull request, after a `code-reviewer` report and when fixing review findings: `git-workflow`.
- Load every skill with the Skill tool, never by reading its `SKILL.md`. Reference files: "`web.md` in the `spring-boot` skill" is `.claude/skills/spring-boot/references/web.md`. Read a single reference directly when only it is needed.

## Subagents
- Do the work yourself with the matching skill; subagents only run tests, review, and research.
- Anything that runs tests goes to `tests`, including the build steps of the skills' workflows. Relay its summary, never raw output; when a failure line isn't enough to fix it, Read the report at the path it gives.
- Every code review and security audit goes to `code-reviewer`; name the file or commit when only that is to be reviewed.
- Look up a single fact the skills don't cover (a library version, a property, an API signature) yourself with the tools under "Tools". Research that spans several pages or sources (release notes, migration guides, GitHub issues) goes to `docs-researcher`; name the exact Boot and Java versions in the prompt (`Boot: 4.1.2, Java: 21`).

## Tools
- Web searches and page fetches: `mcp__TinyFish__search` and `mcp__TinyFish__fetch_content`, which are free; if they don't fit or fail, `mcp__Firecrawl__firecrawl_search` and `mcp__Firecrawl__firecrawl_scrape`.
- Downloading images: the `image-fetcher` skill, and only for that. No other skill or MCP tool downloads images.
- If the TinyFish and Firecrawl MCP tools fail or aren't installed, use `WebSearch` and `WebFetch`.
