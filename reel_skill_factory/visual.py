"""Adapt Watch Skill's local frame and OCR evidence to this worker."""

from __future__ import annotations

import json
import math
import os
import sys
from pathlib import Path

from .core import ROOT, WorkflowError


def timestamp(seconds: float) -> str:
    total = max(0, int(round(seconds)))
    return f"[{total // 60:02d}:{total % 60:02d}]"


def _coverage_cues(duration: float, max_frames: int) -> list[float]:
    """Pin early context and regular moments that scene dedup might discard."""
    if not math.isfinite(duration) or duration <= 0:
        return [0.0]
    first = [second for second in (0.0, 1.0, 2.0) if second < duration]
    slots = max(0, min(max_frames, round(max_frames * 0.75)) - len(first))
    count = min(slots, math.ceil(duration * 2))
    evenly = [round((index + 0.5) * duration / count, 3)
              for index in range(count)] if count else []
    return sorted(set(first + evenly))


def inspect_video(media: str, job_dir: Path, *, max_frames: int = 48) -> dict:
    """Keep frames locally so a transcript retry does not reacquire the video."""
    saved = job_dir / "visual.json"
    if saved.is_file():
        try:
            previous = json.loads(saved.read_text(encoding="utf-8"))
            frames = previous["frames"]
            if (previous.get("evidence_version") == 2
                    and previous.get("frame_cap") == max_frames
                    and isinstance(previous["has_audio"], bool)
                    and "duration_seconds" in previous
                    and "captions" in previous
                    and frames and all(Path(frame["image"]).is_file()
                                       and Path(frame["image"]).resolve().is_relative_to(job_dir.resolve())
                                       for frame in frames)):
                return previous
        except (OSError, ValueError, KeyError, TypeError):
            pass

    # Watch Skill's cache and OCR models belong to this installation, not the
    # user's home directory. The original video remains in Drive or its cache.
    os.environ.setdefault("WATCHSKILL_DATA_DIR", str(ROOT / ".local-state" / "watch-skill"))
    os.environ.setdefault("WATCHSKILL_CACHE_MAX_BYTES", str(2 * 1024 ** 3))
    os.environ.setdefault("WATCHSKILL_SUBTITLE_LANGS", "es.*,en.*")
    os.environ.setdefault("WATCHSKILL_MAX_VIDEO_HEIGHT", "1080")
    os.environ.setdefault("WATCHSKILL_MAX_FPS", "4.0")
    tools_dir = str(Path(sys.executable).parent)
    if tools_dir not in os.environ.get("PATH", "").split(os.pathsep):
        os.environ["PATH"] = tools_dir + os.pathsep + os.environ.get("PATH", "")
    try:
        from watch_skill.acquire import acquire
        from watch_skill.errors import WatchSkillError
        from watch_skill.perceive import probe
        from watch_skill.watch import watch
    except ImportError as exc:
        raise WorkflowError('Falta Watch Skill; ejecuta de nuevo el instalador') from exc
    try:
        acquired = acquire(media)
        if acquired.video_path is None:
            raise WorkflowError("Watch Skill no descargó un video con frames")
        metadata = probe(acquired.video_path)
        result = watch(
            media, out_dir=job_dir / "watch", max_frames=max_frames,
            frame_width=768, cue_timestamps=_coverage_cues(metadata.duration_seconds, max_frames),
            run_ocr=True, allow_local_whisper=False, allow_cloud_stt=False,
        )
    except (WatchSkillError, ImportError, OSError) as exc:
        raise WorkflowError(f"Watch Skill no pudo analizar el video: {exc}") from exc

    if result.perception is None or not result.perception.frames:
        raise WorkflowError("Watch Skill no extrajo frames; revisa el video y FFmpeg/ffprobe")
    frames = [{"timestamp": timestamp(frame.timestamp_seconds),
               "seconds": round(frame.timestamp_seconds, 2),
               "image": str(frame.path.resolve()),
               "ocr_text": frame.ocr_text[:800]}
              for frame in result.perception.frames]
    captions = None
    if result.transcript and result.transcript.source == "captions":
        captions = {"transcripcion": result.transcript.formatted(),
                    "duracion_seg": result.metadata.duration_seconds,
                    "n_segmentos": len(result.transcript.segments),
                    "fuente": "subtítulos (Watch Skill)"}
    payload = {"engine": "watch-skill", "evidence_version": 2,
               "frame_cap": max_frames, "frames": frames,
               "has_audio": result.metadata.has_audio,
               "duration_seconds": result.metadata.duration_seconds,
               "scene_count": result.perception.scene_count,
               "media_path": str(result.acquisition.video_path) if result.acquisition.video_path else None,
               "captions": captions}
    saved.parent.mkdir(parents=True, exist_ok=True)
    temporary = saved.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(saved)
    return payload
