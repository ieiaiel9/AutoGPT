"""
RAZ Core - Git Agent
Provides git integration: status, commit, push, log, branch management.
Operations run against the configured repo path (defaults to BASE_DIR).
"""

import os
import subprocess
import sys
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GIT_EXE_FALLBACK = "git"

try:
    from system.config_loader import load_config
except Exception:
    load_config = dict


def _get_repo_path() -> str:
    """Return the configured git repo path, defaulting to BASE_DIR."""
    try:
        cfg = load_config()
        return cfg.get("git_repo_path", BASE_DIR) or BASE_DIR
    except Exception:
        return BASE_DIR


def _git_executable() -> str:
    """Resolve git executable path explicitly when available."""
    resolved = shutil.which("git")
    return resolved if resolved else GIT_EXE_FALLBACK


def _git(args: list, cwd: str = None, timeout: int = 30) -> str:
    """Run a git command and return combined stdout/stderr output."""
    repo = cwd or _get_repo_path()
    if not os.path.isdir(repo):
        return f"Git repo path not found: {repo}"
    try:
        result = subprocess.run(
            [_git_executable()] + args,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=repo,
        )
        out = (result.stdout or "").strip()
        err = (result.stderr or "").strip()
        combined = "\n".join(filter(None, [out, err]))
        return combined or "(no output)"
    except FileNotFoundError:
        return "Git is not installed or not in PATH. Install from https://git-scm.com"
    except subprocess.TimeoutExpired:
        return f"Git command timed out after {timeout}s"
    except Exception as e:
        return f"Git error: {e}"


def _run_git_status(_: list) -> str:
    return _git(["status", "--short"])


def _run_git_log(args: list) -> str:
    count = args[0] if args else "10"
    try:
        count = int(count)
    except ValueError:
        count = 10
    return _git(["log", "--oneline", f"-{count}"])


def _run_git_commit(args: list) -> str:
    if not args:
        return "Usage: /git commit <message>"
    msg = " ".join(args)
    _git(["add", "-A"])
    return _git(["commit", "-m", msg])


def _run_git_push(args: list) -> str:
    remote = args[0] if args else "origin"
    branch_out = _git(["branch", "--show-current"])
    branch = branch_out.strip().split("\n")[0] or "main"
    return _git(["push", remote, branch])


def _run_git_pull(_: list) -> str:
    return _git(["pull"])


def _run_git_branch(args: list) -> str:
    if not args:
        return _git(["branch", "-a"])
    new_branch = args[0]
    return _git(["checkout", "-b", new_branch])


def _run_git_checkout(args: list) -> str:
    if not args:
        return "Usage: /git checkout <branch>"
    return _git(["checkout", args[0]])


def _run_git_diff(_: list) -> str:
    return _git(["diff", "--stat"])


def _run_git_stash(args: list) -> str:
    action = args[0] if args else "push"
    return _git(["stash", action])


def _run_git_reset(_: list) -> str:
    return _git(["reset", "--soft", "HEAD~1"])


def _run_git_init(_: list) -> str:
    repo = _get_repo_path()
    if not os.path.exists(os.path.join(repo, ".git")):
        return _git(["init"])
    return "Repo already initialized."


def run_git(sub: str, args: list) -> str:
    """Dispatch a /git sub-command."""
    sub = sub.strip().lower()
    handlers = {
        "status": _run_git_status,
        "log": _run_git_log,
        "commit": _run_git_commit,
        "push": _run_git_push,
        "pull": _run_git_pull,
        "branch": _run_git_branch,
        "checkout": _run_git_checkout,
        "diff": _run_git_diff,
        "stash": _run_git_stash,
        "reset": _run_git_reset,
        "init": _run_git_init,
    }
    handler = handlers.get(sub)
    if handler:
        return handler(args)

    return (
        "Git commands: status | log [n] | commit <msg> | push [remote] | pull | "
        "branch [name] | checkout <branch> | diff | stash [push|pop] | reset | init"
    )
