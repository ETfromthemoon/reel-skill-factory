"""Render a small, offline skill library from local review artifacts."""

from __future__ import annotations

import json
import re
from html import escape
from pathlib import Path

from .demo import motion_evidence_ready, read_demo, requires_motion, skill_revision


STYLE = """body{font:16px system-ui,sans-serif;max-width:860px;margin:32px auto;padding:0 18px;background:#f7f6f2;color:#20232b}h1{font-size:2rem}h2{margin:8px 0}h3{margin-bottom:8px}p{line-height:1.5}.grid{display:grid;gap:18px}.card{background:white;border:1px solid #ddd;border-radius:16px;padding:22px;box-shadow:0 2px 10px #0001}.meta{color:#626873;font-size:.9rem;overflow-wrap:anywhere}.badge{display:inline-block;background:#e7f4ec;color:#176438;border-radius:99px;padding:4px 10px}a{color:#185caa}details{margin-top:14px}summary{cursor:pointer;font-weight:650}pre{white-space:pre-wrap;overflow-wrap:anywhere;font:14px/1.5 ui-monospace,monospace;background:#f5f5f5;padding:16px;border-radius:10px}img{max-width:180px;max-height:130px;object-fit:cover;border-radius:8px;float:right;margin:0 0 12px 16px}.motion-frames{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px}.motion-frames figure{margin:0}.motion-frames img{float:none;display:block;width:100%;max-width:none;max-height:none;aspect-ratio:3/2;object-fit:contain;background:#17191e}.motion-frames figcaption{font-size:.8rem;line-height:1.35;margin-top:6px}form{clear:both;margin:14px 0 0}label{display:block;margin:8px 0;font-weight:600}textarea{display:block;width:100%;min-height:72px;box-sizing:border-box;margin-top:5px;font:inherit}button{background:#176438;color:white;border:0;border-radius:8px;padding:10px 14px;cursor:pointer;font:inherit}button.caution{background:#8a4700}button:focus-visible,summary:focus-visible,textarea:focus-visible,input:focus-visible{outline:3px solid #185caa;outline-offset:2px}.hint{background:#eef3fa;border-left:4px solid #185caa;padding:12px 16px;border-radius:8px}.warning{background:#fff4e6;border-left:4px solid #ae5a00;padding:12px 16px;border-radius:8px}.example{clear:both;border-top:1px solid #eee;margin-top:18px;padding-top:10px}.actions{clear:both;border-top:1px solid #eee;margin-top:18px;padding-top:6px}@media(max-width:600px){img{float:none;display:block;margin:0 0 12px}.motion-frames{grid-template-columns:1fr}}"""
STATUS_LABELS = {"draft": "Borrador privado", "processing": "Procesando", "failed": "Error",
                 "needs_review": "Requiere revisión", "not_skillable": "Sin skill reutilizable",
                 "skillable": "Creando borrador", "demo_processing": "Preparando demostración"}
STYLE += "input[name=skill_name]{display:block;box-sizing:border-box;width:100%;padding:10px;margin-top:5px;font:inherit;border:1px solid #aaa;border-radius:8px}input[name=skill_name]:focus-visible{outline:3px solid #185caa;outline-offset:2px}code{font:600 1em ui-monospace,monospace}"
STYLE += ".card{margin:0}.card>summary{display:list-item}.card-title{display:block;font-size:1.25rem;margin:8px 0 0}.card>summary .meta{display:block;margin-top:4px}.card-content{margin-top:14px}"


def _text(value: object) -> str:
    return escape(str(value or ""), quote=True)


def render_vault(state: dict, jobs_dir: Path, state_dir: Path, *, token: str | None = None,
                 activity: dict | None = None) -> str:
    cards = []
    opened = False
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
        activation_path = jobs_dir / item_id / "activation.json"
        activated = activation_path.exists()
        activation = {}
        if activated:
            try:
                activation = json.loads(activation_path.read_text(encoding="utf-8"))
                if not isinstance(activation, dict):
                    activation = {}
            except (OSError, ValueError):
                pass
        status = "Activa" if activated else _text(STATUS_LABELS.get(record.get("status"), "Pendiente"))
        description = _text(result.get("description") or record.get("error") or "En proceso o pendiente de revisión.")
        draft_path = record.get("draft_path", "")
        draft_name = result.get("slug", "")
        if draft_path and Path(draft_path).is_file():
            try:
                draft_name = json.loads((Path(draft_path).parent / "metadata.json").read_text(encoding="utf-8")).get("slug", draft_name)
            except (OSError, ValueError):
                pass
        installed_name = activation.get("name") or Path(activation.get("approved", "")).parent.name
        skill_name = installed_name if activated else draft_name
        if not isinstance(skill_name, str) or not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", skill_name):
            skill_name = ""
        link = ""
        source_map = result.get("source_map")
        if isinstance(source_map, dict) and source_map.get("thesis"):
            link += f'<p><strong>El video enseña:</strong> {_text(source_map["thesis"])}</p>'
        if activated and skill_name:
            link += f'<p class="hint"><strong>Para usarla en Codex:</strong> <code>${_text(skill_name)}</code></p>'
        activity_text = (activity or {}).get(item_id)
        if activity_text:
            link += f'<p class="meta">{_text(activity_text)}</p>'
        if record.get("status") == "needs_review" and draft_path:
            link += '<p class="warning">La corrección no se completó. Puedes volver a pedir el cambio.</p>'
        if token and record.get("status") == "demo_processing" and draft_path:
            link += ('<p class="hint">Preparando el ejemplo. Pulsa «Actualizar progreso» en unos minutos.</p>'
                     '<details><summary>¿No avanza?</summary>'
                     f'<form method="post" action="/action"><input type="hidden" name="token" value="{_text(token)}">'
                     f'<input type="hidden" name="item_id" value="{_text(item_id)}">'
                     '<button name="action" value="demo">Reintentar ejemplo</button></form></details>')
        if token and record.get("status") == "draft" and not activated:
            current_hash = (skill_revision(Path(draft_path)) if draft_path and Path(draft_path).is_file() else "")
            demo = read_demo(jobs_dir / item_id, current_hash) if current_hash else None
            if demo:
                kind = demo.get("proof_kind", "legacy")
                link += ('<section class="example"><h3>Ejemplo de lo que hace la skill</h3>'
                         f'<p>{_text(demo.get("scenario"))}</p>')
                if demo.get("preview_html"):
                    link += (f'<iframe src="/demo/{_text(item_id)}" title="Vista de ejemplo de {_text(title)}" '
                             'sandbox="" loading="lazy" style="width:100%;height:390px;border:1px solid #aaa;border-radius:8px;background:white"></iframe>'
                             '<p class="meta">Ejemplo generado para esta revisión.</p>')
                elif demo.get("sample_output_md"):
                    link += f'<pre>{_text(demo.get("sample_output_md"))}</pre>'
                else:
                    link += '<p class="warning">Este ejemplo no tiene una muestra visible.</p>'
                shots = demo.get("motion_screenshots") if isinstance(demo.get("motion_screenshots"), list) else []
                stages = demo.get("motion_stages") if isinstance(demo.get("motion_stages"), list) else []
                if kind == "interface_motion":
                    if shots and token:
                        link += '<h4>Momentos del movimiento</h4><div class="motion-frames">'
                        for index, name in enumerate(shots[:3]):
                            if re.fullmatch(r"motion-[a-f0-9]{16}-[0-2]\.png", str(name)):
                                label = stages[index] if index < len(stages) else f"Estado {index + 1}"
                                link += (f'<figure><img src="/motion/{_text(item_id)}/{index}" alt="Estado {index + 1} de la demostración">'
                                         f'<figcaption>{_text(label)}</figcaption></figure>')
                        link += '</div>'
                    else:
                        link += '<p class="warning">El movimiento aún no tiene imágenes comprobables.</p>'
                link += '</section>'
            else:
                if record.get("demo_error"):
                    link += f'<p class="warning">No se pudo preparar la demostración: {_text(record["demo_error"])}</p>'
                link += (f'<form method="post" action="/action"><input type="hidden" name="token" value="{_text(token)}">'
                         f'<input type="hidden" name="item_id" value="{_text(item_id)}">'
                         '<button name="action" value="demo">Crear ejemplo</button></form>')
            report_dir = jobs_dir / item_id / "evaluations"
            reports = sorted(report_dir.glob("*/report.json")) if report_dir.is_dir() else []
            manual_review = None
            manual_note = ""
            if reports:
                try:
                    report = json.loads(reports[-1].read_text(encoding="utf-8"))
                    if report.get("status") == "review" and report.get("revision") == current_hash:
                        manual_review = report
                        if not report.get("files"):
                            manual_note = '<p class="warning">La prueba adicional no creó archivos.</p>'
                    elif report.get("status") == "failed" and report.get("revision") == current_hash:
                        manual_note = f'<p class="warning">La prueba adicional falló: {_text(report.get("error"))}</p>'
                except (OSError, ValueError):
                    pass
            review = manual_review or demo
            if review:
                judgment = review.get("judgment") if isinstance(review.get("judgment"), dict) else {}
                verdict = judgment.get("verdict")
                motion = requires_motion(result.get("source_map", {}))
                motion_proven = motion_evidence_ready(jobs_dir / item_id, demo)
                passed = verdict == "pass" and (not motion or motion_proven)
                label = ("Aprobar e instalar" if passed else "Aprobar con vacíos e instalar")
                caution = '' if passed else ' class="caution"'
                link += '<section class="actions"><h3>Evaluación</h3>'
                fidelity = result.get("fidelity_review")
                if isinstance(fidelity, dict) and fidelity.get("summary"):
                    link += f'<p><strong>Relación con el video:</strong> {_text(fidelity["summary"])}</p>'
                link += (f'<p class="{"hint" if passed else "warning"}"><strong>'
                         f'{"El ejemplo cumple este caso." if passed else "Hay puntos por revisar."}</strong> '
                         f'{_text(judgment.get("summary"))}</p>')
                gaps = judgment.get("gaps") if isinstance(judgment.get("gaps"), list) else []
                issues = fidelity.get("issues") if isinstance(fidelity, dict) and isinstance(fidelity.get("issues"), list) else []
                if gaps or issues:
                    link += '<ul>' + ''.join(f'<li>{_text(value)}</li>' for value in [*issues, *gaps]) + '</ul>'
                link += manual_note
                if motion and not motion_proven:
                    link += '<p class="warning">El movimiento todavía no está demostrado; revisa los estados antes de instalar.</p>'
                link += (f'<form method="post" action="/action"><input type="hidden" name="token" value="{_text(token)}">'
                         f'<input type="hidden" name="item_id" value="{_text(item_id)}">'
                         f'<label>Nombre de la skill<input name="skill_name" value="{_text(skill_name)}" '
                         'pattern="[a-z0-9]+(-[a-z0-9]+)*" maxlength="48" required></label>'
                         '<p class="meta">Después podrás usarla en Codex escribiendo $nombre.</p>'
                         f'<button{caution} name="action" value="activate">{label}</button></form>')
                link += '</section>'
            link += (f'<details><summary>Pedir un cambio</summary>'
                     f'<form method="post" action="/action"><input type="hidden" name="token" value="{_text(token)}">'
                     f'<input type="hidden" name="item_id" value="{_text(item_id)}">'
                     '<label>¿Qué falta o qué cambiarías?<textarea name="feedback" minlength="10" maxlength="2000" required '
                     'placeholder="Ej.: La skill omitió el paso visual de los primeros segundos y la muestra no lo aplica"></textarea></label>'
                     '<button name="action" value="correct">Corregir y crear otro ejemplo</button></form></details>')
        if token and record.get("status") == "needs_review" and draft_path and not activated:
            link += (f'<form method="post" action="/action"><input type="hidden" name="token" value="{_text(token)}">'
                     f'<input type="hidden" name="item_id" value="{_text(item_id)}">'
                     '<label>Qué falta para corregir este borrador<textarea name="feedback" minlength="10" maxlength="2000" required></textarea></label>'
                     '<button name="action" value="correct">Volver a pedir el cambio</button></form>')
        if activated:
            if token and skill_name:
                link += (f'<details><summary>Cambiar nombre</summary>'
                         f'<form method="post" action="/action"><input type="hidden" name="token" value="{_text(token)}">'
                         f'<input type="hidden" name="item_id" value="{_text(item_id)}">'
                         f'<label>Nuevo nombre<input name="skill_name" value="{_text(skill_name)}" '
                         'pattern="[a-z0-9]+(-[a-z0-9]+)*" maxlength="48" required></label>'
                         '<button name="action" value="rename">Guardar nuevo nombre</button></form></details>')
        skill = result.get("instructions_md", "")
        if skill and not activated:
            link += f'<details><summary>Ver instrucciones de la skill</summary><pre>{_text(skill)}</pre></details>'
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
        expanded = record.get("status") == "draft" and not activated and not opened
        opened = opened or expanded
        invocation = f' · ${_text(skill_name)}' if activated and skill_name else ""
        cards.append(f'<details class="card"{" open" if expanded else ""}>'
                     f'<summary><span class="badge">{status}</span><span class="card-title">{title}</span>'
                     f'<span class="meta">{_text(description)}{invocation}</span></summary>'
                     f'<div class="card-content">{preview}{link}</div></details>')
    content = "\n".join(cards) if cards else "<p>Aún no hay videos procesados.</p>"
    image_source = "'self'" if token is not None else "file:"
    return ('<!doctype html><html lang="es"><meta charset="utf-8">'
            '<meta name="viewport" content="width=device-width,initial-scale=1">'
            f'<meta http-equiv="Content-Security-Policy" content="default-src \'none\'; img-src {image_source}; frame-src \'self\'; style-src \'unsafe-inline\'; form-action \'self\'">'
            f'<title>Bóveda de skills</title><style>{STYLE}</style><main><h1>Bóveda de skills</h1>'
             '<p>Revisa el ejemplo. Si te sirve, elige un nombre y aprueba; si falta algo, pide un cambio. '
             '<a href="/">Actualizar progreso</a>.</p>'
            f'<div class="grid">{content}</div></main></html>')


def write_vault(state: dict, jobs_dir: Path, state_dir: Path) -> Path:
    state_dir.mkdir(parents=True, exist_ok=True)
    target = state_dir / "vault.html"
    temporary = state_dir / "vault.html.tmp"
    temporary.write_text(render_vault(state, jobs_dir, state_dir), encoding="utf-8")
    temporary.replace(target)
    return target
