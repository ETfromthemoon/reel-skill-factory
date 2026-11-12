"""Loopback-only review controls for the local vault."""

from __future__ import annotations

import secrets
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import parse_qs

from .core import WorkflowError, load_config
from .lifecycle import activate, evaluate
from .vault import render_vault
from .worker import JOBS_DIR, STATE_DIR, load_state


def serve(config_path, port: int = 8766) -> None:
    token = secrets.token_urlsafe(32)
    activity: dict[str, str] = {}
    busy: set[str] = set()
    lock = threading.Lock()
    config = load_config(config_path)

    class Handler(BaseHTTPRequestHandler):
        def do_GET(self):
            if self.path != "/":
                self.send_error(404)
                return
            page = render_vault(load_state(), JOBS_DIR, STATE_DIR, token=token, activity=activity)
            body = page.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Security-Policy", "default-src 'none'; style-src 'unsafe-inline'; form-action 'self'")
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
            if one("token") != token or not item_id or action not in {"evaluate", "activate"}:
                self.send_error(403)
                return
            if action == "activate" and one("confirm") != "yes":
                self.send_error(403)
                return
            with lock:
                if item_id in busy:
                    self.send_error(409)
                    return
                busy.add(item_id)
                activity[item_id] = "Evaluando…" if action == "evaluate" else "Activando…"

            def work():
                try:
                    if action == "evaluate":
                        path = evaluate(config, item_id, one("scenario") or "", one("expected") or "")
                        message = f"Prueba terminada: {path}. Revisa los archivos y el resultado."
                    else:
                        paths = activate(config, item_id, accept_gaps=True)
                        message = "Skill integrada e instalada: " + ", ".join(map(str, paths))
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
