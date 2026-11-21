# Hooks

## Bash Guard

[`guard-bash.py`](guard-bash.py) runs before every Bash call and denies destructive commands, also when chained, piped or wrapped in `sudo`, `bash -c` or `$(…)`: recursive deletes of `/`, home, system directories or the project, disk wipes, recursive `chmod`, `chown` or `chgrp` of system directories, pushes to `main` or `master`, shutdown, kill-all and fork bombs, and destroy or drop commands for GitHub, Kubernetes, Helm, Terraform, Pulumi and databases.

Without `python3` 3.13+ on the `PATH`, Claude Code shows a hook error and runs the command unguarded (`install.py` warns). It is a guardrail, not a sandbox: a command hidden in a script file, a variable or a computed `eval` string passes. Most checks are in [`CHECKS`](guard-bash.py#L445); `mkfs*`, fork bombs and redirects to a disk device are checked outside it.
