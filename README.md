# Spring Boot Template for Claude Code

Skills and agents that guide Claude Code to build Spring Boot 4.x / Java 21+ applications with best practices for REST APIs, JPA, security, testing and Kubernetes.

## Quick Start

1. Create a Spring Boot project with Maven or Gradle (e.g. with Spring Initializr). `setup.sh` needs a `pom.xml`, `build.gradle(.kts)` or `settings.gradle(.kts)` and refuses to run otherwise.
2. Run the script from the project, or pass the project directory:

   ```bash
   cd my-project
   /path/to/claude-ai-spring-boot/setup.sh   # or: setup.sh /path/to/my-project
   ```

3. Start `claude` and describe what you want to build:

   ```bash
   claude
   > "Build a REST API for managing orders with PostgreSQL"
   ```

The script copies `agents/`, `skills/` and `config/settings.json` into `.claude/`, and `config/CLAUDE.md` into the project root with the project name as its top heading (Maven `artifactId`, Gradle `rootProject.name`, else the directory name).

On a re-run, an existing `CLAUDE.md` is saved as `CLAUDE.md.bak` before it is replaced (merge project-specific rules back), same-named agents and skills are overwritten, and `.claude/settings.json` is kept. Nothing is removed, so delete renamed or dropped agents and skills by hand.

## What's Included

### CLAUDE.md ([`config/CLAUDE.md`](config/CLAUDE.md))

Copied into the project root and loaded in every session. It holds the rules for Claude in the generated project:

- **Build tool:** detects Maven or Gradle once per session, with a command table for build, test, run and image.
- **Workflow:** plan mode, proof before "done".
- **Routing:** which skill to load for which task, and when to hand work to the `tests`, reviewer and `docs-researcher` agents.
- **Conventions:** imports the `conventions` skill (see [Conventions](#conventions)).

### Agents ([`agents/`](agents/))

Subagents for work that pays off in a fresh context. The main agent does development, migration and deployment itself with the skills below.

| Agent | Purpose |
|-------|---------|
| [`code-reviewer`](agents/code-reviewer.md) | Reviews a file, a commit or a finished feature, and audits security; findings as a checkbox list, branch reviews posted to the PR |
| [`tests`](agents/tests.md) | Runs the test suite, returns only failing tests |
| [`docs-researcher`](agents/docs-researcher.md) | Researches version-specific docs, release notes and GitHub issues across several sources; returns a short, sourced answer |

`docs-researcher` and `CLAUDE.md` prefer the MCP servers `TinyFish`, `Firecrawl` and `github` (installed under those names) and fall back to WebSearch/WebFetch without them.

### Skills ([`skills/`](skills/))

Knowledge that Claude loads when the task needs it:

| Skill | What it teaches |
|-------|-----------------|
| [`conventions`](skills/conventions/SKILL.md) | Mandatory project rules, loaded with `CLAUDE.md` (see [Conventions](#conventions)) |
| [`spring-boot`](skills/spring-boot/SKILL.md) | Core development workflow with 7 reference guides (OpenAPI, web, Swagger UI, data, security, cloud, Boot 4 changes) |
| [`code-quality`](skills/code-quality/SKILL.md) | Clean code principles and Java pitfalls |
| [`design-patterns`](skills/design-patterns/SKILL.md) | Spring forms of the classic patterns; Outbox, Saga and CQRS |
| [`testing-patterns`](skills/testing-patterns/SKILL.md) | JUnit 5, Mockito, MockMvc, RestTestClient, Testcontainers; 1 reference guide (integration tests) |
| [`java-modern`](skills/java-modern/SKILL.md) | Records, Java 21+ preferences, virtual threads; 1 reference guide (Lombok rules) |
| [`jpa-patterns`](skills/jpa-patterns/SKILL.md) | JPA/Hibernate pitfalls, Hibernate 7, optimistic locking |
| [`logging-patterns`](skills/logging-patterns/SKILL.md) | Structured JSON logging, SLF4J, MDC |
| [`db-migrations`](skills/db-migrations/SKILL.md) | Liquibase (default) or Flyway, kept consistent with JPA entities; 2 reference guides (liquibase, flyway) |
| [`boot-migration`](skills/boot-migration/SKILL.md) | Upgrades Spring Boot 2.x/3.x projects to 4.x (`/boot-migration 4.1`) |
| [`deployment`](skills/deployment/SKILL.md) | Containers, Docker Compose, CI/CD, Kubernetes and Helm with 3 reference guides (containers, kubernetes, helm) |
| [`git-workflow`](skills/git-workflow/SKILL.md) | Commit and pull request rules, review findings as checkboxes in a PR comment |
| [`review-checklist`](skills/review-checklist/SKILL.md) | What to flag in a review; preloaded by `code-reviewer`, hidden from the `/` menu |

### Conventions

- **Java:** records for DTOs, Lombok only where a record can't replace the boilerplate, constructor injection, Jakarta Persistence.
- **REST:** contract-first. A hand-written `src/main/resources/static/openapi.yaml` defines the endpoints, openapi-generator creates the interfaces and models at build time, and controllers implement them. Swagger UI at `/swagger-ui.html`, spec at `/openapi.yaml`.
- **HTTP and tests:** `RestClient` for blocking calls; `RestTestClient` and Testcontainers with `@ServiceConnection` for integration tests.
- **Build and project:** Maven or Gradle, detected once per session. Base package = group ID; the project name is the top heading of `CLAUDE.md`.
- **Infrastructure:** Docker Compose for local dependencies; no CI pipeline unless asked.

## Usage

Describe what you want; Claude picks the skills and agents. You can also call them directly:

```bash
> /jpa-patterns
> /boot-migration 4.1
> @agent-code-reviewer
```

For example, `> "Add a products API: list, search by name, create. PostgreSQL."` makes the `spring-boot` skill:

1. write `openapi.yaml` with `/api/v1/products` and generate the `ProductsApi` interface and models;
2. create the entity, repository, migration, mapper, transactional service, and a controller that implements `ProductsApi`;
3. add a `@RestControllerAdvice` returning Problem Details, and enable virtual threads and graceful shutdown;
4. write unit, slice and Testcontainers tests with positive and negative cases; the `tests` agent runs them and reports failures only.

To change the API later, edit the spec and rebuild; never edit generated code.

## Directory Structure

```
.
├── .claude/settings.json   # settings for working on this template
├── .github/workflows/claude-files.yml
├── agents/
│   ├── code-reviewer.md
│   ├── docs-researcher.md
│   └── tests.md
├── skills/
│   ├── boot-migration/SKILL.md
│   ├── code-quality/SKILL.md
│   ├── conventions/SKILL.md
│   ├── db-migrations/
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── flyway.md
│   │       └── liquibase.md
│   ├── deployment/
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── containers.md
│   │       ├── helm.md
│   │       └── kubernetes.md
│   ├── design-patterns/SKILL.md
│   ├── git-workflow/SKILL.md
│   ├── java-modern/
│   │   ├── SKILL.md
│   │   └── references/
│   │       └── lombok.md
│   ├── jpa-patterns/SKILL.md
│   ├── logging-patterns/SKILL.md
│   ├── review-checklist/SKILL.md
│   ├── spring-boot/
│   │   ├── SKILL.md
│   │   └── references/
│   │       ├── boot4.md
│   │       ├── cloud.md
│   │       ├── data.md
│   │       ├── openapi.md
│   │       ├── security.md
│   │       ├── swagger-ui.md
│   │       └── web.md
│   └── testing-patterns/
│       ├── SKILL.md
│       └── references/
│           └── integration.md
├── config/                 # copied into the project
│   ├── CLAUDE.md           # project rules (project root)
│   └── settings.json       # .claude/settings.json
├── tests/                  # checks for this template, not copied
├── CLAUDE.md               # rules for working on this template
├── README.md
├── setup.sh
└── LICENSE
```

## Tests

`tests/` checks the template files and stays in this repository. GitHub Actions runs it with `shellcheck setup.sh` on every pull request. Locally:

```bash
pip install -r tests/requirements.txt
pytest tests
```
