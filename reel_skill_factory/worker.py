"""Local job orchestration, review artifacts, and idempotent inbox processing."""

from __future__ import annotations

import json
import os
import sys
import tempfile
import time
import uuid
from contextlib import contextmanager
from dataclasses import dataclass
from pathlib import Path

from .core import ROOT, TIMESTAMP, WorkflowError, generate, load_config, publish, transcribe
from .inputs import InboxItem, inbox_files, read_inbox_item
from .visual import inspect_video


STATE_DIR = ROOT / ".local-state"
STATE_PATH = STATE_DIR / "results.json"
JOBS_DIR = STATE_DIR / "jobs"


@dataclass(frozen=True)
class ProcessOptions:
    retry_failed: bool = False
    target_id: str | None = None
    model_override: str | None = None
    use_saved_transcript: bool = False


def _write_text(path: Path, value: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_text(value, encoding="utf-8")
    temporary.replace(path)


def _write_json(path: Path, value: dict) -> None:
    _write_text(path, json.dumps(value, ensure_ascii=False, indent=2) + "\n")


def load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        state = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"Estado local dañado: {STATE_PATH}: {exc}") from exc
    if not isinstance(state, dict):
        raise WorkflowError(f"Estado local inválido: {STATE_PATH}")
    return state


@contextmanager
def worker_lock(*, skip_if_busy: bool = False):
    """Prevent a manual retry from racing the scheduled worker."""
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    with (STATE_DIR / "worker.lock").open("a+b") as handle:
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            if skip_if_busy:
                yield False
                return
            raise WorkflowError("Ya hay otro procesamiento en curso; inténtalo al terminar") from exc
        try:
            yield True
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _attempt_dir(job_dir: Path, model: str) -> Path:
    stamp = time.strftime("%Y%m%dT%H%M%SZ", time.gmtime())
    path = job_dir / "attempts" / f"{stamp}-{model}-{uuid.uuid4().hex[:6]}"
    path.mkdir(parents=True, exist_ok=False)
    return path


def _save_transcript(path: Path, transcript: dict, model: str) -> None:
    _write_text(path / "transcript.txt", transcript["transcripcion"].strip() + "\n")
    _write_json(path / "transcript-meta.json", {
        "model": model,
        "duration_seconds": transcript.get("duracion_seg"),
        "segments": transcript.get("n_segmentos"),
        "method": transcript.get("fuente"),
    })


def _saved_transcript(job_dir: Path) -> dict:
    try:
        transcript = (job_dir / "transcript.txt").read_text(encoding="utf-8").strip()
        metadata = json.loads((job_dir / "transcript-meta.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError("No hay una transcripción guardada para este video; usa retry sin --use-transcript") from exc
    lines = [line for line in transcript.splitlines() if line.strip()]
    if not lines or any(not TIMESTAMP.match(line) for line in lines):
        raise WorkflowError("Cada línea de la transcripción editada debe comenzar con [mm:ss] o [hh:mm:ss]")
    return {"transcripcion": transcript, "duracion_seg": metadata.get("duration_seconds"),
            "n_segmentos": len(lines), "fuente": "transcripción revisada"}


def _analyze(item: InboxItem, model: str, job_dir: Path, visual: dict, *,
             use_saved: bool = False, force_whisper: bool = False) -> tuple[dict, dict]:
    attempt = _attempt_dir(job_dir, "edited" if use_saved else model)
    with tempfile.TemporaryDirectory(prefix="reel-skill-") as temp:
        workdir = Path(temp)
        if use_saved:
            transcript = _saved_transcript(job_dir)
        elif visual.get("captions") and not force_whisper:
            transcript = visual["captions"]
        elif not visual["has_audio"]:
            transcript = {"transcripcion": "", "duracion_seg": visual["duration_seconds"],
                          "n_segmentos": 0, "fuente": "video sin audio"}
        else:
            media_path = visual.get("media_path")
            media = media_path if media_path and Path(media_path).is_file() else item.media
            transcript = transcribe(media, model, workdir)
        _save_transcript(attempt, transcript, "edited" if use_saved else model)
        result = generate(item.source, transcript, workdir, source_type=item.source_type,
                          visual=visual)
    _write_json(attempt / "result.json", result)
    return transcript, result


def _save_current(job_dir: Path, transcript: dict, result: dict, model: str) -> None:
    _save_transcript(job_dir, transcript, model)
    _write_text(job_dir / "analysis.md", result["analysis"].strip() + "\n")
    _write_json(job_dir / "result.json", result)


def _process_item(item: InboxItem, config, state: dict, options: ProcessOptions) -> None:
    job_dir = JOBS_DIR / item.item_id
    state[item.item_id] = {"status": "processing", "source": item.source,
                           "filename": item.filename, "job_dir": str(job_dir)}
    _write_json(STATE_PATH, state)
    model = options.model_override or config.whisper_model
    visual = inspect_video(item.media, job_dir,
                           max_frames=getattr(config, "visual_max_frames", 48))
    transcript, result = _analyze(item, model, job_dir, visual,
                                  use_saved=options.use_saved_transcript)
    chosen_model = "edited" if options.use_saved_transcript else model
    fallback_error = None
    fallback = config.review_whisper_model
    if (not options.use_saved_transcript and result["status"] == "needs_review"
            and result["review_reason"] == "transcription" and fallback and fallback != model):
        print(f"Transcripción dudosa; reintentando con Whisper {fallback}", flush=True)
        try:
            improved_transcript, improved_result = _analyze(item, fallback, job_dir, visual,
                                                            force_whisper=True)
            # A contradictory "not_skillable" result is not enough to discard a method.
            if improved_result["status"] != "not_skillable":
                transcript, result, chosen_model = improved_transcript, improved_result, fallback
        except (OSError, UnicodeError, WorkflowError) as exc:
            fallback_error = str(exc)
    _save_current(job_dir, transcript, result, chosen_model)
    record = {"status": result["status"], "source": item.source, "filename": item.filename,
              "job_dir": str(job_dir), "model": chosen_model,
              "review_reason": result["review_reason"], "analysis": result["analysis"]}
    if fallback_error:
        record["fallback_error"] = fallback_error
    state[item.item_id] = record
    _write_json(STATE_PATH, state)
    if result["status"] == "skillable":
        record["pr"] = publish(config, item.source, item.item_id, result)
        record["status"] = "published"
        print(f"PR: {record['pr']}", flush=True)
    else:
        print(f"{record['status']}: {job_dir / 'analysis.md'}", flush=True)


def process_inbox(config_path: Path, options: ProcessOptions | None = None) -> tuple[int, int]:
    options = options or ProcessOptions()
    if options.use_saved_transcript and not options.target_id:
        raise WorkflowError("--use-transcript requiere un ID de video")
    config = load_config(config_path)
    count = failures = 0
    found_target = False
    with worker_lock(skip_if_busy=not options.target_id) as acquired:
        if not acquired:
            print("Otro procesamiento está en curso; esta pasada se omite", flush=True)
            return 0, 0
        state = load_state()
        for path in inbox_files(config.inbox_dir):
            key = path.name
            previous = state.get(key, {}).copy()
            try:
                if previous.get("status") == "failed" and not options.retry_failed and not options.target_id:
                    continue
                item = read_inbox_item(path)
                if item is None:
                    continue
                key = item.item_id
                if options.target_id and key != options.target_id:
                    continue
                found_target = found_target or bool(options.target_id)
                previous = state.get(key, {}).copy()
                if previous.get("status") == "published" and options.target_id:
                    raise WorkflowError("Este video ya tiene un PR; revisa el enlace antes de reprocesarlo")
                if previous.get("status") in {"published", "not_skillable", "needs_review"} and not options.target_id:
                    continue
                if previous.get("status") == "failed" and not options.retry_failed and not options.target_id:
                    continue
                print(f"Procesando {path.name}", flush=True)
                _process_item(item, config, state, options)
                count += 1
            except (OSError, UnicodeError, WorkflowError) as exc:
                if options.target_id and key == path.name:
                    # An unrelated malformed file must not affect a targeted retry.
                    continue
                failures += 1
                if options.target_id and previous.get("status") in {"needs_review", "not_skillable", "published"}:
                    state[key] = {**previous, "retry_error": str(exc)}
                else:
                    state[key] = {**state.get(key, {}), "status": "failed", "error": str(exc)}
                print(f"Error en {path.name}: {exc}", file=sys.stderr, flush=True)
            finally:
                _write_json(STATE_PATH, state)
        if options.target_id and not found_target:
            raise WorkflowError(f"No se encontró el video {options.target_id} en la carpeta de entrada")
    return count, failures


def print_status(item_id: str | None = None) -> None:
    state = load_state()
    if item_id:
        if item_id not in state:
            raise WorkflowError(f"No hay estado para {item_id}")
        print(json.dumps({item_id: state[item_id]}, ensure_ascii=False, indent=2))
    elif state:
        for key, value in sorted(state.items()):
            print(f"{key}: {value.get('status', 'desconocido')}"
                     + (f" — {value['job_dir']}" if value.get("job_dir") else ""))
    else:
        print("No hay videos procesados")
