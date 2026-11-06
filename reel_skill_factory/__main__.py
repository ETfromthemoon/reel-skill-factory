from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tempfile
import time
from pathlib import Path

from .core import ROOT, WorkflowError, find_reel_url, generate, load_config, publish, transcribe
from .doctor import diagnose


STATE_PATH = ROOT / ".local-state" / "results.json"
VIDEO_EXTENSIONS = {".mp4", ".mov", ".m4v", ".webm", ".mkv"}
MAX_VIDEO_BYTES = 500 * 1024 * 1024


def _load_state() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise WorkflowError(f"Estado local dañado: {STATE_PATH}: {exc}") from exc


def _save_state(state: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    temp = STATE_PATH.with_suffix(".tmp")
    temp.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temp.replace(STATE_PATH)


def process_inbox(config_path: Path, retry_failed: bool = False) -> tuple[int, int]:
    config = load_config(config_path)
    state = _load_state()
    count = 0
    failures = 0
    inputs = sorted(item for item in config.inbox_dir.iterdir()
                    if item.is_file() and item.suffix.lower() in VIDEO_EXTENSIONS | {".txt"})
    for item in inputs:
        key = item.name
        try:
            if state.get(key, {}).get("status") == "failed" and not retry_failed:
                continue
            if item.suffix.lower() == ".txt":
                if item.stat().st_size > 16_384:
                    raise WorkflowError("El archivo de entrada supera 16 KB")
                source, shortcode = find_reel_url(item.read_text(encoding="utf-8"))
                media = source
                source_type = "reel_url"
            else:
                # Drive puede mostrar el archivo antes de terminar de sincronizarlo.
                metadata = item.stat()
                if time.time() - metadata.st_mtime < 30 or metadata.st_size == 0:
                    continue
                if metadata.st_size > MAX_VIDEO_BYTES:
                    raise WorkflowError("El video supera 500 MB")
                digest = hashlib.sha256()
                with item.open("rb") as video:
                    for chunk in iter(lambda: video.read(1024 * 1024), b""):
                        digest.update(chunk)
                current = item.stat()
                if (current.st_size != metadata.st_size or
                        current.st_mtime_ns != metadata.st_mtime_ns):
                    continue
                shortcode = f"video-{digest.hexdigest()[:16]}"
                source = ("Video local aportado por el usuario "
                          f"(SHA-256: {digest.hexdigest()}; archivo no incluido en el repositorio)")
                media = str(item)
                source_type = "local_video"
            key = shortcode
            previous = state.get(shortcode, {})
            if previous.get("status") in {"published", "not_skillable", "needs_review"}:
                continue
            if previous.get("status") == "failed" and not retry_failed:
                continue
            print(f"Procesando {item.name}", flush=True)
            with tempfile.TemporaryDirectory(prefix="reel-skill-") as temp:
                workdir = Path(temp)
                transcript = transcribe(media, config.whisper_model, workdir)
                result = generate(source, transcript, workdir, source_type=source_type)
            if result["status"] == "skillable":
                pr_url = publish(config, source, shortcode, result)
                state[shortcode] = {"status": "published", "source": source, "pr": pr_url}
                print(f"PR: {pr_url}", flush=True)
            else:
                state[shortcode] = {"status": result["status"], "source": source,
                                    "analysis": result["analysis"]}
                print(f"{result['status']}: {result['analysis']}", flush=True)
            count += 1
        except (OSError, UnicodeError, WorkflowError) as exc:
            failures += 1
            state[key] = {"status": "failed", "error": str(exc)}
            print(f"Error en {item.name}: {exc}", file=sys.stderr, flush=True)
        finally:
            _save_state(state)
    return count, failures


def main() -> int:
    parser = argparse.ArgumentParser(description="Reels de Instagram a skills revisables en GitHub")
    parser.add_argument("--config", type=Path, default=ROOT / "config.local.json")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="comprueba equipo, herramientas e integraciones")
    doctor.add_argument("--preinstall", action="store_true")
    doctor.add_argument("--url", help="Reel público para probar acceso de yt-dlp")
    once = sub.add_parser("once", help="procesa videos y enlaces nuevos una vez")
    once.add_argument("--retry-failed", action="store_true")
    sub.add_parser("watch", help="vigila la carpeta mientras este proceso esté abierto")
    args = parser.parse_args()
    if args.command == "doctor":
        return diagnose(args.config, preinstall=args.preinstall, sample_url=args.url)
    if args.command == "once":
        _, failures = process_inbox(args.config, args.retry_failed)
        return 1 if failures else 0
    config = load_config(args.config)
    print(f"Vigilando {config.inbox_dir} cada {config.poll_seconds} s. Ctrl+C para detener.")
    while True:
        process_inbox(args.config)
        time.sleep(config.poll_seconds)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        raise SystemExit(0)
    except WorkflowError as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
