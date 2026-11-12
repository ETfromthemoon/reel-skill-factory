"""Render a small, offline skill library from local review artifacts."""

from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path


STYLE = """body{font:16px system-ui,sans-serif;max-width:980px;margin:36px auto;padding:0 20px;background:#f7f6f2;color:#20232b}h1{font-size:2rem}p{line-height:1.5}.grid{display:grid;gap:18px}.card{background:white;border:1px solid #ddd;border-radius:16px;padding:22px;box-shadow:0 2px 10px #0001}.meta{color:#626873;font-size:.9rem}.badge{display:inline-block;background:#e7f4ec;color:#176438;border-radius:99px;padding:4px 10px}a{color:#185caa}details{margin-top:14px;border-top:1px solid #eee;padding-top:12px}summary{cursor:pointer;font-weight:650}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.5 ui-monospace,monospace;background:#f5f5f5;padding:16px;border-radius:10px}img{max-width:180px;max-height:130px;object-fit:cover;border-radius:8px;float:right;margin:0 0 12px 16px}@media(max-width:600px){img{float:none;display:block;margin:0 0 12px}}"""
STATUS_LABELS = {"published": "Borrador listo", "processing": "Procesando", "failed": "Error",
                 "needs_review": "Requiere revisión", "not_skillable": "Sin skill reutilizable",
                 "skillable": "Creando borrador"}


def _text(value: object) -> str:
    return escape(str(value or ""), quote=True)


def render_vault(state: dict, jobs_dir: Path, state_dir: Path) -> str:
    cards = []
    for item_id, record in sorted(state.items(), reverse=True):
        if not isinstance(item_id, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", item_id) or not isinstance(record, dict):
            continue
        result_path = jobs_dir / item_id / "result.json"
        result = {}
        if result_path.is_file():
            try:
                result = json.loads(result_path.read_text(encoding="utf-8"))
                if not isinstance(result, dict):
                    result = {}
            except (OSError, ValueError):
                pass
        title = _text(result.get("title") or item_id)
        status = _text(STATUS_LABELS.get(record.get("status"), "Pendiente"))
        description = _text(result.get("description") or record.get("error") or "En proceso o pendiente de revisión.")
        pr = record.get("pr", "")
        link = (f'<p><a href="{_text(pr)}" target="_blank" rel="noopener noreferrer">Abrir borrador en GitHub ↗</a></p>'
                if isinstance(pr, str) and pr.startswith("https://github.com/") else "")
        if record.get("status") == "needs_review" and link:
            link += '<p class="meta">El PR conserva la versión anterior; esta regeneración necesita revisión.</p>'
        skill = result.get("instructions_md", "")
        details = ""
        if skill:
            details += f'<details><summary>Leer skill</summary><pre>{_text(skill)}</pre></details>'
        if result.get("analysis"):
            details += f'<details><summary>Por qué se creó</summary><pre>{_text(result["analysis"])}</pre></details>'
        source_map = result.get("source_map")
        if isinstance(source_map, dict):
            lessons = source_map.get("lessons") or []
            lines = [f'Tesis: {source_map.get("thesis", "")}', '']
            lines += [f'{e.get("id", "")}: {e.get("point", "")} ({e.get("basis", "")})'
                      for e in lessons if isinstance(e, dict)]
            details += f'<details><summary>Qué enseñaba el video</summary><pre>{_text(chr(10).join(lines))}</pre></details>'
        review = result.get("fidelity_review")
        if isinstance(review, dict):
            lines = [f'Veredicto: {review.get("verdict", "")}', str(review.get("summary", ""))]
            lines += [f'Pendiente: {x}' for x in review.get("issues", [])]
            lines += [f'Añadido para aplicar la skill: {x}' for x in review.get("editorial_additions", [])]
            details += f'<details><summary>Contraste y adaptaciones</summary><pre>{_text(chr(10).join(lines))}</pre></details>'
        evidence = result.get("evidence") or []
        if evidence:
            lines = "\n".join(f'{e.get("timestamp", "")} · {e.get("modality", "audio")} · {e.get("finding", "")}'
                              for e in evidence if isinstance(e, dict))
            details += f'<details><summary>Evidencia del video ({len(evidence)})</summary><pre>{_text(lines)}</pre></details>'
        preview = ""
        visual_path = jobs_dir / item_id / "visual.json"
        if visual_path.is_file():
            try:
                visual = json.loads(visual_path.read_text(encoding="utf-8"))
                frames = visual.get("frames", []) if isinstance(visual, dict) else []
                if frames:
                    frame = Path(frames[0]["image"]).resolve()
                    if frame.is_file() and frame.is_relative_to(jobs_dir.resolve()):
                        preview = f'<img src="{_text(frame.relative_to(state_dir.resolve()).as_posix())}" alt="Primer frame del video">'
            except (OSError, ValueError, KeyError, TypeError):
                pass
        cards.append(f'<article class="card">{preview}<span class="badge">{status}</span><h2>{title}</h2><p>{description}</p><p class="meta">Video { _text(item_id) }</p>{link}{details}</article>')
    content = "\n".join(cards) if cards else "<p>Aún no hay videos procesados.</p>"
    return ('<!doctype html><html lang="es"><meta charset="utf-8"><meta http-equiv="refresh" content="30">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            '<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src file:; style-src \'unsafe-inline\'">'
            f'<title>Bóveda de skills</title><style>{STYLE}</style><main><h1>Bóveda de skills</h1>'
            '<p>Skills y análisis guardados en este computador. La página se actualiza cada 30 segundos. '
            'Los borradores requieren revisión antes de fusionarse en GitHub.</p>'
            f'<div class="grid">{content}</div></main></html>')


def write_vault(state: dict, jobs_dir: Path, state_dir: Path) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    target = state_dir / "vault.html"
    temporary = state_dir / "vault.html.tmp"
    temporary.write_text(render_vault(state, jobs_dir, state_dir), encoding="utf-8")
    temporary.replace(target)
    return target
