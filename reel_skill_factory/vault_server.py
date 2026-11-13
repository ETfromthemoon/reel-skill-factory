"""Loopback-only review controls for the local vault."""

from __future__ import annotations

import secrets
import threading
import json
import re
from pathlib import Path
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from .core import WorkflowError, load_config
from .demo import create_demo, read_demo, skill_revision
from .lifecycle import activate, evaluate
from .library import draft_dir
from .vault import render_vault
from .worker import JOBS_DIR, STATE_DIR, STATE_PATH, ProcessOptions, _write_json, load_state, process_inbox, worker_lock


def serve(config_path, port: int = 8766) -> None:
    token = secrets.token_urlsafe(32)
    activity: dict[str, str] = {}
    busy: set[str] = set()
    lock = threading.Lock()
    config = load_config(config_path)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path.startswith("/motion/"):
                match = re.fullmatch(r"/motion/([A-Za-z0-9_-]+)/([0-2])", self.path)
                if not match:
                    self.send_error(404)
                    return
                item_id, index = match.group(1), int(match.group(2))
                try:
                    draft = draft_dir(config, item_id) / "SKILL.md"
                    demo = read_demo(JOBS_DIR / item_id, skill_revision(draft))
                    names = demo.get("motion_screenshots", []) if demo else []
                    name = names[index]
                    if not re.fullmatch(r"motion-[a-f0-9]{16}-[0-2]\.png", name):
                        raise ValueError("Captura inválida")
                    shot = (JOBS_DIR / item_id / name).resolve()
                    if not shot.is_relative_to(JOBS_DIR.resolve()) or shot.stat().st_size > 2_000_000:
                        raise ValueError("Captura no disponible")
                    body = shot.read_bytes()
                except (OSError, ValueError, IndexError, TypeError, WorkflowError):
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/png")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path.startswith("/demo/"):
                item_id = self.path.removeprefix("/demo/")
                if not re.fullmatch(r"[A-Za-z0-9_-]+", item_id):
                    self.send_error(404)
                    return
                try:
                    draft = draft_dir(config, item_id) / "SKILL.md"
                    demo = read_demo(JOBS_DIR / item_id, skill_revision(draft))
                    html = demo.get("preview_html") if demo else None
                    if not isinstance(html, str) or not html or len(html) > 60_000:
                        raise ValueError("Vista no disponible")
                except (OSError, ValueError, WorkflowError):
                    self.send_error(404)
                    return
                body = html.encode("utf-8")
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Security-Policy", "sandbox; default-src 'none'; style-src 'unsafe-inline'; img-src data:; font-src data:")
                self.send_header("X-Content-Type-Options", "nosniff")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path.startswith("/frame/"):
                item_id = self.path.removeprefix("/frame/")
                if not re.fullmatch(r"[A-Za-z0-9_-]+", item_id):
                    self.send_error(404)
                    return
                try:
                    visual = json.loads((JOBS_DIR / item_id / "visual.json").read_text(encoding="utf-8"))
                    frame = Path(visual["frames"][0]["image"]).resolve()
                    if (not frame.is_relative_to(JOBS_DIR.resolve()) or frame.suffix.lower() not in {".jpg", ".jpeg", ".png"}
                            or not frame.is_file() or frame.stat().st_size > 2_000_000):
                        raise ValueError("Frame no permitido")
                    body = frame.read_bytes()
                except (OSError, ValueError, KeyError, IndexError, TypeError):
                    self.send_error(404)
                    return
                self.send_response(200)
                self.send_header("Content-Type", "image/png" if frame.suffix.lower() == ".png" else "image/jpeg")
                self.send_header("Cache-Control", "no-store")
                self.send_header("Content-Length", str(len(body)))
                self.end_headers()
                self.wfile.write(body)
                return
            if self.path != "/":
                self.send_error(404)
                return
            page = render_vault(load_state(), JOBS_DIR, STATE_DIR, token=token, activity=activity)
            body = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Security-Policy", "default-src 'none'; img-src 'self'; frame-src 'self'; style-src 'unsafe-inline'; form-action 'self'")
            self.send_header("Cache-Control", "no-store")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        def do_POST(self):
            host = f"127.0.0.1:{port}"
            if (self.path != "/action" or self.headers.get("Host") != host
                    or self.headers.get("Origin") != f"http://{host}"):
                self.send_error(403)
                return
            try:
                length = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                self.send_error(400)
                return
            if length <= 0 or length > 10_000:
                self.send_error(413)
                return
            data = parse_qs(self.rfile.read(length).decode("utf-8"), strict_parsing=True)
            one = lambda key: data[key][0] if len(data.get(key, [])) == 1 else None
            item_id, action = one("item_id"), one("action")
            if one("token") != token or not item_id or action not in {"evaluate", "activate", "correct", "demo"}:
                self.send_error(403)
                return
            if action == "correct" and not 10 <= len((one("feedback") or "").strip()) <= 2000:
                self.send_error(400)
                return
            with lock:
                if item_id in busy:
                    self.send_error(409)
                    return
                busy.add(item_id)
                activity[item_id] = {"evaluate": "Evaluando…", "activate": "Activando…",
                                     "correct": "Corrigiendo borrador y preparando nueva muestra…",
                                     "demo": "Preparando demostración…"}[action]

            def work():
                try:
                    if action == "evaluate":
                        path = evaluate(config, item_id, one("scenario") or "", one("expected") or "")
                        message = f"Prueba terminada: {path}. Revisa los archivos y el resultado."
                    elif action == "activate":
                        paths = activate(config, item_id, accept_gaps=True)
                        message = "Skill aprobada e instalada localmente: " + ", ".join(map(str, paths))
                    elif action == "demo":
                        with worker_lock():
                            draft = draft_dir(config, item_id) / "SKILL.md"
                            job = JOBS_DIR / item_id
                            result = json.loads((job / "result.json").read_text(encoding="utf-8"))
                            path = create_demo(draft, job, result)
                            state = load_state()
                            if state.get(item_id, {}).get("status") == "demo_processing":
                                state[item_id]["status"] = "draft"
                                state[item_id].pop("demo_error", None)
                                _write_json(STATE_PATH, state)
                        message = f"Demostración preparada: {path}"
                    else:
                        _, failures = process_inbox(config_path, ProcessOptions(
                            target_id=item_id, refresh_draft=True, feedback=one("feedback")))
                        if failures:
                            record = load_state().get(item_id, {})
                            raise WorkflowError(record.get("retry_error") or record.get("error") or "No se pudo corregir")
                        message = "Borrador corregido. Revisa la nueva demostración."
                except (WorkflowError, OSError, ValueError) as exc:
                    message = f"Error: {exc}"
                with lock:
                    activity[item_id] = message
                    busy.discard(item_id)

            threading.Thread(target=work, daemon=True).start()
            self.send_response(303)
            self.send_header("Location", "/")
            self.send_header("Content-Length", "0")
            self.end_headers()

    server = ThreadingHTTPServer(("127.0.0.1", port), Handler)
    print(f"Bóveda interactiva: http://127.0.0.1:{port}/", flush=True)
    server.serve_forever()
