#!/usr/bin/env sh
set -eu
cd "$(dirname "$0")"

skip_model=0
skip_drive=0
inbox_dir=
while [ "$#" -gt 0 ]; do
    option=$1
    case "$option" in
        --skip-model-download) skip_model=1 ;;
        --skip-drive-desktop) skip_drive=1 ;;
        --inbox) shift; inbox_dir=${1:-}; [ -n "$inbox_dir" ] || { echo 'Falta la ruta después de --inbox' >&2; exit 2; } ;;
        *) echo "Opción desconocida: $option" >&2; exit 2 ;;
    esac
    shift
done

install_linux_package() {
    package=$1
    if command -v apt-get >/dev/null 2>&1; then
        if [ "$(id -u)" -eq 0 ]; then
            apt-get update && apt-get install -y "$package"
        else
            sudo apt-get update && sudo apt-get install -y "$package"
        fi
    elif command -v dnf >/dev/null 2>&1; then
        if [ "$(id -u)" -eq 0 ]; then dnf install -y "$package"; else sudo dnf install -y "$package"; fi
    elif command -v pacman >/dev/null 2>&1; then
        if [ "$(id -u)" -eq 0 ]; then pacman -S --needed --noconfirm "$package"; else sudo pacman -S --needed --noconfirm "$package"; fi
    else
        echo "Instala $package con el gestor de paquetes de tu distribución y repite ./setup.sh." >&2
        exit 1
    fi
}

find_python() {
    if [ -n "${PYTHON:-}" ]; then
        printf '%s\n' "$PYTHON"
        return 0
    fi
    for candidate in python3.11 python3.12 python3; do
        if command -v "$candidate" >/dev/null 2>&1 && \
            "$candidate" -c 'import sys; assert sys.version_info[:2] in ((3, 11), (3, 12))' 2>/dev/null; then
            command -v "$candidate"
            return 0
        fi
    done
    return 1
}

if [ -n "${PYTHON:-}" ] && ! "$PYTHON" -c 'import sys; assert sys.version_info[:2] in ((3, 11), (3, 12))' 2>/dev/null; then
    echo 'PYTHON debe apuntar a Python 3.11 o 3.12.' >&2
    exit 1
fi

platform=$(uname -s)
case "$platform" in
    Darwin)
        if ! command -v brew >/dev/null 2>&1; then
            echo 'Falta Homebrew. Instálalo desde https://brew.sh/ y repite ./setup.sh.' >&2
            exit 1
        fi
        if ! python_cmd=$(find_python); then
            brew install python@3.11
            python_cmd="$(brew --prefix python@3.11)/bin/python3.11"
        fi
        ;;
    Linux)
        if ! python_cmd=$(find_python); then
            install_linux_package python3.11
            python_cmd=$(find_python) || { echo 'Se requiere Python 3.11 o 3.12.' >&2; exit 1; }
        fi
        ;;
    *) echo "Sistema no soportado: $platform" >&2; exit 1 ;;
esac

"$python_cmd" -m reel_skill_factory doctor --preinstall
"$python_cmd" -c 'import shutil,sys; sys.exit(0 if shutil.disk_usage(".").free >= 3*1024**3 else 1)' || {
    echo 'Se necesitan al menos 3 GB libres para instalar Whisper y su modelo.' >&2
    exit 1
}

case "$platform" in
    Darwin)
        command -v codex >/dev/null 2>&1 || brew install --cask codex
        if [ "$skip_drive" -eq 0 ] && [ ! -d '/Applications/Google Drive.app' ]; then
            brew install --cask google-drive
        fi
        ;;
    Linux)
        if ! command -v codex >/dev/null 2>&1; then
            command -v curl >/dev/null 2>&1 || install_linux_package curl
            installer=$(mktemp)
            trap 'rm -f "$installer"' EXIT HUP INT TERM
            curl -fsSL https://chatgpt.com/codex/install.sh -o "$installer"
            sh "$installer"
            rm -f "$installer"
            trap - EXIT HUP INT TERM
            PATH="$HOME/.local/bin:$PATH"
            export PATH
        fi
        echo 'Linux: usa una carpeta local o configura por tu cuenta la sincronización de Drive; Google Drive para escritorio no ofrece instalador oficial para Linux.'
        ;;
esac

command -v codex >/dev/null 2>&1 || { echo 'Falta Codex CLI; abre otra terminal y repite ./setup.sh.' >&2; exit 1; }
codex --version >/dev/null

if [ ! -x .venv/bin/python ]; then
    if ! "$python_cmd" -m venv .venv; then
        if [ "$platform" = Linux ] && command -v apt-get >/dev/null 2>&1; then
            python_version=$("$python_cmd" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
            install_linux_package "python$python_version-venv"
            "$python_cmd" -m venv .venv
        else
            echo 'No se pudo crear .venv; revisa que Python incluya el módulo venv.' >&2
            exit 1
        fi
    fi
fi
.venv/bin/python -c 'import sys; assert sys.version_info[:2] in ((3, 11), (3, 12))' || {
    echo 'El .venv existente usa una versión incompatible de Python; revísalo antes de repetir.' >&2
    exit 1
}
if [ "$platform" = Linux ]; then
    .venv/bin/python -m pip install --disable-pip-version-check torch --index-url https://download.pytorch.org/whl/cpu
fi
.venv/bin/python -m pip install --disable-pip-version-check -r requirements.txt
if [ "$skip_model" -eq 1 ]; then
    .venv/bin/python scripts/prepare_runtime.py --skip-model
else
    .venv/bin/python scripts/prepare_runtime.py
fi
if [ -z "$inbox_dir" ] && [ -f config.local.json ]; then
    inbox_dir=$(.venv/bin/python -c 'import json; print(json.load(open("config.local.json", encoding="utf-8"))["inbox_dir"])')
fi
if [ -z "$inbox_dir" ]; then
    if [ ! -t 0 ]; then
        echo 'Indica la carpeta local sincronizada con --inbox RUTA.' >&2
        exit 1
    fi
    printf 'Ruta local de la carpeta donde llegarán los videos: '
    IFS= read -r inbox_dir
fi
.venv/bin/python -m reel_skill_factory configure --inbox "$inbox_dir"
if ! codex login status >/dev/null 2>&1; then
    if [ ! -t 0 ]; then echo 'Inicia sesión con codex login y repite el instalador.' >&2; exit 1; fi
    echo 'Completa el inicio de sesión de Codex.'
    codex login
fi
.venv/bin/python -m reel_skill_factory doctor
echo 'Instalación terminada. Para procesar videos, inicia .venv/bin/python -m reel_skill_factory watch y abre .venv/bin/python -m reel_skill_factory vault --serve en otra sesión.'
