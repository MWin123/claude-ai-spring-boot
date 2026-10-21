## Workflow
- Use plan mode for non-trivial tasks (3+ steps or architectural decisions); write the spec upfront.
- After a user correction, record the pattern in `tasks/lessons.md`; review it at session start.
- Never mark a task done without proof: run tests, check logs, diff behavior against main when relevant.
- Make the simplest change that works; find root causes, no temporary fixes. For non-trivial changes look for the more elegant solution, but don't overengineer.

## Project Rules
- Spring Boot 4.x with Maven and the latest stable dependency versions (Jackson 3, `@MockitoBean`, modular starters); see the Boot 4 reference in the `spring-boot` skill.
- Write positive and negative tests for generated code.
- Minimize generated code: records for DTOs/value types, pattern matching, switch expressions; Lombok only where a record can't replace the boilerplate (rules in the `java-modern` skill).
- `pom.xml`: artifactId = parent directory name (if it differs, ask; never rename silently); base package = group ID. If there is no `pom.xml`, ask for the group ID and starting version first.
- Semantic versioning: bump PATCH on each new version and update README.md.
- Docker Compose: extend an existing `compose.yaml`/`docker-compose.yml`, otherwise generate `compose.yaml` with all needed components.

## Subagents
- Anything that runs tests goes to `tests`. Relay its summary, never raw output.
- Review a single commit or file with `quick-reviewer`.
