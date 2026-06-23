import subprocess
from pathlib import Path

from .models import GitInfo


def get_git_info(corpus_root: Path) -> tuple[GitInfo, list[str]]:
    """
    Attempt to read Git commit and dirty status for the repository containing corpus_root.

    Returns (GitInfo, warnings).  GitInfo fields are None when Git is unavailable
    or the directory is not inside a repository — the inventory never fails for this.
    """
    warnings: list[str] = []

    commit = _run_git(["git", "rev-parse", "HEAD"], corpus_root)
    if commit is None:
        warnings.append(
            "Git information unavailable: 'git rev-parse HEAD' failed or git is not installed. "
            "corpus.git will be recorded as unknown."
        )
        return GitInfo(commit=None, dirty=None), warnings

    commit = commit.strip()
    if not commit:
        warnings.append("Git returned an empty commit hash; treating as unknown.")
        return GitInfo(commit=None, dirty=None), warnings

    status_out = _run_git(["git", "status", "--porcelain"], corpus_root)
    if status_out is None:
        warnings.append("Git status unavailable; dirty flag recorded as unknown.")
        dirty = None
    else:
        dirty = bool(status_out.strip())

    return GitInfo(commit=commit, dirty=dirty), warnings


def _run_git(cmd: list[str], cwd: Path) -> str | None:
    """Run a git subprocess and return stdout, or None on any error."""
    try:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return None
        return result.stdout
    except (FileNotFoundError, subprocess.TimeoutExpired, OSError):
        return None
