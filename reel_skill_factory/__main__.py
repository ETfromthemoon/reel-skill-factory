"""Command-line entry points for the local video-to-skill worker."""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

from .core import ROOT, WorkflowError, load_config
from .doctor import diagnose
from .worker import ProcessOptions, print_status, process_inbox
from .vault import write_vault
from .vault_server import serve
from .lifecycle import activate, evaluate, sync_approved
from .setup_config import configure
from .worker import JOBS_DIR, STATE_DIR, load_state


def main() -> int:
    parser = argparse.ArgumentParser(description="Videos de Instagram a skills privadas revisables")
    parser.add_argument("--config", type=Path, default=ROOT / "config.local.json")
    sub = parser.add_subparsers(dest="command", required=True)
    doctor = sub.add_parser("doctor", help="comprueba equipo, herramientas e integraciones")
    doctor.add_argument("--preinstall", action="store_true")
    doctor.add_argument("--url", help="Reel público para probar acceso de yt-dlp")
    configuration = sub.add_parser("configure", help="guarda la carpeta de entrada privada")
    configuration.add_argument("--inbox", required=True, type=Path)
    once = sub.add_parser("once", help="procesa videos y enlaces nuevos una vez")
    once.add_argument("--retry-failed", action="store_true")
    retry = sub.add_parser("retry", help="reprocesa un video concreto, incluso si necesita revisión")
    retry.add_argument("item_id", help="código del Reel o video-<hash> mostrado por status")
    retry.add_argument("--model", choices=("tiny", "base", "small", "medium"))
    retry.add_argument("--use-transcript", action="store_true",
                       help="usa la transcripción editada guardada en .local-state/jobs/<ID>/transcript.txt")
    retry.add_argument("--refresh-draft", action="store_true",
                       help="regenera un borrador local usando transcripción y frames guardados")
    retry.add_argument("--feedback", help="indica qué corregir al regenerar el borrador")
    status = sub.add_parser("status", help="muestra resultados y rutas de revisión")
    status.add_argument("item_id", nargs="?")
    vault = sub.add_parser("vault", help="actualiza o abre la bóveda local")
    vault.add_argument("--serve", action="store_true", help="bóveda interactiva en 127.0.0.1:8766")
    evaluation = sub.add_parser("evaluate", help="prueba un borrador en un directorio temporal")
    evaluation.add_argument("item_id")
    evaluation.add_argument("--scenario", required=True)
    evaluation.add_argument("--expected", required=True)
    demo = sub.add_parser("demo", help="crea una demostración automática para un borrador existente")
    demo.add_argument("item_id")
    activation = sub.add_parser("activate", help="aprueba e instala localmente una skill evaluada")
    activation.add_argument("item_id")
    activation.add_argument("--target", type=Path, action="append", help="carpeta adicional de skills del agente")
    activation.add_argument("--accept-gaps", action="store_true", help="confirmo que revisé los vacíos del evaluador")
    synchronize = sub.add_parser("sync-skills", help="instala skills aprobadas de la biblioteca privada")
    synchronize.add_argument("--target", type=Path, action="append", help="carpeta de skills del agente")
    sub.add_parser("watch", help="vigila la carpeta mientras este proceso esté abierto")
    args = parser.parse_args()
    if args.command == "doctor":
        return diagnose(args.config, preinstall=args.preinstall, sample_url=args.url)
    if args.command == "configure":
        print(configure(args.config, args.inbox))
        return 0
    if args.command == "status":
        print_status(args.item_id)
        return 0
    if args.command == "vault":
        if args.serve:
            serve(args.config)
            return 0
        print(write_vault(load_state(), JOBS_DIR, STATE_DIR))
        return 0
    if args.command == "evaluate":
        print(evaluate(load_config(args.config), args.item_id, args.scenario, args.expected))
        return 0
    if args.command == "demo":
        from .demo import create_demo
        from .library import draft_dir
        config = load_config(args.config)
        record = load_state().get(args.item_id, {})
        if record.get("status") != "draft":
            raise WorkflowError("Este video no tiene un borrador listo")
        job = JOBS_DIR / args.item_id
        result = json.loads((job / "result.json").read_text(encoding="utf-8"))
        print(create_demo(draft_dir(config, args.item_id) / "SKILL.md", job, result))
        return 0
    if args.command == "activate":
        for path in activate(load_config(args.config), args.item_id, targets=args.target,
                             accept_gaps=args.accept_gaps):
            print(path)
        return 0
    if args.command == "sync-skills":
        library = load_config(args.config).library_dir if args.config.is_file() else None
        installed = sync_approved(library_dir=library, targets=args.target)
        print(f"{len(installed)} instalaciones verificadas" if installed else "No hay skills aprobadas todavía")
        return 0
    if args.command == "retry":
        if args.use_transcript and args.model:
            parser.error("--model y --use-transcript son alternativas")
        if args.refresh_draft and args.model:
            parser.error("--refresh-draft usa la transcripción guardada; no acepta --model")
        options = ProcessOptions(target_id=args.item_id, model_override=args.model,
                                 use_saved_transcript=args.use_transcript,
                                 refresh_draft=args.refresh_draft, feedback=args.feedback)
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
