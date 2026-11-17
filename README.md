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

The script copies `agents/`, `skills/`, `config/.claude/settings.json` and `config/.claude/hooks/` into `.claude/`, `config/AGENTS.md` and `config/CLAUDE.md` into the project root, and `config/.claude/settings.user.json` to `~/.claude/settings.json`. `AGENTS.md` gets the project name as its top heading (Maven `artifactId`, Gradle `rootProject.name`, else the directory name); `CLAUDE.md` holds only `@AGENTS.md`, an import that works without symlinks (so on Windows too) and leaves the rules readable by other AI agents. The user settings start Claude Code in auto mode, which Claude Code ignores in project settings. To keep token usage down, the project settings allow only the latest models (Haiku 5.5, Sonnet 5.5, Opus 5.5, Fable 5.2), cap effort at `xhigh`, turn off fast mode and ultracode, and compact at 750k tokens. A hook denies destructive Bash commands (see [Bash Guard](#bash-guard)).

On a re-run, an existing `AGENTS.md` or `CLAUDE.md` that differs is saved as `AGENTS.md.bak` or `CLAUDE.md.bak` before it is replaced (merge project-specific rules back; later backups are numbered, as in `AGENTS.md.2.bak`), same-named agents, skills and hooks are overwritten, and `.claude/settings.json` and `~/.claude/settings.json` are kept (merge the `hooks` block of `config/.claude/settings.json` and `config/.claude/settings.user.json` into existing settings by hand). Nothing is removed, so delete renamed or dropped agents and skills by hand.

## What's Included

### AGENTS.md ([`config/AGENTS.md`](config/AGENTS.md))

Copied into the project root and loaded in every session through the `@AGENTS.md` import in `CLAUDE.md`. It holds the rules for Claude in the generated project:

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

`docs-researcher` and `AGENTS.md` prefer the MCP servers `TinyFish`, `Firecrawl` and `github` (installed under those names) and fall back to WebSearch/WebFetch without them.

### Skills ([`skills/`](skills/))

Knowledge that Claude loads when the task needs it:

| Skill | What it teaches |
|-------|-----------------|
| [`conventions`](skills/conventions/SKILL.md) | Mandatory project rules, loaded with `AGENTS.md` (see [Conventions](#conventions)) |
| [`spring-boot`](skills/spring-boot/SKILL.md) | Core development workflow with 8 reference guides (OpenAPI, web, Swagger UI, data, security, cloud, Spring AI, Boot 4 changes) |
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
- **Build and project:** Maven or Gradle, detected once per session. Base package = group ID; the project name is the top heading of `AGENTS.md`.
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

## Bash Guard

Permission patterns such as `Bash(rm -rf /)` miss `sudo rm -fr /` and `cd x && rm -r -f ~`. So the project settings run `.claude/hooks/guard-bash.py` as a `PreToolUse` hook before every Bash call, in the main session and in subagents. The script splits the command into its simple commands (through `&&`, `;`, pipes, `sudo`, `bash -c`, `$(…)`) and denies these:

| Group | Denied |
|-------|--------|
| Recursive delete | `rm -r` when a target resolves to `/`, the home directory, a system directory (`/etc`, `/usr`, …), the project root, a directory above it, or the project's `.git`. `rm -rf target` and `cd build && rm -rf *` pass. After a `cd` to a directory that doesn't exist yet, only the commands chained with `&&` count as running there: `cd out; rm -rf *` is denied in the project root. |
| find | `find … -delete` or `-exec rm` that starts in one of those directories. In the project root it passes with a name filter (`find . -name '*.orig' -delete`). |
| Disk tools | `dd of=/dev/…`, `mkfs…`, `wipefs`, `shred`, output redirected to a disk device |
| Permissions | `chmod -R`, `chown -R` or `chgrp -R` on `/`, the home directory or a system directory |
| Git push | Any push to `main` or `master`: by name, `HEAD:main`, a plain `git push` while on main or tracking it, `--all`, `--mirror`, deleting it on the remote. Force pushes to feature branches pass. |
| GitHub CLI | `gh repo delete`, `gh repo archive`, `gh release delete`, `gh api -X DELETE` |
| Kubernetes, Helm | `kubectl delete namespace`, `kubectl delete` with `--all` or `-A`, `kubectl drain`, `helm uninstall` |
| Infrastructure | `terraform destroy`, `terraform apply -destroy`, `tofu destroy`, `pulumi destroy` |
| System | `shutdown`, `reboot`, `halt`, `poweroff`, `systemctl poweroff`, `kill -9 -1`, `killall5`, fork bombs |
| Database | `flyway clean` (also through Maven and Gradle), `liquibase drop-all`, `dropdb`, `mysqladmin drop`, `redis-cli FLUSHALL` or `FLUSHDB`, `dropDatabase` in mongosh |

The hook needs `python3` (3.13 or later) on the `PATH`; without it, or with an older one, Claude Code shows a hook error and runs the command. Text that is only data passes: a quoted string, or a heredoc that no shell reads. It is a guardrail, not a sandbox: a command hidden in a script file, in a variable or in a computed `eval` string still passes. To change the list, edit `CHECKS` in the script and the cases in `tests/test_guard_bash.py`.

## Directory Structure

```
.
├── .claude/
│   └── settings.json       # settings for working on this template; runs the hook in config/
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
│   │       ├── ai.md
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
│   ├── .claude/
│   │   ├── hooks/
│   │   │   └── guard-bash.py  # .claude/hooks/guard-bash.py, see Bash Guard
│   │   ├── settings.json   # .claude/settings.json
│   │   └── settings.user.json  # ~/.claude/settings.json
│   ├── AGENTS.md           # project rules (project root)
│   └── CLAUDE.md           # @AGENTS.md (project root)
├── tests/                  # checks for this template, not copied
├── AGENTS.md               # rules for working on this template
├── CLAUDE.md               # @AGENTS.md
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
