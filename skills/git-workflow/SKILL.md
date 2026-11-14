---
name: git-workflow
description: This project's rules for commits, pull requests and review findings - commit message and identity, posting code-reviewer reports to the PR, checkbox findings.
when_to_use: 'Before a commit, push or pull request; "commit this", "open a PR"; after a code-reviewer report; fixing or ticking review findings.'
---

# Git Workflow

GitHub (PRs, comments, files, commits): the `mcp__github__*` tools, not web scraping; if they fail or aren't installed, `WebSearch` and `WebFetch`.

## Reviews
- Show each `code-reviewer` report in the chat as it is. Post reviews of the whole branch and security audits on the branch's open PR without asking: as a new comment, or, if an earlier review comment there still has open checkboxes, by updating that comment (add only the new findings and name the new commit). Without a PR or GitHub access, only show it.
- Each finding has a checkbox: unchecked is open; checked is fixed (with "Fixed in `<sha>`") or closed (with the reason). After a squash or rebase, update the SHAs.
- Fix findings with a plan, one at a time: verify, commit, push and tick it in the comment before starting the next. After every push to a branch with an open PR, also when nobody mentioned a review, read its review comments and tick each open finding the pushed commits fix.

## Commits and Pull Requests
- Short title, then a one- or two-sentence body that says what changed.
- Author and committer: the configured git identity. If it is unset or Claude's own (`noreply@anthropic.com`, as in cloud sessions), look up the GitHub login with `get_me` and commit with `git -c user.name=<login> -c user.email=<login>@users.noreply.github.com commit --no-gpg-sign`; if the lookup fails, ask.
- Commits end with `Co-Authored-By: Claude <noreply@anthropic.com>`, so GitHub shows both.
- No `Claude-Session` lines in commits or pull requests.
