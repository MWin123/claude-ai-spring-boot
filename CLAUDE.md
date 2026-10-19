### 1. Plan Mode Default
- Enter plan mode for ANY not-trivial task (3+ steps or architectural decisions)
- Use plan mode for verification steps, not just building
- Write detailed specs upfront to reduce ambiguity

### 2. Self-Improvement Loop
- After ANY correction from the user: update `tasks/lessons.md` with the pattern
- Write rules for yourself that prevent the same mistake
- Ruthlessly iterate on these lessons until the mistake rate drops
- Review lessons at session start for a project

### 3. Verification Before Done
- Never mark a task complete without proving it works
- Diff behavior between main and your changes when relevant
- Ask yourself: "Would a staff engineer approve this?"
- Run tests, check logs, demonstrate correctness

### 4. Demand Elegance (Balanced)
- For non-trivial changes: pause and ask "is there a more elegant way?"
- If a fix feels hacky: "Knowing everything I know now, implement the elegant solution"
- Skip this for simple, obvious fixes. Don't overengineer
- Challenge your own work before presenting it

## Core Principles
- **Simplicity First**: Make every change as simple as possible. Impact minimal code
- **No Laziness**: Find root causes. No temporary fixes. Senior developer standards

## Project General Instructions

- Always use the latest stable versions of dependencies, unless a non-stable version is strictly required.
- Always write Java code as the Spring Boot application.
- Always use Maven for dependency management.
- Always create test cases for the generated code both positive and negative.
- Always generate the GitHub Actions workflow in the .github/workflows directory to verify the code.
- Minimize the amount of code generated. Prefer modern Java features that remove boilerplate (records for DTOs/value types, pattern matching, switch expressions).
- The Maven artifact name should be the same as the parent directory name. If an existing `pom.xml` has a different `artifactId`, ask the user whether to keep it or rename it; never change it silently.
- Use semantic versioning for the Maven project. Each time you generate a new version, bump the PATCH section of the version number.
- Use the group ID from pom.xml as the base Java package. If there is no `pom.xml`, ask the user for the group ID (and the starting version) before generating code.
- Records first, Lombok only where a record cannot replace the boilerplate; follow the Lombok rules in the `java-modern` skill.
- Docker Compose: if a compose file (`compose.yaml` or `docker-compose.yml`) already exists, change or extend it; otherwise generate `compose.yaml` with all components the application needs.
- Target Spring Boot 4.x (Jackson 3, `@MockitoBean`, modular starters); see `.claude/skills/spring-boot/references/boot4.md`.
- Update README.md each time you generate a new version.
