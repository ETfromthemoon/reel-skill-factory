"""Put the bundled FFmpeg on this virtual environment's PATH and cache Whisper."""

from __future__ import annotations

import argparse
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def install_ffmpeg() -> Path:
    if sys.prefix == sys.base_prefix:
        raise RuntimeError("Ejecuta este script con el Python de .venv")

    import imageio_ffmpeg

    source = Path(imageio_ffmpeg.get_ffmpeg_exe()).resolve()
    target = Path(sys.executable).parent / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if not target.exists() and target.is_symlink():
        target.unlink()
    if not target.exists():
        bundled_dir = Path(imageio_ffmpeg.__file__).resolve().parent / "binaries"
        if source.parent != bundled_dir:
            raise RuntimeError("No se encontró el FFmpeg incluido en imageio-ffmpeg")
        if os.name == "nt":
            shutil.copy2(source, target)
        else:
            target.symlink_to(source)
    subprocess.run([str(target), "-version"], check=True, capture_output=True, timeout=15)
    return target


def configured_model() -> str:
    config = ROOT / "config.local.json"
    if config.is_file():
        data = json.loads(config.read_text(encoding="utf-8"))
        model = str(data.get("whisper_model", "base"))
        if model in {"tiny", "base", "small", "medium"}:
            return model
    return "base"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--skip-model", action="store_true", help="no descarga el modelo Whisper ahora")
    args = parser.parse_args()
    path = install_ffmpeg()
    print(f"FFmpeg listo: {path}", flush=True)
    if not args.skip_model:
        import whisper

        model = configured_model()
        print(f"Preparando modelo Whisper '{model}' (puede tardar varios minutos)...", flush=True)
        whisper.load_model(model)
        print(f"Modelo Whisper '{model}' listo", flush=True)


if __name__ == "__main__":
    main()
