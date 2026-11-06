from __future__ import annotations

import platform
import shutil
import subprocess
import sys
from pathlib import Path

from .core import Config, WorkflowError, load_config, normalize_reel_url


def _tool(name: str) -> str | None:
    suffix = ".exe" if platform.system() == "Windows" else ""
    local = Path(sys.executable).parent / (name + suffix)
    return str(local) if local.is_file() else shutil.which(name)


def _probe(command: list[str], timeout: int = 20) -> bool:
    try:
        return subprocess.run(command, capture_output=True, text=True,
                              timeout=timeout, check=False).returncode == 0
    except (OSError, subprocess.TimeoutExpired):
        return False


def _output(command: list[str], timeout: int = 20) -> str | None:
    try:
        result = subprocess.run(command, capture_output=True, text=True,
                                timeout=timeout, check=False)
        return result.stdout.strip() if result.returncode == 0 else None
    except (OSError, subprocess.TimeoutExpired):
        return None


def _memory_gb() -> float | None:
    system = platform.system()
    try:
        if system == "Windows":
            import ctypes

            class MemoryStatus(ctypes.Structure):
                _fields_ = [("dwLength", ctypes.c_ulong), ("dwMemoryLoad", ctypes.c_ulong),
                            ("ullTotalPhys", ctypes.c_ulonglong), ("ullAvailPhys", ctypes.c_ulonglong),
                            ("ullTotalPageFile", ctypes.c_ulonglong), ("ullAvailPageFile", ctypes.c_ulonglong),
                            ("ullTotalVirtual", ctypes.c_ulonglong), ("ullAvailVirtual", ctypes.c_ulonglong),
                            ("ullAvailExtendedVirtual", ctypes.c_ulonglong)]

            status = MemoryStatus()
            status.dwLength = ctypes.sizeof(status)
            if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(status)):
                return status.ullTotalPhys / 1024 ** 3
        elif system == "Darwin":
            return int(subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()) / 1024 ** 3
        elif system == "Linux":
            line = next(line for line in Path("/proc/meminfo").read_text().splitlines()
                        if line.startswith("MemTotal:"))
            return int(line.split()[1]) / 1024 ** 2
    except (OSError, ValueError, StopIteration):
        pass
    return None


def diagnose(config_path: Path, *, preinstall: bool = False, sample_url: str | None = None) -> int:
    hard_fail = False

    def report(level: str, label: str, detail: str = "") -> None:
        nonlocal hard_fail
        print(f"{level:7} {label}" + (f": {detail}" if detail else ""))
        if level == "FALTA" and not preinstall:
            hard_fail = True

    report("OK", "Sistema", f"{platform.system()} {platform.release()}")
    if sys.version_info[:2] in {(3, 11), (3, 12)}:
        report("OK", "Python", platform.python_version())
    else:
        report("FALTA", "Python", "se recomienda 3.11 o 3.12 para Whisper")
        hard_fail = True
    memory = _memory_gb()
    if memory is None:
        report("REVISAR", "RAM", "no se pudo medir")
    else:
        report("OK" if memory >= 4 else "REVISAR", "RAM", f"{memory:.1f} GB; con menos de 4 GB usa tiny o transcripción externa")
    free = shutil.disk_usage(config_path.parent).free / 1024 ** 3
    report("OK" if free >= 3 else "REVISAR", "Disco", f"{free:.1f} GB libres; Whisper puede descargar modelos grandes")
    for name in ("git", "gh", "codex", "ffmpeg", "yt-dlp", "whisper"):
        found = _tool(name)
        report("OK" if found else "FALTA", name, found or "no encontrado en PATH")

    config: Config | None = None
    if config_path.is_file():
        try:
            config = load_config(config_path)
            report("OK", "Carpeta Drive", str(config.inbox_dir))
            report("OK", "Configuración", config.repository)
        except WorkflowError as exc:
            report("FALTA", "Configuración", str(exc))
    else:
        report("REVISAR" if preinstall else "FALTA", "Configuración",
               f"copia config.example.json a {config_path.name} y edita sus valores")

    if _tool("gh"):
        report("OK" if _probe(["gh", "auth", "status"]) else "FALTA", "GitHub login",
               "usa gh auth login si falta")
        if config:
            permission = _output(["gh", "api", f"repos/{config.repository}", "--jq", ".permissions.push"])
            report("OK" if permission == "true" else "FALTA", "GitHub escritura",
                   config.repository if permission == "true" else "sin acceso de escritura o repo inexistente")
    if _tool("codex"):
        report("OK" if _probe(["codex", "login", "status"]) else "FALTA", "Codex login",
               "usa codex login si falta")
    if not _probe(["git", "config", "user.name"]) or not _probe(["git", "config", "user.email"]):
        report("FALTA", "Git autor", "configura user.name y user.email")
    else:
        report("OK", "Git autor")

    if sample_url:
        try:
            url, _ = normalize_reel_url(sample_url)
            tool = _tool("yt-dlp")
            available = bool(tool) and _probe(
                [tool, "--simulate", "--skip-download", "--no-playlist", url], timeout=90)
            report("OK" if available else "REVISAR", "Instagram",
                   "metadata accesible" if available else "Reel inaccesible; puede ser privado o estar bloqueado")
        except WorkflowError as exc:
            report("FALTA", "Instagram", str(exc))
    report("REVISAR", "Móvil y Apps Script", "envía un Reel de prueba y confirma que aparece un .txt en la carpeta")
    return 1 if hard_fail else 0
