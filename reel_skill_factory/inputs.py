"""Read stable files from a synced Drive inbox without trusting their names."""

from __future__ import annotations

import hashlib
import time
from dataclasses import dataclass
from pathlib import Path

from .core import WorkflowError, find_reel_url


VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
MAX_VIDEO_BYTES = 500 * 1024 * 1024


@dataclass(frozen=True)
class InboxItem:
    item_id: str
    filename: str
    media: str
    source: str
    source_type: str


def inbox_files(folder: Path) -> list[Path]:
    return sorted(item for item in folder.iterdir()
                  if item.is_file() and not item.is_symlink()
                  and item.suffix.lower() in VIDEO_EXTENSIONS | {".txt"})


def read_inbox_item(item: Path, *, now: float | None = None) -> InboxItem | None:
    """Return None while Drive may still be writing a new file."""
    metadata = item.stat()
    age = (time.time() if now is None else now) - metadata.st_mtime
    if age < (10 if item.suffix.lower() == ".txt" else 30) or metadata.st_size == 0:
        return None
    if item.suffix.lower() == ".txt":
        if metadata.st_size > 16_384:
            raise WorkflowError("El archivo de entrada supera 16 KB")
        source, item_id = find_reel_url(item.read_text(encoding="utf-8"))
        return InboxItem(item_id, item.name, source, source, "reel_url")

    if metadata.st_size > MAX_VIDEO_BYTES:
        raise WorkflowError("El video supera 500 MB")
    digest = hashlib.sha256()
    with item.open("rb") as video:
        for chunk in iter(lambda: video.read(1024 * 1024), b""):
            digest.update(chunk)
    current = item.stat()
    if current.st_size != metadata.st_size or current.st_mtime_ns != metadata.st_mtime_ns:
        return None
    source = ("Video local aportado por el usuario "
              f"(SHA-256: {digest.hexdigest()}; archivo no incluido en el repositorio)")
    return InboxItem(f"video-{digest.hexdigest()[:16]}", item.name, str(item), source, "local_video")
