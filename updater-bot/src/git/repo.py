"""Local git operations: branch, stage, commit, push.

Wraps the `git` CLI rather than pulling in another dep. The CLI is always
available in GitHub Actions runners.
"""

from __future__ import annotations

import logging
import subprocess
from pathlib import Path

log = logging.getLogger(__name__)


class GitRepo:
    def __init__(self, root: Path, token: str, repo_slug: str):
        self.root = root
        self.token = token
        self.repo_slug = repo_slug  # e.g. "huji-ai-hub/huji-ai-hub.github.io"

    def _run(self, *args: str, check: bool = True) -> subprocess.CompletedProcess:
        log.debug("git %s", " ".join(args))
        return subprocess.run(
            ["git", *args],
            cwd=self.root,
            check=check,
            capture_output=True,
            text=True,
        )

    def configure_identity(self, name: str, email: str) -> None:
        self._run("config", "user.name", name)
        self._run("config", "user.email", email)

    def checkout_new_branch(self, branch: str, base: str = "main") -> None:
        self._run("fetch", "origin", base)
        self._run("checkout", "-B", branch, f"origin/{base}")

    def stage(self, paths: list[Path]) -> None:
        rels = [str(p.relative_to(self.root)) for p in paths]
        if rels:
            self._run("add", "--", *rels)

    def has_staged_changes(self) -> bool:
        result = self._run("diff", "--cached", "--quiet", check=False)
        return result.returncode == 1  # 1 = differences, 0 = none, >1 = error

    def commit(self, message: str) -> None:
        self._run("commit", "-m", message)

    def push(self, branch: str) -> None:
        # Push via HTTPS using the token. Format: https://x-access-token:TOKEN@github.com/owner/repo
        push_url = f"https://x-access-token:{self.token}@github.com/{self.repo_slug}.git"
        self._run("push", push_url, f"HEAD:{branch}", "--force-with-lease")
