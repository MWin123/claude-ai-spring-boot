"""The guard-bash.py hook denies destructive Bash commands in any spelling and lets everything else pass."""
import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from helpers import CONFIG

HOOK = CONFIG / ".claude" / "hooks" / "guard-bash.py"

DENIED = [
    # recursive delete of a key directory
    "rm -rf /",
    "sudo rm -fr /",
    "rm -r -f ~",
    "rm --recursive --force $HOME",
    'rm -rf "${HOME}/"',
    "rm -rf /*",
    "rm -rf ~/*",
    "rm -rf /etc",
    "rm -rf /usr/lib",
    "rm -Rf .",
    "rm -rf *",
    "rm -rf ./",
    "rm -rf ..",
    "rm -rf src/../..",
    "rm -rf .git",
    'rm -rf "$CLAUDE_PROJECT_DIR"',
    "rm -rf -- .",
    'rm -rf "${HOME:?}"',
    'rm -rf "${HOME:?}/"*',
    'rm -rf "${HOME:?home is unset}"',
    'rm -rf "${PWD:-.}"',
    'rm -rf "${CLAUDE_PROJECT_DIR%/}"',
    'rm -rf "${CLAUDE_PROJECT_DIR%%/}/.git"',
    'rm -rf "${HOME%/*}"',
    'rm -rf "${UNSET:-/}"',
    'rm -rf "${UNSET-$HOME}"',
    'rm -rf "${UNSET:=${HOME}}"',
    "/bin/rm -rf /",
    "\\rm -rf /",
    "cd src && rm -rf ..",
    "cd /tmp; cd / && rm -rf *",
    "ls; rm -rf /",
    "ls\nrm -rf /",
    "true || rm -rf /",
    "ls | xargs rm -rf /",
    "FOO=bar rm -rf /",
    "env FOO=bar rm -rf /",
    "sudo -u root rm -rf /",
    "timeout 5 rm -rf /",
    "nohup rm -rf / &",
    "sudo --user root rm -rf /",
    "sudo --user=root --group wheel rm -rf /",
    "timeout --signal KILL 5 rm -rf /",
    "nice --adjustment 5 rm -rf /",
    "stdbuf -o L rm -rf /",
    "ls | xargs --max-args 1 rm -rf /",
    "function f { rm -rf ~; }; f",
    "function f() { rm -rf ~; }; f",
    "bash -c 'rm -rf /'",
    'sh -lc "rm -rf ~"',
    "eval 'rm -rf /'",
    "echo $(rm -rf /)",
    'echo "$(rm -rf /)"',
    "echo `rm -rf /`",
    "if true; then rm -rf /; fi",
    "{ rm -rf /; }",
    "(rm -rf /)",
    "rm -rf / # clean up",
    "rm -rf target /",
    "bash <<EOF\nrm -rf /\nEOF",
    "rm -rf / 'unclosed",
    # << in quotes or arithmetic starts no heredoc; a heredoc without its end line is checked
    'echo "x << y"\nrm -rf ~',
    "echo $((1 << n))\nrm -rf /",
    "(( i << 1 ))\nrm -rf /",
    "echo $((rm -rf /))",
    "cat <<EOF\nrm -rf /",
    "sh <<-'END'\n\trm -rf /\n\tEND",
    # a heredoc with an unquoted delimiter runs the substitutions in its body
    "cat <<EOF\n$(rm -rf ~)\nEOF",
    "cat <<EOF\n`rm -rf ~`\nEOF",
    "cat <<-EOF > notes.md\n\tx $(rm -rf /)\n\tEOF",
    "cat <<EOF\n\\\\$(rm -rf ~)\nEOF",
    # a cd in a subshell or pipeline, or to a missing directory, doesn't move the commands after it
    "(cd build && ls); rm -rf *",
    "(cd build; ls)\nrm -rf *",
    "echo $(cd build && pwd); rm -rf *",
    "cd build | cat; rm -rf *",
    "ls | cd build; rm -rf *",
    "cd build & rm -rf *",
    "cd missing; rm -rf *",
    "cd missing\nrm -rf *",
    "cd missing && ls; rm -rf *",
    "cd missing || rm -rf *",
    "(cd missing; rm -rf *)",
    "(cd build && rm -rf ..)",
    "{ cd build; }; rm -rf ..",
    "echo 'rm -rf ~' | (sh)",
    # a shell reads its script from a heredoc, a here-string or a pipe
    "cat <<EOF | bash\nrm -rf ~\nEOF",
    "cat <<EOF | sudo bash\nrm -rf /\nEOF",
    "cat <<EOF | tee log.txt | sh -s\nrm -rf /\nEOF",
    'bash <<< "rm -rf ~"',
    "echo 'rm -rf ~' | sh",
    "echo rm -rf / | bash",
    "printf 'rm -rf %s' / |& zsh",
    # find
    "find / -name '*.log' -delete",
    "find ~ -type f -exec rm {} +",
    "find . -delete",
    "find -delete",
    "find . \\( -type f -o -type l \\) -delete",
    "find .. -name '*.class' -delete",
    "find . -type f -exec sudo rm {} +",
    "find . -type f -exec env LC_ALL=C /bin/rm {} \\;",
    "find . -name '*.sh' -exec sh -c 'rm -rf /' \\;",
    "find . -name '*.log' -exec rm -rf / \\;",
    "find . -name '*.log' -exec rm {} + -o -exec chmod -R 777 / \\;",
    # disk tools
    "dd if=/dev/zero of=/dev/sda bs=1M",
    "mkfs.ext4 /dev/sdb1",
    "wipefs -a /dev/sda",
    "shred -u secrets.txt",
    "echo x > /dev/sda",
    "cat image.iso >/dev/nvme0n1",
    # permissions
    "chmod -R 777 /",
    "sudo chown -R app:app /usr",
    "chmod --recursive 700 ~",
    "chgrp -R staff /etc",
    # git push
    "git push origin main",
    "git push origin master",
    "git push --force origin main",
    "git push -f origin +main",
    "git push origin HEAD:main",
    "git push origin feature/x:refs/heads/main",
    "git push origin --delete main",
    "git push origin :main",
    "git push --all",
    "git push --mirror origin",
    "git -c user.name=x push -u origin main",
    "git push -o ci.skip origin main",
    "git push --dry-run origin main",
    "git status && git push origin main",
    # GitHub CLI
    "gh repo delete owner/repo --yes",
    "gh repo archive owner/repo",
    "gh release delete v1.0.0",
    "gh api -X DELETE repos/owner/repo",
    "gh api --method=delete repos/owner/repo/branches/x",
    "gh api -XDELETE repos/owner/repo",
    # Kubernetes and Helm
    "kubectl delete namespace prod",
    "kubectl -n prod delete ns staging",
    "kubectl delete ns/prod",
    "kubectl delete pods --all",
    "kubectl delete deployments -A",
    "kubectl drain node-1 --ignore-daemonsets",
    "helm uninstall demo",
    "helm -n prod delete demo",
    # infrastructure
    "terraform destroy",
    "terraform -chdir=infra destroy -auto-approve",
    "terraform apply -destroy",
    "tofu destroy",
    "pulumi destroy --yes",
    # system
    "shutdown -h now",
    "sudo reboot",
    "halt",
    "poweroff",
    "systemctl poweroff",
    "kill -9 -1",
    "kill -KILL -- -1",
    "killall5",
    ":(){ :|:& };:",
    "bomb() { bomb | bomb & }; bomb",
    "bash <<EOF\n:(){ :|:& };:\nEOF",
    "echo ':(){ :|:& };:' | sh",
    "bash -c ':(){ :|:& };:'",
    "eval ':(){ :|:& };:'",
    # databases
    "flyway clean",
    "flyway -url=jdbc:postgresql://db/app clean",
    "./mvnw flyway:clean",
    "mvn -q org.flywaydb:flyway-maven-plugin:11.0.0:clean",
    "./gradlew flywayClean",
    "gradle :app:flywayClean",
    "liquibase drop-all",
    "liquibase dropAll",
    "mvn liquibase:dropAll",
    "dropdb app",
    "mysqladmin -u root drop app",
    "redis-cli FLUSHALL",
    "redis-cli -h cache flushdb",
    "mongosh app --eval 'db.dropDatabase()'",
]

ALLOWED = [
    "rm -rf target",
    "rm -rf build/ target/",
    "rm -rf ./build/*",
    "rm -rf src/main/generated",
    "rm -rf /tmp/scratch/demo",
    "rm -rf ~/.m2/repository/com/example",
    "rm -rf .git/index.lock",
    "rm -f /",
    "rm notes.txt",
    'rm -rf "$SCRATCH"/*',
    'rm -rf "${SCRATCH:?}"/*',
    'rm -rf "${HOME:?}/.m2/repository/com/example"',
    'rm -rf "${BUILD_DIR:-target}"',
    'rm -rf "${PWD%/}/build"',
    'rm -rf "${HOME##*/}"',
    'rm -rf "${HOME:+x}"',
    "cd build && rm -rf *",
    "cd build && rm -rf .",
    "cd build; rm -rf *",
    "cd build\nrm -rf *",
    "{ cd build; }; rm -rf *",
    "(cd build && rm -rf *)",
    "(cd build && rm -rf *); ls",
    "cd missing && rm -rf *",
    "(cd build; ls); rm -rf target",
    "mkdir -p out && cd out && rm -rf ./*",
    "rm -rf *.log",
    'echo "rm -rf /"',
    "echo 'rm -rf /'",
    "echo '$(rm -rf /)'",
    'grep -rn "rm -rf /" docs',
    'git commit -m "Deny rm -rf / and git push origin main"',
    "cat > notes.md <<'EOF'\nrm -rf /\ngit push origin main\nEOF",
    'git commit -m "$(cat <<\'EOF\'\nDeny rm -rf /\n\ngit push origin main\nEOF\n)"',
    "cat <<-EOF > notes.md\n\trm -rf /\n\tEOF\nls",
    "cat <<A <<B\nrm -rf /\nA\nrm -rf ~\nB",
    # text that is only data: a heredoc with any delimiter, a quoted fork bomb
    "cat <<\\EOF\nrm -rf /\nEOF",
    "cat <<'END-X'\nrm -rf /\nEND-X",
    'cat <<"E.O.F" > notes.md\nrm -rf /\nE.O.F',
    "cat <<'EOF' > notes.md\n:(){ :|:& };:\nEOF",
    "echo ':(){ :|:& };:'",
    "grep -F ':(){ :|:& };:' README.md",
    'git commit -m "Deny :(){ :|:& };: in the guard"',
    "f() { f | cat && f; }",
    "cat <<'EOF'\n$(rm -rf ~)\nEOF",
    "cat <<\\EOF\n`rm -rf ~`\nEOF",
    'cat <<"EOF"\n$(rm -rf ~)\nEOF',
    "cat <<EOF\n\\$(rm -rf ~) \\`rm -rf ~\\`\nEOF",
    "cat <<EOF\n$(date) in $(pwd)\nEOF",
    'echo "a << b"\nls',
    "cat <<EOF | grep rm\nrm -rf /\nEOF",
    "echo 'rm -rf /' | cat",
    "echo 'rm -rf /'; sh build.sh",
    "echo 'rm -rf target' | sh",
    'grep -c x <<< "rm -rf /"',
    "echo $((1 << 2))",
    'echo "$((1 << 2))"\nls',
    "ls # rm -rf /",
    "find . -name '*.orig' -delete",
    "find . -name __pycache__ -exec rm -rf {} +",
    "find target -delete",
    "find . -name '*.orig' -exec sudo rm {} +",
    "find . -exec chmod 644 {} +",
    "find . -name '*.sh' -exec sh -c 'chmod +x \"$1\"' _ {} \\;",
    "sudo --user=app ls",
    "sudo --user app rm -rf target",
    "function clean { rm -rf target; }; clean",
    "find / -name '*.log'",
    "find . \\( -name '*.class' -o -name '*.jar' \\) -delete",
    "dd if=/dev/zero of=disk.img bs=1M count=10",
    "echo x > /dev/null",
    "./mvnw test 2>&1 | tail -20",
    "chmod -R u+w target",
    "chmod -R 755 .",
    "chmod 600 ~/.netrc",
    "chown -R app:app build",
    "git push",
    "git push origin feature/x",
    "git push -u origin feature/x",
    "git push --force origin feature/x",
    "git push --force-with-lease origin feature/x",
    "git push -f origin +feature/x",
    "git push origin --delete feature/x",
    "git push origin main-backup",
    "git push origin HEAD:feature/main-page",
    "git push origin v1.0.0 --tags",
    "git push origin refs/tags/main",
    "git pull origin main",
    "git fetch origin main",
    "git rebase main",
    "git log main..HEAD",
    "git reset --hard HEAD~1",
    "git clean -fdx",
    "git branch -D feature/x",
    "gh pr create --fill",
    "gh repo view owner/repo",
    "gh release create v1.0.0",
    "gh api repos/owner/repo",
    "gh api -X POST repos/owner/repo/issues -f title=x",
    "kubectl delete pod demo-123",
    "kubectl delete pod demo -n ns",
    "kubectl -n namespace delete deployment demo",
    "kubectl delete -f k8s/deployment.yaml",
    "kubectl get namespaces",
    "helm upgrade --install demo ./chart",
    "helm list -A",
    "terraform plan -destroy",
    "terraform apply",
    "pulumi preview",
    "kill -9 1234",
    "kill -1 1234",
    "systemctl status docker",
    "./mvnw clean verify",
    "./gradlew clean build",
    "./mvnw flyway:migrate",
    "flyway info",
    "liquibase update",
    "redis-cli GET key",
    "mongosh app --eval 'db.orders.find()'",
    "docker compose down -v",
    "docker system prune -af --volumes",
    "psql -c 'DROP TABLE orders'",
    "echo 'unclosed",
    "",
]


def run_hook(
    command: str, cwd: Path, home: Path, project: Path | None = None, tool: str = "Bash"
) -> dict[str, Any] | None:
    event = {"hook_event_name": "PreToolUse", "tool_name": tool, "tool_input": {"command": command}, "cwd": str(cwd)}
    env = {"HOME": str(home), "CLAUDE_PROJECT_DIR": str(project or cwd), "PATH": "/usr/local/bin:/usr/bin:/bin"}
    result = subprocess.run(
        [sys.executable, str(HOOK)], input=json.dumps(event), capture_output=True, text=True, env=env
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)["hookSpecificOutput"] if result.stdout else None


@pytest.fixture
def home(tmp_path: Path) -> Path:
    (tmp_path / "home").mkdir()
    return tmp_path / "home"


@pytest.fixture
def project(home: Path) -> Path:
    project = home / "code" / "demo"
    (project / "build").mkdir(parents=True)
    return project


@pytest.mark.parametrize("command", DENIED)
def test_denies(command: str, project: Path, home: Path) -> None:
    decision = run_hook(command, project, home)

    assert decision, "allowed"
    assert decision["permissionDecision"] == "deny"
    assert decision["permissionDecisionReason"].startswith("Denied by .claude/hooks/guard-bash.py: ")


@pytest.mark.parametrize("command", ALLOWED)
def test_allows(command: str, project: Path, home: Path) -> None:
    assert run_hook(command, project, home) is None


def test_paths_resolve_against_the_session_directory(project: Path, home: Path) -> None:
    """In a subdirectory `.` is not the project, but `..` is."""
    assert run_hook("rm -rf .", project / "build", home, project) is None
    assert run_hook("rm -rf *", project / "build", home, project) is None
    assert run_hook("rm -rf ..", project / "build", home, project)
    assert run_hook(f"rm -rf {project}", home, home, project)


def git(repo: Path, *args: str) -> None:
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@example.com", *args],
                   check=True, capture_output=True)


@pytest.fixture
def repo(project: Path) -> Path:
    git(project, "init", "-b", "main")
    git(project, "commit", "--allow-empty", "-m", "init")
    return project


@pytest.mark.parametrize("command", ["git push", "git push origin", "git push origin HEAD", "git push -u origin HEAD"])
def test_a_plain_push_depends_on_the_current_branch(command: str, repo: Path, home: Path) -> None:
    assert run_hook(command, repo, home), "on main"

    git(repo, "switch", "-c", "feature/x")

    assert run_hook(command, repo, home) is None, "on a feature branch"


def test_a_plain_push_follows_the_upstream_branch(repo: Path, home: Path, tmp_path: Path) -> None:
    """A feature branch that tracks main pushes to main when push.default is upstream."""
    remote = tmp_path / "remote.git"
    git(repo, "init", "--bare", str(remote))
    git(repo, "remote", "add", "origin", str(remote))
    git(repo, "push", "origin", "main")
    git(repo, "config", "push.default", "upstream")
    git(repo, "switch", "-c", "feature/x", "--track", "origin/main")

    assert run_hook("git push", repo, home)


def test_git_dash_c_names_the_repository(repo: Path, home: Path, tmp_path: Path) -> None:
    assert run_hook(f"git -C {repo} push", tmp_path, home, tmp_path)
    assert run_hook(f"cd {repo} && git push", tmp_path, home, tmp_path)


def test_ignores_other_tools(project: Path, home: Path) -> None:
    assert run_hook("rm -rf /", project, home, tool="Write") is None
