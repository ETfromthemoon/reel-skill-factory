"""Human review, isolated trials, and promotion of generated skills."""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path

from .core import Config, WorkflowError, run
from .library import SLUG, approved_dir, draft_dir, write_json, write_text
from .demo import motion_evidence_ready, read_demo, requires_motion
from .worker import JOBS_DIR, load_state


ID = re.compile(r"^[A-Za-z0-9_-]+$")
def _job(config: Config, item_id: str) -> tuple[Path, Path]:
    if not ID.fullmatch(item_id):
        raise WorkflowError("ID de video inválido")
    record = load_state().get(item_id)
    if not isinstance(record, dict) or record.get("status") != "draft":
        raise WorkflowError("El video no tiene un borrador local listo")
    job = JOBS_DIR / item_id
    draft = draft_dir(config, item_id)
    if not (draft / "SKILL.md").is_file():
        raise WorkflowError("Falta el archivo del borrador privado")
    return job, draft


def _write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    tmp.replace(path)


def _codex_env() -> dict[str, str]:
    env = os.environ.copy()
    if shutil.which("codex", path=env.get("PATH")):
        return env
    if os.name == "nt":
        root = Path(env.get("LOCALAPPDATA", "")) / "OpenAI" / "Codex" / "bin"
        candidates = sorted(root.glob("*/codex.exe"), key=lambda p: p.stat().st_mtime, reverse=True)
        if candidates:
            env["PATH"] = str(candidates[0].parent) + os.pathsep + env.get("PATH", "")
            return env
    raise WorkflowError("No se encontró Codex CLI para evaluar la skill")


def sync_approved(*, library_dir: Path | None = None, targets: list[Path] | None = None) -> list[Path]:
    """Install skills approved in the user's private library."""
    library = library_dir or Path.home() / ".reel-skill-factory" / "library"
    catalog = library / "approved"
    if not catalog.exists():
        return []
    if not catalog.is_dir() or catalog.is_symlink():
        raise WorkflowError("El catálogo privado aprobado no es una carpeta normal")
    destinations = targets or [Path.home() / ".codex" / "skills", Path.home() / ".agents" / "skills"]
    manifest_path = library / "installed-skills.json"
    try:
        manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    except (OSError, ValueError) as exc:
        raise WorkflowError("No se pudo leer el registro de skills instaladas") from exc
    if not isinstance(manifest, dict):
        raise WorkflowError("Registro de skills instaladas inválido")
    planned = []
    for folder in sorted(catalog.iterdir()):
        if folder.is_symlink() or not folder.is_dir() or not SLUG.fullmatch(folder.name):
            raise WorkflowError(f"Carpeta de skill inválida: {folder.name}")
        source = folder / "SKILL.md"
        if not source.is_file() or source.is_symlink():
            raise WorkflowError(f"Falta SKILL.md válido en {folder.name}")
        content = source.read_text(encoding="utf-8")
        if not content.startswith(f"---\nname: {folder.name}\ndescription: "):
            raise WorkflowError(f"Frontmatter inválido en {folder.name}")
        for root in destinations:
            target = root.expanduser() / folder.name / "SKILL.md"
            if target.parent.is_symlink() or target.is_symlink():
                raise WorkflowError(f"Destino enlazado no admitido: {target}")
            previous_hash = manifest.get(str(target))
            if target.exists():
                existing = target.read_text(encoding="utf-8")
                if existing != content and hashlib.sha256(existing.encode()).hexdigest() != previous_hash:
                    raise WorkflowError(f"La skill local fue modificada: {target}; no se reemplazó")
            planned.append((target, content))
    installed = []
    for target, content in planned:
        target.parent.mkdir(parents=True, exist_ok=True)
        temporary = target.with_suffix(".tmp")
        temporary.write_text(content, encoding="utf-8")
        temporary.replace(target)
        manifest[str(target)] = hashlib.sha256(content.encode()).hexdigest()
        installed.append(target)
    _write_json(manifest_path, manifest)
    return installed


def _judge(trial: Path, scenario: str, expected: str, answer: str, files: dict) -> dict:
    output = trial / "judge.json"
    payload = {"scenario": scenario, "expected": expected, "answer": answer, "files": files}
    command = ["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check",
               "--ephemeral", "--ignore-user-config", "--strict-config",
               "-c", 'web_search="disabled"', "-c", "features.shell_tool=false",
               "--output-schema", str(Path(__file__).resolve().parent.parent / "prompts" / "evaluate_skill_schema.json"),
               "--output-last-message", str(output), "--cd", str(trial)]
    prompt = (Path(__file__).resolve().parent.parent / "prompts" / "evaluate_skill.md").read_text(encoding="utf-8")
    run(command, cwd=trial, input_text=prompt + "\n\n<input_json>\n"
        + json.dumps(payload, ensure_ascii=False) + "\n</input_json>\n", timeout=900, env=_codex_env())
    judgment = json.loads(output.read_text(encoding="utf-8"))
    if judgment.get("verdict") not in {"pass", "review"} or not isinstance(judgment.get("gaps"), list):
        raise WorkflowError("El evaluador no devolvió un veredicto válido")
    return judgment


def evaluate(config: Config, item_id: str, scenario: str, expected: str) -> Path:
    """Run the candidate in a disposable workspace and retain a reviewable report."""
    if not 20 <= len(scenario.strip()) <= 2000 or not 20 <= len(expected.strip()) <= 2000:
        raise WorkflowError("Describe un caso y el resultado esperado (20 a 2000 caracteres cada uno)")
    job, draft = _job(config, item_id)
    path = draft / "SKILL.md"
    skill = path.read_text(encoding="utf-8")
    revision = hashlib.sha256(skill.encode()).hexdigest()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    trial = job / "evaluations" / stamp
    trial.mkdir(parents=True, exist_ok=False)
    report_path = trial / "report.json"
    _write_json(report_path, {"status": "running", "revision": revision, "scenario": scenario,
                              "expected": expected, "skill_path": str(path)})
    with tempfile.TemporaryDirectory(prefix="skill-trial-") as tmp:
        workspace = Path(tmp) / "workspace"
        workspace.mkdir()
        output = Path(tmp) / "answer.txt"
        prompt = ("Prueba esta skill en este directorio desechable. Aplica sus instrucciones al caso. "
                  "No accedas a archivos externos, no instales dependencias, no uses red y no publiques nada. "
                  "Crea los archivos mínimos que demuestren el resultado.\n\n"
                  f"<skill>\n{skill}\n</skill>\n\n<caso>\n{scenario}\n</caso>\n\n"
                  f"<resultado_esperado>\n{expected}\n</resultado_esperado>")
        command = ["codex", "exec", "--sandbox", "workspace-write", "--skip-git-repo-check",
                   "--ephemeral", "--ignore-user-config", "--strict-config",
                   "-c", 'web_search="disabled"', "--output-last-message", str(output),
                   "--cd", str(workspace)]
        try:
            run(command, cwd=workspace, input_text=prompt, timeout=900, env=_codex_env())
            files = {}
            total_size = 0
            for file in workspace.rglob("*"):
                if file.is_symlink():
                    raise WorkflowError("La prueba creó un enlace simbólico; se detuvo la evaluación")
                if file.is_file():
                    relative = file.relative_to(workspace).as_posix()
                    if len(files) >= 30 or file.stat().st_size > 500_000:
                        raise WorkflowError("La prueba excedió el límite de 30 archivos o 500 KB por archivo")
                    total_size += file.stat().st_size
                    if total_size > 200_000:
                        raise WorkflowError("La prueba excedió el límite de 200 KB total")
                    files[relative] = file.read_text(encoding="utf-8", errors="replace")
            answer = output.read_text(encoding="utf-8") if output.exists() else ""
            judgment = _judge(trial, scenario, expected, answer, files)
            _write_json(report_path, {"status": "review", "revision": revision,
                                      "scenario": scenario, "expected": expected,
                                      "skill_path": str(path), "answer": answer, "files": files,
                                      "judgment": judgment})
        except (WorkflowError, OSError) as exc:
            _write_json(report_path, {"status": "failed", "revision": revision,
                                      "scenario": scenario, "expected": expected, "error": str(exc)})
            raise
    return report_path


def activate(config: Config, item_id: str, *, targets: list[Path] | None = None,
             accept_gaps: bool = False) -> list[Path]:
    """Approve one reviewed private draft and install it for local code agents."""
    job, draft = _job(config, item_id)
    skill = (draft / "SKILL.md").read_text(encoding="utf-8")
    revision = hashlib.sha256(skill.encode()).hexdigest()
    reports = sorted((job / "evaluations").glob("*/report.json")) if (job / "evaluations").is_dir() else []
    matching = [report for p in reports
                if (report := json.loads(p.read_text(encoding="utf-8"))).get("status") == "review"
                and report.get("revision") == revision]
    demo = read_demo(job, revision)
    if not matching and not demo:
        raise WorkflowError("La versión actual del borrador necesita una demostración o prueba terminada")
    review = matching[-1] if matching else demo
    source_result = json.loads((job / "result.json").read_text(encoding="utf-8")) if (job / "result.json").is_file() else {}
    motion = requires_motion(source_result.get("source_map", {}))
    motion_proven = motion_evidence_ready(job, demo)
    if (review.get("judgment", {}).get("verdict") != "pass" or (motion and not motion_proven)) and not accept_gaps:
        raise WorkflowError("El evaluador dejó vacíos: revísalos y usa --accept-gaps si los comprobaste")
    metadata = json.loads((draft / "metadata.json").read_text(encoding="utf-8"))
    name = metadata.get("slug")
    if not isinstance(name, str) or not SLUG.fullmatch(name) or not skill.startswith(f"---\nname: {name}\n"):
        raise WorkflowError("El borrador tiene un nombre de skill inválido")
    approved = approved_dir(config) / name
    approved_skill = approved / "SKILL.md"
    if approved_skill.exists() and approved_skill.read_text(encoding="utf-8") != skill:
        raise WorkflowError(f"Ya hay otra skill aprobada con el nombre {name}")
    destinations = targets or [Path.home() / ".codex" / "skills", Path.home() / ".agents" / "skills"]
    for root in destinations:
        target = root.expanduser() / name / "SKILL.md"
        if target.exists() and target.read_text(encoding="utf-8") != skill:
            raise WorkflowError(f"Ya existe una skill distinta en {target}; no se reemplazó")
    write_text(approved_skill, skill)
    write_text(approved / "source.md", (draft / "source.md").read_text(encoding="utf-8"))
    write_json(approved / "metadata.json", {"item_id": item_id, "slug": name,
               "sha256": revision, "approved_at": datetime.now(timezone.utc).isoformat()})
    installed = []
    for root in destinations:
        target = root.expanduser() / name / "SKILL.md"
        write_text(target, skill)
        installed.append(target)
    manifest_path = config.library_dir / "installed-skills.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8")) if manifest_path.exists() else {}
    manifest.update({str(path): revision for path in installed})
    write_json(manifest_path, manifest)
    _write_json(job / "activation.json", {"revision": revision, "approved": str(approved_skill),
                "sha256": revision,
                "installed": [str(p) for p in installed], "accepted_gaps": accept_gaps,
                "review_mode": "manual_trial" if matching else "generated_demo",
                "motion_evidence": motion_proven})
    return installed
