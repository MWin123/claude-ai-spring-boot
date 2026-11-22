# Spring Boot Template for Claude Code

Skills and agents that guide Claude Code to build Spring Boot 4.x / Java 21+ applications with best practices for REST APIs, JPA, security, testing and Kubernetes.

## Quick Start

1. Create a Spring Boot project with Maven or Gradle (e.g. with Spring Initializr). `install.py` needs Python 3.13 or later and a `pom.xml`, `build.gradle(.kts)` or `settings.gradle(.kts)`.
2. Run the script from the project, or pass the project directory:

   ```bash
   cd my-project
   /path/to/claude-ai-spring-boot/install.py   # or: install.py /path/to/my-project
   ```

3. Start `claude` and describe what you want to build:

   ```bash
   claude
   > "Build a REST API for managing orders with PostgreSQL"
   ```

Claude picks the skills and agents itself; call them directly with `/jpa-patterns`, `/boot-migration 4.1` or `@agent-code-reviewer`.

## What's Included

- **[Claude Template](config/):** the files for the project root and `.claude/`. `AGENTS.md` holds the rules for Claude in the project (build tool detection, workflow, which skill or agent handles which task) and imports the [`conventions`](skills/conventions/SKILL.md) skill.
- **[Agents](agents/README.md):** subagents for work that pays off in a fresh context.
- **[Skills](skills/README.md):** Spring Boot, testing, JPA, migrations, deployment and more, loaded when the task needs them.
- **[Hooks](config/.claude/hooks/README.md):** the Bash Guard, which denies destructive Bash commands.

## Installation

`install.py` copies `agents/`, `skills/` and `config/.claude/hooks/` to `.claude/` and `config/AGENTS.md` and `config/CLAUDE.md` to the project root, and merges the settings into `.claude/settings.json` and `~/.claude/settings.json`.

The user settings (in `$CLAUDE_CONFIG_DIR`, if set) turn on auto mode; the project settings register the Bash Guard and limit the models and the effort level. A settings file with invalid JSON stops the install.

On a re-run, same-named agents, skills and hooks are overwritten; a changed `AGENTS.md`, `CLAUDE.md` or settings file is backed up as `.bak` first. Nothing is removed. The MCP servers `TinyFish`, `Firecrawl` and `github` are optional; without them Claude uses WebSearch and WebFetch.

## Directory Structure

```
.
├── .claude/settings.json   # settings for working on this template; runs the hook in config/
├── .github/
│   ├── dependabot.yml      # monthly grouped updates for tests/ and Actions
│   └── workflows/claude-files.yml
├── agents/                 # subagents, see agents/README.md
├── skills/                 # skills, see skills/README.md
├── config/                 # copied into the project
│   ├── .claude/
│   │   ├── hooks/          # hooks, see hooks/README.md
│   │   ├── settings.json   # .claude/settings.json
│   │   └── settings.user.json  # ~/.claude/settings.json
│   ├── AGENTS.md           # project rules (project root)
│   └── CLAUDE.md           # @AGENTS.md (project root)
├── tests/                  # checks for this template, not copied
├── AGENTS.md               # rules for working on this template
├── CLAUDE.md               # @AGENTS.md
├── install.py              # installs the template into a project
└── LICENSE
```

## Tests

`tests/` checks the template files and stays in this repository. GitHub Actions runs it with `mypy --strict install.py config/.claude/hooks tests` on every pull request. Locally:

```bash
pip install -r tests/requirements.txt
mypy --strict install.py config/.claude/hooks tests
pytest tests
```
