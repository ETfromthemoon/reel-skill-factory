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
from .worker import JOBS_DIR, STATE_DIR, load_state


ID = re.compile(r"^[A-Za-z0-9_-]+$")
SKILL_PATH = re.compile(r"^skills/([a-z0-9]+(?:-[a-z0-9]+)*)/SKILL\.md$")


def _job(item_id: str) -> tuple[dict, Path]:
    if not ID.fullmatch(item_id):
        raise WorkflowError("ID de video inválido")
    record = load_state().get(item_id)
    if not isinstance(record, dict) or record.get("status") != "published":
        raise WorkflowError("El video no tiene un borrador publicado")
    job = JOBS_DIR / item_id
    return record, job


def _pr(config: Config, record: dict) -> tuple[dict, str, str]:
    url = record.get("pr")
    prefix = f"https://github.com/{config.repository}/pull/"
    if not isinstance(url, str) or not url.startswith(prefix) or not url[len(prefix):].isdigit():
        raise WorkflowError("El PR no pertenece al repositorio configurado")
    details = json.loads(run(["gh", "pr", "view", url, "--repo", config.repository,
                              "--json", "url,state,isDraft,headRefOid,headRefName,baseRefName,files,statusCheckRollup,mergeCommit"],
                             timeout=60))
    files = {file["path"] for file in details.get("files", [])}
    skill_files = [path for path in files if SKILL_PATH.fullmatch(path)]
    if details.get("url") != url or details.get("baseRefName") != config.base_branch or len(skill_files) != 1:
        raise WorkflowError("El PR no coincide con una skill del repositorio configurado")
    if files != {skill_files[0], f"sources/{record['_item_id']}.md"}:
        raise WorkflowError("El PR contiene archivos adicionales")
    return details, skill_files[0], url


def _skill_at(config: Config, revision: str, path: str) -> str:
    with tempfile.TemporaryDirectory(prefix="skill-review-source-") as tmp:
        checkout = Path(tmp) / "repo"
        run(["git", "clone", "--quiet", "--depth", "1", "--branch", config.base_branch,
             f"https://github.com/{config.repository}.git", str(checkout)], timeout=180)
        run(["git", "fetch", "--quiet", "--depth", "1", "origin", revision], cwd=checkout, timeout=120)
        return run(["git", "show", f"FETCH_HEAD:{path}"], cwd=checkout, timeout=60) + "\n"


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
    record, job = _job(item_id)
    details, path, _ = _pr(config, {**record, "_item_id": item_id})
    if details.get("state") != "OPEN" or not details.get("isDraft"):
        raise WorkflowError("La prueba requiere un PR abierto en borrador")
    revision = details.get("headRefOid")
    if not isinstance(revision, str) or not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise WorkflowError("No se pudo verificar la versión del PR")
    skill = _skill_at(config, revision, path)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    trial = job / "evaluations" / stamp
    trial.mkdir(parents=True, exist_ok=False)
    report_path = trial / "report.json"
    _write_json(report_path, {"status": "running", "revision": revision, "scenario": scenario,
                              "expected": expected, "skill_path": path})
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
                                      "skill_path": path, "answer": answer, "files": files,
                                      "judgment": judgment})
        except (WorkflowError, OSError) as exc:
            _write_json(report_path, {"status": "failed", "revision": revision,
                                      "scenario": scenario, "expected": expected, "error": str(exc)})
            raise
    return report_path


def activate(config: Config, item_id: str, *, targets: list[Path] | None = None,
             accept_gaps: bool = False) -> list[Path]:
    """Merge an explicitly reviewed PR, then install its verified main-branch file."""
    record, job = _job(item_id)
    details, path, url = _pr(config, {**record, "_item_id": item_id})
    if details.get("state") not in {"OPEN", "MERGED"}:
        raise WorkflowError("El PR no está abierto ni fusionado")
    checks = details.get("statusCheckRollup") or []
    if not checks or any(check.get("conclusion") != "SUCCESS" for check in checks):
        raise WorkflowError("Los checks del PR deben haber terminado correctamente")
    revision = details["headRefOid"]
    reports = sorted((job / "evaluations").glob("*/report.json")) if (job / "evaluations").is_dir() else []
    matching = [report for p in reports
                if (report := json.loads(p.read_text(encoding="utf-8"))).get("status") == "review"
                and report.get("revision") == revision]
    if not matching:
        raise WorkflowError("La versión actual del PR necesita una prueba terminada")
    if matching[-1].get("judgment", {}).get("verdict") != "pass" and not accept_gaps:
        raise WorkflowError("El evaluador dejó vacíos: revísalos y usa --accept-gaps si los comprobaste")
    skill = _skill_at(config, revision, path)
    name = SKILL_PATH.fullmatch(path).group(1)
    destinations = targets or [Path.home() / ".codex" / "skills", Path.home() / ".agents" / "skills"]
    for root in destinations:
        target = root.expanduser() / name / "SKILL.md"
        if target.exists() and target.read_text(encoding="utf-8") != skill:
            raise WorkflowError(f"Ya existe una skill distinta en {target}; no se reemplazó")
    if details["state"] == "OPEN":
        if details.get("isDraft"):
            run(["gh", "pr", "ready", url, "--repo", config.repository], timeout=60)
        run(["gh", "pr", "merge", url, "--repo", config.repository, "--squash",
             "--match-head-commit", revision], timeout=180)
        merged = json.loads(run(["gh", "pr", "view", url, "--repo", config.repository,
                                 "--json", "state,mergeCommit"], timeout=60))
    else:
        merged = details
    if merged.get("state") != "MERGED" or not merged.get("mergeCommit", {}).get("oid"):
        raise WorkflowError("No se pudo verificar la integración del PR")
    integrated = _skill_at(config, merged["mergeCommit"]["oid"], path)
    if integrated != skill:
        raise WorkflowError("La skill integrada difiere de la evaluada; instalación detenida")
    installed = []
    for root in destinations:
        target = root.expanduser() / name / "SKILL.md"
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(integrated, encoding="utf-8")
        installed.append(target)
    _write_json(job / "activation.json", {"pr": url, "revision": revision,
                "merge_commit": merged["mergeCommit"]["oid"],
                "sha256": hashlib.sha256(integrated.encode()).hexdigest(),
                "installed": [str(p) for p in installed], "accepted_gaps": accept_gaps})
    return installed
