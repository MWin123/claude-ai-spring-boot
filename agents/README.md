# Agents

Subagents for work that pays off in a fresh context; the main agent does the rest with the [skills](../skills/README.md). "Subagents" in `config/AGENTS.md` says when Claude hands work to one.

| Agent | Purpose |
|-------|---------|
| [`code-reviewer`](code-reviewer.md) | Reviews files, a commit or a branch and audits security; findings as a checkbox list |
| [`tests`](tests.md) | Runs the test suite, returns only failing tests |
| [`docs-researcher`](docs-researcher.md) | Researches version-specific docs, release notes and issues; returns a short, sourced answer |
