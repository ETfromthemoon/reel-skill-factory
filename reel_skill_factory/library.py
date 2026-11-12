"""Private skill drafts and approved catalog outside the shared repository."""

from __future__ import annotations

import hashlib
import json
import re
from pathlib import Path

from .core import Config, WorkflowError, skill_markdown, source_markdown


ITEM_ID = re.compile(r"^[A-Za-z0-9_-]+$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def draft_dir(config: Config, item_id: str) -> Path:
    if not ITEM_ID.fullmatch(item_id):
        raise WorkflowError("ID de video inválido")
    return config.library_dir / "drafts" / item_id


def approved_dir(config: Config) -> Path:
    return config.library_dir / "approved"


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)


def write_text(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(content, encoding="utf-8")
    temporary.replace(path)


def save_draft(config: Config, item_id: str, source: str, result: dict, *, update: bool = False) -> Path:
    location = draft_dir(config, item_id)
    slug = result["slug"]
    if not SLUG.fullmatch(slug):
        raise WorkflowError("Nombre de skill inválido")
    skill = skill_markdown(slug, result)
    source_text = source_markdown(source, result)
    skill_path = location / "SKILL.md"
    if skill_path.exists() and skill_path.read_text(encoding="utf-8") != skill and not update:
        raise WorkflowError("Ya existe un borrador distinto para este video; usa retry --refresh-draft")
    write_text(skill_path, skill)
    write_text(location / "source.md", source_text)
    write_json(location / "metadata.json", {"item_id": item_id, "slug": slug,
               "title": result["title"], "sha256": hashlib.sha256(skill.encode()).hexdigest()})
    return skill_path
