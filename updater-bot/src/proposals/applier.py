"""Apply a Proposal to the working tree as a file edit."""

from __future__ import annotations

import logging
from pathlib import Path

import frontmatter

from .models import Proposal

log = logging.getLogger(__name__)


def apply(proposal: Proposal, repo_root: Path) -> Path:
    """Mutate the file on disk to reflect the proposal. Return the affected path."""
    target = (repo_root / proposal.file_path).resolve()
    # Sanity-check: refuse to write outside the repo root.
    if repo_root.resolve() not in target.parents and target != repo_root.resolve():
        raise ValueError(f"refusing to edit path outside repo: {target}")

    target.parent.mkdir(parents=True, exist_ok=True)

    if proposal.change_type == "new_file":
        target.write_text(proposal.new_content, encoding="utf-8")
    elif proposal.change_type == "body_append":
        if not target.exists():
            target.write_text(proposal.new_content, encoding="utf-8")
        else:
            post = frontmatter.load(target)
            post.content = (post.content.rstrip() + "\n\n" +
                            proposal.new_content.strip() + "\n")
            target.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")
    elif proposal.change_type == "body_replace":
        if not target.exists():
            raise FileNotFoundError(f"cannot replace body of nonexistent file {target}")
        post = frontmatter.load(target)
        post.content = proposal.new_content
        target.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")
    elif proposal.change_type == "frontmatter":
        # new_content is expected to be a `key: value` line for v1.
        if "\n" in proposal.new_content or ":" not in proposal.new_content:
            raise ValueError(
                "frontmatter change must be a single 'key: value' line; "
                f"got: {proposal.new_content!r}"
            )
        key, _, value = proposal.new_content.partition(":")
        post = frontmatter.load(target) if target.exists() else frontmatter.Post("")
        post[key.strip()] = value.strip()
        target.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")
    elif proposal.change_type == "comment":
        # Append a flag comment at the end of the body — visible in PR diff,
        # invisible in rendered HTML so the site keeps working until human acts.
        if not target.exists():
            target.write_text(proposal.new_content + "\n", encoding="utf-8")
        else:
            post = frontmatter.load(target)
            if proposal.new_content.strip() in post.content:
                log.info("applier: comment already present in %s, skipping", target)
                return target
            post.content = post.content.rstrip() + "\n\n" + proposal.new_content + "\n"
            target.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")
    else:
        raise ValueError(f"unknown change_type: {proposal.change_type}")

    return target
