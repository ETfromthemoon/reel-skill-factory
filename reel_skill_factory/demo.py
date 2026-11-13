"""Generate a small, reviewable example for each private draft."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .core import WorkflowError, _model_json, run


MOTION_CUE = re.compile(r"\b(?:animaci[oó]n|animar|movimiento|transici[oó]n|motion|animated?|keyframes?|microinteracci[oó]n)\b", re.I)
FRAME_TIMES = (150, 900, 1800)


def _browser() -> Path | None:
    for name in ("msedge", "chrome", "chromium", "chromium-browser", "google-chrome"):
        found = shutil.which(name)
        if found:
            return Path(found)
    paths = ([Path(os.environ.get("PROGRAMFILES(X86)", "")) / "Microsoft/Edge/Application/msedge.exe",
              Path(os.environ.get("PROGRAMFILES", "")) / "Google/Chrome/Application/chrome.exe"]
             if sys.platform == "win32" else
             [Path("/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"),
              Path("/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge")])
    return next((path for path in paths if path.is_file()), None)


def _capture_motion(html: str, workdir: Path) -> tuple[list[Path], str | None]:
    browser = _browser()
    if not browser:
        return [], "No hay un navegador Chromium/Edge para observar el movimiento."
    if re.search(r"animation-delay\s*:", html, re.I):
        return [], "El prototipo usa animation-delay; utiliza porcentajes de keyframes para muestrear la misma línea temporal."
    # Pause the CSS timeline at each instant; CLI virtual time does not reliably
    # advance compositor animations. Script and network remain blocked by CSP.
    csp = ("<meta http-equiv=\"Content-Security-Policy\" content=\"default-src 'none'; "
           "style-src 'unsafe-inline'; img-src data:; font-src data:\">")
    shots: list[Path] = []
    try:
        for index, milliseconds in enumerate(FRAME_TIMES):
            freeze = ("<style>*{animation-play-state:paused!important;"
                      f"animation-delay:-{milliseconds}ms!important}}</style>")
            page = workdir / f"motion-{index}.html"
            frozen_html, replacements = re.subn(r"</head\s*>", lambda match: freeze + match.group(),
                                                html, count=1, flags=re.I)
            page.write_text(csp + (frozen_html if replacements else freeze + html), encoding="utf-8")
            shot = workdir / f"motion-{index}.png"
            profile = workdir / f"browser-{index}"
            run([str(browser), "--headless=new", "--force-prefers-no-reduced-motion",
                 "--no-first-run", "--no-default-browser-check",
                 "--disable-background-networking", "--disable-extensions", "--disable-gpu",
                 f"--user-data-dir={profile}", "--window-size=960,640",
                 f"--screenshot={shot}",
                 page.as_uri()], cwd=workdir, timeout=45)
            if not shot.is_file() or not 1000 <= shot.stat().st_size <= 2_000_000:
                raise WorkflowError("El navegador no produjo una captura válida")
            shots.append(shot)
    except (WorkflowError, OSError) as exc:
        return [], f"No se pudieron capturar los estados de movimiento: {exc}"
    if len({hashlib.sha256(shot.read_bytes()).digest() for shot in shots}) < 2:
        return shots, "Las capturas del inicio, desarrollo y final no muestran un cambio visual."
    return shots, None


def skill_revision(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()


def requires_motion(source_map: dict) -> bool:
    if not isinstance(source_map, dict):
        return False
    lessons = source_map.get("lessons")
    points = [str(lesson.get("point", "")) for lesson in lessons if isinstance(lesson, dict)] \
        if isinstance(lessons, list) else []
    text = " ".join([str(source_map.get("thesis", "")), *points])
    return bool(MOTION_CUE.search(text))


def read_demo(job_dir: Path, revision: str) -> dict | None:
    path = job_dir / "auto-demo.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("revision") == revision and data.get("status") == "ready" else None


def motion_evidence_ready(job_dir: Path, demo: dict | None) -> bool:
    if not demo or demo.get("proof_kind") != "interface_motion" or demo.get("judgment", {}).get("verdict") != "pass":
        return False
    names = demo.get("motion_screenshots")
    if not isinstance(names, list) or len(names) != 3:
        return False
    try:
        shots = [job_dir / name for name in names
                 if isinstance(name, str) and re.fullmatch(r"motion-[a-f0-9]{16}-[0-2]\.png", name)]
        return len(shots) == 3 and all(shot.is_file() and shot.stat().st_size <= 2_000_000 for shot in shots) \
            and len({hashlib.sha256(shot.read_bytes()).digest() for shot in shots}) >= 2
    except OSError:
        return False


def create_demo(draft_path: Path, job_dir: Path, result: dict, *,
                prior_feedback: dict | None = None) -> Path:
    skill = draft_path.read_text(encoding="utf-8")
    revision = skill_revision(draft_path)
    source_map = result.get("source_map") if isinstance(result.get("source_map"), dict) else {}
    payload = {"skill": skill, "description": result.get("description", ""),
               "source_map": {"thesis": source_map.get("thesis", ""), "lessons": source_map.get("lessons", [])}}
    if prior_feedback:
        payload["prior_demo_feedback"] = prior_feedback
    with tempfile.TemporaryDirectory(prefix="skill-demo-") as temp:
        workdir = Path(temp)
        demo = _model_json("auto_demo.md", "auto_demo_schema.json", "demo.json", workdir, payload,
                           search=False)
        for key in ("scenario", "expected", "sample_output_md"):
            if not isinstance(demo.get(key), str) or not 20 <= len(demo[key].strip()) <= 30000:
                raise WorkflowError(f"La demostración automática no contiene {key} suficiente")
        kind = demo.get("proof_kind")
        if kind not in {"document", "interface_static", "interface_motion", "code"}:
            raise WorkflowError("Tipo de demostración inválido")
        if kind != "interface_motion" and requires_motion(source_map):
            kind = demo["proof_kind"] = "interface_motion"
        html = demo.get("preview_html")
        if not isinstance(html, str) or len(html) > 60000 or (html and "<html" not in html.lower()):
            raise WorkflowError("La vista HTML de la demostración no es válida")
        if not isinstance(demo.get("limitations"), list):
            raise WorkflowError("Lista inválida en la demostración: limitations")
        if html and re.search(r"<\s*(?:script|iframe|object|embed|link|base|form)\b|\bon[a-z]+\s*=|@import\b|"
                              r"\b(?:src|href)\s*=\s*['\"]?\s*(?:https?:|//|javascript:)|"
                              r"url\s*\(\s*['\"]?\s*(?:https?:|//|javascript:)", html, re.IGNORECASE):
            demo["preview_html"] = ""
            demo.setdefault("limitations", []).append("La vista HTML incluía contenido activo o externo y se omitió.")
        stages = demo.get("motion_stages")
        if not isinstance(stages, list) or len(stages) > 3 or any(
                not isinstance(value, str) or len(value) > 500 for value in stages):
            raise WorkflowError("Lista inválida en la demostración: motion_stages")
        motion_gap = None
        screenshots: list[Path] = []
        if kind == "interface_motion":
            if len(stages) != 3 or not demo["preview_html"] or not re.search(r"@keyframes\b", html, re.I):
                motion_gap = "La prueba de movimiento necesita tres estados y un prototipo animado reproducible."
            else:
                screenshots, motion_gap = _capture_motion(demo["preview_html"], workdir)
        for key in ("checklist", "limitations"):
            if (not isinstance(demo.get(key), list) or len(demo[key]) > 30
                    or any(not isinstance(value, str) or len(value) > 500 for value in demo[key])):
                raise WorkflowError(f"Lista inválida en la demostración: {key}")
        review = _model_json("auto_demo_review.md", "evaluate_skill_schema.json", "demo-review.json",
                             workdir, {"skill": skill, "source_map": payload["source_map"], "demo": demo,
                                       "capture_times_ms": list(FRAME_TIMES) if screenshots else [],
                                       "capture_error": motion_gap},
                             image_paths=screenshots, search=False)
        if (review.get("verdict") not in {"pass", "review"} or not isinstance(review.get("summary"), str)
                or not isinstance(review.get("gaps"), list) or not isinstance(review.get("evidence"), list)):
            raise WorkflowError("El revisor de la demostración no devolvió un resultado válido")
        if review["verdict"] == "pass" and review["gaps"]:
            review["verdict"] = "review"
        if motion_gap:
            review["verdict"] = "review"
            review["gaps"].append(motion_gap)
        saved_shots = []
        for index, shot in enumerate(screenshots):
            destination = job_dir / f"motion-{revision[:16]}-{index}.png"
            destination.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(shot, destination)
            saved_shots.append(destination.name)
    output = {"status": "ready", "mode": "generated_demo", "revision": revision,
              "generated_at": datetime.now(timezone.utc).isoformat(), **demo,
              "motion_screenshots": saved_shots, "judgment": review}
    path = job_dir / "auto-demo.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    if (kind == "interface_motion" and screenshots and review["verdict"] == "review"
            and prior_feedback is None):
        try:
            return create_demo(draft_path, job_dir, result, prior_feedback={
                "scenario": demo["scenario"], "summary": review["summary"],
                "gaps": review["gaps"][:8]})
        except (WorkflowError, OSError, ValueError):
            # Keep the first reviewable result if automatic repair fails.
            return path
    return path
