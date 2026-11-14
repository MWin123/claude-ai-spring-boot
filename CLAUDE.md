# claude-ai-spring-boot

## Repository
- This is a template, not an application: agents, skills and config that `setup.sh` copies into Spring Boot projects. There is no Spring Boot build here.
- No project uses the template yet: `setup.sh` installs from scratch, so add no upgrade path, migration steps or backward compatibility.
- Copied into projects: `agents/` and `skills/` (to `.claude/`), `config/settings.json` (to `.claude/settings.json`) and `config/CLAUDE.md` (to the project root). Everything else (`tests/`, `.github/`, `.claude/settings.json`, README, this file) stays here.
- `config/CLAUDE.md` holds the rules for generated projects; don't apply them to this repository.

## Workflow
- Use plan mode for changes across several files or with design choices; write the plan upfront.
- Before committing, run `shellcheck setup.sh` and `pytest tests` (`pip install -r tests/requirements.txt`). Never mark a task done with a failing or skipped check.
- Prove changed Java, Maven, Gradle or YAML examples by building them in a throwaway Spring Boot project in a scratch directory (latest Boot 4.x, the documented plugin and library versions), with positive and negative tests. Start Docker when a check needs it. Never add that project to this repository.
- Keep files short: say each rule once and refer to it from other files instead of repeating it. Simplify where possible without dropping features.

## Consistency
- A renamed section, file, workflow step, agent or skill must be renamed everywhere it is cited; the tests in `tests/test_references.py` find stale references.
- New or renamed agents and skills go into the README tables and directory tree.
- Facts repeated across files stay identical: docs security matchers, library versions, Boot 4 versions. Example code follows the template's own rules: contract-first controllers implementing generated `*Api` interfaces, exception handlers returning `ProblemDetail`, no Boot 3 leftovers.
- When a test rule is too strict for a legitimate example, narrow the rule or add a documented exemption in the test; never weaken the example to satisfy it.

## Reviews
- Findings go into one PR comment, each with a checkbox: unchecked is open; checked is fixed (with "Fixed in `<sha>`") or closed (with the reason). After a squash or rebase, update the SHAs.
- Fix findings with a plan. For each finding, verify, commit, push and tick it in the comment before starting the next.
- Settled, don't raise again: the routing eval (`claude plugin eval`) runs later in a real project, not here.

## Commits and Pull Requests
- Short title, then a one- or two-sentence body that says what changed.
- Author and committer: the configured git identity. If it is unset or Claude's own (`noreply@anthropic.com`, as in cloud sessions), look up the GitHub login with `get_me` and commit with `git -c user.name=<login> -c user.email=<login>@users.noreply.github.com commit --no-gpg-sign`; if the lookup fails, ask.
- Commits end with `Co-Authored-By: Claude <noreply@anthropic.com>`, so GitHub shows both.
- No `Claude-Session` lines in commits or pull requests.

## Tools
- Developer documentation (Spring, Maven, Gradle, libraries): `mcp__Firecrawl__firecrawl_developer_search` first.
- Other web searches and page fetches: `mcp__TinyFish__search` and `mcp__TinyFish__fetch_content`, which are free. Use them instead of `WebSearch` and `WebFetch`.
- GitHub (PRs, comments, files, commits): the `mcp__github__*` tools, not web scraping.
- If those don't fit or fail, use Firecrawl: `mcp__Firecrawl__firecrawl_search` and `mcp__Firecrawl__firecrawl_scrape`.
- Downloading images: the `image-fetcher` skill, and only for that. No other skill or MCP tool downloads images.
- If the TinyFish, GitHub and Firecrawl MCP tools fail or aren't installed, use `WebSearch` and `WebFetch`.
