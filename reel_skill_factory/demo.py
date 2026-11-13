"""Generate a small, reviewable example for each private draft."""

from __future__ import annotations

import hashlib
import json
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .core import WorkflowError, _model_json


def skill_revision(path: Path) -> str:
    return hashlib.sha256(path.read_text(encoding="utf-8").encode()).hexdigest()


def read_demo(job_dir: Path, revision: str) -> dict | None:
    path = job_dir / "auto-demo.json"
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) and data.get("revision") == revision and data.get("status") == "ready" else None


def create_demo(draft_path: Path, job_dir: Path, result: dict) -> Path:
    skill = draft_path.read_text(encoding="utf-8")
    revision = skill_revision(draft_path)
    source_map = result.get("source_map") if isinstance(result.get("source_map"), dict) else {}
    payload = {"skill": skill, "description": result.get("description", ""),
               "source_map": {"thesis": source_map.get("thesis", ""), "lessons": source_map.get("lessons", [])}}
    with tempfile.TemporaryDirectory(prefix="skill-demo-") as temp:
        workdir = Path(temp)
        demo = _model_json("auto_demo.md", "auto_demo_schema.json", "demo.json", workdir, payload,
                           search=False)
        for key in ("scenario", "expected", "sample_output_md"):
            if not isinstance(demo.get(key), str) or not 20 <= len(demo[key].strip()) <= 30000:
                raise WorkflowError(f"La demostración automática no contiene {key} suficiente")
        html = demo.get("preview_html")
        if not isinstance(html, str) or len(html) > 60000 or (html and "<html" not in html.lower()):
            raise WorkflowError("La vista HTML de la demostración no es válida")
        if not isinstance(demo.get("limitations"), list):
            raise WorkflowError("Lista inválida en la demostración: limitations")
        if html and re.search(r"<\s*(?:script|iframe|object|embed)\b|\bon[a-z]+\s*=|@import\b|"
                              r"\b(?:src|href)\s*=\s*['\"]?\s*(?:https?:|//|javascript:)", html, re.IGNORECASE):
            demo["preview_html"] = ""
            demo.setdefault("limitations", []).append("La vista HTML incluía contenido activo o externo y se omitió.")
        for key in ("checklist", "limitations"):
            if (not isinstance(demo.get(key), list) or len(demo[key]) > 30
                    or any(not isinstance(value, str) or len(value) > 500 for value in demo[key])):
                raise WorkflowError(f"Lista inválida en la demostración: {key}")
        review = _model_json("auto_demo_review.md", "evaluate_skill_schema.json", "demo-review.json",
                             workdir, {"skill": skill, "source_map": payload["source_map"], "demo": demo},
                             search=False)
        if (review.get("verdict") not in {"pass", "review"} or not isinstance(review.get("summary"), str)
                or not isinstance(review.get("gaps"), list) or not isinstance(review.get("evidence"), list)):
            raise WorkflowError("El revisor de la demostración no devolvió un resultado válido")
        if review["verdict"] == "pass" and review["gaps"]:
            review["verdict"] = "review"
    output = {"status": "ready", "mode": "generated_demo", "revision": revision,
              "generated_at": datetime.now(timezone.utc).isoformat(), **demo, "judgment": review}
    path = job_dir / "auto-demo.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(output, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    temporary.replace(path)
    return path
