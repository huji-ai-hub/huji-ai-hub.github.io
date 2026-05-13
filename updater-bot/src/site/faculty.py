"""Read and write faculty markdown files (frontmatter + body)."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from pathlib import Path

import frontmatter


@dataclass
class FacultyEntry:
    slug: str
    path: Path
    name: str
    title: str
    lab: str
    fields: list[str] = field(default_factory=list)
    photo: str | None = None
    website: str | None = None
    scholar: str | None = None
    areas: list[str] = field(default_factory=list)
    order: int | None = None
    body: str = ""

    @classmethod
    def from_path(cls, path: Path) -> "FacultyEntry":
        post = frontmatter.load(path)
        meta = post.metadata
        return cls(
            slug=path.stem,
            path=path,
            name=meta.get("name", ""),
            title=meta.get("title", ""),
            lab=meta.get("lab", ""),
            fields=list(meta.get("fields", []) or []),
            photo=meta.get("photo"),
            website=meta.get("website"),
            scholar=meta.get("scholar"),
            areas=list(meta.get("areas", []) or []),
            order=meta.get("order"),
            body=post.content,
        )


def load_all(faculty_dir: Path) -> list[FacultyEntry]:
    if not faculty_dir.exists():
        return []
    return [FacultyEntry.from_path(p) for p in sorted(faculty_dir.glob("*.md"))]


def write(entry: FacultyEntry) -> None:
    """Write a FacultyEntry back to disk, preserving the frontmatter shape."""
    metadata = {
        "name": entry.name,
        "title": entry.title,
        "lab": entry.lab,
    }
    if entry.fields:
        metadata["fields"] = entry.fields
    if entry.photo:
        metadata["photo"] = entry.photo
    if entry.website:
        metadata["website"] = entry.website
    if entry.scholar:
        metadata["scholar"] = entry.scholar
    if entry.areas:
        metadata["areas"] = entry.areas
    if entry.order is not None:
        metadata["order"] = entry.order

    post = frontmatter.Post(entry.body, **metadata)
    entry.path.write_text(frontmatter.dumps(post) + "\n", encoding="utf-8")


def slugify(name: str) -> str:
    """Convert a faculty name to a slug matching the site's convention."""
    s = re.sub(r"^(prof\.?|dr\.?)\s+", "", name.strip(), flags=re.IGNORECASE)
    s = re.sub(r"\W+", "-", s.lower()).strip("-")
    return s
