#!/usr/bin/env python3
"""PreToolUse hook for the Bash tool: denies destructive commands in any spelling.

Permission patterns such as `Bash(rm -rf /)` miss `sudo rm -fr /` or `cd x && rm -r -f ~`. This script splits
the command into its simple commands and checks each one. It is a guardrail, not a sandbox: a command hidden in a
script file, in a variable or in a computed `eval` string still passes.

Input: the hook JSON on stdin. Output: a deny decision as JSON, or nothing. Standard library only, Python 3.13+.
"""
import json
import os
import re
from fnmatch import fnmatchcase
import subprocess
import sys
from collections.abc import Callable, Collection
from typing import Any

type Token = tuple[str, str]  # ("w", word), ("o", operator) or ("h", heredoc body)
type Check = Callable[[list[str], str], str | None]  # (arguments, cwd) -> the reason to deny

HOME = os.path.realpath(os.path.expanduser("~"))
PROJECT = HOME  # set in main()
PROTECTED_BRANCHES = {"main", "master"}
OPERATORS = ";&|()<>"
KEYWORDS = {"{", "}", "!", "if", "then", "else", "elif", "do", "while", "until"}
SHELLS = {"sh", "bash", "zsh", "dash", "ksh"}
# Commands that run another command, with their options that take a value
WRAPPERS: dict[str, set[str]] = {
    "sudo": {"-u", "--user", "-g", "--group", "-h", "--host", "-p", "--prompt", "-C", "--close-from", "-D", "--chdir",
             "-R", "--chroot", "-T", "--command-timeout", "-r", "--role", "-t", "--type", "-U", "--other-user"},
    "doas": {"-u", "-C"}, "env": {"-u", "--unset", "-C", "--chdir"}, "nice": {"-n", "--adjustment"},
    "ionice": {"-c", "--class", "-n", "--classdata", "-p", "--pid", "-P", "--pgid", "-u", "--uid"},
    "timeout": {"-s", "--signal", "-k", "--kill-after"}, "exec": {"-a"},
    "xargs": {"-I", "-n", "--max-args", "-P", "--max-procs", "-L", "--max-lines", "-d", "--delimiter", "-E", "-s",
              "--max-chars", "-a", "--arg-file", "--process-slot-var"},
    "stdbuf": {"-i", "--input", "-o", "--output", "-e", "--error"},
    "command": set(), "builtin": set(), "nohup": set(), "time": set(), "setsid": set(),
}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
VARIABLE = re.compile(r"\$(?:\{(\w+)(?:(:?[-=?]|%%?|##?)([^{}]*))?\}|(\w+))")  # $VAR, ${VAR}, ${VAR:-word}, ${VAR%word}
DISK = re.compile(r"^/dev/(?:sd|hd|vd|xvd|nvme|mmcblk|disk|rdisk|dm-|mapper/|loop)")
EVERYTHING = {"*", ".*", ".[!.]*", "..?*"}
FIND_FILTERS = {"-name", "-iname", "-path", "-ipath", "-wholename", "-iwholename", "-regex", "-iregex"}


def lex(text: str) -> tuple[list[Token], list[str]]:
    """Splits shell text into ("w", word) and ("o", operator) tokens, plus the commands substituted inside
    double quotes or `$((…))`. Quoted or escaped operators stay words, which shlex cannot tell apart. A heredoc
    body replaces its delimiter as an ("h", body) token; without its end line it is lexed as commands."""
    tokens: list[Token] = []
    substitutions: list[str] = []
    word: str | None = None
    heredoc = False  # the next word is a heredoc delimiter
    quoted = False  # that delimiter has a quote or a backslash, so the shell expands nothing in the body
    pending: list[tuple[int, bool]] = []  # the delimiter tokens whose bodies start after the next newline
    i, n = 0, len(text)

    def flush() -> None:
        nonlocal word, heredoc, quoted
        if word is not None:
            tokens.append(("w", word))
            word = None
            if heredoc:
                pending.append((len(tokens) - 1, quoted))
                heredoc = quoted = False

    while i < n:
        c = text[i]
        quoted = quoted or (heredoc and c in "\\'\"")
        if c == "\\":
            if i + 1 < n and text[i + 1] != "\n":
                word = (word or "") + text[i + 1]
            i += 2
        elif c == "'":
            end = text.find("'", i + 1)
            if end < 0:
                raise ValueError("unclosed quote")
            word = (word or "") + text[i + 1:end]
            i = end + 1
        elif c == '"':
            word = word or ""
            i += 1
            while i < n and text[i] != '"':
                if text[i] == "\\" and i + 1 < n:
                    word += text[i + 1]
                    i += 2
                elif text.startswith("$(", i) or text[i] == "`":
                    end = closing(text, i + 2) if text[i] == "$" else text.find("`", i + 1)
                    if end < 0:
                        raise ValueError("unclosed substitution")
                    substitutions.append(text[i + (2 if text[i] == "$" else 1):end])
                    word += text[i:end + 1]
                    i = end + 1
                else:
                    word += text[i]
                    i += 1
            if i >= n:
                raise ValueError("unclosed quote")
            i += 1
        elif c in " \t\r":
            flush()
            i += 1
        elif c == "#" and word is None:
            end = text.find("\n", i)
            i = n if end < 0 else end
        elif c == "\n" and (pending or heredoc):
            flush()
            for index, literal in pending:
                body: list[str] = []
                closed = False
                while i < n and not closed:  # i is at the newline before the next body line
                    end = text.find("\n", i + 1)
                    end = n if end < 0 else end
                    closed = text[i + 1:end].strip() == tokens[index][1]
                    if not closed:
                        body.append(text[i + 1:end])
                    i = end
                tokens[index] = ("h", "\n".join(body))
                if not closed:
                    more, inner = lex("\n".join(body))
                    tokens += [("o", ";"), *more]
                    substitutions += inner
                elif not literal:
                    substitutions += substituted("\n".join(body))
            pending.clear()
            tokens.append(("o", ";"))
        elif c in "\n`":
            flush()
            tokens.append(("o", ";"))
            i += 1
        elif c in OPERATORS:
            flush()
            end = i
            while end < n and text[end] in OPERATORS:
                end += 1
            tokens.append(("o", text[i:end]))
            heredoc = text[i:end].endswith("<<") and not text[i:end].endswith("<<<")
            i = end + (heredoc and text.startswith("-", end))
        elif text.startswith("$((", i):  # arithmetic, where << is no heredoc
            end = closing(text, i + 2)
            if end < 0:
                raise ValueError("unclosed arithmetic")
            substitutions.append(text[i + 3:end - 1])
            word = (word or "") + text[i:end + 1]
            i = end + 1
        else:
            word = (word or "") + c
            i += 1
    flush()
    return tokens, substitutions


def closing(text: str, start: int) -> int:
    """Index of the parenthesis that closes the one opened just before `start`, or -1."""
    depth = 1
    for i in range(start, len(text)):
        depth += {"(": 1, ")": -1}.get(text[i], 0)
        if depth == 0:
            return i
    return -1


def substituted(text: str) -> list[str]:
    """The commands in the `$(…)` and backtick substitutions of a text the shell expands: a heredoc body."""
    found: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "\\":
            i += 2
        elif text.startswith("$(", i) or text[i] == "`":
            start = i + (2 if text[i] == "$" else 1)
            end = closing(text, start) if text[i] == "$" else text.find("`", start)
            end = len(text) if end < 0 else end
            found.append(text[start:end])
            i = end + 1
        else:
            i += 1
    return found


def fork_bomb(tokens: list[Token]) -> bool:
    """A function that pipes itself into itself in the background: `f() { f | f & }`. Quoted text and heredoc
    bodies are single tokens, so a fork bomb that is only data doesn't count."""
    for i in range(len(tokens) - 6):
        name, background = tokens[i], tokens[i + 6]
        if (name[0] == "w" and tokens[i + 1:i + 6] == [("o", "()"), ("w", "{"), name, ("o", "|"), name]
                and background[0] == "o" and background[1].startswith("&") and not background[1].startswith("&&")):
            return True
    return False


def expanded(match: re.Match[str], known: dict[str, str]) -> str:
    """The value of a variable reference, or the reference itself when this script can't know the value."""
    name, operator, word = match.group(1) or match.group(4), match.group(2) or "", match.group(3)
    if name not in known:  # perhaps unset: then ${VAR:-word} and ${VAR:=word} are the word
        return word if operator.lstrip(":") in ("-", "=") else match.group(0)
    value = known[name]
    if operator[:1] in ("%", "#"):  # cut the shortest (%, #) or longest (%%, ##) suffix or prefix that matches
        suffix = operator[0] == "%"
        cuts = range(len(value) + 1)
        for i in cuts if operator in ("%%", "#") else reversed(cuts):
            if fnmatchcase(value[i:] if suffix else value[:i], word):
                return value[:i] if suffix else value[i:]
    return value


def resolve(word: str, cwd: str) -> str | None:
    """The absolute path a word names, or None when it holds a variable this script can't know."""
    known = {"HOME": HOME, "PWD": cwd, "CLAUDE_PROJECT_DIR": PROJECT}
    for _ in range(2):  # twice, for a variable in a default: ${DIR:-$HOME}
        word = VARIABLE.sub(lambda m: expanded(m, known), word)
    if "$" in word:
        return None
    if word == "~" or word.startswith("~/"):
        word = HOME + word[1:]
    # `dir/*` empties dir, so it counts as dir itself
    while os.path.basename(word.rstrip("/")) in EVERYTHING:
        word = os.path.dirname(word.rstrip("/")) or "."
    return os.path.realpath(os.path.join(cwd, word))


def contains(parent: str, child: str) -> bool:
    return child == parent or child.startswith(parent.rstrip("/") + "/")


def outside(path: str) -> bool:
    """/, a system directory, the home directory, or a directory above the home directory or the project."""
    parts = path.strip("/").split("/")
    return (
        path == "/" or len(parts) == 1 or (len(parts) == 2 and parts[0] in {"usr", "var", "private"})
        or contains(path, HOME) or (contains(path, PROJECT) and path != PROJECT)
    )


def key_directory(path: str) -> bool:
    return outside(path) or path in (PROJECT, os.path.join(PROJECT, ".git"))


def options_and_operands(args: list[str]) -> tuple[list[str], list[str]]:
    end = args.index("--") if "--" in args else len(args)
    return [a for a in args[:end] if a.startswith("-")], [a for a in args[:end] if not a.startswith("-")] + args[end + 1:]


def positionals(args: list[str], valued: Collection[str] = ()) -> list[str]:
    """The arguments that are neither options nor the values of the `valued` options."""
    out: list[str] = []
    i = 0
    while i < len(args):
        if args[i] in valued:
            i += 2
        else:
            if not args[i].startswith("-"):
                out.append(args[i])
            i += 1
    return out


def recursive(options: list[str]) -> bool:
    return any(o == "--recursive" or (not o.startswith("--") and set(o) & set("rR")) for o in options)


def check_rm(args: list[str], cwd: str) -> str | None:
    options, targets = options_and_operands(args)
    if recursive(options):
        for path in filter(None, (resolve(t, cwd) for t in targets)):
            if key_directory(path):
                return f"it deletes {path} recursively"
    return None


def check_find(args: list[str], cwd: str) -> str | None:
    deletes = "-delete" in args
    for i, arg in enumerate(args):
        if arg in ("-exec", "-execdir", "-ok", "-okdir"):  # the command up to `;` or `+`
            end = next((j for j in range(i + 1, len(args)) if args[j] in (";", "+")), len(args))
            command = unwrapped(args[i + 1:end])
            reason = check_words(command, cwd, 1)
            if reason:
                return reason
            deletes = deletes or os.path.basename("".join(command[:1])) == "rm"
    if not deletes:
        return None
    args = [a for a in args if a not in ("-H", "-L", "-P")]
    first_test = next((i for i, a in enumerate(args) if a.startswith("-") or a in ("(", "!")), len(args))
    filtered = bool(FIND_FILTERS & set(args))
    for path in filter(None, (resolve(s, cwd) for s in args[:first_test] or ["."])):
        if outside(path) or (key_directory(path) and not filtered):
            return f"it deletes files found under {path}"
    return None


def check_permissions(args: list[str], cwd: str) -> str | None:
    options, targets = options_and_operands(args)
    if recursive(options):
        for path in filter(None, (resolve(t, cwd) for t in targets)):
            if outside(path):
                return f"it changes permissions or owners under {path} recursively"
    return None


def check_dd(args: list[str], cwd: str) -> str | None:
    if any(a.startswith("of=") and DISK.match(a[3:]) for a in args):
        return "it writes to a disk device"
    return None


def git_output(directory: str, *args: str) -> str:
    try:
        result = subprocess.run(["git", "-C", directory, *args], capture_output=True, text=True, timeout=5)
    except (OSError, subprocess.SubprocessError):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def check_git(args: list[str], cwd: str) -> str | None:
    i, directory = 0, cwd
    while i < len(args) and args[i].startswith("-"):
        if args[i] == "-C" and i + 1 < len(args):
            directory = resolve(args[i + 1], directory) or directory
        i += 2 if args[i] in ("-C", "-c", "--git-dir", "--work-tree", "--namespace") else 1
    if args[i:i + 1] != ["push"]:
        return None
    options, operands = options_and_operands(args[i + 1:])
    if {"--all", "--mirror", "--branches"} & set(options):
        return "it pushes every branch, including main"
    refs = positionals(args[i + 1:], valued=("-o", "--push-option", "--repo", "--receive-pack", "--exec"))[1:]
    current = git_output(directory, "symbolic-ref", "--short", "-q", "HEAD")
    if not refs:
        upstream = git_output(directory, "rev-parse", "--abbrev-ref", "@{push}")
        refs = [current, upstream.partition("/")[2]]
    for ref in refs:
        target = ref.lstrip("+").rpartition(":")[2]
        target = current if target in ("HEAD", "@") else target
        if target.replace("refs/heads/", "", 1) in PROTECTED_BRANCHES:
            return f"it pushes to {target}; push a feature branch and open a pull request"
    return None


def check_gh(args: list[str], cwd: str) -> str | None:
    words = positionals(args)
    if words[:2] in (["repo", "delete"], ["repo", "archive"], ["release", "delete"]):
        return f"gh {' '.join(words[:2])} can't be undone"
    methods = [b for a, b in zip(args, args[1:]) if a in ("-X", "--method")]
    methods += [a[2:] for a in args if a.startswith("-X")] + [a.partition("=")[2] for a in args if a.startswith("--method=")]
    if words[:1] == ["api"] and "DELETE" in (m.upper() for m in methods):
        return "it sends a DELETE request to the GitHub API"
    return None


KUBE_VALUED = (
    "-n", "--namespace", "-l", "--selector", "-f", "--filename", "-k", "-o", "--output", "--context", "--cluster",
    "--kubeconfig", "--kube-context", "--field-selector", "--grace-period", "--timeout", "--user", "-s", "--server",
)


def check_kubectl(args: list[str], cwd: str) -> str | None:
    words = positionals(args, KUBE_VALUED)
    if words[:1] == ["drain"]:
        return "it drains a cluster node"
    if words[:1] == ["delete"]:
        kinds = [k.partition("/")[0] for k in words[1].split(",")] if len(words) > 1 else []
        if {"namespace", "namespaces", "ns"} & set(kinds):
            return "it deletes a namespace with everything in it"
        if any(a in ("--all", "-A", "--all-namespaces") or a.startswith("--all=t") for a in args):
            return "it deletes all resources of a kind"
    return None


def check_helm(args: list[str], cwd: str) -> str | None:
    if positionals(args, KUBE_VALUED)[:1] in (["uninstall"], ["delete"], ["del"], ["un"]):
        return "it uninstalls a Helm release"
    return None


def check_terraform(args: list[str], cwd: str) -> str | None:
    words = positionals(args)
    if words[:1] == ["destroy"] or (words[:1] == ["apply"] and {"-destroy", "--destroy"} & set(args)):
        return "it destroys the managed infrastructure"
    return None


def check_pulumi(args: list[str], cwd: str) -> str | None:
    if positionals(args)[:1] == ["destroy"]:
        return "it destroys the managed infrastructure"
    return None


def check_kill(args: list[str], cwd: str) -> str | None:
    if "-1" in args[1:]:
        return "it kills every process of the user"
    return None


def check_systemctl(args: list[str], cwd: str) -> str | None:
    if {"poweroff", "reboot", "halt"} & set(positionals(args)):
        return "it shuts the machine down"
    return None


def check_flyway(args: list[str], cwd: str) -> str | None:
    if "clean" in args:
        return "flyway clean drops every object in the schema"
    return None


def check_build(args: list[str], cwd: str) -> str | None:
    for arg in args:
        if re.search(r"flyway[\w.:-]*:clean$|(^|:)flywayClean$", arg):
            return "Flyway's clean drops every object in the schema"
        if re.search(r"liquibase[\w.:-]*:dropAll$|(^|:)dropAll$", arg):
            return "Liquibase's dropAll drops every object in the schema"
    return None


def check_liquibase(args: list[str], cwd: str) -> str | None:
    if {"drop-all", "dropAll"} & set(args):
        return "liquibase drop-all drops every object in the schema"
    return None


def check_mysqladmin(args: list[str], cwd: str) -> str | None:
    if "drop" in args:
        return "it drops a database"
    return None


def check_redis(args: list[str], cwd: str) -> str | None:
    if {"FLUSHALL", "FLUSHDB"} & {a.upper() for a in args}:
        return "it deletes every key"
    return None


def check_mongo(args: list[str], cwd: str) -> str | None:
    if any("dropDatabase" in a for a in args):
        return "it drops a database"
    return None


def always(reason: str) -> Check:
    return lambda args, cwd: reason


# Commands the guard checks, by name; mkfs* is matched by prefix in check_words
CHECKS: dict[str, Check] = {
    "chgrp": check_permissions,
    "chmod": check_permissions,
    "chown": check_permissions,
    "dd": check_dd,
    "dropdb": always("it drops a database"),
    "find": check_find,
    "flyway": check_flyway,
    "gh": check_gh,
    "git": check_git,
    "gradle": check_build,
    "gradlew": check_build,
    "halt": always("it shuts the machine down"),
    "helm": check_helm,
    "kill": check_kill,
    "killall5": always("it kills every process"),
    "kubectl": check_kubectl,
    "liquibase": check_liquibase,
    "mongo": check_mongo,
    "mongosh": check_mongo,
    "mvn": check_build,
    "mvnw": check_build,
    "mysqladmin": check_mysqladmin,
    "poweroff": always("it shuts the machine down"),
    "pulumi": check_pulumi,
    "reboot": always("it shuts the machine down"),
    "redis-cli": check_redis,
    "rm": check_rm,
    "shred": always("it overwrites files beyond recovery"),
    "shutdown": always("it shuts the machine down"),
    "systemctl": check_systemctl,
    "terraform": check_terraform,
    "tofu": check_terraform,
    "wipefs": always("it wipes a disk"),
}


def unwrapped(words: list[str]) -> list[str]:
    """The words without leading assignments, keywords, `function name` and wrappers such as sudo."""
    while words:
        name = os.path.basename(words[0])
        if ASSIGNMENT.match(words[0]) or words[0] in KEYWORDS:
            words = words[1:]
        elif words[0] == "function":
            words = words[2:]
        elif name in WRAPPERS:
            i = 1
            while i < len(words) and (words[i].startswith("-") or (name == "env" and ASSIGNMENT.match(words[i]))):
                i += 2 if words[i] in WRAPPERS[name] else 1
            words = words[i + (name == "timeout"):]
        else:
            break
    return words


def check_words(words: list[str], cwd: str, depth: int, stdin: Collection[str] = ()) -> str | None:
    """The reason to deny a command given as words. `stdin` holds the texts a shell would read as its script."""
    words = unwrapped(words)
    if not words:
        return None
    name, args = os.path.basename(words[0]), words[1:]
    if name in SHELLS:
        scripts = [b for a, b in zip(args, args[1:]) if a.startswith("-") and not a.startswith("--") and "c" in a]
        return next(filter(None, (check(s, cwd, depth + 1) for s in scripts[:1] or stdin)), None)
    if name == "eval":
        return check(" ".join(args), cwd, depth + 1)
    if name.startswith("mkfs"):
        return "it formats a disk"
    return CHECKS[name](args, cwd) if name in CHECKS else None


def check_simple(tokens: list[Token], cwd: str, depth: int, piped: list[str]) -> str | None:
    """The reason to deny one simple command, given as tokens with its redirections. `piped` holds the texts
    that earlier commands of the pipeline write; this command's own texts are added to it."""
    words: list[str] = []
    inputs: list[str] = []  # heredoc bodies and here-strings
    i = 0
    while i < len(tokens):
        kind, text = tokens[i]
        if kind == "o":  # a redirection: its target is no argument
            target_kind, target = tokens[i + 1] if i + 1 < len(tokens) else ("w", "")
            if ">" in text and DISK.match(target):
                return "it writes to a disk device"
            if target_kind == "h" or text.endswith("<<<"):
                inputs.append(target)
            i += 2
        else:
            words.append(text)
            i += 1
    reason = check_words(words, cwd, depth, piped + inputs)
    piped += [*inputs, " ".join(unwrapped(words)[1:])]
    return reason


def check(command: str, cwd: str, depth: int = 0) -> str | None:
    """The reason to deny a command line, or None."""
    if depth > 5:
        return None
    try:
        tokens, substitutions = lex(command)
    except ValueError:  # unbalanced quotes: split roughly rather than not at all
        pieces = re.findall(r"[;&|()<>`\n]+|[^\s;&|()<>`\n]+", command)
        tokens = [("o", p) if p[0] in OPERATORS + "`\n" else ("w", p.strip("'\"")) for p in pieces]
        substitutions = []
    if fork_bomb(tokens):
        return "it is a fork bomb"
    for inner in substitutions:
        reason = check(inner, cwd, depth + 1)
        if reason:
            return reason
    # A cd may fail or run in a subshell, so `cwds` holds every directory the next command may run in.
    cwds, fallback = [cwd], list[str]()  # fallback: where the commands run if a cd in this && chain failed
    subshells: list[tuple[list[str], list[str]]] = []
    simple: list[Token] = []
    piped: list[str] = []
    after_pipe = False
    for kind, text in tokens + [("o", ";")]:
        if kind != "o" or (set(text) <= set("<>&") and set(text) & set("<>")):
            simple.append((kind, text))
            continue
        texts = piped
        for directory in cwds:
            texts = list(piped)
            reason = check_simple(simple, directory, depth, texts)
            if reason:
                return reason
        separator = text.strip("()")
        pipe = separator in ("|", "|&")
        words = unwrapped([t for k, t in simple if k == "w"])
        if words[:1] in (["cd"], ["pushd"]) and not (pipe or after_pipe or separator == "&"):
            target = positionals(words[1:])
            new = list(dict.fromkeys((resolve(target[0], d) if target else HOME) or d for d in cwds))
            if not all(os.path.isdir(d) for d in new):
                fallback += cwds
            cwds = new
        if separator != "&&":
            cwds, fallback = list(dict.fromkeys(cwds + fallback)), []
        for parenthesis in text:
            if parenthesis == "(":
                subshells.append((cwds, fallback))
            elif parenthesis == ")" and subshells:
                cwds, fallback = subshells.pop()
        if separator:  # a lone parenthesis ends neither a pipeline nor its texts
            piped, after_pipe = (texts, True) if pipe else ([], False)
        simple = []
    return None


def main() -> None:
    global PROJECT
    event: dict[str, Any] = json.load(sys.stdin)
    if event.get("tool_name") != "Bash":
        return
    cwd = os.path.realpath(event.get("cwd") or os.getcwd())
    PROJECT = os.path.realpath(os.environ.get("CLAUDE_PROJECT_DIR") or cwd)
    reason = check(event.get("tool_input", {}).get("command", ""), cwd)
    if reason:
        json.dump({"hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": "deny",
            "permissionDecisionReason": f"Denied by .claude/hooks/guard-bash.py: {reason}. "
                                        "Don't work around it; if the user wants this, they run it themselves.",
        }}, sys.stdout)


if __name__ == "__main__":
    main()
