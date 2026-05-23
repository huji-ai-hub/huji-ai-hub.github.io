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
        result = subprocess.run(
            ["git", *args],
            cwd=self.root,
            capture_output=True,
            text=True,
        )
        if check and result.returncode != 0:
            # Surface stderr in the exception message — the default
            # CalledProcessError loses it, leaving only "exit status N".
            stderr = (result.stderr or "").strip()
            stdout = (result.stdout or "").strip()
            detail = stderr or stdout or "(no output)"
            raise RuntimeError(
                f"git {' '.join(args)} failed (exit {result.returncode}): {detail}"
            )
        return result

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
        # Push via HTTPS using the token.
        # Use 'oauth2:TOKEN' as the credential — works for classic PATs
        # (ghp_*), fine-grained PATs (github_pat_*), and GitHub App tokens.
        # The previously-used 'x-access-token:TOKEN' is for App installation
        # tokens specifically and rejects classic PATs.
        push_url = f"https://oauth2:{self.token}@github.com/{self.repo_slug}.git"
        # Drop --force-with-lease: the bot uses a fresh date-based branch name
        # per run, so there's no remote ref to lease against; force-with-lease
        # against a non-existent remote ref behaves inconsistently across git
        # versions. A plain push to a new branch is what we actually want.
        self._run("push", push_url, f"HEAD:{branch}")
