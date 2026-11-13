"""Guided, local configuration without publishing personal paths."""

from __future__ import annotations

import json
from pathlib import Path

from .core import ROOT, WorkflowError, load_config


def configure(config_path: Path, inbox_path: Path) -> Path:
    inbox = inbox_path.expanduser().resolve()
    if not inbox.is_dir():
        raise WorkflowError(f"No existe la carpeta sincronizada: {inbox}")
    if inbox.is_relative_to(ROOT.resolve()):
        raise WorkflowError("La carpeta de entrada debe estar fuera del programa")
    if config_path.exists():
        current = load_config(config_path)
        if current.inbox_dir != inbox:
            raise WorkflowError(f"Ya existe una configuración para {current.inbox_dir}; edítala manualmente si quieres cambiarla")
        return config_path
    data = json.loads((ROOT / "config.example.json").read_text(encoding="utf-8"))
    data["inbox_dir"] = str(inbox)
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    try:
        load_config(config_path)
    except Exception:
        config_path.unlink(missing_ok=True)
        raise
    return config_path
