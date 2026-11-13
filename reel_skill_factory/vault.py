"""Render a small, offline skill library from local review artifacts."""

from __future__ import annotations

import json
import hashlib
import re
from html import escape
from pathlib import Path


STYLE = """body{font:16px system-ui,sans-serif;max-width:980px;margin:36px auto;padding:0 20px;background:#f7f6f2;color:#20232b}h1{font-size:2rem}p{line-height:1.5}.grid{display:grid;gap:18px}.card{background:white;border:1px solid #ddd;border-radius:16px;padding:22px;box-shadow:0 2px 10px #0001}.meta{color:#626873;font-size:.9rem;overflow-wrap:anywhere}.badge{display:inline-block;background:#e7f4ec;color:#176438;border-radius:99px;padding:4px 10px}a{color:#185caa}details{margin-top:14px;border-top:1px solid #eee;padding-top:12px}summary{cursor:pointer;font-weight:650}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.5 ui-monospace,monospace;background:#f5f5f5;padding:16px;border-radius:10px}img{max-width:180px;max-height:130px;object-fit:cover;border-radius:8px;float:right;margin:0 0 12px 16px}form{clear:both;margin:16px 0;padding:14px;border:1px solid #ddd;border-radius:10px}label{display:block;margin:8px 0;font-weight:600}textarea{display:block;width:100%;min-height:64px;box-sizing:border-box;margin-top:5px;font:inherit}button{background:#176438;color:white;border:0;border-radius:8px;padding:10px 14px;cursor:pointer;font:inherit}button:focus-visible,summary:focus-visible,textarea:focus-visible{outline:3px solid #185caa;outline-offset:2px}.hint{background:#eef3fa;border-left:4px solid #185caa;padding:12px 16px;border-radius:8px}.warning{background:#fff4e6;border-left:4px solid #ae5a00;padding:12px 16px;border-radius:8px}@media(max-width:600px){img{float:none;display:block;margin:0 0 12px}}"""
STATUS_LABELS = {"draft": "Borrador privado", "processing": "Procesando", "failed": "Error",
                 "needs_review": "Requiere revisión", "not_skillable": "Sin skill reutilizable",
                 "skillable": "Creando borrador"}


def _text(value: object) -> str:
    return escape(str(value or ""), quote=True)


def _report_html(report: dict) -> str:
    if report.get("status") == "running":
        return '<p class="hint">Prueba en curso. Pulsa «Actualizar progreso» para ver el resultado.</p>'
    if report.get("status") == "failed":
        return f'<p class="warning">La prueba falló: {_text(report.get("error"))}</p>'
    judgment = report.get("judgment") if isinstance(report.get("judgment"), dict) else {}
    verdict = judgment.get("verdict")
    heading = ("El evaluador vio una demostración suficiente para este caso" if verdict == "pass"
               else "El evaluador encontró aspectos por revisar")
    gaps = judgment.get("gaps") if isinstance(judgment.get("gaps"), list) else []
    files = report.get("files") if isinstance(report.get("files"), dict) else {}
    parts = [f'<p class="{"hint" if verdict == "pass" else "warning"}"><strong>{heading}.</strong> '
             f'{_text(judgment.get("summary"))}</p>']
    if not files:
        parts.append('<p class="warning">La prueba no creó archivos. Lee la respuesta de Codex antes de aprobar.</p>')
    if gaps:
        parts.append('<p>Vacíos: ' + '; '.join(_text(gap) for gap in gaps) + '</p>')
    parts.append(f'<details><summary>Caso y resultado esperado</summary><p>{_text(report.get("scenario"))}</p>'
                 f'<p><strong>Esperado:</strong> {_text(report.get("expected"))}</p></details>')
    if files:
        parts.append('<details><summary>Archivos producidos (' + str(len(files)) + ')</summary>')
        for name, content in files.items():
            parts.append(f'<h4>{_text(name)}</h4><pre>{_text(content)}</pre>')
        parts.append('</details>')
    parts.append(f'<details><summary>Respuesta de Codex</summary><pre>{_text(report.get("answer"))}</pre></details>')
    return ''.join(parts)


def render_vault(state: dict, jobs_dir: Path, state_dir: Path, *, token: str | None = None,
                 activity: dict | None = None) -> str:
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
        activated = (jobs_dir / item_id / "activation.json").exists()
        status = "Activa" if activated else _text(STATUS_LABELS.get(record.get("status"), "Pendiente"))
        description = _text(result.get("description") or record.get("error") or "En proceso o pendiente de revisión.")
        draft_path = record.get("draft_path", "")
        link = f'<p class="meta">Archivo privado: {_text(draft_path)}</p>' if draft_path else ""
        if record.get("status") == "needs_review" and draft_path:
            link += '<p class="meta">El borrador anterior permanece; esta regeneración necesita revisión.</p>'
        if token and record.get("status") == "draft" and not activated:
            activity_text = (activity or {}).get(item_id)
            if activity_text:
                link += f'<p class="meta">{_text(activity_text)}</p>'
            link += ('<details><summary>Probar esta skill</summary>'
                     f'<form method="post" action="/action"><input type="hidden" name="token" value="{_text(token)}">'
                     f'<input type="hidden" name="item_id" value="{_text(item_id)}">'
                     '<label>Caso de prueba<textarea name="scenario" minlength="20" maxlength="2000" required '
                     'placeholder="Ej.: Crea una tarjeta de producto para una tienda de café con precio y botón de compra"></textarea></label>'
                     '<label>Resultado esperado<textarea name="expected" minlength="20" maxlength="2000" required '
                     'placeholder="Ej.: HTML y CSS con jerarquía clara, contraste legible y animación reducida"></textarea></label>'
                     '<p class="meta">La prueba puede tardar varios minutos. Codex trabajará en una carpeta temporal; luego verás su respuesta, los archivos y los vacíos.</p>'
                     '<button name="action" value="evaluate">Probar este borrador</button></form></details>')
            report_dir = jobs_dir / item_id / "evaluations"
            reports = sorted(report_dir.glob("*/report.json")) if report_dir.is_dir() else []
            if reports:
                try:
                    report = json.loads(reports[-1].read_text(encoding="utf-8"))
                    link += '<details open><summary>Resultado de la última prueba</summary>'
                    link += _report_html(report) + '</details>'
                    current_hash = (hashlib.sha256(Path(draft_path).read_text(encoding="utf-8").encode()).hexdigest()
                                    if draft_path and Path(draft_path).is_file() else "")
                    if report.get("revision") != current_hash:
                        link += '<p class="meta">Esta prueba es de otra versión del borrador. Vuelve a probar.</p>'
                    if report.get("status") == "review" and report.get("revision") == current_hash and not activated:
                        judgment = report.get("judgment") if isinstance(report.get("judgment"), dict) else {}
                        verdict = judgment.get("verdict")
                        prompt = ('Confirmo que revisé el resultado y los vacíos' if verdict != "pass"
                                  else 'Confirmo que revisé el resultado de esta prueba')
                        link += (f'<form method="post" action="/action"><input type="hidden" name="token" value="{_text(token)}">'
                                 f'<input type="hidden" name="item_id" value="{_text(item_id)}">'
                                 f'<label><input type="checkbox" name="confirm" value="yes" required> {prompt}</label>'
                                 '<button name="action" value="activate">Aprobar e instalar en mis agentes</button></form>')
                except (OSError, ValueError):
                    pass
        if activated:
            link += '<p class="badge">Aprobada e instalada localmente</p>'
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
                        source = (f'/frame/{item_id}' if token is not None
                                  else frame.relative_to(state_dir.resolve()).as_posix())
                        preview = f'<img src="{_text(source)}" alt="Primer frame del video">'
            except (OSError, ValueError, KeyError, TypeError):
                pass
        cards.append(f'<article class="card">{preview}<span class="badge">{status}</span><h2>{title}</h2><p>{description}</p><p class="meta">Video { _text(item_id) }</p>{link}{details}</article>')
    content = "\n".join(cards) if cards else "<p>Aún no hay videos procesados.</p>"
    image_source = "'self'" if token is not None else "file:"
    return ('<!doctype html><html lang="es"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src {image_source}; style-src \'unsafe-inline\'; form-action \'self\'">'
            f'<title>Bóveda de skills</title><style>{STYLE}</style><main><h1>Bóveda de skills</h1>'
            '<p>Skills y análisis guardados en este computador. <a href="/">Actualizar progreso</a>.</p>'
            '<details class="card"><summary>Cómo probar una skill, paso a paso</summary>'
            '<ol><li>Abre «Qué enseñaba el video» y «Leer skill» para comprobar que coincidan.</li>'
            '<li>Escribe una tarea concreta en «Caso de prueba» y describe qué resultado comprobarás.</li>'
            '<li>Pulsa «Probar este borrador» y espera el resultado.</li>'
            '<li>Lee la respuesta, los archivos producidos y los vacíos. Puedes repetir con otro caso.</li>'
            '<li>Si estás conforme, marca la revisión y pulsa «Aprobar e instalar».</li></ol>'
            '<p>La carpeta temporal limita la prueba, pero no es una máquina virtual. '
            'Una prueba favorable no garantiza que la skill funcione en todos los proyectos.</p></details>'
            f'<div class="grid">{content}</div></main></html>')


def write_vault(state: dict, jobs_dir: Path, state_dir: Path) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    target = state_dir / "vault.html"
    temporary = state_dir / "vault.html.tmp"
    temporary.write_text(render_vault(state, jobs_dir, state_dir), encoding="utf-8")
    temporary.replace(target)
    return target
