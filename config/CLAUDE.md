# <project-name>

## Project
- Spring Boot 4.x and Java 21+ with Maven or Gradle (see Build Tool), latest stable dependency versions.
- Project name = the top heading (`setup.sh` takes it from `artifactId` or `rootProject.name`); if it isn't lowercase kebab-case, ask before using it for image or Kubernetes names (never rename silently); base package = group ID.
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
- Use plan mode for non-trivial tasks (3+ steps or architectural decisions); write the plan upfront.
- After a user correction, add the rule to the matching section of this file, or sharpen the rule that is there; one line, no duplicates.
- Never mark a task done without proof: run tests, check logs, diff behavior against main when relevant.
- Make the simplest change that works; find root causes, no temporary fixes. For non-trivial changes look for the more elegant solution, but don't overengineer.

## Skills
- The `conventions` skill holds the rules for all code in this project and loads with this file; if its rules aren't in your context, load the skill before writing or reviewing code: @.claude/skills/conventions/SKILL.md
- Features, endpoints and entities follow the Core Workflow of the `spring-boot` skill. Schema changes: `db-migrations`. Images, Compose, CI, Kubernetes and Helm: `deployment`. Tests: `testing-patterns`. Upgrades to Boot 4: `boot-migration`.
- Other skills: `java-modern` for modern Java features, `jpa-patterns` for fetching and N+1 problems, `logging-patterns` for structured logs and MDC, `design-patterns` for Outbox, Saga, CQRS and the classic patterns, `code-quality` for clean-code rules.
- Skills live in `.claude/skills/<skill>/`, their reference files in `.claude/skills/<skill>/references/`; "`web.md` in the `spring-boot` skill" is `.claude/skills/spring-boot/references/web.md`. Read a single reference directly when only it is needed.

## Subagents
- Do the work yourself with the matching skill; subagents only run tests, review, and research.
- Anything that runs tests goes to `tests`, including the build steps of the skills' workflows. Relay its summary, never raw output.
- Review a single commit or file with `quick-reviewer`; a finished feature or a security audit with `code-reviewer`.
- Look up current or version-specific documentation (release notes, migration guides, library versions) with `docs-researcher` when the skills don't cover it; don't search the web yourself. Name the exact Boot and Java versions in the prompt (`Boot: 4.1.2, Java: 21`).

## Reviews
- Show each `code-reviewer` report in the chat as it is, and post it on the branch's open PR without asking: as a new comment, or, if an earlier review comment there still has open checkboxes, by updating that comment (add only the new findings and name the new commit). Without a PR or GitHub access, only show it.
- Each finding has a checkbox: unchecked is open; checked is fixed (with "Fixed in `<sha>`") or closed (with the reason). After a squash or rebase, update the SHAs.
- Fix findings with a plan, one at a time: verify, commit, push and tick it in the comment before starting the next. After every push to a branch with an open PR, also when nobody mentioned a review, read its review comments and tick each open finding the pushed commits fix.

## Commits and Pull Requests
- Short title, then a one- or two-sentence body that says what changed.
- Author and committer: the configured git identity. If it is unset or Claude's own (`noreply@anthropic.com`, as in cloud sessions), look up the GitHub login with `get_me` and commit with `git -c user.name=<login> -c user.email=<login>@users.noreply.github.com commit --no-gpg-sign`; if the lookup fails, ask.
- Commits end with `Co-Authored-By: Claude <noreply@anthropic.com>`, so GitHub shows both.
- No `Claude-Session` lines in commits or pull requests.

## Tools
- GitHub (PRs, comments, files, commits): the `mcp__github__*` tools, not web scraping.
- Web searches and page fetches other than documentation (that goes to `docs-researcher`, see "Subagents" above): `mcp__TinyFish__search` and `mcp__TinyFish__fetch_content`, which are free; if they don't fit or fail, `mcp__Firecrawl__firecrawl_search` and `mcp__Firecrawl__firecrawl_scrape`.
- If the GitHub, TinyFish and Firecrawl MCP tools fail or aren't installed, use `WebSearch` and `WebFetch`.
