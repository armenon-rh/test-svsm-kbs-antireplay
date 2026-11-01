"""Clone/checkout/submodule helpers for the repos under test."""
from pathlib import Path

from . import shell


def clone_or_fetch(path: Path, url: str):
    if (path / ".git").exists():
        actual = shell.run(["git", "remote", "get-url", "origin"], cwd=path).stdout.strip()
        if actual != url:
            raise RuntimeError(
                f"{path} already exists with origin {actual!r}, expected {url!r}; "
                "refusing to reuse a directory that doesn't match the configured repo"
            )
        shell.run(["git", "fetch", "origin"], cwd=path)
    else:
        shell.run(["git", "clone", url, str(path)])


def checkout_clean(path: Path, branch: str):
    """Check out `branch` and hard-reset to origin's tip, for reproducible runs."""
    shell.run(["git", "checkout", branch], cwd=path)
    shell.run(["git", "reset", "--hard", f"origin/{branch}"], cwd=path)
    shell.run(["git", "clean", "-fdx"], cwd=path, check=False)


def submodules_update(path: Path):
    shell.run(["git", "submodule", "update", "--init", "--recursive"], cwd=path)
