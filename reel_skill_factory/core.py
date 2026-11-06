from __future__ import annotations

import json
import math
import os
import re
import subprocess
import sys
import tempfile
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit


ROOT = Path(__file__).resolve().parent.parent
REEL_PATH = re.compile(r"^/reel/([A-Za-z0-9_-]+)/?$")
REPO_NAME = re.compile(r"^[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+$")
SLUG = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
URLS = re.compile(r"https?://[^\s<>\"']+")
TIMESTAMP = re.compile(r"\[(?:\d{2}:)?\d{2}:\d{2}\]")


class WorkflowError(RuntimeError):
    pass


@dataclass(frozen=True)
class Config:
    inbox_dir: Path
    repository: str
    base_branch: str
    whisper_model: str
    poll_seconds: int
    review_whisper_model: str | None = None


def load_config(path: Path) -> Config:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError(f"No se pudo leer {path}: {exc}") from exc
    repository = str(data.get("repository", ""))
    if not REPO_NAME.fullmatch(repository):
        raise WorkflowError("repository debe tener formato OWNER/REPO")
    branch = str(data.get("base_branch", "main"))
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]*", branch):
        raise WorkflowError("base_branch no es válida")
    model = str(data.get("whisper_model", "base"))
    if model not in {"tiny", "base", "small", "medium"}:
        raise WorkflowError("whisper_model debe ser tiny, base, small o medium")
    review_model = data.get("review_whisper_model")
    if review_model is not None and review_model not in {"tiny", "base", "small", "medium"}:
        raise WorkflowError("review_whisper_model debe ser tiny, base, small, medium o null")
    try:
        poll = int(data.get("poll_seconds", 60))
    except (TypeError, ValueError) as exc:
        raise WorkflowError("poll_seconds debe ser un número entero") from exc
    if poll < 15:
        raise WorkflowError("poll_seconds debe ser al menos 15")
    inbox = Path(str(data.get("inbox_dir", ""))).expanduser()
    if not inbox.is_dir():
        raise WorkflowError(f"No existe la carpeta de Drive sincronizada: {inbox}")
    return Config(inbox.resolve(), repository, branch, model, poll, review_model)


def normalize_reel_url(value: str) -> tuple[str, str]:
    try:
        parsed = urlsplit(value.strip().rstrip(".,;!?)"))
        port = parsed.port
    except ValueError as exc:
        raise WorkflowError("El enlace de Instagram no es válido") from exc
    if parsed.scheme != "https" or parsed.hostname not in {"instagram.com", "www.instagram.com"}:
        raise WorkflowError("Se requiere un enlace HTTPS de un Reel de Instagram")
    if parsed.username or parsed.password or port:
        raise WorkflowError("El enlace de Instagram contiene componentes no permitidos")
    match = REEL_PATH.fullmatch(parsed.path)
    if not match:
        raise WorkflowError("El enlace debe tener formato instagram.com/reel/CODIGO/")
    return urlunsplit(("https", "www.instagram.com", f"/reel/{match.group(1)}/", "", "")), match.group(1)


def find_reel_url(text: str) -> tuple[str, str]:
    for match in URLS.finditer(text):
        try:
            return normalize_reel_url(match.group(0))
        except WorkflowError:
            pass
    raise WorkflowError("El archivo no contiene un enlace válido a un Reel")


def run(command: list[str], *, cwd: Path | None = None, input_text: str | None = None,
        timeout: int = 900, env: dict[str, str] | None = None) -> str:
    try:
        result = subprocess.run(command, cwd=cwd, input=input_text, text=True,
                                encoding="utf-8", errors="replace", capture_output=True,
                                timeout=timeout, check=False, env=env)
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise WorkflowError(f"Falló {command[0]}: {exc}") from exc
    if result.returncode:
        # CLI errors can include user data; keep logs short and local.
        raise WorkflowError(f"Falló {command[0]} (código {result.returncode}): {result.stderr[-800:]}")
    return result.stdout.strip()


def transcribe(url: str, model: str, workdir: Path) -> dict:
    script = ROOT / "scripts" / "extraer_transcripcion.py"
    env = os.environ.copy()
    env["PATH"] = str(Path(sys.executable).parent) + os.pathsep + env.get("PATH", "")
    env["PYTHONIOENCODING"] = "utf-8"
    output = run([sys.executable, str(script), url, "--outdir", str(workdir),
                  "--model", model, "--lang", "auto"], timeout=3600, env=env)
    try:
        payload = json.loads(output.splitlines()[-1])
    except (IndexError, json.JSONDecodeError) as exc:
        raise WorkflowError("El transcriptor no devolvió JSON válido") from exc
    if not payload.get("ok") or not payload.get("transcripcion", "").strip() or not payload.get("n_segmentos"):
        raise WorkflowError("No se obtuvo una transcripción del audio; el caption no basta para crear una skill")
    return payload


def generate(source: str, transcript: dict, workdir: Path, *, source_type: str = "reel_url") -> dict:
    prompt = (ROOT / "prompts" / "create_skill.md").read_text(encoding="utf-8")
    duration = transcript.get("duracion_seg")
    rounded_duration = (math.ceil(duration) if isinstance(duration, (int, float))
                        and math.isfinite(duration) and duration >= 0 else None)
    data = {"source": source, "source_type": source_type,
            "duration_seconds": rounded_duration,
            "transcript": transcript["transcripcion"]}
    output_file = workdir / "generation.json"
    run(["codex", "exec", "--sandbox", "read-only", "--skip-git-repo-check",
         "--ephemeral", "--ignore-user-config", "--strict-config",
         "-c", 'web_search="live"', "-c", "skills.include_instructions=false",
         "-c", "skills.max_context_tokens=100", "-c", "features.shell_tool=false",
         "--output-schema",
         str(ROOT / "prompts" / "skill_schema.json"), "--output-last-message",
         str(output_file), "--cd", str(workdir), "-"], cwd=workdir,
        input_text=prompt + "\n\n<video_data_json>\n" + json.dumps(data, ensure_ascii=False)
        + "\n</video_data_json>\n", timeout=900)
    try:
        result = json.loads(output_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise WorkflowError("Codex no produjo el JSON esperado") from exc
    validate_generation(result, transcript["transcripcion"])
    return result


def validate_generation(result: dict, transcript: str) -> None:
    if result.get("status") not in {"skillable", "not_skillable", "needs_review"}:
        raise WorkflowError("Estado de generación inválido")
    reason = result.get("review_reason")
    if reason not in {"none", "transcription", "missing_context", "technical", "other"}:
        raise WorkflowError("Motivo de revisión inválido")
    if (result["status"] == "needs_review") != (reason != "none"):
        raise WorkflowError("Motivo de revisión incoherente con el estado")
    if not isinstance(result.get("analysis"), str) or len(result["analysis"].strip()) < 40:
        raise WorkflowError("Falta análisis verificable")
    if not isinstance(result.get("title"), str) or not 5 <= len(result["title"].strip()) <= 120 or "\n" in result["title"]:
        raise WorkflowError("Título de skill inválido")
    evidence = result.get("evidence")
    if not isinstance(evidence, list):
        raise WorkflowError("Falta lista de evidencia")
    for item in evidence:
        if not isinstance(item, dict) or not isinstance(item.get("timestamp"), str):
            raise WorkflowError("Evidencia inválida")
        if not item["timestamp"].startswith("[") and f"[{item['timestamp']}]" in transcript:
            item["timestamp"] = f"[{item['timestamp']}]"
        if item["timestamp"] not in transcript or not TIMESTAMP.fullmatch(item["timestamp"]):
            raise WorkflowError("La evidencia cita una marca de tiempo ausente en la transcripción")
        if not isinstance(item.get("finding"), str) or not item["finding"].strip():
            raise WorkflowError("La evidencia no explica su hallazgo")
    sources = result.get("technical_sources")
    if not isinstance(sources, list):
        raise WorkflowError("Fuentes técnicas inválidas")
    for source in sources:
        try:
            parsed = urlsplit(source)
            if parsed.scheme != "https" or not parsed.hostname:
                raise ValueError("URL sin HTTPS")
        except (TypeError, ValueError) as exc:
            raise WorkflowError("Fuentes técnicas inválidas") from exc
    if result["status"] != "skillable":
        return
    if not evidence:
        raise WorkflowError("Una skill necesita evidencia de la transcripción")
    if not SLUG.fullmatch(str(result.get("slug", ""))) or len(result["slug"]) > 48:
        raise WorkflowError("Nombre de skill inválido")
    if not isinstance(result.get("description"), str) or not 20 <= len(result["description"]) <= 500:
        raise WorkflowError("Description inválida")
    instructions = result.get("instructions_md")
    if not isinstance(instructions, str) or not 100 <= len(instructions) <= 20000:
        raise WorkflowError("Instrucciones de skill insuficientes")
    if instructions.lstrip().startswith("---"):
        raise WorkflowError("Las instrucciones no deben traer frontmatter duplicado")
    if "```" in instructions and len(instructions) > 12000:
        raise WorkflowError("Skill demasiado extensa; requiere revisión manual")


def skill_markdown(name: str, result: dict) -> str:
    description = json.dumps(result["description"].strip(), ensure_ascii=False)
    return f"---\nname: {name}\ndescription: {description}\n---\n\n{result['instructions_md'].strip()}\n"


def source_markdown(url: str, result: dict) -> str:
    lines = ["# Análisis de origen", "", f"Fuente: {url}", "", result["analysis"].strip(), "",
             "## Evidencia de la transcripción", ""]
    lines += [f"- {item['timestamp']} — {item['finding']}" for item in result["evidence"]]
    if result["technical_sources"]:
        lines += ["", "## Fuentes técnicas", ""]
        lines += [f"- {source}" for source in result["technical_sources"]]
    lines += ["", "## Revisión", "", "Borrador generado automáticamente. Verifica fidelidad, vigencia técnica y derechos antes de fusionar.", ""]
    return "\n".join(lines)


def _create_draft_pr(config: Config, branch: str, url: str, title: str,
                     source_path: Path, temp: Path, checkout: Path) -> str:
    body_file = temp / "pr-body.md"
    body_file.write_text(f"Fuente: {url}\n\nBorrador para revisar. Análisis y marcas de tiempo: `{source_path.as_posix()}`.\n"
                         "Comprueba la vigencia técnica y los derechos de reutilización antes de fusionar.\n",
                         encoding="utf-8")
    run(["gh", "pr", "create", "--repo", config.repository, "--base", config.base_branch,
         "--head", branch, "--draft", "--title", f"Skill: {title}",
         "--body-file", str(body_file)], cwd=checkout, timeout=120)
    details = json.loads(run(["gh", "pr", "view", branch, "--repo", config.repository,
                              "--json", "url,state,isDraft"], timeout=60))
    if not details.get("url") or details.get("state") != "OPEN" or not details.get("isDraft"):
        raise WorkflowError("No se pudo verificar el borrador de PR")
    return details["url"]


def publish(config: Config, url: str, shortcode: str, result: dict) -> str:
    branch = f"skill/{shortcode.lower()}"
    with tempfile.TemporaryDirectory(prefix="reel-skill-git-") as temp:
        checkout = Path(temp) / "repo"
        run(["git", "clone", "--quiet", "--depth", "1", "--branch", config.base_branch,
             f"https://github.com/{config.repository}.git", str(checkout)], timeout=180)
        try:
            existing = subprocess.run(["git", "ls-remote", "--exit-code", "--heads", "origin", branch],
                                      cwd=checkout, capture_output=True, text=True, timeout=30)
        except (OSError, subprocess.TimeoutExpired) as exc:
            raise WorkflowError("No se pudo consultar la rama remota") from exc
        if existing.returncode == 0:
            prs = json.loads(run(["gh", "pr", "list", "--repo", config.repository,
                                  "--head", branch, "--state", "all", "--json", "url,state"], timeout=60))
            opened = next((pr for pr in prs if pr.get("state") == "OPEN"), None)
            if opened:
                return opened["url"]
            if prs:
                raise WorkflowError(f"La rama {branch} tiene un PR cerrado; revísalo antes de reintentar")
            # A previous run may have pushed the branch but stopped before creating the PR.
            run(["git", "fetch", "--quiet", "origin", branch], cwd=checkout, timeout=120)
            source_path = Path("sources") / f"{shortcode}.md"
            remote_source = run(["git", "show", f"FETCH_HEAD:{source_path.as_posix()}"], cwd=checkout)
            changed = set(run(["git", "diff", "--name-only", "HEAD", "FETCH_HEAD"], cwd=checkout).splitlines())
            expected_source = source_path.as_posix()
            skill_files = [path for path in changed if path.startswith("skills/") and path.endswith("/SKILL.md")]
            if f"Fuente: {url}" not in remote_source.splitlines() or changed != {expected_source, *skill_files} or len(skill_files) != 1:
                raise WorkflowError(f"La rama remota {branch} no coincide con este video; revísala manualmente")
            return _create_draft_pr(config, branch, url, result["title"], source_path,
                                    Path(temp), checkout)
        if existing.returncode != 2:
            raise WorkflowError("No se pudo verificar si ya existe la rama remota")
        run(["git", "checkout", "-q", "-b", branch], cwd=checkout)
        name = result["slug"]
        if (checkout / "skills" / name).exists():
            name = f"{name}-{shortcode.lower()}"
        skill_path = Path("skills") / name / "SKILL.md"
        source_path = Path("sources") / f"{shortcode}.md"
        if (checkout / source_path).exists():
            raise WorkflowError(f"El Reel {shortcode} ya aparece en la rama base")
        (checkout / skill_path).parent.mkdir(parents=True, exist_ok=True)
        (checkout / source_path).parent.mkdir(parents=True, exist_ok=True)
        (checkout / skill_path).write_text(skill_markdown(name, result), encoding="utf-8")
        (checkout / source_path).write_text(source_markdown(url, result), encoding="utf-8")
        run(["git", "add", str(skill_path), str(source_path)], cwd=checkout)
        run(["git", "diff", "--cached", "--check"], cwd=checkout)
        run(["git", "commit", "-qm", f"Add skill from video {shortcode}"], cwd=checkout)
        run(["git", "push", "-q", "-u", "origin", branch], cwd=checkout, timeout=180)
        return _create_draft_pr(config, branch, url, result["title"], source_path,
                                Path(temp), checkout)
