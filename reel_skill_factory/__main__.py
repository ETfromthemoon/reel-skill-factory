"""Command-line entry points for the local video-to-skill worker."""

from __future__ import annotations

import argparse
import sys
import time
from pathlib import Path

from .core import ROOT, WorkflowError, load_config
from .doctor import diagnose
from .worker import ProcessOptions, print_status, process_inbox
from .vault import write_vault
from .worker import JOBS_DIR, STATE_DIR, load_state


def main() -> int:
    parser = argparse.ArgumentParser(description="Videos de Instagram a skills revisables en GitHub")
    parser.add_argument("--config", type=Path, default=ROOT / "config.local.json")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="comprueba equipo, herramientas e integraciones")
    doctor.add_argument("--preinstall", action="store_true")
    doctor.add_argument("--url", help="Reel público para probar acceso de yt-dlp")
    once = sub.add_parser("once", help="procesa videos y enlaces nuevos una vez")
    once.add_argument("--retry-failed", action="store_true")
    retry = sub.add_parser("retry", help="reprocesa un video concreto, incluso si necesita revisión")
    retry.add_argument("item_id", help="código del Reel o video-<hash> mostrado por status")
    retry.add_argument("--model", choices=("tiny", "base", "small", "medium"))
    retry.add_argument("--use-transcript", action="store_true",
                       help="usa la transcripción editada guardada en .local-state/jobs/<ID>/transcript.txt")
    retry.add_argument("--refresh-draft", action="store_true",
                       help="regenera un PR en borrador usando transcripción y frames guardados")
    status = sub.add_parser("status", help="muestra resultados y rutas de revisión")
    status.add_argument("item_id", nargs="?")
    sub.add_parser("vault", help="actualiza la bóveda HTML local y muestra su ruta")
    sub.add_parser("watch", help="vigila la carpeta mientras este proceso esté abierto")
    args = parser.parse_args()
    if args.command == "doctor":
        return diagnose(args.config, preinstall=args.preinstall, sample_url=args.url)
    if args.command == "status":
        print_status(args.item_id)
        return 0
    if args.command == "vault":
        print(write_vault(load_state(), JOBS_DIR, STATE_DIR))
        return 0
    if args.command == "retry":
        if args.use_transcript and args.model:
            parser.error("--model y --use-transcript son alternativas")
        if args.refresh_draft and args.model:
            parser.error("--refresh-draft usa la transcripción guardada; no acepta --model")
        options = ProcessOptions(target_id=args.item_id, model_override=args.model,
                                 use_saved_transcript=args.use_transcript,
                                 refresh_draft=args.refresh_draft)
        _, failures = process_inbox(args.config, options)
        return 1 if failures else 0
    if args.command == "once":
        _, failures = process_inbox(args.config, ProcessOptions(retry_failed=args.retry_failed))
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
    except (WorkflowError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        raise SystemExit(1)
