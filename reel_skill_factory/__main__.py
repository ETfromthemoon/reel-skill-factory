from __future__ import annotations

import argparse
import json
import sys
import tempfile
import time
from pathlib import Path

from .core import ROOT, WorkflowError, find_reel_url, generate, load_config, publish, transcribe
from .doctor import diagnose


STATE_PATH = ROOT / ".local-state" / "results.json"


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
    for item in sorted(config.inbox_dir.glob("*.txt")):
        try:
            if state.get(item.name, {}).get("status") == "failed" and not retry_failed:
                continue
            if item.stat().st_size > 16_384:
                raise WorkflowError("El archivo de entrada supera 16 KB")
            url, shortcode = find_reel_url(item.read_text(encoding="utf-8"))
            previous = state.get(shortcode, {})
            if previous.get("status") in {"published", "not_skillable", "needs_review"}:
                continue
            if previous.get("status") == "failed" and not retry_failed:
                continue
            print(f"Procesando {url}", flush=True)
            with tempfile.TemporaryDirectory(prefix="reel-skill-") as temp:
                workdir = Path(temp)
                transcript = transcribe(url, config.whisper_model, workdir)
                result = generate(url, transcript, workdir)
            if result["status"] == "skillable":
                pr_url = publish(config, url, shortcode, result)
                state[shortcode] = {"status": "published", "source": url, "pr": pr_url}
                print(f"PR: {pr_url}", flush=True)
            else:
                state[shortcode] = {"status": result["status"], "source": url,
                                    "analysis": result["analysis"]}
                print(f"{result['status']}: {result['analysis']}", flush=True)
            count += 1
        except (OSError, UnicodeError, WorkflowError) as exc:
            failures += 1
            key = item.name
            try:
                _, key = find_reel_url(item.read_text(encoding="utf-8"))
            except (OSError, UnicodeError, WorkflowError):
                pass
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
    once = sub.add_parser("once", help="procesa enlaces nuevos una vez")
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
